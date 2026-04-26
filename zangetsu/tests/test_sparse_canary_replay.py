"""Tests for TEAM ORDER 0-9S-CANARY-OBSERVE-COMPLETE — replay /
backfill helper.

Minimal coverage: classification, reconstruction by source type, scan
manifest, runtime safety.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from zangetsu.tools.replay_sparse_canary_observation import (
    REPLAY_VERSION,
    ReplayManifest,
    ReplaySource,
    _classify_record,
    _reconstruct_lifecycle_records,
    _reconstruct_orchestrator_log,
    _reconstruct_per_candidate_batch,
    reconstruct_records,
    run_replay,
    scan_source,
)


# ---------------------------------------------------------------------------
# 1. Constants
# ---------------------------------------------------------------------------


def test_replay_version_pinned():
    assert REPLAY_VERSION == "0-9S-CANARY-OBSERVE-COMPLETE"


# ---------------------------------------------------------------------------
# 2. Classification
# ---------------------------------------------------------------------------


def test_classify_arena_batch_metrics():
    rec = {"event_type": "arena_batch_metrics", "arena_stage": "A2"}
    assert _classify_record(rec) == "arena_batch_metrics"


def test_classify_per_candidate_event():
    rec = {"arena_stage": "A3", "raw_reason_stem": "OOS_FAIL", "candidate_id": "1"}
    assert _classify_record(rec) == "per_candidate_event"


def test_classify_lifecycle_record():
    rec = {"final_stage": "A3", "final_status": "DEPLOYABLE"}
    assert _classify_record(rec) == "lifecycle_record"


def test_classify_orchestrator_log():
    rec = {"ts": "2026-04-25T00:00:00", "level": "INFO", "msg": "A2 stats: processed=10 promoted=2 rejected=8"}
    assert _classify_record(rec) == "orchestrator_log"


def test_classify_unsupported_format():
    assert _classify_record({"random": "thing"}) == "unsupported_format"
    assert _classify_record(None) == "unsupported_format"
    assert _classify_record(42) == "unsupported_format"


# ---------------------------------------------------------------------------
# 3. Reconstruction
# ---------------------------------------------------------------------------


def test_reconstruct_orchestrator_log_a2_stats():
    rec = {"msg": "A2 stats: processed=20 promoted=5 rejected=15 (1.2s)"}
    out = _reconstruct_orchestrator_log(rec)
    assert out is not None
    assert out["arena_stage"] == "A2"
    assert out["entered_count"] == 20
    assert out["passed_count"] == 5
    assert out["rejected_count"] == 15


def test_reconstruct_orchestrator_log_a3_stats():
    rec = {"msg": "A3 stats: processed=10 completed=4 (0.5s)"}
    out = _reconstruct_orchestrator_log(rec)
    assert out is not None
    assert out["arena_stage"] == "A3"
    assert out["entered_count"] == 10
    assert out["passed_count"] == 4


def test_reconstruct_orchestrator_log_unrecognised():
    rec = {"msg": "Something else"}
    assert _reconstruct_orchestrator_log(rec) is None


def test_reconstruct_per_candidate_batch():
    records = [
        {"arena_stage": "A2", "raw_reason_stem": "trades < 25"},
        {"arena_stage": "A2", "raw_reason_stem": "trades < 25"},
        {"arena_stage": "A3", "raw_reason_stem": "validation split fail"},
    ]
    out = _reconstruct_per_candidate_batch(records)
    a2 = next(b for b in out if b["arena_stage"] == "A2")
    a3 = next(b for b in out if b["arena_stage"] == "A3")
    assert a2["entered_count"] == 2
    assert a2["rejected_count"] == 2
    assert a2["reject_reason_distribution"]["SIGNAL_TOO_SPARSE"] == 2
    assert a3["entered_count"] == 1
    assert a3["reject_reason_distribution"]["OOS_FAIL"] == 1


def test_reconstruct_lifecycle_records():
    records = [
        {"final_stage": "A3", "final_status": "DEPLOYABLE"},
        {"final_stage": "A3", "final_status": "DEPLOYABLE"},
        {"final_stage": "A3", "final_status": "REJECT"},
    ]
    out = _reconstruct_lifecycle_records(records)
    assert len(out) == 1
    assert out[0]["arena_stage"] == "A3"
    assert out[0]["entered_count"] == 3
    assert out[0]["passed_count"] == 2
    assert out[0]["deployable_count"] == 2


def test_reconstruct_lifecycle_records_empty():
    assert _reconstruct_lifecycle_records([]) == []


def test_reconstruct_per_candidate_batch_empty():
    assert _reconstruct_per_candidate_batch([]) == []


# ---------------------------------------------------------------------------
# 4. Scan source
# ---------------------------------------------------------------------------


def test_scan_source_nonexistent_file(tmp_path):
    src = scan_source(tmp_path / "nope.jsonl")
    assert src.line_count == 0
    assert "not exist" in src.reason_if_excluded


def test_scan_source_empty_file(tmp_path):
    p = tmp_path / "empty.jsonl"
    p.write_text("", encoding="utf-8")
    src = scan_source(p)
    assert src.line_count == 0


def test_scan_source_classifies_per_candidate(tmp_path):
    p = tmp_path / "sample.jsonl"
    p.write_text(
        "\n".join([
            json.dumps({"arena_stage": "A2", "raw_reason_stem": "trades", "candidate_id": "1"}),
            json.dumps({"arena_stage": "A3", "raw_reason_stem": "OOS", "candidate_id": "2"}),
        ]),
        encoding="utf-8",
    )
    src = scan_source(p)
    assert src.source_type == "per_candidate_event"
    assert src.contains_a2_metrics is True
    assert src.contains_a3_metrics is True
    assert src.usable_for_observation is True
    assert src.usable_for_baseline is False  # < 20 records


def test_scan_source_classifies_arena_batch_metrics(tmp_path):
    p = tmp_path / "batch.jsonl"
    p.write_text(
        json.dumps({
            "event_type": "arena_batch_metrics",
            "arena_stage": "A2",
            "entered_count": 10,
            "passed_count": 3,
            "rejected_count": 7,
            "reject_reason_distribution": {"SIGNAL_TOO_SPARSE": 7},
            "generation_profile_id": "gp_a",
        }),
        encoding="utf-8",
    )
    src = scan_source(p)
    assert src.source_type == "arena_batch_metrics"
    assert src.contains_profile_id is True


# ---------------------------------------------------------------------------
# 5. reconstruct_records dispatch
# ---------------------------------------------------------------------------


def test_reconstruct_records_arena_batch_metrics_passthrough(tmp_path):
    p = tmp_path / "batch.jsonl"
    p.write_text(
        json.dumps({"event_type": "arena_batch_metrics", "arena_stage": "A2",
                    "entered_count": 10, "passed_count": 3, "rejected_count": 7}),
        encoding="utf-8",
    )
    out = reconstruct_records(p, "arena_batch_metrics")
    assert len(out) == 1
    assert out[0]["arena_stage"] == "A2"


def test_reconstruct_records_unsupported_returns_empty(tmp_path):
    p = tmp_path / "unknown.jsonl"
    p.write_text(json.dumps({"random": "data"}), encoding="utf-8")
    assert reconstruct_records(p, "unsupported_format") == []


def test_reconstruct_records_nonexistent_returns_empty(tmp_path):
    assert reconstruct_records(tmp_path / "nope.jsonl", "arena_batch_metrics") == []


# ---------------------------------------------------------------------------
# 6. run_replay end-to-end
# ---------------------------------------------------------------------------


def test_run_replay_writes_manifest(tmp_path):
    p = tmp_path / "events.jsonl"
    p.write_text(
        "\n".join([
            json.dumps({"arena_stage": "A2", "raw_reason_stem": "trades", "candidate_id": "1"}),
            json.dumps({"arena_stage": "A3", "raw_reason_stem": "OOS", "candidate_id": "2"}),
        ]),
        encoding="utf-8",
    )
    out = run_replay(
        sources=[p],
        output_dir=tmp_path / "out",
        run_id="test-replay",
        attribution_verdict="GREEN",
    )
    manifest_path = tmp_path / "out" / "replay_source_manifest.json"
    assert manifest_path.exists()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["replay_version"] == "0-9S-CANARY-OBSERVE-COMPLETE"
    assert len(payload["sources"]) == 1


def test_run_replay_handles_empty_source_list(tmp_path):
    out = run_replay(
        sources=[],
        output_dir=tmp_path / "out",
        run_id="test",
    )
    assert out["rounds_observed"] == 0


def test_run_replay_reconstructs_per_candidate_to_batches(tmp_path):
    p = tmp_path / "events.jsonl"
    p.write_text(
        "\n".join([
            json.dumps({"arena_stage": "A2", "raw_reason_stem": "trades", "candidate_id": str(i)})
            for i in range(5)
        ]),
        encoding="utf-8",
    )
    out = run_replay(
        sources=[p],
        output_dir=tmp_path / "out",
        run_id="test",
    )
    # Should produce 1 synthetic A2 batch from 5 per-candidate events.
    assert out["manifest"]["total_synthetic_batches_built"] == 1


# ---------------------------------------------------------------------------
# 7. Runtime safety
# ---------------------------------------------------------------------------


def test_replay_module_has_no_apply_method():
    import zangetsu.tools.replay_sparse_canary_observation as mod
    publics = [n for n in dir(mod) if not n.startswith("_")]
    for name in publics:
        assert not name.lower().startswith("apply"), name


def test_replay_does_not_import_arena_runtime():
    import zangetsu.tools.replay_sparse_canary_observation as mod
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    forbidden = (
        "from zangetsu.services.arena_pipeline",
        "from zangetsu.services.arena23_orchestrator",
        "from zangetsu.services.arena45_orchestrator",
        "from zangetsu.engine",
        "from zangetsu.live",
    )
    for fragment in forbidden:
        assert fragment not in src
