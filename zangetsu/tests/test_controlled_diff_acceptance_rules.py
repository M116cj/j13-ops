"""Tests for TEAM ORDER 0-9M — Phase 7 Controlled-Diff Acceptance Rules Upgrade.

Validates the new classification vocabulary in
``scripts/governance/diff_snapshots.py``:

    ZERO_DIFF
    EXPLAINED
    EXPLAINED_TRACE_ONLY   ← 0-9M new
    FORBIDDEN
    FORBIDDEN_UNAUTHORIZED_RUNTIME_SHA   ← 0-9M new (subclass)
    FORBIDDEN_THRESHOLD                  ← 0-9M new (subclass)

Uses synthetic snapshot dicts — no filesystem I/O — so the tests run fast
and isolate the classification logic.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


# Load diff_snapshots.py as a module (it lives under scripts/governance/ which
# is not a Python package, so we use importlib directly).
_DIFF_PATH = Path(__file__).resolve().parents[2] / "scripts" / "governance" / "diff_snapshots.py"
_spec = importlib.util.spec_from_file_location("diff_snapshots", _DIFF_PATH)
_ds = importlib.util.module_from_spec(_spec)
sys.modules["diff_snapshots"] = _ds
_spec.loader.exec_module(_ds)


def _snap(field_values: dict, manifest: str = "sha_xxx") -> dict:
    """Build a minimal snapshot dict for a given flat field map."""
    # Flat map like {"config.arena_pipeline_sha": "sha_1", "runtime.arena_processes.count": 0}
    # → expand to nested {"config": {...}, "runtime": {...}}
    surfaces: dict = {}
    for dotted, val in field_values.items():
        parts = dotted.split(".")
        cur = surfaces
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = val
    return {"surfaces": surfaces, "sha256_manifest": manifest}


# ---------------------------------------------------------------------------
# §10.1 Positive test — authorized trace-only runtime SHA is EXPLAINED_TRACE_ONLY
# ---------------------------------------------------------------------------


def test_authorized_trace_only_runtime_sha_is_explained_trace_only():
    pre = _snap({
        "config.arena_pipeline_sha": "sha_before",
        "config.zangetsu_settings_sha": "sha_stable",
    }, manifest="pre_m")
    post = _snap({
        "config.arena_pipeline_sha": "sha_after",
        "config.zangetsu_settings_sha": "sha_stable",
    }, manifest="post_m")
    result = _ds.diff(
        pre, post, set(), {"config.arena_pipeline_sha"}
    )
    assert result["overall"] == "EXPLAINED_TRACE_ONLY"
    assert len(result["explained_trace_only"]) == 1
    assert result["explained_trace_only"][0][0] == "config.arena_pipeline_sha"
    assert len(result["forbidden"]) == 0


# ---------------------------------------------------------------------------
# §10.2 Unauthorized runtime SHA change remains FORBIDDEN
# ---------------------------------------------------------------------------


def test_unauthorized_runtime_sha_change_is_forbidden():
    pre = _snap({"config.arena_pipeline_sha": "sha_a"})
    post = _snap({"config.arena_pipeline_sha": "sha_b"})
    result = _ds.diff(pre, post, set(), set())  # no trace-only authorization
    assert result["overall"] == "FORBIDDEN"
    assert len(result["forbidden"]) == 1
    assert result["forbidden"][0][3] == "FORBIDDEN_UNAUTHORIZED_RUNTIME_SHA"


def test_unauthorized_arena23_orchestrator_sha_is_forbidden():
    pre = _snap({"config.arena23_orchestrator_sha": "sha_a"})
    post = _snap({"config.arena23_orchestrator_sha": "sha_b"})
    result = _ds.diff(pre, post, set(), set())
    assert result["overall"] == "FORBIDDEN"
    assert result["forbidden"][0][3] == "FORBIDDEN_UNAUTHORIZED_RUNTIME_SHA"


# ---------------------------------------------------------------------------
# §10.3 Threshold protection — zangetsu_settings_sha NEVER trace-only-authorizable
# ---------------------------------------------------------------------------


def test_threshold_change_remains_forbidden_even_under_authorization_attempt():
    pre = _snap({"config.zangetsu_settings_sha": "sha_a"})
    post = _snap({"config.zangetsu_settings_sha": "sha_b"})
    # Operator wrongly passes trace-only authorization for the settings file —
    # the tool MUST refuse to honor it (defense-in-depth).
    result = _ds.diff(
        pre, post, set(), {"config.zangetsu_settings_sha"}
    )
    assert result["overall"] == "FORBIDDEN"
    assert any(
        entry[3] == "FORBIDDEN_THRESHOLD" for entry in result["forbidden"]
    )


def test_threshold_change_without_authorization_is_forbidden_threshold():
    pre = _snap({"config.zangetsu_settings_sha": "sha_a"})
    post = _snap({"config.zangetsu_settings_sha": "sha_b"})
    result = _ds.diff(pre, post, set(), set())
    assert result["overall"] == "FORBIDDEN"
    assert result["forbidden"][0][3] == "FORBIDDEN_THRESHOLD"


# ---------------------------------------------------------------------------
# §10.4-§10.6 Arena pass/fail / champion promotion / execution / capital / risk
# ---------------------------------------------------------------------------
# These all live inside arena_pipeline / arena23_orchestrator / arena45_orchestrator
# runtime files. Without trace-only authorization, any SHA change classifies as
# FORBIDDEN_UNAUTHORIZED_RUNTIME_SHA. Verified via the unauthorized tests above.


def test_arena_pass_fail_runtime_change_remains_forbidden_without_authorization():
    # arena_gates.py is NOT in CODE_FROZEN; in current spec only the snapshot
    # captures arena23_orchestrator SHA. Test via arena23_orchestrator since that
    # hosts A2/A3 pass/fail logic.
    pre = _snap({"config.arena23_orchestrator_sha": "sha_a"})
    post = _snap({"config.arena23_orchestrator_sha": "sha_b"})
    result = _ds.diff(pre, post, set(), set())
    assert result["overall"] == "FORBIDDEN"


def test_champion_promotion_path_change_forbidden_without_authorization():
    # champion promotion is a logical concept — verify via the arena runtime
    # SHA tripwire that catches any change to promotion-relevant file.
    pre = _snap({"config.arena45_orchestrator_sha": "sha_a"})
    post = _snap({"config.arena45_orchestrator_sha": "sha_b"})
    result = _ds.diff(pre, post, set(), set())
    assert result["overall"] == "FORBIDDEN"


def test_calcifer_supervisor_sha_change_forbidden_without_authorization():
    # supervisor.py executes capital/risk/runtime decisions at the orchestrator
    # level; sha change without authorization = forbidden.
    pre = _snap({"config.calcifer_supervisor_sha": "sha_a"})
    post = _snap({"config.calcifer_supervisor_sha": "sha_b"})
    result = _ds.diff(pre, post, set(), set())
    assert result["overall"] == "FORBIDDEN"


# ---------------------------------------------------------------------------
# Hard forbidden: arena respawn / engine log growth
# ---------------------------------------------------------------------------


def test_arena_process_count_change_remains_hard_forbidden():
    pre = _snap({"runtime.arena_processes.count": 0})
    post = _snap({"runtime.arena_processes.count": 4})
    result = _ds.diff(pre, post, set(), {"runtime.arena_processes.count"})
    # Even if an operator passes trace-only auth for this, hard-forbidden wins.
    assert result["overall"] == "FORBIDDEN"


def test_engine_jsonl_growth_remains_hard_forbidden():
    pre = _snap({"runtime.engine_jsonl_size_bytes": 1000})
    post = _snap({"runtime.engine_jsonl_size_bytes": 2000})
    result = _ds.diff(pre, post, set(), set())
    assert result["overall"] == "FORBIDDEN"


# ---------------------------------------------------------------------------
# §10.7 Regressions — zero / explained / forbidden still behave correctly
# ---------------------------------------------------------------------------


def test_zero_diff_fields_remain_zero():
    pre = _snap({"config.arena_pipeline_sha": "same_sha"})
    post = _snap({"config.arena_pipeline_sha": "same_sha"})
    result = _ds.diff(pre, post, set(), set())
    assert result["overall"] == "ZERO_DIFF"
    assert len(result["zero"]) == 1


def test_existing_explained_fields_remain_explained():
    # runtime.calcifer_deploy_block_ts_iso is in ALWAYS_ALLOWED — should
    # classify as EXPLAINED even without authorization flags.
    pre = _snap({"runtime.calcifer_deploy_block_ts_iso": "2026-04-24T09:00:00Z"})
    post = _snap({"runtime.calcifer_deploy_block_ts_iso": "2026-04-24T09:05:00Z"})
    result = _ds.diff(pre, post, set(), set())
    assert result["overall"] == "EXPLAINED"
    assert len(result["explained"]) == 1


def test_existing_forbidden_runtime_changes_remain_forbidden():
    """A bare arena_pipeline_sha change without explanation remains FORBIDDEN
    (backward-compat with the MOD-6 guard)."""
    pre = _snap({"config.arena_pipeline_sha": "sha_a"})
    post = _snap({"config.arena_pipeline_sha": "sha_b"})
    result = _ds.diff(pre, post, set(), set())
    assert result["overall"] == "FORBIDDEN"


def test_explicit_explain_flag_still_works_for_code_frozen():
    # --explain route predates 0-9M; must still work.
    pre = _snap({"config.arena_pipeline_sha": "sha_a"})
    post = _snap({"config.arena_pipeline_sha": "sha_b"})
    result = _ds.diff(pre, post, {"config.arena_pipeline_sha"}, set())
    assert result["overall"] == "EXPLAINED"


# ---------------------------------------------------------------------------
# Mixed scenarios
# ---------------------------------------------------------------------------


def test_mix_of_trace_only_and_explained_yields_trace_only_overall():
    pre = _snap({
        "config.arena_pipeline_sha": "sha_a",
        "runtime.calcifer_deploy_block_ts_iso": "2026-04-24T09:00:00Z",
    })
    post = _snap({
        "config.arena_pipeline_sha": "sha_b",
        "runtime.calcifer_deploy_block_ts_iso": "2026-04-24T09:05:00Z",
    })
    result = _ds.diff(
        pre, post, set(), {"config.arena_pipeline_sha"}
    )
    assert result["overall"] == "EXPLAINED_TRACE_ONLY"
    assert len(result["explained_trace_only"]) == 1
    assert len(result["explained"]) == 1


def test_mix_of_trace_only_and_forbidden_is_forbidden():
    pre = _snap({
        "config.arena_pipeline_sha": "sha_a",
        "config.zangetsu_settings_sha": "sha_before",
    })
    post = _snap({
        "config.arena_pipeline_sha": "sha_b",
        "config.zangetsu_settings_sha": "sha_after",
    })
    # trace-only authorization for arena_pipeline only; settings still changes.
    result = _ds.diff(
        pre, post, set(), {"config.arena_pipeline_sha"}
    )
    assert result["overall"] == "FORBIDDEN"  # settings change wins
    assert any(e[3] == "FORBIDDEN_THRESHOLD" for e in result["forbidden"])
    assert any(e[3] == "EXPLAINED_TRACE_ONLY" for e in result["explained_trace_only"])


def test_trace_only_authorization_does_not_extend_to_hard_forbidden():
    pre = _snap({"runtime.arena_processes.count": 0})
    post = _snap({"runtime.arena_processes.count": 3})
    result = _ds.diff(
        pre, post, set(),
        {"runtime.arena_processes.count"},  # attempt to authorize (must fail)
    )
    assert result["overall"] == "FORBIDDEN"


# ---------------------------------------------------------------------------
# Unauthorized but no CODE_FROZEN-matching path
# ---------------------------------------------------------------------------


def test_unknown_path_default_forbidden():
    pre = _snap({"unknown.surface.foo": "a"})
    post = _snap({"unknown.surface.foo": "b"})
    result = _ds.diff(pre, post, set(), set())
    assert result["overall"] == "FORBIDDEN"


# ---------------------------------------------------------------------------
# §7 — the encoded 0-9L-PLUS historical case must classify as EXPLAINED_TRACE_ONLY
# ---------------------------------------------------------------------------


def test_0_9l_plus_historical_case_classifies_as_explained_trace_only():
    """Encode the 0-9L-PLUS motivating scenario:
    arena_pipeline.py SHA changed due to authorized A1 trace-native emission.
    With --authorize-trace-only config.arena_pipeline_sha, the classification
    must be EXPLAINED_TRACE_ONLY, NOT FORBIDDEN."""
    pre = _snap({
        "config.arena_pipeline_sha": "34a3791f1686cc5f7c50c5f2f7e6db7eb1afca7340166dec63a32c5b05273d83",
        "config.zangetsu_settings_sha": "stable_sha_value",
        "config.arena23_orchestrator_sha": "stable_sha_value",
        "config.arena45_orchestrator_sha": "stable_sha_value",
        "governance.branch_protection_main": {"enforce_admins": True, "req_sig": True},
    }, manifest="pre_0_9l")
    post = _snap({
        "config.arena_pipeline_sha": "888e2fdd4b4af5f6f6523256462d02ba012dafa64c968663fd6d8225bc749142",
        "config.zangetsu_settings_sha": "stable_sha_value",
        "config.arena23_orchestrator_sha": "stable_sha_value",
        "config.arena45_orchestrator_sha": "stable_sha_value",
        "governance.branch_protection_main": {"enforce_admins": True, "req_sig": True},
    }, manifest="post_0_9l")
    result = _ds.diff(
        pre, post, set(), {"config.arena_pipeline_sha"}
    )
    assert result["overall"] == "EXPLAINED_TRACE_ONLY"
    assert not any(
        e[3].startswith("FORBIDDEN") for e in result["forbidden"]
    ), f"forbidden bucket should be empty but is: {result['forbidden']}"
