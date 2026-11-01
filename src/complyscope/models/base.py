"""Building blocks shared by all complyscope models."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

# redscope check ids: "<module>.<check>", e.g. "ssltls.deprecated_protocol".
CheckId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]+(\.[a-z0-9_]+)+$")]


class StrictModel(BaseModel):
    # Reject unknown keys so a typo in YAML or JSON (e.g. "asessment") fails loudly
    # instead of being silently ignored. Instances are immutable records.
    model_config = ConfigDict(extra="forbid", frozen=True)
