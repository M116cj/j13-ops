"""Tests for zangetsu.services.candidate_lifecycle_reconstruction (P7-PR2 / 0-9K)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from zangetsu.services.candidate_lifecycle_reconstruction import (
    ReconstructionStats,
    reconstruct_from_logs_and_derive_deployable_count,
    reconstruct_lifecycles,
)
from zangetsu.services.candidate_trace import (
    PROVENANCE_FULL,
    PROVENANCE_PARTIAL,
    PROVENANCE_UNAVAILABLE,
    STATUS_PASS,
    STATUS_REJECT,
    STATUS_SKIPPED,
    STATUS_NOT_RUN,
)


def _write_jsonl(tmp: Path, events):
    with open(tmp, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")


def test_reconstruct_empty_log_returns_empty():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "engine.jsonl"
        _write_jsonl(p, [])
        lcs, stats = reconstruct_lifecycles([p])
    assert lcs == []
    assert stats.unique_candidates == 0
    assert stats.events_matched == 0


def test_reconstruct_deployable_lifecycle_a2_pass_a3_complete():
    events = [
        {"ts": "2026-04-16T04:34:21", "level": "INFO",
         "msg": "A2 PASS id=70381 SOLUSDT | improved: ['economic_viability'] | WR: 0.5"},
        {"ts": "2026-04-16T04:34:22", "level": "INFO",
         "msg": "A3 COMPLETE id=70381 SOLUSDT | pool=sharpe TP=trailing(0.02)"},
    ]
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "engine.jsonl"
        _write_jsonl(p, events)
        lcs, stats = reconstruct_lifecycles([p])
    assert len(lcs) == 1
    lc = lcs[0]
    assert lc.candidate_id == "70381"
    assert lc.source_pool == "SOLUSDT"
    # A1 is inferred as PASS, A2 and A3 explicit PASS
    assert lc.arena_1_status == STATUS_PASS
    assert lc.arena_2_status == STATUS_PASS
    assert lc.arena_3_status == STATUS_PASS
    assert lc.final_status == "DEPLOYABLE"
    assert lc.deployable_count_contribution == 1
    assert lc.is_deployable() is True
    assert stats.a2_pass == 1 and stats.a3_complete == 1


def test_reconstruct_a2_reject_lifecycle():
    events = [
        {"ts": "2026-04-16T10:00:00", "level": "INFO",
         "msg": "A2 REJECTED id=99999 BTCUSDT: <2 valid indicators after zero-MAD filter | details=..."},
    ]
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "engine.jsonl"
        _write_jsonl(p, events)
        lcs, stats = reconstruct_lifecycles([p])
    assert len(lcs) == 1
    lc = lcs[0]
    assert lc.candidate_id == "99999"
    assert lc.arena_2_status == STATUS_REJECT
    assert lc.reject_stage == "A2"
    assert lc.reject_reason == "SIGNAL_TOO_SPARSE"
    assert lc.reject_category == "SIGNAL_DENSITY"
    assert lc.reject_severity == "BLOCKING"
    assert lc.is_deployable() is False
    assert lc.deployable_count_contribution == 0
    assert stats.a2_reject == 1


def test_reconstruct_a3_reject_after_a2_pass():
    events = [
        {"ts": "2026-04-16T07:59:00", "level": "INFO",
         "msg": "A2 PASS id=70386 SOLUSDT | improved: [...]"},
        {"ts": "2026-04-16T07:59:21", "level": "INFO",
         "msg": "A3 REJECTED id=70386 SOLUSDT: train/val PnL divergence | train_pnl=0.0756"},
    ]
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "engine.jsonl"
        _write_jsonl(p, events)
        lcs, _ = reconstruct_lifecycles([p])
    lc = lcs[0]
    assert lc.arena_2_status == STATUS_PASS
    assert lc.arena_3_status == STATUS_REJECT
    assert lc.reject_stage == "A3"
    assert lc.reject_reason == "OOS_FAIL"
    assert lc.final_status == STATUS_REJECT
    assert lc.is_deployable() is False


def test_reconstruct_a3_prefilter_skip():
    events = [
        {"ts": "2026-04-16T08:00:00", "level": "INFO",
         "msg": "A2 PASS id=70400 BTCUSDT"},
        {"ts": "2026-04-16T08:00:30", "level": "INFO",
         "msg": "A3 PREFILTER SKIP id=70400 BTCUSDT: correlation duplicate"},
    ]
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "engine.jsonl"
        _write_jsonl(p, events)
        lcs, _ = reconstruct_lifecycles([p])
    lc = lcs[0]
    assert lc.arena_2_status == STATUS_PASS
    assert lc.arena_3_status == STATUS_SKIPPED
    assert lc.final_status == STATUS_SKIPPED
    assert lc.is_deployable() is False


def test_reconstruct_stalled_at_a2_when_a3_never_runs():
    """Candidate passed A2 but A3 never ran — final_status = STALLED_AT_A2."""
    events = [
        {"ts": "2026-04-20T00:00:00", "level": "INFO",
         "msg": "A2 PASS id=8888 XRPUSDT | improved: [...]"},
    ]
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "engine.jsonl"
        _write_jsonl(p, events)
        lcs, _ = reconstruct_lifecycles([p])
    lc = lcs[0]
    assert lc.arena_2_status == STATUS_PASS
    assert lc.arena_3_status == STATUS_NOT_RUN
    assert lc.final_status == "STALLED_AT_A2"
    assert lc.is_deployable() is False


def test_duplicate_candidate_id_events_deterministic_merge():
    """Same candidate_id appearing multiple times must yield ONE lifecycle
    that integrates all observed states."""
    events = [
        {"ts": "2026-04-16T04:34:21", "level": "INFO",
         "msg": "A2 PASS id=77777 SOLUSDT | improved: [...]"},
        {"ts": "2026-04-16T04:44:39", "level": "INFO",
         "msg": "A2 PASS id=77777 SOLUSDT | improved: [...]"},  # duplicate
        {"ts": "2026-04-16T04:45:00", "level": "INFO",
         "msg": "A3 COMPLETE id=77777 SOLUSDT | pool=sharpe"},
    ]
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "engine.jsonl"
        _write_jsonl(p, events)
        lcs, stats = reconstruct_lifecycles([p])
    assert len(lcs) == 1  # deduplicated on candidate_id
    lc = lcs[0]
    assert lc.final_status == "DEPLOYABLE"
    assert lc.deployable_count_contribution == 1
    assert stats.a2_pass == 2  # both raw events counted
    assert stats.a3_complete == 1


def test_reconstruction_stats_dict_serializable():
    s = ReconstructionStats(lines_scanned=100, events_matched=20, unique_candidates=5)
    d = s.to_dict()
    json.dumps(d)  # must be JSON-safe
    assert d["lines_scanned"] == 100
    assert d["unique_candidates"] == 5


def test_reconstruct_from_logs_and_derive_deployable_count_integration():
    """End-to-end: 3 candidates, 1 deployable, 1 rejected A2, 1 rejected A3."""
    events = [
        {"ts": "2026-04-16T00:00:00", "level": "INFO",
         "msg": "A2 PASS id=1 AAA"},
        {"ts": "2026-04-16T00:00:01", "level": "INFO",
         "msg": "A3 COMPLETE id=1 AAA | pool=sharpe"},  # deployable
        {"ts": "2026-04-16T00:00:02", "level": "INFO",
         "msg": "A2 REJECTED id=2 BBB: <2 valid indicators after zero-MAD filter"},
        {"ts": "2026-04-16T00:00:03", "level": "INFO",
         "msg": "A2 PASS id=3 CCC"},
        {"ts": "2026-04-16T00:00:04", "level": "INFO",
         "msg": "A3 REJECTED id=3 CCC: validation split fail"},
    ]
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "engine.jsonl"
        _write_jsonl(p, events)
        result = reconstruct_from_logs_and_derive_deployable_count([p])
    assert result["lifecycles_count"] == 3
    assert result["deployable"]["deployable_count"] == 1
    assert "1" in result["deployable"]["deployable_candidate_ids"]
    assert "2" in result["deployable"]["non_deployable_candidate_ids"]
    assert "3" in result["deployable"]["non_deployable_candidate_ids"]
    assert result["deployable"]["breakdown_by_reject_reason"]["SIGNAL_TOO_SPARSE"] == 1
    assert result["deployable"]["breakdown_by_reject_reason"]["OOS_FAIL"] == 1


def test_non_jsonl_lines_ignored_gracefully():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "engine.jsonl"
        with open(p, "w", encoding="utf-8") as f:
            f.write("not json\n")
            f.write("{\"msg\": \"A2 PASS id=1 AAA\"}\n")
            f.write("partial {\n")
            f.write("{broken json\n")
        lcs, stats = reconstruct_lifecycles([p])
    assert len(lcs) == 1
    assert stats.lines_scanned == 4
    assert stats.events_matched == 1
