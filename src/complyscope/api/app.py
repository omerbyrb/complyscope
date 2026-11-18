"""FastAPI application: GET endpoints only, files re-read on every request."""

from collections.abc import Callable, Collection
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse

from complyscope import __version__
from complyscope.assessment import Assessment, AssessmentInputError, load_assessment
from complyscope.mapping.engine import score
from complyscope.models import RiskStatus
from complyscope.risk.register import RegisterError, load_register

# Host header values a browser sends when the page was opened on this machine. Anything
# else may be a DNS rebinding attack: a web page whose domain now points at 127.0.0.1
# reading the API through the visitor's browser (ADR-0016).
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

COMMON_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


def host_name(header: str) -> str:
    """The host part of a Host header: 'localhost:8000' -> 'localhost', '[::1]:80' -> '::1'."""
    header = header.strip().lower()
    if header.startswith("["):
        return header[1 : header.find("]")]
    return header.rsplit(":", 1)[0] if header.count(":") == 1 else header


def create_app(
    *,
    scope_path: Path,
    evidence_path: Path,
    answers_path: Path,
    register_path: Path,
    framework: str = "cyber-essentials",
    allowed_hosts: Collection[str] | None = LOCAL_HOSTS,
    today: Callable[[], date] = date.today,
) -> FastAPI:
    """Build the API. ``allowed_hosts=None`` accepts any Host header (remote serving only)."""
    app = FastAPI(
        title="complyscope",
        version=__version__,
        description="Read-only view of a complyscope assessment and risk register.",
    )

    @app.middleware("http")
    async def protect(request: Request, call_next: Callable) -> Response:
        if allowed_hosts is not None:
            if host_name(request.headers.get("host", "")) not in allowed_hosts:
                return PlainTextResponse("Invalid host header", status_code=400)
        response = await call_next(request)
        response.headers.update(COMMON_HEADERS)
        if request.url.path.startswith("/api/"):
            # Assessment data describes security weaknesses; keep it out of browser caches.
            response.headers["Cache-Control"] = "no-store"
        return response

    def assessment() -> Assessment:
        # Files are read per request so the API always shows the latest collect/assess run.
        try:
            return load_assessment(scope_path, evidence_path, framework, answers_path)
        except AssessmentInputError as e:
            raise HTTPException(422, {"source": e.source, "message": str(e)}) from e

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/api/assessment")
    def get_assessment() -> dict[str, Any]:
        current = assessment()
        controls = {c.id: c for c in current.framework.controls}
        return {
            "organisation": current.scope.organisation,
            "framework": {
                "id": current.framework.id,
                "name": current.framework.name,
                "version": current.framework.version,
            },
            "score": score(current.results).model_dump(),
            "controls": [
                {
                    "id": r.control_id,
                    "title": controls[r.control_id].title,
                    "theme": controls[r.control_id].theme,
                    "assessment": controls[r.control_id].assessment.value,
                    "status": r.status.value,
                    "rationale": r.rationale,
                }
                for r in current.results
            ],
        }

    @app.get("/api/controls/{control_id}")
    def get_control(control_id: str) -> dict[str, Any]:
        current = assessment()
        result = next((r for r in current.results if r.control_id == control_id), None)
        if result is None:
            raise HTTPException(404, f"unknown control {control_id}")
        control = current.framework.get(control_id)
        return {
            "id": control.id,
            "title": control.title,
            "theme": control.theme,
            "description": control.description,
            "assessment": control.assessment.value,
            "crosswalk": {k: list(v) for k, v in control.crosswalk.items()},
            **result.model_dump(mode="json", exclude={"control_id"}),
        }

    @app.get("/api/risks")
    def get_risks() -> dict[str, Any]:
        current = assessment()
        try:
            register = load_register(register_path)
        except RegisterError as e:
            raise HTTPException(422, {"source": "register", "message": str(e)}) from e
        risks = register.risks if register else ()
        return {
            "organisation": current.scope.organisation,
            "risks": [
                risk.model_dump(mode="json")
                | {
                    "score": risk.score,
                    "level": risk.level.value,
                    "needs_attention": risk.needs_attention(),
                    "review_overdue": risk.status is RiskStatus.OPEN and risk.review_by < today(),
                }
                for risk in risks
            ],
        }

    return app
