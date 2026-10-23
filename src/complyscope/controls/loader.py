"""Load a framework's control catalogue from YAML files.

Expected layout::

    <framework dir>/
        framework.yaml        # id, name, version, publisher, source_url, themes
        controls/*.yaml       # each file: {controls: [<control>, ...]}
"""

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from complyscope.models import Control, Framework


class FrameworkLoadError(Exception):
    """A framework catalogue could not be loaded; the message names the file at fault."""


def load_framework(path: Path) -> Framework:
    path = Path(path)
    framework_file = path / "framework.yaml"
    if not framework_file.is_file():
        raise FrameworkLoadError(f"{framework_file}: file not found")

    metadata = _read_yaml(framework_file)
    if not isinstance(metadata, dict):
        raise FrameworkLoadError(f"{framework_file}: expected a mapping of framework fields")
    if "controls" in metadata:
        raise FrameworkLoadError(
            f"{framework_file}: controls belong in controls/*.yaml, not in framework.yaml"
        )

    controls: list[Control] = []
    defined_in: dict[str, Path] = {}
    for control_file in sorted((path / "controls").glob("*.yaml")):
        for control in _load_control_file(control_file):
            if control.id in defined_in:
                raise FrameworkLoadError(
                    f"duplicate control id {control.id}: defined in "
                    f"{defined_in[control.id].name} and {control_file.name}"
                )
            defined_in[control.id] = control_file
            controls.append(control)

    try:
        return Framework.model_validate({**metadata, "controls": controls})
    except ValidationError as e:
        raise FrameworkLoadError(f"{path}: invalid framework: {e}") from e


def _load_control_file(control_file: Path) -> list[Control]:
    content = _read_yaml(control_file)
    if not isinstance(content, dict) or not isinstance(content.get("controls"), list):
        raise FrameworkLoadError(f"{control_file}: expected a top-level 'controls' list")

    controls = []
    for entry in content["controls"]:
        control_id = (
            entry.get("id", "<missing id>") if isinstance(entry, dict) else "<not a mapping>"
        )
        try:
            controls.append(Control.model_validate(entry))
        except ValidationError as e:
            raise FrameworkLoadError(f"{control_file}: control {control_id}: {e}") from e
    return controls


def _read_yaml(file: Path) -> Any:
    # safe_load only builds plain data (dicts, lists, strings, numbers). yaml.load
    # can construct arbitrary Python objects, so a malicious catalogue could run code.
    try:
        return yaml.safe_load(file.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise FrameworkLoadError(f"{file}: invalid YAML: {e}") from e
