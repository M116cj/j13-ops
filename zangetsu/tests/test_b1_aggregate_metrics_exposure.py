"""Tests for 0-9Y-B1 aggregate_metrics exposure.

Required by TEAM ORDER 0-9Y-B1-PIPELINE-METRICS-EXPOSURE-FIX.

These tests verify that:
1. ArenaBatchMetrics dataclass has the new aggregate_metrics +
   aggregate_metrics_availability fields with default None.
2. ArenaStageMetrics accumulator has the same fields.
3. build_arena_batch_metrics() flows them through verbatim.
4. The new fields are JSON-serializable via to_dict() / to_json().
5. Backward compatibility: events emitted without aggregate_metrics still
   parse cleanly (None default).
6. Conservation identity (entered = passed + rejected + skipped) is not
   affected by aggregate_metrics presence/absence.

These are pure-Python unit tests; they do not run the live arena_pipeline
worker. The runtime emit path is exercised separately in
04_live_sample.md.
"""
from __future__ import annotations

import json

import pytest

from zangetsu.services.arena_pass_rate_telemetry import (
    ArenaBatchMetrics,
    ArenaStageMetrics,
    build_arena_batch_metrics,
)


def _make_stage_metrics() -> ArenaStageMetrics:
    """Helper: minimal mutable accumulator with conservation-clean state."""
    acc = ArenaStageMetrics(arena_stage="A1", run_id="r-1", batch_id="b-1")
    acc.entered_count = 10
    acc.passed_count = 0
    acc.rejected_count = 10
    acc.skipped_count = 0
    acc.reject_counter.add("COST_NEGATIVE", 10)
    return acc


# ---------------------------------------------------------------------------
# B1.1 — schema additions
# ---------------------------------------------------------------------------


def test_b1_arena_batch_metrics_defaults_none() -> None:
    """Default values for the new fields are None (backwards-compat)."""
    ev = ArenaBatchMetrics()
    assert ev.aggregate_metrics is None
    assert ev.aggregate_metrics_availability is None


def test_b1_arena_stage_metrics_defaults_none() -> None:
    """ArenaStageMetrics accumulator gets the same defaults."""
    acc = ArenaStageMetrics(arena_stage="A1")
    assert acc.aggregate_metrics is None
    assert acc.aggregate_metrics_availability is None


# ---------------------------------------------------------------------------
# B1.2 — builder pass-through (None case)
# ---------------------------------------------------------------------------


def test_b1_builder_passes_none_when_unset() -> None:
    """When the accumulator never sets aggregate_metrics, the built event
    has None for both new fields. Existing parsers see no semantic change."""
    acc = _make_stage_metrics()
    event = build_arena_batch_metrics(acc)
    assert event.aggregate_metrics is None
    assert event.aggregate_metrics_availability is None
    # And conservation still holds.
    assert event.entered_count == 10
    assert event.passed_count == 0
    assert event.rejected_count == 10
    assert event.skipped_count == 0
    assert event.entered_count == (
        event.passed_count + event.rejected_count + event.skipped_count
    )


# ---------------------------------------------------------------------------
# B1.3 — builder pass-through (populated case)
# ---------------------------------------------------------------------------


def test_b1_builder_passes_populated_aggregates() -> None:
    """When the accumulator is populated, the built event carries the same
    dicts verbatim (by-value)."""
    acc = _make_stage_metrics()
    aggregates = {
        "schema_version": "0-9y-b1-v1",
        "symbol": "BTCUSDT",
        "regime": "BULL_TREND",
        "lane": "baseline",
        "round_total_cost_bps": 11.5,
        "alphas_with_train_backtest": 8,
        "train_gross_pnl_median": 1.234,
        "train_net_pnl_median": -0.567,
        "train_gross_minus_net_median": 1.801,
        "train_total_trades_median": 47,
        "train_sharpe_median": 0.05,
        "val_net_pnl_median": None,  # missing for this batch
        "signal_density_per_bar": 0.000336,
    }
    availability = {
        "round_total_cost_bps": True,
        "train_gross_pnl_median": True,
        "train_net_pnl_median": True,
        "train_gross_minus_net_median": True,
        "train_total_trades_median": True,
        "train_sharpe_median": True,
        "val_net_pnl_median": False,
        "signal_density_per_bar": True,
        "fee_cost_separate": False,
        "slippage_cost_separate": False,
        "funding_cost_separate": False,
        "long_trade_count_separate": False,
        "short_trade_count_separate": False,
        "primary_reject_gate_explicit": False,
    }
    acc.aggregate_metrics = aggregates
    acc.aggregate_metrics_availability = availability

    event = build_arena_batch_metrics(acc)

    assert event.aggregate_metrics == aggregates
    assert event.aggregate_metrics_availability == availability


# ---------------------------------------------------------------------------
# B1.4 — JSON serialization
# ---------------------------------------------------------------------------


def test_b1_to_dict_includes_new_fields() -> None:
    acc = _make_stage_metrics()
    acc.aggregate_metrics = {"schema_version": "0-9y-b1-v1", "symbol": "ETH"}
    acc.aggregate_metrics_availability = {"signal_density_per_bar": True}
    event = build_arena_batch_metrics(acc)
    d = event.to_dict()
    assert "aggregate_metrics" in d
    assert "aggregate_metrics_availability" in d
    assert d["aggregate_metrics"]["symbol"] == "ETH"
    assert d["aggregate_metrics_availability"]["signal_density_per_bar"] is True


def test_b1_to_json_round_trip_preserves_aggregates() -> None:
    acc = _make_stage_metrics()
    acc.aggregate_metrics = {
        "schema_version": "0-9y-b1-v1",
        "round_total_cost_bps": 11.5,
        "train_net_pnl_median": -0.123,
    }
    acc.aggregate_metrics_availability = {"round_total_cost_bps": True}
    event = build_arena_batch_metrics(acc)
    raw = event.to_json()
    loaded = json.loads(raw)
    assert loaded["aggregate_metrics"]["schema_version"] == "0-9y-b1-v1"
    assert loaded["aggregate_metrics"]["round_total_cost_bps"] == 11.5
    assert loaded["aggregate_metrics"]["train_net_pnl_median"] == pytest.approx(
        -0.123
    )
    assert loaded["aggregate_metrics_availability"]["round_total_cost_bps"] is True


def test_b1_to_json_round_trip_with_none_aggregates() -> None:
    """When the new fields are None, JSON shape still includes them as null,
    which is harmless for parsers that ignore unknown keys."""
    acc = _make_stage_metrics()
    event = build_arena_batch_metrics(acc)
    raw = event.to_json()
    loaded = json.loads(raw)
    assert loaded["aggregate_metrics"] is None
    assert loaded["aggregate_metrics_availability"] is None


# ---------------------------------------------------------------------------
# B1.5 — conservation invariant unchanged by new fields
# ---------------------------------------------------------------------------


def test_b1_conservation_holds_with_aggregates_present() -> None:
    """Adding aggregate_metrics MUST NOT change entered/passed/rejected/skipped
    arithmetic. The conservation identity is the foundation of the
    arena_batch_metrics contract; any drift would invalidate prior
    PR #50 / PR #51 verification work."""
    acc = _make_stage_metrics()
    acc.aggregate_metrics = {"x": 1}
    acc.aggregate_metrics_availability = {"x": True}
    event = build_arena_batch_metrics(acc)
    assert event.entered_count == event.passed_count + event.rejected_count + event.skipped_count
    assert sum(event.reject_reason_distribution.values()) == event.rejected_count


def test_b1_conservation_holds_with_aggregates_none() -> None:
    """Same as above but with new fields untouched."""
    acc = _make_stage_metrics()
    event = build_arena_batch_metrics(acc)
    assert event.entered_count == event.passed_count + event.rejected_count + event.skipped_count


# ---------------------------------------------------------------------------
# B1.6 — emit wrapper signature accepts new kwargs
# ---------------------------------------------------------------------------


def test_b1_emit_wrapper_signature_accepts_aggregates() -> None:
    """The arena_pipeline emit wrapper must accept aggregate_metrics and
    aggregate_metrics_availability kwargs without raising TypeError. We
    validate signature only (no live arena_pipeline run)."""
    import inspect

    from zangetsu.services.arena_pipeline import (
        _emit_a1_batch_metrics_from_stats_safe,
    )

    sig = inspect.signature(_emit_a1_batch_metrics_from_stats_safe)
    params = sig.parameters
    assert "aggregate_metrics" in params
    assert "aggregate_metrics_availability" in params
    assert params["aggregate_metrics"].default is None
    assert params["aggregate_metrics_availability"].default is None
