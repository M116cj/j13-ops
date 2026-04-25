"""Tests for TEAM ORDER 0-9S-OBSERVE-FAST — sparse CANARY observation
runner.

Minimal coverage per fast-governance order: launch path, output
structure, empty-input behavior, runtime safety.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from zangetsu.tools.run_sparse_canary_observation import (
    MIN_ROUNDS_FOR_COMPLETE,
    RUNNER_VERSION,
    STATUS_FAILED_OBSERVATION,
    STATUS_OBSERVATION_COMPLETE_GREEN,
    STATUS_OBSERVING_NOT_COMPLETE,
    aggregate_arena_batch_metrics,
    derive_baseline,
    run_observation,
)
from zangetsu.services.sparse_canary_observer import (
    STATUS_FAIL,
    STATUS_INSUFFICIENT_HISTORY,
    STATUS_PASS,
    VERDICT_GREEN,
    VERDICT_RED,
)


# ---------------------------------------------------------------------------
# 1. Constants + version
# ---------------------------------------------------------------------------


def test_runner_version_pinned():
    assert RUNNER_VERSION == "0-9S-OBSERVE-FAST"


def test_min_rounds_for_complete_pinned():
    assert MIN_ROUNDS_FOR_COMPLETE == 20


# ---------------------------------------------------------------------------
# 2. Aggregation
# ---------------------------------------------------------------------------


def test_aggregate_empty_returns_zeros():
    out = aggregate_arena_batch_metrics([])
    assert out["a1_pass_rate"] == 0.0
    assert out["a2_pass_rate"] == 0.0
    assert out["a3_pass_rate"] == 0.0
    assert out["rounds_observed"] == 0
    assert out["profiles_observed"] == 0


def test_aggregate_handles_a1_a2_a3():
    events = [
        {"arena_stage": "A1", "entered_count": 100, "passed_count": 30,
         "rejected_count": 70, "generation_profile_id": "gp_a"},
        {"arena_stage": "A2", "entered_count": 30, "passed_count": 6,
         "rejected_count": 24, "reject_reason_distribution": {"SIGNAL_TOO_SPARSE": 24},
         "generation_profile_id": "gp_a"},
        {"arena_stage": "A3", "entered_count": 6, "passed_count": 2,
         "rejected_count": 4, "reject_reason_distribution": {"OOS_FAIL": 4},
         "generation_profile_id": "gp_a", "deployable_count": 1},
    ]
    out = aggregate_arena_batch_metrics(events)
    assert abs(out["a1_pass_rate"] - 0.30) < 1e-9
    assert abs(out["a2_pass_rate"] - 0.20) < 1e-9
    assert abs(out["a3_pass_rate"] - (2.0 / 6.0)) < 1e-9
    assert out["passed_a3"] == 2
    assert out["deployable_count"] == 1
    assert out["profiles_observed"] == 1


def test_aggregate_skips_malformed_events():
    events = [None, "garbage", 42, {"arena_stage": "A1", "entered_count": 10, "passed_count": 5}]
    out = aggregate_arena_batch_metrics(events)
    assert out["rounds_observed"] == 4  # length of input list
    assert abs(out["a1_pass_rate"] - 0.5) < 1e-9


def test_derive_baseline_sample_size_zero_for_fresh_run():
    aggregate = {"a2_pass_rate": 0.2, "a3_pass_rate": 0.1}
    baseline = derive_baseline(aggregate, sample_size_rounds=0)
    assert baseline.sample_size_rounds == 0
    assert baseline.composite_score_stddev is None


# ---------------------------------------------------------------------------
# 3. run_observation — empty input
# ---------------------------------------------------------------------------


def test_run_observation_empty_input_marks_observing_not_complete(tmp_path):
    out = run_observation(
        batch_events_path=None,
        plans_path=None,
        output_dir=tmp_path,
        run_id="canary-test",
        attribution_verdict=VERDICT_GREEN,
    )
    assert out["status"] == STATUS_OBSERVING_NOT_COMPLETE


def test_run_observation_empty_input_writes_aggregate(tmp_path):
    run_observation(
        batch_events_path=None,
        plans_path=None,
        output_dir=tmp_path,
        run_id="canary-test",
    )
    agg_path = tmp_path / "sparse_canary_aggregate.json"
    assert agg_path.exists()
    payload = json.loads(agg_path.read_text(encoding="utf-8"))
    assert payload["runner_version"] == "0-9S-OBSERVE-FAST"
    assert payload["rounds_observed"] == 0
    assert payload["status"] == STATUS_OBSERVING_NOT_COMPLETE


def test_run_observation_writes_jsonl_record(tmp_path):
    run_observation(
        batch_events_path=None,
        plans_path=None,
        output_dir=tmp_path,
        run_id="canary-test",
    )
    obs_path = tmp_path / "sparse_canary_observations.jsonl"
    assert obs_path.exists()
    line = obs_path.read_text(encoding="utf-8").strip().splitlines()[0]
    payload = json.loads(line)
    assert payload["mode"] == "DRY_RUN_CANARY"
    assert payload["applied"] is False
    assert payload["canary_version"] == "0-9S-CANARY"


def test_run_observation_observation_window_complete_false_at_zero_rounds(tmp_path):
    out = run_observation(
        batch_events_path=None,
        plans_path=None,
        output_dir=tmp_path,
        run_id="canary-test",
    )
    obs = out["observation"]
    assert obs.observation_window_complete is False


# ---------------------------------------------------------------------------
# 4. run_observation — RED attribution verdict
# ---------------------------------------------------------------------------


def test_run_observation_red_attribution_triggers_failed_observation(tmp_path):
    # F7 (attribution_verdict regresses to RED) should fire when there
    # is real telemetry to observe. Empty-input runs short-circuit to
    # OBSERVING_NOT_COMPLETE — supply non-empty events to exercise the
    # F-criteria path.
    events_file = tmp_path / "events.jsonl"
    events_file.write_text(
        json.dumps({
            "arena_stage": "A1",
            "entered_count": 10,
            "passed_count": 3,
            "rejected_count": 7,
            "generation_profile_id": "gp_a",
        }),
        encoding="utf-8",
    )
    out = run_observation(
        batch_events_path=events_file,
        plans_path=None,
        output_dir=tmp_path / "out",
        run_id="canary-test",
        attribution_verdict=VERDICT_RED,
    )
    # F7 fires → rollback_required → FAILED_OBSERVATION
    assert out["status"] == STATUS_FAILED_OBSERVATION
    assert out["aggregate"]["rollback_required"] is True


# ---------------------------------------------------------------------------
# 5. run_observation — file input path
# ---------------------------------------------------------------------------


def test_run_observation_reads_jsonl_input(tmp_path):
    events_file = tmp_path / "events.jsonl"
    events_file.write_text(
        "\n".join([
            json.dumps({"arena_stage": "A1", "entered_count": 10, "passed_count": 3,
                        "rejected_count": 7, "generation_profile_id": "gp_a"}),
            json.dumps({"arena_stage": "A2", "entered_count": 3, "passed_count": 1,
                        "rejected_count": 2, "generation_profile_id": "gp_a"}),
        ]),
        encoding="utf-8",
    )
    out = run_observation(
        batch_events_path=events_file,
        plans_path=None,
        output_dir=tmp_path / "out",
        run_id="canary-test",
        attribution_verdict=VERDICT_GREEN,
    )
    assert out["aggregate"]["rounds_observed"] == 2
    assert out["aggregate"]["profiles_observed"] == 1


def test_run_observation_handles_nonexistent_input(tmp_path):
    out = run_observation(
        batch_events_path=tmp_path / "does-not-exist.jsonl",
        plans_path=None,
        output_dir=tmp_path / "out",
        run_id="canary-test",
    )
    # Should not crash; treats missing file as empty.
    assert out["status"] == STATUS_OBSERVING_NOT_COMPLETE


# ---------------------------------------------------------------------------
# 6. Runtime safety
# ---------------------------------------------------------------------------


def test_runner_module_has_no_apply_method():
    import zangetsu.tools.run_sparse_canary_observation as mod
    publics = [n for n in dir(mod) if not n.startswith("_")]
    for name in publics:
        assert not name.lower().startswith("apply"), name


def test_runner_does_not_import_arena_runtime():
    import zangetsu.tools.run_sparse_canary_observation as mod
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    forbidden_imports = (
        "from zangetsu.services.arena_pipeline",
        "import zangetsu.services.arena_pipeline",
        "from zangetsu.services.arena23_orchestrator",
        "from zangetsu.services.arena45_orchestrator",
        "from zangetsu.engine",
        "from zangetsu.live",
    )
    for fragment in forbidden_imports:
        assert fragment not in src, f"runner imports forbidden: {fragment}"


def test_runner_status_observing_not_complete_when_records_empty(tmp_path):
    # Same path as test_run_observation_empty_input_marks_observing_not_complete
    # but explicit assertion that status is exactly OBSERVING_NOT_COMPLETE.
    out = run_observation(
        batch_events_path=None,
        plans_path=None,
        output_dir=tmp_path,
        run_id="canary-test",
        attribution_verdict=VERDICT_GREEN,
    )
    assert out["status"] == STATUS_OBSERVING_NOT_COMPLETE


def test_runner_observation_record_immutable_invariants(tmp_path):
    out = run_observation(
        batch_events_path=None,
        plans_path=None,
        output_dir=tmp_path,
        run_id="canary-test",
    )
    obs = out["observation"]
    # Three-layer dry-run invariant from observer.
    obs.mode = "APPLIED"  # try to mutate
    obs.applied = True
    obs.canary_version = "HACKED"
    e = obs.to_event()
    assert e["mode"] == "DRY_RUN_CANARY"
    assert e["applied"] is False
    assert e["canary_version"] == "0-9S-CANARY"


def test_runner_does_not_mutate_input_events(tmp_path):
    events = [
        {"arena_stage": "A1", "entered_count": 10, "passed_count": 3,
         "rejected_count": 7, "generation_profile_id": "gp_a"},
    ]
    snapshot = json.dumps(events, sort_keys=True)
    aggregate_arena_batch_metrics(events)
    assert json.dumps(events, sort_keys=True) == snapshot


def test_aggregate_returns_required_fields():
    out = aggregate_arena_batch_metrics([
        {"arena_stage": "A1", "entered_count": 10, "passed_count": 3,
         "rejected_count": 7, "generation_profile_id": "gp_a"}
    ])
    for key in (
        "a1_pass_rate", "a2_pass_rate", "a3_pass_rate",
        "signal_too_sparse_rate", "oos_fail_rate", "unknown_reject_rate",
        "deployable_count", "passed_a3",
        "rounds_observed", "profiles_observed",
    ):
        assert key in out
