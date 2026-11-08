"""`complyscope collect` tests: redscope is replaced by a fake runner, nothing is scanned."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from complyscope.cli import cli
from complyscope.collectors import redscope_adapter
from complyscope.models import EvidenceCollection

EXAMPLE_SCOPE = str(Path(__file__).resolve().parents[1] / "examples" / "scope.example.yaml")


def clean_result(module, target):
    data = {
        "portscan": {"open_ports": [{"port": 22}]},
        "banner": {"banners": [{"port": 22, "service": "ssh"}]},
    }.get(module, {})
    return {"module": module, "target": target, "findings": [], "data": data, "errors": []}


@pytest.fixture
def fake_redscope(monkeypatch):
    """Replace the real redscope runner; record (module, host) for every call."""
    calls = []
    overrides = {}

    def runner(module, target, **kwargs):
        calls.append((module, target))
        if (module, target) in overrides:
            outcome = overrides[(module, target)]
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        return clean_result(module, target)

    monkeypatch.setattr(redscope_adapter, "run_redscope_module", runner)
    monkeypatch.setattr(redscope_adapter, "redscope_version", lambda: "redscope 2.0.0")
    runner.calls = calls
    runner.overrides = overrides
    return runner


def collect(*args, input=None):
    return CliRunner().invoke(cli, ["collect", "--scope", EXAMPLE_SCOPE, *args], input=input)


def test_shows_authorisation_and_targets_then_stops_unless_confirmed(fake_redscope, tmp_path):
    result = collect("--output", str(tmp_path / "evidence.json"), input="n\n")

    assert result.exit_code == 1
    assert "Acme Ltd (fictional)" in result.stdout
    assert "Jane Doe, IT Manager (fictional)" in result.stdout
    assert "app.example.test" in result.stdout
    assert fake_redscope.calls == []
    assert not (tmp_path / "evidence.json").exists()


def test_writes_an_evidence_collection_for_every_host(fake_redscope, tmp_path):
    out = tmp_path / "evidence.json"

    result = collect("--output", str(out), "--yes")

    assert result.exit_code == 0, result.output
    collection = EvidenceCollection.from_json(out.read_text())
    assert collection.organisation == "Acme Ltd (fictional)"
    assert {e.target for e in collection.items} == {"localhost", "127.0.0.1", "app.example.test"}
    assert {e.collector for e in collection.items} == {"redscope 2.0.0"}
    assert f"Wrote {len(collection.items)} evidence items" in result.stdout


def test_host_option_limits_the_run_to_listed_hosts(fake_redscope, tmp_path):
    result = collect("--output", str(tmp_path / "e.json"), "--yes", "--host", "LOCALHOST")

    assert result.exit_code == 0, result.output
    assert {host for _, host in fake_redscope.calls} == {"localhost"}


def test_out_of_scope_host_is_refused_before_anything_runs(fake_redscope, tmp_path):
    result = collect("--output", str(tmp_path / "e.json"), "--yes", "--host", "evil.example.com")

    assert result.exit_code == 2
    assert "not in scope" in result.stderr
    assert fake_redscope.calls == []


def test_invalid_scope_file_is_a_usage_error(fake_redscope, tmp_path):
    result = CliRunner().invoke(
        cli, ["collect", "--scope", str(tmp_path / "missing.yaml"), "--yes"]
    )

    assert result.exit_code == 2
    assert "not found" in result.stderr


def test_existing_output_is_not_overwritten_without_force(fake_redscope, tmp_path):
    out = tmp_path / "evidence.json"
    out.write_text("keep me")

    refused = collect("--output", str(out), "--yes")
    assert refused.exit_code == 2
    assert "--force" in refused.stderr
    assert out.read_text() == "keep me"
    assert fake_redscope.calls == []

    forced = collect("--output", str(out), "--yes", "--force")
    assert forced.exit_code == 0, forced.output
    assert json.loads(out.read_text())["organisation"] == "Acme Ltd (fictional)"


def test_skipped_modules_are_reported_per_host(fake_redscope, tmp_path):
    fake_redscope.overrides[("ssltls", "localhost")] = ConnectionRefusedError("refused")

    result = collect("--output", str(tmp_path / "e.json"), "--yes")

    assert result.exit_code == 0, result.output
    assert "localhost: ssltls skipped (crashed: ConnectionRefusedError: refused)" in result.stdout


def test_missing_redscope_explains_how_to_install(monkeypatch, tmp_path):
    def unavailable(module, target, **kwargs):
        raise redscope_adapter.RedscopeUnavailableError("redscope is not installed")

    monkeypatch.setattr(redscope_adapter, "run_redscope_module", unavailable)

    result = collect("--output", str(tmp_path / "e.json"), "--yes")

    assert result.exit_code == 1
    assert "complyscope[scan]" in result.stderr
    assert not (tmp_path / "e.json").exists()
