"""The dashboard is static files served next to the API (ADR-0016)."""

import re
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from complyscope.api import create_app  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "complyscope" / "api" / "static"
ASSETS = sorted(STATIC.glob("*.*"))


@pytest.fixture
def api(tmp_path):
    app = create_app(
        scope_path=ROOT / "examples" / "scope.example.yaml",
        evidence_path=tmp_path / "evidence.json",
        answers_path=ROOT / "examples" / "answers.example.yaml",
        register_path=tmp_path / "risks.yaml",
    )
    return TestClient(app, base_url="http://127.0.0.1:8000")


def test_dashboard_is_served_at_the_root(api):
    response = api.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<title>complyscope</title>" in response.text
    assert '<script src="/static/dashboard.js" defer></script>' in response.text


@pytest.mark.parametrize(
    ("path", "content_type"),
    [("/static/dashboard.js", "text/javascript"), ("/static/dashboard.css", "text/css")],
)
def test_assets_are_served(api, path, content_type):
    response = api.get(path)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(content_type)


def test_dashboard_has_a_strict_content_security_policy(api):
    policy = api.get("/").headers["content-security-policy"]

    assert "default-src 'self'" in policy
    assert "frame-ancestors 'none'" in policy
    assert "unsafe-inline" not in policy
    assert "unsafe-eval" not in policy


def test_dashboard_says_it_is_not_a_certification(api):
    assert "not a certification" in api.get("/").text


def test_assets_load_nothing_from_other_sites():
    # Assessment data must not leak to a CDN, and the dashboard must work offline.
    assert ASSETS
    for asset in ASSETS:
        assert not re.search(r"https?://", asset.read_text()), asset.name


def test_script_never_parses_data_as_html():
    # Titles, notes and plans come from editable YAML; rendering them as HTML would be XSS.
    script = (STATIC / "dashboard.js").read_text()

    for sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
        assert sink not in script


def test_dashboard_files_live_inside_the_package():
    # hatch packages everything under src/complyscope; keep the files inside the package.
    assert {p.name for p in ASSETS} >= {"index.html", "dashboard.js", "dashboard.css"}
