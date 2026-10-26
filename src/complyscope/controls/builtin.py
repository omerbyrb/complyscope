"""Framework catalogues shipped inside the complyscope package."""

from pathlib import Path

from complyscope.controls.loader import FrameworkLoadError, load_framework
from complyscope.models import Framework

BUILTIN_DIR = Path(__file__).resolve().parent.parent / "frameworks"


def builtin_framework_dirs() -> dict[str, Path]:
    """Map each built-in framework id (as declared in its framework.yaml) to its directory."""
    dirs = {}
    for framework_file in sorted(BUILTIN_DIR.glob("*/framework.yaml")):
        framework = load_framework(framework_file.parent)
        dirs[framework.id] = framework_file.parent
    return dirs


def load_builtin_framework(framework_id: str) -> Framework:
    dirs = builtin_framework_dirs()
    if framework_id not in dirs:
        available = ", ".join(sorted(dirs)) or "none"
        raise FrameworkLoadError(f"unknown framework '{framework_id}' (available: {available})")
    return load_framework(dirs[framework_id])
