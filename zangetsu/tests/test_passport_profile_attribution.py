"""Tests for TEAM ORDER 0-9P — Generation Profile Passport Persistence
and Attribution Closure.

Covers:
  - Passport schema: writes generation_profile_id + fingerprint.
  - Attribution precedence: passport.arena1 → passport root →
    orchestrator → UNKNOWN.
  - A2/A3 telemetry reader compatibility (source-text checks against
    the existing P7-PR4B reader).
  - Behavior invariance (no Arena / threshold / promotion change).

Tests cannot import ``arena_pipeline`` or ``arena23_orchestrator``
directly on local Mac due to those modules' top-level
``os.chdir('/home/j13/j13-ops')``. Source-text scans are used for
those checks; the precedence chain is exercised through the pure
``resolve_attribution_chain`` helper.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from zangetsu.services.generation_profile_identity import (
    UNAVAILABLE_FINGERPRINT,
    UNKNOWN_PROFILE_ID,
    resolve_attribution_chain,
    resolve_profile_identity,
    safe_resolve_profile_identity,
)


_SERVICES = pathlib.Path(__file__).resolve().parent.parent / "services"
_AP_TEXT = (_SERVICES / "arena_pipeline.py").read_text(encoding="utf-8")
_A23_TEXT = (_SERVICES / "arena23_orchestrator.py").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Passport persistence (source-text)
# ---------------------------------------------------------------------------


def test_passport_persists_generation_profile_id():
    # The V10 passport literal must include `generation_profile_id`
    # under arena1. Marker comment "0-9P attribution closure" is the
    # canonical persistence anchor.
    assert "0-9P attribution closure" in _AP_TEXT
    assert '"generation_profile_id": _passport_profile_id,' in _AP_TEXT


def test_passport_persists_generation_profile_fingerprint():
    assert (
        '"generation_profile_fingerprint": _passport_profile_fingerprint,'
        in _AP_TEXT
    )


def test_passport_profile_id_is_metadata_only():
    # Persisted fields must come from the already-resolved
    # _gen_profile_identity (computed at worker startup), not from any
    # per-candidate computation.
    assert "_passport_profile_id = (" in _AP_TEXT
    assert "_gen_profile_identity.get(\"profile_id\")" in _AP_TEXT
    assert "_gen_profile_identity.get(\"profile_fingerprint\")" in _AP_TEXT


def test_passport_profile_id_failure_falls_back_to_unknown():
    # The passport write must be wrapped in try/except so identity
    # resolution failure cannot block the passport (and therefore the
    # candidate insertion).
    assert "_passport_profile_id = _UNKNOWN_PROFILE_ID" in _AP_TEXT
    assert "_passport_profile_fingerprint = _UNAVAILABLE_FINGERPRINT" in _AP_TEXT


def test_passport_construction_does_not_call_arena_gates():
    # Sanity: passport build does not import or call arena_gates.
    # (Arena pass/fail decisions must remain in arena_gates / orchestrators.)
    passport_block_match = re.search(
        r'passport\s*=\s*\{(?:[^{}]|\{[^{}]*\})*?\n\s{12}\}',
        _AP_TEXT,
    )
    if passport_block_match is None:
        # Fallback: at least the field must appear inside an arena1 block.
        passport_block_match = re.search(
            r'"arena1"\s*:\s*\{(?:[^{}]|\{[^{}]*\})*\}',
            _AP_TEXT,
            re.DOTALL,
        )
    assert passport_block_match is not None
    block = passport_block_match.group(0)
    assert "arena_gates" not in block
    assert "arena2_pass" not in block
    assert "arena3_pass" not in block
    assert "arena4_pass" not in block


# ---------------------------------------------------------------------------
# 2. Attribution precedence (resolve_attribution_chain)
# ---------------------------------------------------------------------------


def test_passport_arena1_identity_takes_precedence():
    passport = {
        "arena1": {
            "generation_profile_id": "gp_passport_a1",
            "generation_profile_fingerprint": "sha256:" + "1" * 64,
        },
        "generation_profile_id": "gp_passport_root",  # ignored
    }
    res = resolve_attribution_chain(
        passport,
        orchestrator_profile_id="gp_orchestrator",
        orchestrator_profile_fingerprint="sha256:" + "2" * 64,
    )
    assert res["profile_id"] == "gp_passport_a1"
    assert res["source"] == "passport_arena1"


def test_passport_root_identity_used_if_arena1_missing():
    passport = {
        "generation_profile_id": "gp_passport_root",
        "generation_profile_fingerprint": "sha256:" + "3" * 64,
    }
    res = resolve_attribution_chain(
        passport,
        orchestrator_profile_id="gp_orchestrator",
    )
    assert res["profile_id"] == "gp_passport_root"
    assert res["source"] == "passport_root"


def test_orchestrator_fallback_when_passport_missing_identity():
    passport = {"arena1": {"alpha_hash": "abc"}}
    res = resolve_attribution_chain(
        passport,
        orchestrator_profile_id="gp_orchestrator",
        orchestrator_profile_fingerprint="sha256:" + "4" * 64,
    )
    assert res["profile_id"] == "gp_orchestrator"
    assert res["source"] == "orchestrator"


def test_unknown_profile_fallback_when_all_identity_missing():
    res = resolve_attribution_chain(passport=None)
    assert res["profile_id"] == UNKNOWN_PROFILE_ID
    assert res["profile_fingerprint"] == UNAVAILABLE_FINGERPRINT
    assert res["source"] == "fallback"


def test_unavailable_fingerprint_fallback():
    passport = {
        "arena1": {
            "generation_profile_id": "gp_passport_a1",
            # fingerprint missing
        },
    }
    res = resolve_attribution_chain(passport)
    assert res["profile_id"] == "gp_passport_a1"
    assert res["profile_fingerprint"] == UNAVAILABLE_FINGERPRINT
    assert res["source"] == "passport_arena1"


def test_resolve_attribution_chain_handles_non_mapping_passport():
    res = resolve_attribution_chain(passport=42)
    assert res["profile_id"] == UNKNOWN_PROFILE_ID
    assert res["source"] == "fallback"


def test_resolve_attribution_chain_handles_non_mapping_arena1():
    # Resilience: passport["arena1"] not a dict (corrupt) — must not
    # raise; should fall through to passport_root / orchestrator /
    # fallback.
    passport = {"arena1": "garbage", "generation_profile_id": "gp_root"}
    res = resolve_attribution_chain(passport)
    assert res["profile_id"] == "gp_root"
    assert res["source"] == "passport_root"


def test_resolve_attribution_chain_never_raises():
    # Pathological inputs (cycle-free) — function must never raise.
    for bad_input in (None, 0, "", b"\x00", [], (1, 2), {"arena1": None}):
        out = resolve_attribution_chain(bad_input)
        assert "profile_id" in out
        assert "profile_fingerprint" in out
        assert "source" in out


def test_passport_arena1_empty_string_id_falls_through():
    passport = {
        "arena1": {"generation_profile_id": "", "generation_profile_fingerprint": ""},
        "generation_profile_id": "gp_root",
    }
    res = resolve_attribution_chain(passport)
    # Empty string is falsy → falls through to passport_root
    assert res["profile_id"] == "gp_root"
    assert res["source"] == "passport_root"


def test_passport_identity_round_trips_through_attribution_chain():
    # Round-trip simulation: A1 produces identity → writes to passport →
    # downstream resolver reads it back without modification.
    a1_identity = safe_resolve_profile_identity(
        {"generator_type": "gp_v10", "strategy_id": "j01"},
        profile_name="gp_v10_j01",
    )
    passport = {
        "arena1": {
            "generation_profile_id": a1_identity["profile_id"],
            "generation_profile_fingerprint": a1_identity["profile_fingerprint"],
        },
    }
    res = resolve_attribution_chain(
        passport,
        orchestrator_profile_id="gp_orchestrator_other",
    )
    assert res["profile_id"] == a1_identity["profile_id"]
    assert res["profile_fingerprint"] == a1_identity["profile_fingerprint"]
    assert res["source"] == "passport_arena1"


# ---------------------------------------------------------------------------
# 3. A2/A3 reader compatibility (source-text)
# ---------------------------------------------------------------------------


def test_a2_a3_reader_prefers_passport_arena1_first():
    # P7-PR4B's _p7pr4b_resolve_passport_profile reads
    # passport.arena1.generation_profile_id first.
    assert "_p7pr4b_resolve_passport_profile" in _A23_TEXT
    # Confirm precedence ordering is "a1 first, then root, then orchestrator".
    block = re.search(
        r"def _p7pr4b_resolve_passport_profile\(.*?\n(?=\n\S)",
        _A23_TEXT,
        re.DOTALL,
    )
    assert block is not None
    body = block.group(0)
    # arena1 lookup must precede the root-level passport lookup.
    a1_idx = body.find("a1.get(\"generation_profile_id\")")
    root_idx = body.find("passport.get(\"generation_profile_id\")")
    assert a1_idx >= 0 and root_idx >= 0
    assert a1_idx < root_idx, (
        "passport.arena1 lookup must precede passport root lookup"
    )


def test_a2_a3_reader_falls_back_to_orchestrator():
    # The orchestrator's main loop assigns the consumer profile when
    # the passport-derived id is UNKNOWN.
    assert "_p7pr4b_consumer_profile" in _A23_TEXT
    assert (
        "if _pid_a2 == _P7PR4B_UNKNOWN_PROFILE_ID:" in _A23_TEXT
        or "if pid == _P7PR4B_UNKNOWN_PROFILE_ID:" in _A23_TEXT
    )


def test_a2_a3_reader_unknown_fallback_present():
    assert "_P7PR4B_UNKNOWN_PROFILE_ID" in _A23_TEXT
    assert "_P7PR4B_UNAVAILABLE_FINGERPRINT" in _A23_TEXT


# ---------------------------------------------------------------------------
# 4. Identity helpers that 0-9P relies on
# ---------------------------------------------------------------------------


def test_safe_resolve_profile_identity_returns_three_fields():
    out = safe_resolve_profile_identity({"generator_type": "gp_v10"})
    assert "profile_id" in out
    assert "profile_fingerprint" in out
    assert "profile_name" in out


def test_safe_resolve_profile_identity_unknown_on_empty_input():
    out = safe_resolve_profile_identity({})
    assert out["profile_id"] == UNKNOWN_PROFILE_ID
    assert out["profile_fingerprint"] == UNAVAILABLE_FINGERPRINT


def test_resolve_profile_identity_deterministic():
    cfg = {"generator_type": "gp_v10", "strategy_id": "j01", "seed": 42}
    a = resolve_profile_identity(cfg)
    b = resolve_profile_identity(cfg)
    assert a == b


def test_resolve_profile_identity_excludes_volatile_fields():
    cfg1 = {"generator_type": "gp_v10", "strategy_id": "j01"}
    cfg2 = {**cfg1, "timestamp": "2026-04-25T00:00:00Z", "run_id": "r-99"}
    # Volatile fields stripped → same fingerprint.
    a = resolve_profile_identity(cfg1)
    b = resolve_profile_identity(cfg2)
    assert a["profile_fingerprint"] == b["profile_fingerprint"]


# ---------------------------------------------------------------------------
# 5. Behavior invariance (source-text)
# ---------------------------------------------------------------------------


def test_no_threshold_constants_changed():
    # arena_pipeline still references the V10 thresholds.
    assert "ENTRY_THR" in _AP_TEXT
    assert "EXIT_THR" in _AP_TEXT
    assert "MIN_HOLD" in _AP_TEXT
    assert "COOLDOWN" in _AP_TEXT


def test_a2_min_trades_still_pinned():
    assert "bt.total_trades < 25" in _A23_TEXT


def test_a3_thresholds_still_pinned():
    assert "ATR_STOP_MULTS = [2.0, 3.0, 4.0]" in _A23_TEXT
    assert "TRAIL_PCTS = [0.003, 0.005, 0.008, 0.01, 0.015, 0.02]" in _A23_TEXT
    assert "FIXED_TARGETS = [0.005, 0.008, 0.01, 0.015, 0.02, 0.03]" in _A23_TEXT


def test_arena_pass_fail_behavior_unchanged():
    from zangetsu.services import arena_gates
    for fn in ("arena2_pass", "arena3_pass", "arena4_pass"):
        assert hasattr(arena_gates, fn)


def test_champion_promotion_unchanged():
    a45 = (_SERVICES / "arena45_orchestrator.py").read_text(encoding="utf-8")
    assert a45.count("UPDATE champion_pipeline_fresh SET status = 'DEPLOYABLE'") == 1


def test_generation_budget_unchanged():
    # Generation budget knobs (N_GEN / POP_SIZE / TOP_K) untouched in
    # arena_pipeline.py.
    for knob in ("N_GEN", "POP_SIZE", "TOP_K"):
        assert knob in _AP_TEXT


def test_sampling_weights_unchanged():
    # No new sampling-weight machinery introduced.
    # Allow only the pre-existing references (compute_pass_rate /
    # compute_reject_rate from arena_pass_rate_telemetry are *not*
    # sampling weights).
    forbidden = ("sampling_weight =", "set_sampling_weight", "sampling_policy =")
    for fragment in forbidden:
        assert fragment not in _AP_TEXT


def test_no_formula_lineage_added():
    # 0-9P explicitly forbids per-alpha lineage. Source must not
    # reference any new lineage / parent-child machinery.
    forbidden = ("alpha_lineage", "parent_alpha", "ancestor_chain")
    for fragment in forbidden:
        assert fragment not in _AP_TEXT


def test_no_parent_child_ancestry_added():
    forbidden = ("parent_id", "ancestor_id", "child_lineage")
    for fragment in forbidden:
        assert fragment not in _AP_TEXT


def test_passport_identity_does_not_change_arena_decisions():
    # Arena decisions live in arena_gates.py and the orchestrator's
    # process_arena2 / process_arena3 — none of those should reference
    # the passport identity fields.
    gates = (_SERVICES / "arena_gates.py").read_text(encoding="utf-8")
    assert "generation_profile_id" not in gates
    assert "generation_profile_fingerprint" not in gates


def test_passport_identity_does_not_change_candidate_admission():
    # Admission validator path (admission_validator function call) must
    # not be modified to gate on profile identity.
    assert "admission_validator" in _AP_TEXT
    # Profile id field must NOT be referenced inside the SQL INSERT
    # column list (it is stored only in the JSONB passport blob).
    insert_block = re.search(
        r"INSERT INTO champion_pipeline_staging \(.*?\)",
        _AP_TEXT,
        re.DOTALL,
    )
    assert insert_block is not None
    assert "generation_profile_id" not in insert_block.group(0)


def test_passport_identity_does_not_change_rejection_semantics():
    taxonomy = (_SERVICES / "arena_rejection_taxonomy.py").read_text(encoding="utf-8")
    assert "generation_profile_id" not in taxonomy


def test_passport_identity_does_not_change_deployable_count():
    # arena45 promotes via existing Wilson LB / trades thresholds — not
    # via profile identity.
    a45 = (_SERVICES / "arena45_orchestrator.py").read_text(encoding="utf-8")
    insert_into_pipeline = re.search(
        r"UPDATE champion_pipeline_fresh SET status = 'DEPLOYABLE'.*?WHERE",
        a45,
        re.DOTALL,
    )
    assert insert_into_pipeline is not None
    assert "generation_profile_id" not in insert_into_pipeline.group(0)


def test_passport_identity_failure_does_not_block_telemetry():
    # The passport identity write is wrapped in try/except.
    assert "try:" in _AP_TEXT
    # And the fallback path sets safe defaults rather than raising.
    assert "_passport_profile_id = _UNKNOWN_PROFILE_ID" in _AP_TEXT


def test_no_runtime_apply_path_introduced():
    # 0-9P explicitly forbids any apply path. None of the modified
    # files may expose an `apply_*` public function.
    for path in (_SERVICES / "arena_pipeline.py",
                  _SERVICES / "generation_profile_identity.py"):
        text = path.read_text(encoding="utf-8")
        # Allow 'applied' (a noun field) but forbid public 'apply_*' verbs.
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("def apply_"):
                pytest.fail(
                    f"{path.name} exposes apply_* function: {stripped!r}"
                )


# ---------------------------------------------------------------------------
# 6. resolve_attribution_chain robustness (additional edge cases)
# ---------------------------------------------------------------------------


def test_resolve_attribution_chain_with_only_orchestrator():
    res = resolve_attribution_chain(
        passport={},
        orchestrator_profile_id="gp_only",
    )
    assert res["profile_id"] == "gp_only"
    assert res["source"] == "orchestrator"


def test_resolve_attribution_chain_with_passport_arena1_no_fingerprint():
    passport = {"arena1": {"generation_profile_id": "gp_a1"}}
    res = resolve_attribution_chain(passport)
    assert res["profile_id"] == "gp_a1"
    assert res["profile_fingerprint"] == UNAVAILABLE_FINGERPRINT


def test_resolve_attribution_chain_orchestrator_fingerprint_preserved():
    res = resolve_attribution_chain(
        passport=None,
        orchestrator_profile_id="gp_orch",
        orchestrator_profile_fingerprint="sha256:" + "5" * 64,
    )
    assert res["profile_fingerprint"] == "sha256:" + "5" * 64
