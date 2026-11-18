"""Read-only HTTP API and dashboard over an assessment (ADR-0015, ADR-0016).

Needs ``complyscope[web]``.
"""

from complyscope.api.app import LOCAL_HOSTS, create_app

__all__ = ["LOCAL_HOSTS", "create_app"]
