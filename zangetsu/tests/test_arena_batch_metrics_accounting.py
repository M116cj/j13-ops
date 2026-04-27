"""Regression tests for the per-round delta accounting in
``zangetsu.services.arena_pipeline._emit_a1_batch_metrics_from_stats_safe``.

Background — TEAM ORDER 0-9X-A1-REJECT-DISTRIBUTION-SHIFT-DIAGNOSIS proved
that the previous implementation read worker-lifetime cumulative
``stats[reject_*]`` counters against a per-round ``entered_count``, which
made the conservation identity ``entered = passed + rejected + skipped``
fail after warmup. The residual-correction branch then emitted a huge
spurious ``COUNTER_INCONSISTENCY`` bucket every batch.

The fix (TEAM ORDER 0-9X-ARENA-BATCH-METRICS-ACCOUNTING-FIX) is a per-round
delta: each emit takes ``current - previous`` against the snapshot from the
last emit. The helper ``_compute_a1_reject_deltas`` is the pure function
that performs the delta arithmetic; this file tests it directly.

The full ``arena_pipeline.py`` cannot be imported on this Mac CI host
(heavy runtime deps such as ``pyarrow``, Rust extensions, hard-coded
``/home/j13/j13-ops`` chdir at module top). The tests therefore extract
the pure helper via AST and exec it in an isolated namespace. This is
intentional: the helper is purposely written without runtime dependencies
so it remains unit-testable in any environment.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

_ARENA_PIPELINE_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "services"
    / "arena_pipeline.py"
)


def _load_helper_and_keys():
    """Extract _compute_a1_reject_deltas and _A1_REJECT_STATS_KEYS from
    arena_pipeline.py via AST + exec. Returns (helper_fn, keys_tuple)."""
    text = _ARENA_PIPELINE_PATH.read_text()
    tree = ast.parse(text)
    helper_src = None
    keys_src = None
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_compute_a1_reject_deltas":
            helper_src = ast.get_source_segment(text, node)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "_A1_REJECT_STATS_KEYS":
                keys_src = ast.get_source_segment(text, node)
    assert helper_src is not None, "_compute_a1_reject_deltas not found in arena_pipeline.py"
    assert keys_src is not None, "_A1_REJECT_STATS_KEYS not found in arena_pipeline.py"
    ns: dict = {}
    exec(keys_src, ns)
    exec(helper_src, ns)
    return ns["_compute_a1_reject_deltas"], ns["_A1_REJECT_STATS_KEYS"]


@pytest.fixture
def helper():
    fn, _ = _load_helper_and_keys()
    return fn


@pytest.fixture
def reject_keys():
    _, keys = _load_helper_and_keys()
    return keys


# ---------- Required by TEAM ORDER 0-9X-ARENA-BATCH-METRICS-ACCOUNTING-FIX ----------


def test_residual_zero_per_batch(helper, reject_keys):
    """After warmup, conservation must hold: entered = passed + sum(deltas) + skipped.

    Simulate two consecutive batches against a steady-state cumulative stats
    dict. The first batch's deltas equal the round-1 increments; the second
    batch's deltas equal the round-2 increments only. residual = 0 each time."""
    # Round 1: 10 candidates, 2 passed, 5 rejected (3 few + 2 neg_pnl), 3 skipped
    cumul = {"reject_few_trades": 3, "reject_neg_pnl": 2}
    deltas, snap = helper(cumul, {}, reject_keys)
    assert sum(deltas.values()) == 5
    entered, passed = 10, 2
    rejected_total = sum(deltas.values())
    skipped = entered - passed - rejected_total
    assert skipped == 3
    assert entered == passed + rejected_total + skipped  # conservation

    # Round 2: cumulative grows to {few:5, neg_pnl:5, train_neg_pnl:2} = +7 deltas
    cumul = {
        "reject_few_trades": 5, "reject_neg_pnl": 5,
        "reject_train_neg_pnl": 2,
    }
    deltas, snap = helper(cumul, snap, reject_keys)
    # Round 2 entered=10, passed=1, rejected=7 → skipped=2
    entered, passed = 10, 1
    rejected_total = sum(deltas.values())
    assert rejected_total == 7  # 2 + 3 + 2 (delta-only)
    skipped = entered - passed - rejected_total
    assert skipped == 2
    assert entered == passed + rejected_total + skipped


def test_counter_inconsistency_not_triggered_for_valid_data(helper, reject_keys):
    """When entered_count is consistent with passed + sum(deltas), the residual
    is non-negative and COUNTER_INCONSISTENCY is NOT emitted (residual goes
    to skipped_count instead). This is what the production code does post-fix."""
    # Steady-state worker, 100 rounds in. Round-101 increments by exactly:
    # entered=10, passed=3, rejected=7. No residual deficit.
    prev = {
        "reject_few_trades": 50, "reject_neg_pnl": 70,
        "reject_train_neg_pnl": 30, "reject_val_neg_pnl": 80,
        "reject_val_low_sharpe": 60, "reject_val_low_wr": 40,
        "reject_combined_sharpe_low": 20,
    }
    cumul = dict(prev)
    cumul["reject_few_trades"] += 4
    cumul["reject_train_neg_pnl"] += 3
    deltas, snap = helper(cumul, prev, reject_keys)
    rejected_total = sum(deltas.values())
    assert rejected_total == 7
    entered, passed = 10, 3
    residual = entered - passed - rejected_total
    assert residual == 0  # residual ≥ 0 → no COUNTER_INCONSISTENCY trigger


def test_existing_distribution_keys_preserved(helper, reject_keys):
    """The helper must walk all 10 documented stats keys in the same order
    as the previous (cumulative) implementation. The fix is delta-only;
    the key vocabulary is unchanged."""
    expected_keys = (
        "reject_few_trades", "reject_neg_pnl", "reject_train_neg_pnl",
        "reject_val_constant", "reject_val_error", "reject_val_few_trades",
        "reject_val_neg_pnl", "reject_val_low_sharpe", "reject_val_low_wr",
        "reject_combined_sharpe_low",
    )
    assert reject_keys == expected_keys

    # Each key, when nonzero in current and zero in prev, surfaces in deltas.
    for k in expected_keys:
        cumul = {k: 1}
        deltas, _snap = helper(cumul, {}, reject_keys)
        assert deltas == {k: 1}, f"key {k} not surfaced in deltas"


def test_first_batch_initialization(helper, reject_keys):
    """First emit (empty prev_snapshot) must:
      (a) treat current values as deltas (everything-since-worker-start)
      (b) populate the new_snapshot with all stats_keys (including zeros)
      (c) NOT crash on missing-from-current stats keys
    """
    # First call with empty prev: current values become deltas
    cumul = {"reject_few_trades": 4, "reject_neg_pnl": 6}
    deltas, snap = helper(cumul, {}, reject_keys)
    assert deltas == {"reject_few_trades": 4, "reject_neg_pnl": 6}
    # Snapshot covers all 10 keys (including zeros for keys absent from current)
    assert set(snap.keys()) == set(reject_keys)
    for k in reject_keys:
        if k in cumul:
            assert snap[k] == cumul[k]
        else:
            assert snap[k] == 0
    # Second call with same cumul → deltas empty (no growth)
    deltas2, snap2 = helper(cumul, snap, reject_keys)
    assert deltas2 == {}
    assert snap2 == snap


# ---------- Belt-and-braces guard against silent regression ----------


def test_helper_is_pure_does_not_mutate_input(helper, reject_keys):
    """The helper returns a NEW snapshot dict; the input prev_snapshot
    must not be mutated. This guarantees safe use in tests and in
    production where we may want to keep the previous snapshot for logging."""
    prev_snapshot = {"reject_few_trades": 7}
    prev_copy = dict(prev_snapshot)
    cumul = {"reject_few_trades": 9}
    _deltas, new_snapshot = helper(cumul, prev_snapshot, reject_keys)
    assert prev_snapshot == prev_copy, "prev_snapshot was mutated"
    assert new_snapshot is not prev_snapshot
    assert new_snapshot["reject_few_trades"] == 9


def test_negative_or_zero_delta_not_counted(helper, reject_keys):
    """If current < previous (worker stats reset / counter rollback) or
    current == previous (no growth this round), no delta is emitted.
    Snapshot still updates so future deltas are correct."""
    prev = {"reject_few_trades": 100}
    cumul = {"reject_few_trades": 100}  # no growth
    deltas, snap = helper(cumul, prev, reject_keys)
    assert deltas == {}
    assert snap["reject_few_trades"] == 100

    prev = {"reject_few_trades": 100}
    cumul = {"reject_few_trades": 80}  # decreased (rollback)
    deltas, snap = helper(cumul, prev, reject_keys)
    assert deltas == {}
    assert snap["reject_few_trades"] == 80  # snapshot tracks the new low
