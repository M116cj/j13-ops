"""Tests for TEAM ORDER 0-9S-CANARY — sparse_canary_readiness_check.

Covers:
  - 12.1 readiness tests CR1-CR15
  - GREEN / YELLOW / RED attribution handling
  - missing j13 authorization
  - missing rollback / alert plan
  - branch protection state checks
  - exception safety
"""

from __future__ import annotations

import json
import pathlib

import pytest

from zangetsu.tools.sparse_canary_readiness_check import (
    READINESS_TOOL_VERSION,
    ReadinessReport,
    VERDICT_FAIL,
    VERDICT_GREEN,
    VERDICT_OVERRIDE,
    VERDICT_PASS,
    VERDICT_RED,
    VERDICT_YELLOW,
    check_readiness,
    required_cr_ids,
    safe_check_readiness,
)


_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


def _good_branch_protection():
    return {
        "enforce_admins": True,
        "required_signatures": True,
        "linear_history": True,
        "allow_force_pushes": False,
        "allow_deletions": False,
    }


def _all_pass_kwargs(*, verdict=VERDICT_GREEN, override=False, days_stable=10,
                     unknown=0.02, signed_pr=True, j13=True):
    return dict(
        repo_root=_REPO_ROOT,
        audit_verdict=verdict,
        consumer_days_stable=days_stable,
        consumer_override=override,
        unknown_reject_rate=unknown,
        a2_sparse_trend_measured=True,
        a3_pass_rate_measured=True,
        deployable_evidence_measured=True,
        branch_protection=_good_branch_protection(),
        signed_pr_only=signed_pr,
        j13_authorization_present=j13,
    )


# ---------------------------------------------------------------------------
# 1. Schema + tool version
# ---------------------------------------------------------------------------


def test_required_cr_ids_returns_15():
    ids = required_cr_ids()
    assert len(ids) == 15
    assert ids[0] == "CR1"
    assert ids[-1] == "CR15"


def test_readiness_tool_version_pinned():
    assert READINESS_TOOL_VERSION == "0-9S-CANARY"


def test_report_serializes_to_json():
    rpt = check_readiness(**_all_pass_kwargs())
    payload = json.loads(rpt.to_json())
    assert payload["tool_version"] == "0-9S-CANARY"


# ---------------------------------------------------------------------------
# 2. CR1-CR15 (happy path)
# ---------------------------------------------------------------------------


def test_canary_readiness_requires_cr1_to_cr15():
    rpt = check_readiness(**_all_pass_kwargs())
    ids = [r.cr_id for r in rpt.cr_results]
    for cr in required_cr_ids():
        assert cr in ids


def test_all_pass_overall_verdict_pass():
    rpt = check_readiness(**_all_pass_kwargs())
    assert rpt.overall_verdict == VERDICT_PASS
    assert rpt.overall_blocks_canary is False


def test_all_pass_no_failing_crs():
    rpt = check_readiness(**_all_pass_kwargs())
    fails = [r for r in rpt.cr_results if r.verdict == VERDICT_FAIL]
    assert fails == []


# ---------------------------------------------------------------------------
# 3. CR2 attribution verdict
# ---------------------------------------------------------------------------


def test_canary_blocks_when_attribution_red():
    rpt = check_readiness(**_all_pass_kwargs(verdict=VERDICT_RED))
    cr2 = next(r for r in rpt.cr_results if r.cr_id == "CR2")
    assert cr2.verdict == VERDICT_FAIL
    assert rpt.overall_verdict == VERDICT_FAIL


def test_canary_allows_green_attribution():
    rpt = check_readiness(**_all_pass_kwargs(verdict=VERDICT_GREEN))
    cr2 = next(r for r in rpt.cr_results if r.cr_id == "CR2")
    assert cr2.verdict == VERDICT_PASS


def test_canary_allows_documented_yellow_attribution():
    rpt = check_readiness(**_all_pass_kwargs(verdict=VERDICT_YELLOW))
    cr2 = next(r for r in rpt.cr_results if r.cr_id == "CR2")
    assert cr2.verdict == VERDICT_PASS  # documented YELLOW counts as PASS


def test_attribution_unknown_value_fails():
    rpt = check_readiness(**_all_pass_kwargs(verdict="bogus"))
    cr2 = next(r for r in rpt.cr_results if r.cr_id == "CR2")
    assert cr2.verdict == VERDICT_FAIL


def test_attribution_missing_value_fails():
    kwargs = _all_pass_kwargs()
    kwargs["audit_verdict"] = None
    rpt = check_readiness(**kwargs)
    cr2 = next(r for r in rpt.cr_results if r.cr_id == "CR2")
    assert cr2.verdict == VERDICT_FAIL


# ---------------------------------------------------------------------------
# 4. CR6 consumer stability + override
# ---------------------------------------------------------------------------


def test_canary_blocks_consumer_unstable_no_override():
    rpt = check_readiness(**_all_pass_kwargs(days_stable=3, override=False))
    cr6 = next(r for r in rpt.cr_results if r.cr_id == "CR6")
    assert cr6.verdict == VERDICT_FAIL


def test_canary_allows_consumer_unstable_with_override():
    rpt = check_readiness(**_all_pass_kwargs(days_stable=3, override=True))
    cr6 = next(r for r in rpt.cr_results if r.cr_id == "CR6")
    assert cr6.verdict == VERDICT_OVERRIDE


def test_canary_consumer_stable_passes():
    rpt = check_readiness(**_all_pass_kwargs(days_stable=7))
    cr6 = next(r for r in rpt.cr_results if r.cr_id == "CR6")
    assert cr6.verdict == VERDICT_PASS


# ---------------------------------------------------------------------------
# 5. CR7 unknown_reject
# ---------------------------------------------------------------------------


def test_cr7_pass_when_below_005():
    rpt = check_readiness(**_all_pass_kwargs(unknown=0.04))
    cr7 = next(r for r in rpt.cr_results if r.cr_id == "CR7")
    assert cr7.verdict == VERDICT_PASS


def test_cr7_fail_when_at_or_above_005():
    rpt = check_readiness(**_all_pass_kwargs(unknown=0.05))
    cr7 = next(r for r in rpt.cr_results if r.cr_id == "CR7")
    assert cr7.verdict == VERDICT_FAIL


def test_cr7_fail_when_missing():
    kwargs = _all_pass_kwargs()
    kwargs["unknown_reject_rate"] = None
    rpt = check_readiness(**kwargs)
    cr7 = next(r for r in rpt.cr_results if r.cr_id == "CR7")
    assert cr7.verdict == VERDICT_FAIL


# ---------------------------------------------------------------------------
# 6. CR15 j13 authorization
# ---------------------------------------------------------------------------


def test_canary_blocks_missing_j13_authorization():
    rpt = check_readiness(**_all_pass_kwargs(j13=False))
    cr15 = next(r for r in rpt.cr_results if r.cr_id == "CR15")
    assert cr15.verdict == VERDICT_FAIL
    assert rpt.overall_verdict == VERDICT_FAIL


def test_canary_passes_with_j13_authorization():
    rpt = check_readiness(**_all_pass_kwargs(j13=True))
    cr15 = next(r for r in rpt.cr_results if r.cr_id == "CR15")
    assert cr15.verdict == VERDICT_PASS


# ---------------------------------------------------------------------------
# 7. CR11 / CR12 docs
# ---------------------------------------------------------------------------


def test_canary_blocks_missing_rollback_plan(tmp_path):
    # Use a fake repo root with no rollback plan.
    rpt = check_readiness(**{
        **_all_pass_kwargs(),
        "repo_root": tmp_path,
    })
    cr11 = next(r for r in rpt.cr_results if r.cr_id == "CR11")
    assert cr11.verdict == VERDICT_FAIL


def test_canary_blocks_missing_alert_plan(tmp_path):
    rpt = check_readiness(**{
        **_all_pass_kwargs(),
        "repo_root": tmp_path,
    })
    cr12 = next(r for r in rpt.cr_results if r.cr_id == "CR12")
    assert cr12.verdict == VERDICT_FAIL


def test_canary_finds_rollback_plan_in_repo():
    rpt = check_readiness(**_all_pass_kwargs())
    cr11 = next(r for r in rpt.cr_results if r.cr_id == "CR11")
    assert cr11.verdict == VERDICT_PASS


def test_canary_finds_alert_plan_in_repo():
    rpt = check_readiness(**_all_pass_kwargs())
    cr12 = next(r for r in rpt.cr_results if r.cr_id == "CR12")
    assert cr12.verdict == VERDICT_PASS


# ---------------------------------------------------------------------------
# 8. CR13 branch protection
# ---------------------------------------------------------------------------


def test_canary_blocks_branch_protection_weakened():
    bad = _good_branch_protection()
    bad["enforce_admins"] = False
    rpt = check_readiness(**{**_all_pass_kwargs(), "branch_protection": bad})
    cr13 = next(r for r in rpt.cr_results if r.cr_id == "CR13")
    assert cr13.verdict == VERDICT_FAIL


def test_canary_blocks_branch_protection_missing_signatures():
    bad = _good_branch_protection()
    bad["required_signatures"] = False
    rpt = check_readiness(**{**_all_pass_kwargs(), "branch_protection": bad})
    cr13 = next(r for r in rpt.cr_results if r.cr_id == "CR13")
    assert cr13.verdict == VERDICT_FAIL


def test_canary_blocks_branch_protection_force_pushes_allowed():
    bad = _good_branch_protection()
    bad["allow_force_pushes"] = True
    rpt = check_readiness(**{**_all_pass_kwargs(), "branch_protection": bad})
    cr13 = next(r for r in rpt.cr_results if r.cr_id == "CR13")
    assert cr13.verdict == VERDICT_FAIL


def test_canary_branch_protection_missing_payload_fails():
    rpt = check_readiness(**{**_all_pass_kwargs(), "branch_protection": None})
    cr13 = next(r for r in rpt.cr_results if r.cr_id == "CR13")
    assert cr13.verdict == VERDICT_FAIL


# ---------------------------------------------------------------------------
# 9. CR14 signed PR-only
# ---------------------------------------------------------------------------


def test_canary_signed_pr_only_pass():
    rpt = check_readiness(**_all_pass_kwargs(signed_pr=True))
    cr14 = next(r for r in rpt.cr_results if r.cr_id == "CR14")
    assert cr14.verdict == VERDICT_PASS


def test_canary_signed_pr_only_fail():
    rpt = check_readiness(**_all_pass_kwargs(signed_pr=False))
    cr14 = next(r for r in rpt.cr_results if r.cr_id == "CR14")
    assert cr14.verdict == VERDICT_FAIL


def test_canary_signed_pr_only_missing_payload_fails():
    rpt = check_readiness(**{**_all_pass_kwargs(), "signed_pr_only": None})
    cr14 = next(r for r in rpt.cr_results if r.cr_id == "CR14")
    assert cr14.verdict == VERDICT_FAIL


# ---------------------------------------------------------------------------
# 10. CR1 / CR3 source-text checks
# ---------------------------------------------------------------------------


def test_cr1_passport_persistence_passes():
    rpt = check_readiness(**_all_pass_kwargs())
    cr1 = next(r for r in rpt.cr_results if r.cr_id == "CR1")
    assert cr1.verdict == VERDICT_PASS


def test_cr3_consumer_present_passes():
    rpt = check_readiness(**_all_pass_kwargs())
    cr3 = next(r for r in rpt.cr_results if r.cr_id == "CR3")
    assert cr3.verdict == VERDICT_PASS


def test_cr4_no_runtime_apply_path_passes():
    rpt = check_readiness(**_all_pass_kwargs())
    cr4 = next(r for r in rpt.cr_results if r.cr_id == "CR4")
    assert cr4.verdict == VERDICT_PASS


def test_cr5_consumer_no_runtime_import_passes():
    rpt = check_readiness(**_all_pass_kwargs())
    cr5 = next(r for r in rpt.cr_results if r.cr_id == "CR5")
    assert cr5.verdict == VERDICT_PASS


# ---------------------------------------------------------------------------
# 11. Exception safety
# ---------------------------------------------------------------------------


def test_safe_check_readiness_no_kwargs_returns_fail():
    rpt = safe_check_readiness()
    # Default state — no audit, no protection, no auth — overall FAIL.
    assert rpt.overall_verdict == VERDICT_FAIL


def test_safe_check_readiness_handles_internal_error():
    # Pass a path that doesn't exist as repo_root → still no exception.
    rpt = safe_check_readiness(repo_root=pathlib.Path("/nonexistent"))
    # Still produces a report (no crash).
    assert rpt.overall_verdict == VERDICT_FAIL


def test_check_readiness_overall_fail_when_one_blocking_cr_fails():
    rpt = check_readiness(**_all_pass_kwargs(verdict=VERDICT_RED))
    assert rpt.overall_verdict == VERDICT_FAIL
    assert rpt.overall_blocks_canary is True


def test_check_readiness_pass_with_override_does_not_block():
    rpt = check_readiness(**_all_pass_kwargs(days_stable=3, override=True))
    # CR6 OVERRIDE should not count as FAIL.
    assert rpt.overall_verdict == VERDICT_PASS


def test_check_readiness_notes_record_blocking_crs():
    rpt = check_readiness(**_all_pass_kwargs(verdict=VERDICT_RED, j13=False))
    blocking = [r for r in rpt.cr_results if r.verdict == VERDICT_FAIL]
    assert len(blocking) >= 2
    assert any("blocking CRs" in n for n in rpt.notes)


# ---------------------------------------------------------------------------
# 12. Tool isolation
# ---------------------------------------------------------------------------


def test_readiness_check_does_not_import_runtime_modules():
    import zangetsu.tools.sparse_canary_readiness_check as mod
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    # No runtime arena import.
    assert "from zangetsu.services.arena_pipeline" not in src
    assert "import zangetsu.services.arena_pipeline" not in src
    assert "from zangetsu.services.arena23_orchestrator" not in src
    assert "from zangetsu.services.arena45_orchestrator" not in src
    assert "from zangetsu.engine" not in src
    assert "from zangetsu.live" not in src


def test_readiness_check_module_has_no_apply_method():
    import zangetsu.tools.sparse_canary_readiness_check as mod
    publics = [n for n in dir(mod) if not n.startswith("_")]
    for name in publics:
        assert not name.lower().startswith("apply"), name
