"""Adapter tests use fake redscope results: CI never scans a real host."""

import ast
from datetime import UTC, datetime
from pathlib import Path

import pytest

from complyscope.collectors.redscope_adapter import (
    CE_MODULES,
    MODULE_CHECKS,
    RedscopeCollector,
    evidence_from_result,
)
from complyscope.scoping import OutOfScopeError, load_scope

EXAMPLE_SCOPE = Path(__file__).resolve().parents[1] / "examples" / "scope.example.yaml"
WHEN = datetime(2026, 11, 2, 10, 0, tzinfo=UTC)


def scan_result(module, findings=(), errors=(), data=None):
    """The shape of redscope's ScanResult.to_dict()."""
    return {
        "module": module,
        "target": "app.example.test",
        "findings": [
            {
                "title": f.get("title", "A finding"),
                "severity": f.get("severity", "high"),
                "description": f.get("description", "What was seen"),
                "evidence": f.get("evidence", ""),
                "check_id": f.get("check_id"),
            }
            for f in findings
        ],
        "data": data or {},
        "errors": list(errors),
    }


def convert(result):
    return evidence_from_result(
        result, target="app.example.test", collected_at=WHEN, collector="redscope 2.0.0"
    )


class FakeRunner:
    """Stands in for redscope: returns canned results and records every call."""

    def __init__(self, results):
        self.results = results
        self.calls = []

    def __call__(self, module, target, **kwargs):
        self.calls.append((module, target, kwargs))
        outcome = self.results[module]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


# --- evidence_from_result ---------------------------------------------------------------


def test_finding_becomes_present_evidence_and_other_checks_become_absent():
    result = scan_result(
        "ssltls",
        findings=[{"check_id": "ssltls.deprecated_protocol", "title": "TLSv1 supported"}],
    )

    evidence = convert(result)
    by_check = {e.check: e for e in evidence}

    assert by_check["ssltls.deprecated_protocol"].observed == "present"
    assert by_check["ssltls.deprecated_protocol"].title == "TLSv1 supported"
    assert by_check["ssltls.hsts_missing"].observed == "absent"
    assert set(by_check) == MODULE_CHECKS["ssltls"]


def test_several_findings_for_one_check_are_all_kept():
    result = scan_result(
        "ssltls",
        findings=[
            {"check_id": "ssltls.deprecated_protocol", "title": "TLSv1 supported"},
            {"check_id": "ssltls.deprecated_protocol", "title": "TLSv1.1 supported"},
        ],
    )

    present = [e for e in convert(result) if e.observed == "present"]

    assert [e.title for e in present] == ["TLSv1 supported", "TLSv1.1 supported"]


def test_module_that_reported_errors_produces_no_evidence():
    result = scan_result("ssltls", errors=["Could not retrieve SSL certificate"])

    assert convert(result) == []


def test_finding_without_check_id_is_ignored():
    result = scan_result("headers", findings=[{"check_id": None}])

    assert all(e.observed == "absent" for e in convert(result))


def test_finding_evidence_text_is_kept_in_details():
    result = scan_result(
        "portscan",
        findings=[
            {
                "check_id": "portscan.risky_service_exposed",
                "description": "Port 23/tcp is open",
                "evidence": "Ubuntu telnetd",
            }
        ],
    )

    exposed = next(e for e in convert(result) if e.check == "portscan.risky_service_exposed")

    assert exposed.details == "Port 23/tcp is open\nEvidence: Ubuntu telnetd"


# --- RedscopeCollector -----------------------------------------------------------------


def collector_with(results):
    runner = FakeRunner(results)
    collector = RedscopeCollector(
        load_scope(EXAMPLE_SCOPE), runner=runner, collector="redscope 2.0.0", clock=lambda: WHEN
    )
    return collector, runner


def all_clean():
    return {m: scan_result(m) for m in CE_MODULES} | {
        "portscan": scan_result("portscan", data={"open_ports": [{"port": 22}]}),
        "banner": scan_result("banner", data={"banners": [{"port": 22, "service": "ssh"}]}),
    }


def test_out_of_scope_host_is_refused_before_any_module_runs():
    collector, runner = collector_with(all_clean())

    with pytest.raises(OutOfScopeError):
        collector.collect("www.app.example.test")
    assert runner.calls == []


def test_collect_runs_every_module_against_the_normalised_host():
    collector, runner = collector_with(all_clean())

    run = collector.collect("APP.example.test.")

    assert [call[0] for call in runner.calls] == list(CE_MODULES)
    assert {call[1] for call in runner.calls} == {"app.example.test"}
    assert run.skipped == {}
    assert {e.check for e in run.evidence} == set().union(*MODULE_CHECKS.values())


def test_banner_output_is_passed_to_cvelookup():
    collector, runner = collector_with(all_clean())

    collector.collect("app.example.test")

    cve_call = next(call for call in runner.calls if call[0] == "cvelookup")
    assert cve_call[2] == {"banners": [{"port": 22, "service": "ssh"}]}


def test_cvelookup_is_skipped_when_banner_found_no_services():
    results = all_clean() | {"banner": scan_result("banner", data={"banners": []})}
    collector, runner = collector_with(results)

    run = collector.collect("app.example.test")

    assert "cvelookup" not in [call[0] for call in runner.calls]
    assert "cvelookup" in run.skipped
    assert not any(e.check.startswith("cvelookup.") for e in run.evidence)


def test_crashing_module_is_skipped_and_others_still_run():
    results = all_clean() | {"ssltls": ConnectionResetError("reset by peer")}
    collector, _ = collector_with(results)

    run = collector.collect("app.example.test")

    assert "reset by peer" in run.skipped["ssltls"]
    assert not any(e.check.startswith("ssltls.") for e in run.evidence)
    assert any(e.check.startswith("headers.") for e in run.evidence)


def test_module_reporting_errors_is_listed_as_skipped():
    results = all_clean() | {"headers": scan_result("headers", errors=["Connection refused"])}
    collector, _ = collector_with(results)

    run = collector.collect("app.example.test")

    assert run.skipped["headers"] == "Connection refused"


def later_modules():
    return CE_MODULES[CE_MODULES.index("portscan") + 1 :]


def test_host_with_no_open_ports_yields_no_evidence_and_no_further_traffic():
    results = all_clean() | {"portscan": scan_result("portscan", data={"open_ports": []})}
    collector, runner = collector_with(results)

    run = collector.collect("app.example.test")

    assert run.evidence == []
    assert [call[0] for call in runner.calls] == ["portscan"]
    assert "no open ports" in run.skipped["portscan"]
    assert set(later_modules()) <= set(run.skipped)


@pytest.mark.parametrize(
    "portscan",
    [
        ConnectionResetError("reset by peer"),
        scan_result("portscan", errors=["DNS resolution failed"]),
    ],
)
def test_failed_portscan_stops_the_host(portscan):
    collector, runner = collector_with(all_clean() | {"portscan": portscan})

    run = collector.collect("app.example.test")

    assert run.evidence == []
    assert [call[0] for call in runner.calls] == ["portscan"]
    assert set(later_modules()) <= set(run.skipped)


def test_banner_without_services_records_no_absent_evidence():
    results = all_clean() | {"banner": scan_result("banner", data={"banners": []})}
    collector, _ = collector_with(results)

    run = collector.collect("app.example.test")

    assert not any(e.check.startswith("banner.") for e in run.evidence)
    assert "no services identified" in run.skipped["banner"]


def test_banner_without_services_keeps_real_findings():
    finding = {"check_id": "banner.version_disclosed", "severity": "low"}
    results = all_clean() | {"banner": scan_result("banner", [finding], data={"banners": []})}
    collector, _ = collector_with(results)

    run = collector.collect("app.example.test")

    banner = [e for e in run.evidence if e.check.startswith("banner.")]
    assert [(e.check, e.observed) for e in banner] == [("banner.version_disclosed", "present")]


# --- Drift check against the installed redscope ----------------------------------------


def test_module_checks_match_installed_redscope_source():
    """MODULE_CHECKS must list exactly the check ids each redscope module can emit."""
    redscope = pytest.importorskip("redscope")
    from redscope.core.plugin_loader import _BUILTIN_MODULES

    for module, expected in MODULE_CHECKS.items():
        spec_path = _BUILTIN_MODULES[module].replace(".", "/") + ".py"
        source = Path(redscope.__file__).parent.parent / spec_path
        emitted = {
            kw.value.value
            for node in ast.walk(ast.parse(source.read_text()))
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Finding"
            for kw in node.keywords
            if kw.arg == "check_id"
        }
        assert emitted == expected, module


# --- Real redscope entry points (no network: error paths only) --------------------------


def test_missing_redscope_raises_a_clear_error(monkeypatch):
    import sys

    from complyscope.collectors.redscope_adapter import (
        RedscopeUnavailableError,
        run_redscope_module,
    )

    monkeypatch.setitem(sys.modules, "redscope.core.config", None)

    with pytest.raises(RedscopeUnavailableError, match="complyscope\\[scan\\]"):
        run_redscope_module("ssltls", "localhost")


def test_unknown_redscope_module_is_an_error():
    pytest.importorskip("redscope")
    from complyscope.collectors.redscope_adapter import run_redscope_module

    with pytest.raises(RuntimeError, match="no module named 'nope'"):
        run_redscope_module("nope", "localhost")


def test_redscope_version_names_the_installed_release(monkeypatch):
    import importlib.metadata

    from complyscope.collectors.redscope_adapter import redscope_version

    monkeypatch.setattr(importlib.metadata, "version", lambda name: "2.0.0")
    assert redscope_version() == "redscope 2.0.0"

    def missing(name):
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(importlib.metadata, "version", missing)
    assert redscope_version() == "redscope (not installed)"
