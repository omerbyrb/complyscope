"""The editable risk register file (risks.yaml) and how new assessments merge into it."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from complyscope.models import ControlResult, ControlStatus, Risk, RiskRegister, RiskStatus

HEADER = """\
# complyscope risk register
# Risk owners edit: owner, impact, impact_confirmed, treatment, plan, review_by, status.
# Running `complyscope risks` again only refreshes likelihood and evidence_summary,
# adds risks for newly failed controls and reopens closed risks that fail again.
"""

# Fields the tool derives from evidence; everything else belongs to the risk owner.
_REFRESHED_FIELDS = ("likelihood", "evidence_summary")


class RegisterError(Exception):
    """The register file is invalid or belongs to a different assessment."""


@dataclass(frozen=True)
class RegisterChanges:
    added: tuple[str, ...] = ()
    updated: tuple[str, ...] = ()
    reopened: tuple[str, ...] = ()
    # Open risks whose controls no longer fail: the owner may review and close them.
    no_longer_failing: tuple[str, ...] = ()
    # Open risks whose controls produced no verdict this time: nothing is known either way.
    not_reassessed: tuple[str, ...] = ()


def merge_register(
    existing: RiskRegister | None,
    drafts: Sequence[Risk],
    results: Sequence[ControlResult],
    *,
    organisation: str,
    framework: str,
) -> tuple[RiskRegister, RegisterChanges]:
    if existing and (existing.organisation, existing.framework) != (organisation, framework):
        raise RegisterError(
            f"the register belongs to {existing.organisation!r} ({existing.framework}), "
            f"not {organisation!r} ({framework})"
        )

    drafted = {risk.id: risk for risk in drafts}
    status_of = {result.control_id: result.status for result in results}
    merged: list[Risk] = []
    updated, reopened, no_longer_failing, not_reassessed = [], [], [], []

    for risk in existing.risks if existing else ():
        fresh = drafted.pop(risk.id, None)
        if fresh is not None:
            changes = {field: getattr(fresh, field) for field in _REFRESHED_FIELDS}
            if risk.status is RiskStatus.CLOSED:
                changes["status"] = RiskStatus.OPEN
                reopened.append(risk.id)
            else:
                updated.append(risk.id)
            merged.append(Risk.model_validate(risk.model_dump() | changes))
            continue

        merged.append(risk)
        if risk.status is RiskStatus.OPEN:
            statuses = {status_of.get(control_id) for control_id in risk.control_ids}
            if statuses & {ControlStatus.PASS, ControlStatus.PARTIAL}:
                no_longer_failing.append(risk.id)
            else:
                not_reassessed.append(risk.id)

    merged.extend(drafted.values())
    register = RiskRegister(organisation=organisation, framework=framework, risks=tuple(merged))
    return register, RegisterChanges(
        added=tuple(drafted),
        updated=tuple(updated),
        reopened=tuple(reopened),
        no_longer_failing=tuple(no_longer_failing),
        not_reassessed=tuple(not_reassessed),
    )


def load_register(path: Path) -> RiskRegister | None:
    """Read risks.yaml; a missing file means no register has been started yet."""
    path = Path(path)
    if not path.exists():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise RegisterError(f"{path}: invalid YAML: {e}") from e
    if not isinstance(data, dict):
        raise RegisterError(f"{path}: expected a mapping with organisation, framework, risks")
    try:
        return RiskRegister.model_validate(data)
    except ValidationError as e:
        raise RegisterError(f"{path}: invalid risk register: {e}") from e


def write_register(path: Path, register: RiskRegister) -> None:
    body = yaml.safe_dump(
        register.model_dump(mode="json"), sort_keys=False, allow_unicode=True, width=100
    )
    Path(path).write_text(HEADER + body, encoding="utf-8")
