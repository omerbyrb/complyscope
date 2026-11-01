"""The assessment scope: who authorised testing, and which hosts (see ADR-0009)."""

import ipaddress
import re
from datetime import date
from typing import Annotated, Literal

from pydantic import AfterValidator, Field, field_validator, model_validator

from complyscope.models.base import NonEmptyStr, StrictModel

_HOSTNAME = re.compile(
    r"^(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*$"
)


class OutOfScopeError(Exception):
    """A check was requested against a host that the scope does not authorise."""


def normalise_host(value: str) -> str:
    """Canonical form of a single host: lower-case name without trailing dot, or compressed IP.

    URLs, ports, ranges and wildcards are rejected so a scope can never authorise more
    than the exact hosts written in it.
    """
    host = value.strip().lower().rstrip(".")
    try:
        return ipaddress.ip_address(host).compressed
    except ValueError:
        pass
    if not _HOSTNAME.match(host):
        raise ValueError(f"invalid host {value!r}: expected a single hostname or IP address")
    return host


Host = Annotated[str, AfterValidator(normalise_host)]


class Authorisation(StrictModel):
    confirmed: Literal[True] = Field(
        description="Must be true: the user owns the targets or holds written permission."
    )
    confirmed_by: NonEmptyStr
    confirmed_on: date
    reference: str = ""

    @field_validator("confirmed_on")
    @classmethod
    def _not_in_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("authorisation cannot be dated in the future")
        return value


class Target(StrictModel):
    host: Host
    description: str = ""


class Scope(StrictModel):
    organisation: NonEmptyStr
    authorisation: Authorisation
    targets: tuple[Target, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_hosts(self) -> "Scope":
        seen: set[str] = set()
        for target in self.targets:
            if target.host in seen:
                raise ValueError(f"duplicate host in targets: {target.host}")
            seen.add(target.host)
        return self

    @property
    def hosts(self) -> tuple[str, ...]:
        return tuple(t.host for t in self.targets)

    def ensure_in_scope(self, host: str) -> str:
        """Return the normalised host if it is authorised, otherwise raise OutOfScopeError."""
        try:
            normalised = normalise_host(host)
        except ValueError:
            normalised = None
        if normalised not in self.hosts:
            raise OutOfScopeError(f"{host!r} is not in scope for {self.organisation}")
        return normalised
