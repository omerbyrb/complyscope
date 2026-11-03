"""The only module that talks to redscope (ADR-0003): runs checks and returns Evidence.

redscope is an optional dependency (``pip install complyscope[scan]``) and is imported
lazily, so the rest of complyscope works without it.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from complyscope.models import Evidence, Scope

# Modules run for Cyber Essentials, in order: banner must run before cvelookup.
CE_MODULES = ("portscan", "serviceenum", "banner", "cvelookup", "ssltls", "headers")

# Every check id each module can emit (redscope docs/check-ids.md). A module that finishes
# cleanly without reporting one of these is evidence that the issue is absent (ADR-0008).
# A test compares this table with the installed redscope source.
MODULE_CHECKS: dict[str, frozenset[str]] = {
    "portscan": frozenset({"portscan.open_ports_summary", "portscan.risky_service_exposed"}),
    "serviceenum": frozenset(
        {
            "serviceenum.ftp_anonymous_login",
            "serviceenum.ssh_weak_algorithms",
            "serviceenum.smtp_open_relay",
            "serviceenum.smtp_vrfy_enabled",
            "serviceenum.smtp_expn_enabled",
            "serviceenum.dns_open_recursion",
            "serviceenum.dns_version_disclosed",
            "serviceenum.redis_no_auth",
            "serviceenum.elasticsearch_no_auth",
            "serviceenum.mongodb_no_auth",
            "serviceenum.memcached_no_auth",
            "serviceenum.zookeeper_no_auth",
            "serviceenum.mail_starttls_missing",
            "serviceenum.smb_signing_not_required",
        }
    ),
    "banner": frozenset(
        {"banner.eol_software", "banner.services_fingerprinted", "banner.version_disclosed"}
    ),
    "cvelookup": frozenset({"cvelookup.known_vulnerability"}),
    "ssltls": frozenset(
        {
            "ssltls.cert_expired",
            "ssltls.cert_expiring_soon",
            "ssltls.cert_validity_too_long",
            "ssltls.cert_hostname_mismatch",
            "ssltls.deprecated_protocol",
            "ssltls.weak_cipher",
            "ssltls.weak_key_length",
            "ssltls.hsts_missing",
            "ssltls.hsts_max_age_too_short",
        }
    ),
    "headers": frozenset(
        {
            "headers.missing_security_header",
            "headers.info_disclosure",
            "headers.http_not_redirected",
        }
    ),
}

# Runs one redscope module and returns ScanResult.to_dict().
Runner = Callable[..., Mapping[str, Any]]


class RedscopeUnavailableError(RuntimeError):
    """redscope is not installed."""


@dataclass
class HostRun:
    """Outcome of collecting evidence from one host."""

    target: str
    evidence: list[Evidence] = field(default_factory=list)
    # Modules that produced no evidence, with the reason (crash, errors, missing input).
    skipped: dict[str, str] = field(default_factory=dict)


def evidence_from_result(
    result: Mapping[str, Any], *, target: str, collected_at: datetime, collector: str
) -> list[Evidence]:
    """Convert one module's ScanResult.to_dict() into Evidence.

    A module that reported errors yields nothing: we cannot tell what it did not check.
    """
    if result["errors"]:
        return []

    common = {"source": "redscope", "target": target, "collected_at": collected_at}
    evidence = []
    for finding in result["findings"]:
        if not finding.get("check_id"):
            continue
        details = finding["description"]
        if finding.get("evidence"):
            details += f"\nEvidence: {finding['evidence']}"
        evidence.append(
            Evidence(
                **common,
                check=finding["check_id"],
                observed="present",
                severity=finding["severity"],
                title=finding["title"],
                details=details,
                collector=collector,
            )
        )

    found = {e.check for e in evidence}
    for check in sorted(MODULE_CHECKS.get(result["module"], frozenset()) - found):
        evidence.append(Evidence(**common, check=check, observed="absent", collector=collector))
    return evidence


def run_redscope_module(module: str, target: str, **kwargs: Any) -> Mapping[str, Any]:
    try:
        from redscope.core.config import load_config
        from redscope.core.plugin_loader import load_module
    except ImportError as e:
        raise RedscopeUnavailableError(
            "redscope is not installed; run: pip install 'complyscope[scan]'"
        ) from e

    instance = load_module(module, load_config())
    if instance is None:
        raise RuntimeError(f"redscope has no module named {module!r}")
    result = instance.run(target, **kwargs)
    result.finish()
    return result.to_dict()


def redscope_version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return f"redscope {version('redscope')}"
    except PackageNotFoundError:
        return "redscope (not installed)"


class RedscopeCollector:
    def __init__(
        self,
        scope: Scope,
        modules: tuple[str, ...] = CE_MODULES,
        runner: Runner = run_redscope_module,
        collector: str | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self.scope = scope
        self.modules = modules
        self.runner = runner
        self.collector = collector or redscope_version()
        self.clock = clock

    def collect(self, host: str) -> HostRun:
        # The scope gate comes first: nothing is sent to a host that is not authorised.
        target = self.scope.ensure_in_scope(host)
        run = HostRun(target=target)
        outputs: dict[str, Mapping[str, Any]] = {}

        for module in self.modules:
            kwargs: dict[str, Any] = {}
            if module == "cvelookup":
                banners = outputs.get("banner", {}).get("data", {}).get("banners")
                if not banners:
                    run.skipped[module] = "no service versions from the banner module"
                    continue
                kwargs["banners"] = banners

            try:
                result = self.runner(module, target, **kwargs)
            except RedscopeUnavailableError:
                raise
            except Exception as e:  # one failing module must not stop the others
                run.skipped[module] = f"crashed: {type(e).__name__}: {e}"
                continue

            if result["errors"]:
                run.skipped[module] = "; ".join(result["errors"])
                continue
            outputs[module] = result
            run.evidence.extend(
                evidence_from_result(
                    result, target=target, collected_at=self.clock(), collector=self.collector
                )
            )
        return run
