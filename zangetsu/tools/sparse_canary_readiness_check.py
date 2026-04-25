"""Sparse-Candidate CANARY Readiness Check (TEAM ORDER 0-9S-CANARY).

Offline / read-only readiness checker that verifies CR1–CR15 + a set
of structural runtime-isolation checks before any future
0-9S-CANARY-OBSERVE order activates a multi-day observation window.

The tool **never**:

  - mutates source files
  - executes Arena pipelines
  - imports any runtime module with side effects (e.g.
    ``arena_pipeline`` chdir's to the production path on import)

It only reads source-text + caller-supplied verdicts / evidence and
produces a :class:`ReadinessReport` with PASS / FAIL / OVERRIDE per
criterion plus a final verdict.
"""

from __future__ import annotations

import json
import pathlib
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


READINESS_TOOL_VERSION = "0-9S-CANARY"

VERDICT_PASS = "PASS"
VERDICT_FAIL = "FAIL"
VERDICT_OVERRIDE = "OVERRIDE"
VERDICT_NOT_APPLICABLE = "N/A"

VERDICT_GREEN = "GREEN"
VERDICT_YELLOW = "YELLOW"
VERDICT_RED = "RED"


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


@dataclass
class CRResult:
    cr_id: str
    verdict: str
    note: str = ""


@dataclass
class ReadinessReport:
    """Readiness report covering CR1–CR15 + structural isolation
    checks. Returned by :func:`check_readiness`."""

    tool_version: str = READINESS_TOOL_VERSION
    services_dir: str = ""
    cr_results: List[CRResult] = field(default_factory=list)
    overall_verdict: str = VERDICT_FAIL
    overall_blocks_canary: bool = True
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        try:
            return json.dumps(self.to_dict(), sort_keys=True)
        except Exception:
            return ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _services_dir(repo_root: Optional[pathlib.Path] = None) -> pathlib.Path:
    if repo_root is None:
        repo_root = pathlib.Path(__file__).resolve().parent.parent
    return repo_root / "services"


def _read_source(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _file_contains_import(source: str, qualified_name: str) -> bool:
    """Return True if ``source`` contains an actual ``import`` line
    referencing ``qualified_name``. Docstring / comment mentions do not
    count.
    """
    pattern = re.compile(
        rf"^\s*(?:from\s+{re.escape(qualified_name)}\b|import\s+{re.escape(qualified_name)}\b)",
        re.MULTILINE,
    )
    return bool(pattern.search(source))


def _grep_apply_def(source: str) -> List[str]:
    """Return any line that defines a public ``apply_*`` function whose
    name suggests a budget / plan / consumer / allocator apply path.

    Pre-existing trading helpers like ``apply_trailing_stop`` /
    ``apply_fixed_target`` / ``apply_tp_strategy`` are NOT treated as
    runtime apply paths — they only modify a signal array, never touch
    generation budget or sampling weights.
    """
    out: List[str] = []
    forbidden_keywords = (
        "apply_budget",
        "apply_plan",
        "apply_consumer",
        "apply_allocator",
        "apply_canary",
        "apply_recommendation",
        "apply_weights",
        "apply_sampling",
        "apply_generation",
    )
    for line in source.splitlines():
        stripped = line.strip()
        if not stripped.startswith("def apply_"):
            continue
        for kw in forbidden_keywords:
            if stripped.startswith(f"def {kw}"):
                out.append(stripped)
                break
    return out


# ---------------------------------------------------------------------------
# Per-criterion checks
# ---------------------------------------------------------------------------


_GENERATION_RUNTIME_FILES = (
    "arena_pipeline.py",
    "alpha_signal_live.py",
    "alpha_discovery.py",
    "alpha_dedup.py",
    "alpha_ensemble.py",
    "data_collector.py",
)

_ARENA_RUNTIME_FILES = (
    "arena23_orchestrator.py",
    "arena45_orchestrator.py",
    "arena_gates.py",
)

_EXECUTION_FILES = (
    "alpha_signal_live.py",
)


def _cr1_passport_persistence(services: pathlib.Path) -> CRResult:
    text = _read_source(services / "arena_pipeline.py")
    if "0-9P attribution closure" in text and '"generation_profile_id":' in text:
        return CRResult("CR1", VERDICT_PASS, "passport.arena1 persists generation_profile_id")
    return CRResult("CR1", VERDICT_FAIL, "expected 0-9P attribution closure marker")


def _cr2_attribution_verdict(audit_verdict: Optional[str]) -> CRResult:
    if not audit_verdict:
        return CRResult("CR2", VERDICT_FAIL, "no audit verdict supplied")
    v = str(audit_verdict).upper()
    if v == VERDICT_GREEN:
        return CRResult("CR2", VERDICT_PASS, "attribution verdict GREEN")
    if v == VERDICT_YELLOW:
        return CRResult("CR2", VERDICT_PASS, "attribution verdict YELLOW (documented)")
    if v == VERDICT_RED:
        return CRResult("CR2", VERDICT_FAIL, "attribution verdict RED — STOP")
    return CRResult("CR2", VERDICT_FAIL, f"unrecognised verdict {audit_verdict!r}")


def _cr3_consumer_present(services: pathlib.Path) -> CRResult:
    if (services / "feedback_budget_consumer.py").exists():
        return CRResult("CR3", VERDICT_PASS, "feedback_budget_consumer.py present")
    return CRResult("CR3", VERDICT_FAIL, "missing feedback_budget_consumer.py")


def _cr4_no_runtime_apply_path(services: pathlib.Path) -> CRResult:
    """No public apply_* function in any runtime / dry-run service."""
    offenders: List[str] = []
    for path in services.glob("*.py"):
        for hit in _grep_apply_def(_read_source(path)):
            offenders.append(f"{path.name}: {hit}")
    if not offenders:
        return CRResult("CR4", VERDICT_PASS, "no apply_* function in services/")
    return CRResult("CR4", VERDICT_FAIL, "apply_* found: " + "; ".join(offenders))


def _cr5_consumer_no_runtime_import(services: pathlib.Path) -> CRResult:
    bad: List[str] = []
    for fname in _GENERATION_RUNTIME_FILES + _ARENA_RUNTIME_FILES + _EXECUTION_FILES:
        path = services / fname
        if not path.exists():
            continue
        text = _read_source(path)
        if _file_contains_import(text, "zangetsu.services.feedback_budget_consumer"):
            bad.append(fname)
    if not bad:
        return CRResult("CR5", VERDICT_PASS, "consumer not imported by runtime")
    return CRResult("CR5", VERDICT_FAIL, "imported by: " + ", ".join(bad))


def _cr6_consumer_stability(
    days_stable: Optional[int],
    explicit_override: bool,
) -> CRResult:
    if days_stable is not None and days_stable >= 7:
        return CRResult("CR6", VERDICT_PASS, f"{days_stable}d stable")
    if explicit_override:
        return CRResult(
            "CR6",
            VERDICT_OVERRIDE,
            "j13 order text treated as explicit override per §3 preflight rule",
        )
    return CRResult(
        "CR6",
        VERDICT_FAIL,
        "consumer lacks 7d stability and no override supplied",
    )


def _cr7_unknown_reject(unknown_rate: Optional[float]) -> CRResult:
    if unknown_rate is None:
        return CRResult("CR7", VERDICT_FAIL, "unknown_reject_rate not supplied")
    try:
        rate = float(unknown_rate)
    except Exception:
        return CRResult("CR7", VERDICT_FAIL, "invalid unknown_reject_rate")
    if rate < 0.05:
        return CRResult("CR7", VERDICT_PASS, f"unknown_reject_rate={rate:.4f} < 0.05")
    return CRResult("CR7", VERDICT_FAIL, f"unknown_reject_rate={rate:.4f} >= 0.05")


def _cr8_a2_sparse_trend_measured(measured: bool) -> CRResult:
    if measured:
        return CRResult("CR8", VERDICT_PASS, "A2 sparse rate trend measured")
    return CRResult("CR8", VERDICT_FAIL, "A2 sparse trend evidence missing")


def _cr9_a3_pass_rate_evidence(measured: bool) -> CRResult:
    if measured:
        return CRResult("CR9", VERDICT_PASS, "A3 pass_rate evidence available")
    return CRResult("CR9", VERDICT_FAIL, "A3 pass_rate evidence missing")


def _cr10_deployable_evidence(measured: bool) -> CRResult:
    if measured:
        return CRResult("CR10", VERDICT_PASS, "deployable_count evidence available")
    return CRResult("CR10", VERDICT_FAIL, "deployable_count evidence missing")


def _cr11_rollback_doc(repo_root: pathlib.Path) -> CRResult:
    candidates = [
        repo_root / "docs/recovery/20260424-mod-7/0-9s-ready/03_rollback_plan.md",
    ]
    for p in candidates:
        if p.exists():
            return CRResult("CR11", VERDICT_PASS, f"rollback plan: {p.name}")
    return CRResult("CR11", VERDICT_FAIL, "rollback plan not found")


def _cr12_alert_doc(repo_root: pathlib.Path) -> CRResult:
    candidates = [
        repo_root / "docs/recovery/20260424-mod-7/0-9s-ready/04_alerting_and_monitoring_plan.md",
    ]
    for p in candidates:
        if p.exists():
            return CRResult("CR12", VERDICT_PASS, f"alerting plan: {p.name}")
    return CRResult("CR12", VERDICT_FAIL, "alerting plan not found")


def _cr13_branch_protection(branch_protection: Optional[Mapping[str, bool]]) -> CRResult:
    if not branch_protection:
        return CRResult("CR13", VERDICT_FAIL, "branch protection state not supplied")
    expected = {
        "enforce_admins": True,
        "required_signatures": True,
        "linear_history": True,
        "allow_force_pushes": False,
        "allow_deletions": False,
    }
    missing: List[str] = []
    for k, v in expected.items():
        if bool(branch_protection.get(k)) != v:
            missing.append(f"{k}={branch_protection.get(k)} (expected {v})")
    if missing:
        return CRResult("CR13", VERDICT_FAIL, "; ".join(missing))
    return CRResult("CR13", VERDICT_PASS, "branch protection intact")


def _cr14_signed_pr_only(signed_pr_only: Optional[bool]) -> CRResult:
    if signed_pr_only is True:
        return CRResult("CR14", VERDICT_PASS, "signed PR-only flow intact")
    if signed_pr_only is False:
        return CRResult("CR14", VERDICT_FAIL, "signed PR-only flow weakened")
    return CRResult("CR14", VERDICT_FAIL, "signed PR-only flag not supplied")


def _cr15_j13_authorization(authorization_present: bool) -> CRResult:
    if authorization_present:
        return CRResult(
            "CR15", VERDICT_PASS, "j13 authorization sentence present per §22"
        )
    return CRResult("CR15", VERDICT_FAIL, "j13 authorization missing")


# ---------------------------------------------------------------------------
# Top-level orchestration
# ---------------------------------------------------------------------------


def check_readiness(
    *,
    repo_root: Optional[pathlib.Path] = None,
    audit_verdict: Optional[str] = None,
    consumer_days_stable: Optional[int] = None,
    consumer_override: bool = False,
    unknown_reject_rate: Optional[float] = None,
    a2_sparse_trend_measured: bool = False,
    a3_pass_rate_measured: bool = False,
    deployable_evidence_measured: bool = False,
    branch_protection: Optional[Mapping[str, bool]] = None,
    signed_pr_only: Optional[bool] = None,
    j13_authorization_present: bool = False,
) -> ReadinessReport:
    """Run CR1–CR15 checks and return a :class:`ReadinessReport`.
    Never raises."""

    if repo_root is None:
        repo_root = pathlib.Path(__file__).resolve().parent.parent.parent
    services = _services_dir(repo_root / "zangetsu")

    report = ReadinessReport(services_dir=str(services))

    try:
        report.cr_results.extend(
            [
                _cr1_passport_persistence(services),
                _cr2_attribution_verdict(audit_verdict),
                _cr3_consumer_present(services),
                _cr4_no_runtime_apply_path(services),
                _cr5_consumer_no_runtime_import(services),
                _cr6_consumer_stability(consumer_days_stable, consumer_override),
                _cr7_unknown_reject(unknown_reject_rate),
                _cr8_a2_sparse_trend_measured(a2_sparse_trend_measured),
                _cr9_a3_pass_rate_evidence(a3_pass_rate_measured),
                _cr10_deployable_evidence(deployable_evidence_measured),
                _cr11_rollback_doc(repo_root),
                _cr12_alert_doc(repo_root),
                _cr13_branch_protection(branch_protection),
                _cr14_signed_pr_only(signed_pr_only),
                _cr15_j13_authorization(j13_authorization_present),
            ]
        )
    except Exception as exc:  # noqa: BLE001
        report.notes.append(f"check_readiness raised {type(exc).__name__}")
        report.overall_verdict = VERDICT_FAIL
        return report

    fails = [r for r in report.cr_results if r.verdict == VERDICT_FAIL]
    if fails:
        report.overall_verdict = VERDICT_FAIL
        report.overall_blocks_canary = True
        report.notes.append(
            "blocking CRs: " + ", ".join(r.cr_id for r in fails)
        )
    else:
        # PASS or OVERRIDE allow CANARY observation to proceed.
        report.overall_verdict = VERDICT_PASS
        report.overall_blocks_canary = False

    return report


def required_cr_ids() -> Tuple[str, ...]:
    """Return the canonical 15 CR ids."""
    return tuple(f"CR{i}" for i in range(1, 16))


def safe_check_readiness(**kwargs: Any) -> ReadinessReport:
    """Exception-safe wrapper. Returns a report with overall_verdict
    FAIL and a single note recording the exception class name."""
    try:
        return check_readiness(**kwargs)
    except Exception as exc:  # noqa: BLE001
        rpt = ReadinessReport()
        rpt.overall_verdict = VERDICT_FAIL
        rpt.notes = [f"check_readiness raised {type(exc).__name__}"]
        return rpt
