"""Read-only HTTP API over an assessment (see ADR-0015). Needs ``complyscope[web]``."""

from complyscope.api.app import create_app

__all__ = ["create_app"]
