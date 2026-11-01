"""Load the assessment scope file (scope.yaml)."""

from pathlib import Path

import yaml
from pydantic import ValidationError

from complyscope.models.scope import OutOfScopeError, Scope

__all__ = ["OutOfScopeError", "ScopeError", "load_scope"]


class ScopeError(Exception):
    """The scope file is missing or invalid; the message names the file."""


def load_scope(path: Path) -> Scope:
    path = Path(path)
    if not path.is_file():
        raise ScopeError(f"{path}: file not found")
    try:
        # safe_load only: a scope file must never be able to construct Python objects.
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ScopeError(f"{path}: invalid YAML: {e}") from e
    if not isinstance(data, dict):
        raise ScopeError(f"{path}: expected a mapping with organisation, authorisation, targets")
    try:
        return Scope.model_validate(data)
    except ValidationError as e:
        raise ScopeError(f"{path}: invalid scope: {e}") from e
