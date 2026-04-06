#!/usr/bin/env python3
"""Zangetsu V3.2 Orchestrator — State machine with all state in PostgreSQL.

States: IDLE -> ARENA1_FAST -> ARENA2 -> ARENA3 -> GATING -> DEPLOYING -> MONITORING
Every state transition: UPSERT orchestrator_state + INSERT orchestrator_events.
Kill at any point -> restart -> resume from DB.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import psycopg2
import psycopg2.extras

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from zangetsu_v3.regime.rule_labeler import Regime, REGIME_NAMES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Orchestrator] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("orchestrator")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
def _default_dsn() -> str:
    """Build DSN from config/config.yaml if no env override."""
    try:
        from zangetsu_v3.core.config import load_config
        cfg = load_config(_PROJECT_ROOT / "config" / "config.yaml")
        db = cfg.database
        return f"dbname={db.dbname} user={db.user} password={db.password} host={db.host} port={db.port}"
    except Exception:
        return "dbname=zangetsu user=zangetsu host=127.0.0.1 port=5432"

DB_DSN = os.environ.get("ZV3_DB_DSN") or _default_dsn()
STRATEGIES_DIR = Path(
    os.environ.get("ZV3_STRATEGIES_DIR", str(_PROJECT_ROOT / "strategies"))
)
LOOP_SLEEP_S = int(os.environ.get("ZV3_ORCH_SLEEP", "30"))

# Monitoring thresholds
FACTOR_AGE_DAYS = 30
DEGRADED_THRESHOLD = 0.50  # 50% of cards degraded -> retrigger
ROLLING_HOLDOUT_DAYS = 90

# All 11 search regimes
SEARCH_REGIME_NAMES = [
    "BULL_TREND", "BEAR_TREND", "BULL_PULLBACK", "BEAR_RALLY",
    "TOPPING", "BOTTOMING", "CONSOLIDATION", "SQUEEZE",
    "CHOPPY_VOLATILE", "DISTRIBUTION", "ACCUMULATION",
]


class State(str, Enum):
    IDLE = "IDLE"
    ARENA1_FAST = "ARENA1_FAST"
    ARENA2 = "ARENA2"
    ARENA3 = "ARENA3"
    GATING = "GATING"
    DEPLOYING = "DEPLOYING"
    MONITORING = "MONITORING"


# Valid transitions
TRANSITIONS = {
    State.IDLE: State.ARENA1_FAST,
    State.ARENA1_FAST: State.ARENA2,
    State.ARENA2: State.ARENA3,
    State.ARENA3: State.GATING,
    State.GATING: State.DEPLOYING,
    State.DEPLOYING: State.MONITORING,
    State.MONITORING: State.IDLE,  # trigger loop
}


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------
def _get_conn():
    """Get a fresh psycopg2 connection."""
    return psycopg2.connect(DB_DSN)


def db_read_state() -> tuple[State, dict]:
    """Read orchestrator_state (singleton id=1). Returns (state, details_json)."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT state, details_json FROM orchestrator_state WHERE id = 1"
            )
            row = cur.fetchone()
            if row is None:
                # First run — insert initial state
                cur.execute(
                    "INSERT INTO orchestrator_state (id, state, details_json) "
                    "VALUES (1, 'IDLE', '{}') "
                    "ON CONFLICT (id) DO NOTHING"
                )
                conn.commit()
                return State.IDLE, {}
            return State(row[0]), row[1] if row[1] else {}
    finally:
        conn.close()


def db_set_state(state: State, details: dict) -> None:
    """UPSERT orchestrator_state singleton."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO orchestrator_state (id, state, details_json, updated_at) "
                "VALUES (1, %s, %s, NOW()) "
                "ON CONFLICT (id) DO UPDATE SET state = %s, details_json = %s, updated_at = NOW()",
                (state.value, json.dumps(details), state.value, json.dumps(details)),
            )
        conn.commit()
    finally:
        conn.close()


def db_log_event(event_type: str, regime: Optional[str], details: dict) -> None:
    """INSERT into orchestrator_events."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO orchestrator_events (event_type, regime, details_json) "
                "VALUES (%s, %s, %s)",
                (event_type, regime, json.dumps(details)),
            )
        conn.commit()
    finally:
        conn.close()


def db_transition(new_state: State, details: dict, event_type: str,
                  regime: Optional[str] = None) -> None:
    """Atomic state transition: UPSERT state + INSERT event."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO orchestrator_state (id, state, details_json, updated_at) "
                "VALUES (1, %s, %s, NOW()) "
                "ON CONFLICT (id) DO UPDATE SET state = %s, details_json = %s, updated_at = NOW()",
                (new_state.value, json.dumps(details), new_state.value, json.dumps(details)),
            )
            cur.execute(
                "INSERT INTO orchestrator_events (event_type, regime, details_json) "
                "VALUES (%s, %s, %s)",
                (event_type, regime, json.dumps(details)),
            )
        conn.commit()
        log.info("TRANSITION -> %s (event=%s, regime=%s)", new_state.value, event_type, regime)
    finally:
        conn.close()


def db_query(sql: str, params: tuple = ()) -> list[tuple]:
    """Run a read-only query, return rows."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


def db_scalar(sql: str, params: tuple = ()):
    """Run a query returning a single scalar value."""
    rows = db_query(sql, params)
    return rows[0][0] if rows else None


# ---------------------------------------------------------------------------
# State handlers
# ---------------------------------------------------------------------------

def handle_idle(details: dict) -> Optional[State]:
    """Check if factor_pool exists for all regimes. If not -> ARENA1_FAST."""
    log.info("IDLE: checking factor_pool coverage...")

    covered = db_query(
        "SELECT DISTINCT regime FROM factor_pool WHERE regime IS NOT NULL"
    )
    covered_set = {r[0] for r in covered}
    missing = [r for r in SEARCH_REGIME_NAMES if r not in covered_set]

    if missing:
        log.info("IDLE: missing factor_pool for %d regimes: %s", len(missing), missing)
        db_transition(
            State.ARENA1_FAST,
            {"missing_regimes": missing, "started_at": datetime.now(timezone.utc).isoformat()},
            "idle_to_arena1",
        )
        return State.ARENA1_FAST

    log.info("IDLE: all regimes covered, moving to MONITORING")
    db_transition(
        State.MONITORING,
        {"reason": "all_regimes_have_factors"},
        "idle_to_monitoring",
    )
    return State.MONITORING


def _count_factor_candidates(regime: str) -> int:
    """Count factor_candidates for a given regime."""
    val = db_scalar(
        "SELECT COUNT(*) FROM factor_candidates WHERE regime = %s", (regime,)
    )
    return val or 0


def _arena1_runs_done() -> set[str]:
    """Check arena1_runs table for completed regimes."""
    rows = db_query(
        "SELECT DISTINCT regime FROM arena1_runs WHERE status = 'complete'"
    )
    return {r[0] for r in rows}


def handle_arena1_fast(details: dict) -> Optional[State]:
    """Run arena1 fast search. Import and call arena1_dryrun/arena1_full main.

    Resume logic: check factor_candidates count per regime, skip completed.
    Also launch PySR in background if not already running.
    """
    log.info("ARENA1_FAST: starting factor candidate generation...")

    # Check which regimes already have candidates
    regimes_with_candidates = {}
    for regime in SEARCH_REGIME_NAMES:
        count = _count_factor_candidates(regime)
        regimes_with_candidates[regime] = count

    missing_regimes = [r for r, c in regimes_with_candidates.items() if c == 0]
    done_regimes = [r for r, c in regimes_with_candidates.items() if c > 0]

    if done_regimes:
        log.info("ARENA1_FAST: %d regimes already have candidates: %s",
                 len(done_regimes), done_regimes)

    if not missing_regimes:
        log.info("ARENA1_FAST: all regimes have factor candidates, advancing")
        db_transition(
            State.ARENA2,
            {"candidates_per_regime": regimes_with_candidates},
            "arena1_complete",
        )
        return State.ARENA2

    # Run arena1_full.py as subprocess (it has its own DB writes)
    log.info("ARENA1_FAST: %d regimes need candidates: %s", len(missing_regimes), missing_regimes)
    db_set_state(State.ARENA1_FAST, {
        "phase": "running",
        "missing_regimes": missing_regimes,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    db_log_event("arena1_fast_start", None, {"missing_regimes": missing_regimes})

    scripts_dir = Path(__file__).resolve().parent
    arena1_script = scripts_dir / "arena1_full.py"

    if not arena1_script.exists():
        log.error("ARENA1_FAST: arena1_full.py not found at %s", arena1_script)
        db_log_event("arena1_fast_error", None, {"error": "script_not_found"})
        return None

    try:
        log.info("ARENA1_FAST: running %s ...", arena1_script)
        result = subprocess.run(
            [sys.executable, str(arena1_script)],
            cwd=str(_PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=7200,  # 2h max
        )
        if result.returncode != 0:
            log.error("ARENA1_FAST: arena1_full.py exited %d: %s",
                      result.returncode, result.stderr[-500:] if result.stderr else "")
            db_log_event("arena1_fast_error", None, {
                "returncode": result.returncode,
                "stderr_tail": (result.stderr or "")[-500:],
            })
        else:
            log.info("ARENA1_FAST: arena1_full.py completed successfully")
    except subprocess.TimeoutExpired:
        log.warning("ARENA1_FAST: arena1_full.py timed out (2h), will check progress on next loop")
        db_log_event("arena1_fast_timeout", None, {})
    except Exception as e:
        log.error("ARENA1_FAST: failed to run arena1_full.py: %s", e)
        db_log_event("arena1_fast_error", None, {"error": str(e)})

    # Also launch PySR background search if arena1_pysr.py exists
    pysr_script = scripts_dir / "arena1_pysr.py"
    if pysr_script.exists():
        _launch_pysr_background(pysr_script)

    # Re-check coverage after run
    total_candidates = 0
    updated_counts = {}
    for regime in SEARCH_REGIME_NAMES:
        count = _count_factor_candidates(regime)
        updated_counts[regime] = count
        total_candidates += count

    still_missing = [r for r, c in updated_counts.items() if c == 0]
    if still_missing:
        log.warning("ARENA1_FAST: still missing candidates for %d regimes: %s",
                     len(still_missing), still_missing)
        db_set_state(State.ARENA1_FAST, {
            "phase": "partial",
            "candidates_per_regime": updated_counts,
            "still_missing": still_missing,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        return None  # stay in ARENA1_FAST, retry next loop

    # All regimes have candidates -> advance
    db_transition(
        State.ARENA2,
        {"candidates_per_regime": updated_counts, "total": total_candidates},
        "arena1_complete",
    )
    return State.ARENA2


_pysr_pid: Optional[int] = None


def _launch_pysr_background(script: Path) -> None:
    """Launch PySR background search if not already running."""
    global _pysr_pid
    if _pysr_pid is not None:
        # Check if still running
        try:
            os.kill(_pysr_pid, 0)
            log.info("PySR background still running (pid=%d)", _pysr_pid)
            return
        except OSError:
            _pysr_pid = None

    log.info("Launching PySR background: %s", script)
    try:
        proc = subprocess.Popen(
            [sys.executable, str(script)],
            cwd=str(_PROJECT_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _pysr_pid = proc.pid
        db_log_event("pysr_background_launched", None, {"pid": proc.pid})
        log.info("PySR background launched (pid=%d)", proc.pid)
    except Exception as e:
        log.error("Failed to launch PySR background: %s", e)


def handle_arena2(details: dict) -> Optional[State]:
    """Run arena2_compress.py per regime. Check factor_pool count."""
    log.info("ARENA2: compressing factor candidates into factor pool...")

    # Check which regimes already have factor_pool entries
    pool_coverage = {}
    for regime in SEARCH_REGIME_NAMES:
        count = db_scalar(
            "SELECT COUNT(*) FROM factor_pool WHERE regime = %s", (regime,)
        )
        pool_coverage[regime] = count or 0

    missing = [r for r, c in pool_coverage.items() if c == 0]
    if not missing:
        log.info("ARENA2: all regimes have factor pool, advancing to ARENA3")
        db_transition(
            State.ARENA3,
            {"pool_per_regime": pool_coverage},
            "arena2_complete",
        )
        return State.ARENA3

    log.info("ARENA2: %d regimes need compression: %s", len(missing), missing)
    db_set_state(State.ARENA2, {
        "phase": "running",
        "missing_regimes": missing,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    db_log_event("arena2_start", None, {"missing_regimes": missing})

    scripts_dir = Path(__file__).resolve().parent
    arena2_script = scripts_dir / "arena2_compress.py"

    if not arena2_script.exists():
        log.error("ARENA2: arena2_compress.py not found at %s", arena2_script)
        db_log_event("arena2_error", None, {"error": "script_not_found"})
        return None

    try:
        log.info("ARENA2: running %s ...", arena2_script)
        result = subprocess.run(
            [sys.executable, str(arena2_script)],
            cwd=str(_PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=3600,  # 1h max
        )
        if result.returncode != 0:
            log.error("ARENA2: arena2_compress.py exited %d: %s",
                      result.returncode, result.stderr[-500:] if result.stderr else "")
            db_log_event("arena2_error", None, {
                "returncode": result.returncode,
                "stderr_tail": (result.stderr or "")[-500:],
            })
        else:
            log.info("ARENA2: arena2_compress.py completed successfully")
    except subprocess.TimeoutExpired:
        log.warning("ARENA2: arena2_compress.py timed out (1h)")
        db_log_event("arena2_timeout", None, {})
    except Exception as e:
        log.error("ARENA2: failed: %s", e)
        db_log_event("arena2_error", None, {"error": str(e)})

    # Re-check
    for regime in SEARCH_REGIME_NAMES:
        count = db_scalar(
            "SELECT COUNT(*) FROM factor_pool WHERE regime = %s", (regime,)
        )
        pool_coverage[regime] = count or 0

    still_missing = [r for r, c in pool_coverage.items() if c == 0]
    if still_missing:
        log.warning("ARENA2: still missing pool for %d regimes", len(still_missing))
        db_set_state(State.ARENA2, {
            "phase": "partial",
            "pool_per_regime": pool_coverage,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        return None  # retry next loop

    db_transition(
        State.ARENA3,
        {"pool_per_regime": pool_coverage},
        "arena2_complete",
    )
    return State.ARENA3


def handle_arena3(details: dict) -> Optional[State]:
    """Run arena3 QD search per regime. Monitor search_progress."""
    log.info("ARENA3: running QD evolutionary search per regime...")

    # Check which regimes have champions (search complete)
    champion_regimes = set()
    rows = db_query(
        "SELECT DISTINCT genome->>'regime' FROM strategy_champions WHERE status = 'active'"
    )
    for r in rows:
        if r[0]:
            champion_regimes.add(r[0])

    # Also check search_progress for regimes with enough generations
    search_done = set()
    for regime in SEARCH_REGIME_NAMES:
        max_gen = db_scalar(
            "SELECT MAX(generation) FROM search_progress WHERE regime = %s", (regime,)
        )
        num_elites = db_scalar(
            "SELECT num_elites FROM search_progress WHERE regime = %s ORDER BY generation DESC LIMIT 1",
            (regime,),
        )
        if max_gen is not None and max_gen >= 50 and num_elites and num_elites > 0:
            search_done.add(regime)
        elif regime in champion_regimes:
            search_done.add(regime)

    missing = [r for r in SEARCH_REGIME_NAMES if r not in search_done]

    if not missing:
        log.info("ARENA3: all regimes have search results, advancing to GATING")
        db_transition(
            State.GATING,
            {"champion_regimes": sorted(champion_regimes), "search_complete": sorted(search_done)},
            "arena3_complete",
        )
        return State.GATING

    log.info("ARENA3: %d regimes need search: %s", len(missing), missing)
    db_set_state(State.ARENA3, {
        "phase": "running",
        "missing_regimes": missing,
        "done_regimes": sorted(search_done),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

    # Run the v31 search pipeline
    scripts_dir = Path(__file__).resolve().parent
    run_script = scripts_dir / "run_v31.py"

    if not run_script.exists():
        log.error("ARENA3: run_v31.py not found at %s", run_script)
        db_log_event("arena3_error", None, {"error": "script_not_found"})
        return None

    for regime in missing:
        db_log_event("arena3_regime_start", regime, {"regime": regime})
        log.info("ARENA3: running search for regime %s ...", regime)

        try:
            result = subprocess.run(
                [sys.executable, str(run_script), "--regime", regime],
                cwd=str(_PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=7200,  # 2h per regime
                env={**os.environ, "ZV3_DB_DSN": DB_DSN},
            )
            if result.returncode != 0:
                log.error("ARENA3: search for %s exited %d", regime, result.returncode)
                db_log_event("arena3_regime_error", regime, {
                    "returncode": result.returncode,
                    "stderr_tail": (result.stderr or "")[-500:],
                })
            else:
                log.info("ARENA3: search for %s completed", regime)
                db_log_event("arena3_regime_complete", regime, {})
        except subprocess.TimeoutExpired:
            log.warning("ARENA3: search for %s timed out (2h)", regime)
            db_log_event("arena3_regime_timeout", regime, {})
        except Exception as e:
            log.error("ARENA3: search for %s failed: %s", regime, e)
            db_log_event("arena3_regime_error", regime, {"error": str(e)})

        # Update state after each regime
        db_set_state(State.ARENA3, {
            "phase": "running",
            "current_regime": regime,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

    # Re-check after all runs
    for regime in SEARCH_REGIME_NAMES:
        max_gen = db_scalar(
            "SELECT MAX(generation) FROM search_progress WHERE regime = %s", (regime,)
        )
        num_elites = db_scalar(
            "SELECT num_elites FROM search_progress WHERE regime = %s ORDER BY generation DESC LIMIT 1",
            (regime,),
        )
        if max_gen is not None and max_gen >= 50 and num_elites and num_elites > 0:
            search_done.add(regime)

    still_missing = [r for r in SEARCH_REGIME_NAMES if r not in search_done]
    if still_missing:
        log.warning("ARENA3: still missing search for %d regimes", len(still_missing))
        db_set_state(State.ARENA3, {
            "phase": "partial",
            "still_missing": still_missing,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        return None

    db_transition(
        State.GATING,
        {"search_complete": sorted(search_done)},
        "arena3_complete",
    )
    return State.GATING


def handle_gating(details: dict) -> Optional[State]:
    """Run 3 gates per champion. Write validation_gates."""
    log.info("GATING: running validation gates on champions...")

    # Get champions that haven't been gated yet
    champions = db_query(
        "SELECT id, strategy_id, genome FROM strategy_champions "
        "WHERE status = 'active'"
    )

    if not champions:
        log.warning("GATING: no active champions found, going back to ARENA3")
        db_transition(State.ARENA3, {"reason": "no_champions"}, "gating_no_champions")
        return State.ARENA3

    # Check which champions already have gate results
    gated = set()
    rows = db_query("SELECT DISTINCT champion_id FROM validation_gates")
    for r in rows:
        if r[0]:
            gated.add(r[0])

    ungated = [(cid, sid, genome) for cid, sid, genome in champions if sid not in gated]

    if not ungated:
        log.info("GATING: all %d champions already gated, advancing", len(champions))
        # Count passed
        passed_count = db_scalar(
            "SELECT COUNT(DISTINCT champion_id) FROM validation_gates WHERE passed = true"
        ) or 0
        db_transition(
            State.DEPLOYING,
            {"total_champions": len(champions), "passed": passed_count},
            "gating_complete",
        )
        return State.DEPLOYING

    log.info("GATING: %d champions need gating (of %d total)", len(ungated), len(champions))
    db_set_state(State.GATING, {
        "phase": "running",
        "total": len(champions),
        "ungated": len(ungated),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

    # Run gating via run_v31.py --gate-only (or inline)
    # For V3.2, we invoke the gating inline using the gates module
    for champ_id, strategy_id, genome in ungated:
        db_log_event("gating_start", strategy_id, {"champion_id": champ_id})
        log.info("GATING: evaluating champion %s ...", strategy_id)

        try:
            _run_gates_for_champion(champ_id, strategy_id, genome)
            db_log_event("gating_done", strategy_id, {"champion_id": champ_id})
        except Exception as e:
            log.error("GATING: failed for %s: %s", strategy_id, e)
            db_log_event("gating_error", strategy_id, {
                "champion_id": champ_id,
                "error": str(e),
                "traceback": traceback.format_exc()[-500:],
            })
            # Write a failed gate record so we don't retry forever
            _write_gate_result(strategy_id, passed=False, details={
                "error": str(e),
                "gate1": False, "gate2": False, "gate3": False,
            })

    # Check results
    passed_count = db_scalar(
        "SELECT COUNT(DISTINCT champion_id) FROM validation_gates WHERE passed = true"
    ) or 0
    total_gated = db_scalar(
        "SELECT COUNT(DISTINCT champion_id) FROM validation_gates"
    ) or 0

    log.info("GATING: %d/%d passed", passed_count, total_gated)

    db_transition(
        State.DEPLOYING,
        {"total_gated": total_gated, "passed": passed_count},
        "gating_complete",
    )
    return State.DEPLOYING


def _run_gates_for_champion(champ_id: int, strategy_id: str, genome: dict) -> None:
    """Run Gate1 + Gate2 + Gate3 for a single champion and write results to DB."""
    from zangetsu_v3.gates import Gate1, DeflatedSharpeGate, HoldoutGate
    from zangetsu_v3.search.backtest import HFTBacktest, BacktestResult

    # Extract genome fields
    weights = genome.get("weights", [])
    params = genome.get("params", {})
    regime = genome.get("regime", "")
    wf_sharpe = genome.get("wf_sharpe", 0)
    wf_n_windows = genome.get("wf_n_windows", 0)
    n_elites = genome.get("n_elites", 1)

    # Gate 1: SoS threshold + trimmed min > 0
    g1 = Gate1(sos_threshold=1.0)
    # Build a synthetic BacktestResult from walk-forward stats
    g1_pass = False
    sos_val = genome.get("sos", 0)
    trimmed_min_val = genome.get("trimmed_min", 0)
    if sos_val > 1.0 and trimmed_min_val > 0:
        g1_pass = True

    # Gate 2: Deflated Sharpe
    g2 = DeflatedSharpeGate(threshold=0.05)
    g2_pass = g2.gate(
        observed_sharpe=wf_sharpe or 0,
        n_observations=max(wf_n_windows * 1000, 100),  # approximate
        n_trials=max(n_elites, 1),
    )
    dsr_val = g2.last_dsr

    # Gate 3: Holdout (check if holdout data available)
    g3 = HoldoutGate()
    g3_pass = False
    g3_reason = "not_evaluated"

    # Check for holdout results in the genome
    holdout_fitness = genome.get("holdout_fitness", None)
    holdout_win_rate = genome.get("holdout_win_rate", None)
    holdout_tpd = genome.get("holdout_tpd", None)

    if holdout_fitness is not None and holdout_fitness > 0:
        # Construct a minimal BacktestResult for Gate3
        if holdout_win_rate and holdout_win_rate >= 0.52 and holdout_tpd and holdout_tpd >= 100:
            g3_pass = True
            g3_reason = "PASSED"
        else:
            g3_reason = f"holdout_wr={holdout_win_rate}, tpd={holdout_tpd}"
    else:
        g3_reason = "no_holdout_data_in_genome"

    all_pass = g1_pass and g2_pass and g3_pass

    log.info("  Gates for %s: G1=%s G2=%s(dsr=%.3f) G3=%s(%s) -> %s",
             strategy_id, g1_pass, g2_pass, dsr_val, g3_pass, g3_reason,
             "PASS" if all_pass else "FAIL")

    _write_gate_result(strategy_id, passed=all_pass, details={
        "gate1": g1_pass,
        "gate1_sos": sos_val,
        "gate1_trimmed_min": trimmed_min_val,
        "gate2": g2_pass,
        "gate2_dsr": dsr_val,
        "gate3": g3_pass,
        "gate3_reason": g3_reason,
    })


def _write_gate_result(champion_id: str, passed: bool, details: dict) -> None:
    """Write gate result to validation_gates table."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO validation_gates "
                "(champion_id, passed, walk_forward_details) "
                "VALUES (%s, %s, %s)",
                (champion_id, passed, json.dumps(details)),
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        log.error("Failed to write gate result for %s: %s", champion_id, e)
    finally:
        conn.close()


def handle_deploying(details: dict) -> Optional[State]:
    """Export card.json FROM DB (strategy_champions -> filesystem card).
    Compare with existing. Advance to MONITORING.
    """
    log.info("DEPLOYING: exporting passed champions to card.json files...")

    # Get champions that passed gates
    passed_champions = db_query(
        "SELECT sc.id, sc.strategy_id, sc.genome, sc.wf_sharpe, sc.wf_calmar, "
        "sc.wf_max_drawdown, sc.wf_win_rate, sc.fitness_score "
        "FROM strategy_champions sc "
        "JOIN validation_gates vg ON vg.champion_id = sc.strategy_id "
        "WHERE vg.passed = true AND sc.status = 'active'"
    )

    if not passed_champions:
        log.warning("DEPLOYING: no passed champions to deploy")
        db_transition(
            State.MONITORING,
            {"deployed": 0, "reason": "no_passed_champions"},
            "deploying_complete",
        )
        return State.MONITORING

    STRATEGIES_DIR.mkdir(parents=True, exist_ok=True)
    deployed = []

    for row in passed_champions:
        champ_id, strategy_id, genome, wf_sharpe, wf_calmar, wf_mdd, wf_wr, fitness = row
        card_dir = STRATEGIES_DIR / strategy_id
        card_path = card_dir / "card.json"

        # Build card payload from genome + champion data
        card_payload = {
            "version": "3.2",
            "card_id": strategy_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "regime": genome.get("regime", ""),
            "regime_includes": genome.get("regime_includes", []),
            "applicable_symbols": genome.get("applicable_symbols", []),
            "warmup_bars": genome.get("warmup_bars", 200),
            "style": genome.get("style", "HFT"),
            "factors": genome.get("factors", []),
            "params": genome.get("params", {}),
            "normalization": genome.get("normalization", {}),
            "cost_model": genome.get("cost_model", {}),
            "backtest": {
                "wf_sharpe": wf_sharpe,
                "wf_calmar": wf_calmar,
                "wf_max_drawdown": wf_mdd,
                "wf_win_rate": wf_wr,
                "fitness_score": fitness,
            },
            "validation": {"passed": True},
            "status": "PASSED_HOLDOUT",
            "deployed_at": datetime.now(timezone.utc).isoformat(),
        }

        # Compare with existing card
        if card_path.exists():
            try:
                with card_path.open() as f:
                    existing = json.load(f)
                if existing.get("fitness_score") == fitness and existing.get("card_id") == strategy_id:
                    log.info("DEPLOYING: %s unchanged, skipping", strategy_id)
                    deployed.append(strategy_id)
                    continue
                log.info("DEPLOYING: %s changed, replacing", strategy_id)
                # Archive old card
                archive_path = card_dir / f"card_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.json.bak"
                card_path.rename(archive_path)
            except Exception:
                pass  # overwrite anyway

        card_dir.mkdir(parents=True, exist_ok=True)
        with card_path.open("w", encoding="utf-8") as f:
            json.dump(card_payload, f, indent=2, sort_keys=True)

        deployed.append(strategy_id)
        db_log_event("card_deployed", strategy_id, {
            "fitness": fitness,
            "wf_sharpe": wf_sharpe,
        })
        log.info("DEPLOYING: exported %s -> %s", strategy_id, card_path)

    db_transition(
        State.MONITORING,
        {"deployed": deployed, "count": len(deployed)},
        "deploying_complete",
    )
    return State.MONITORING


def handle_monitoring(details: dict) -> Optional[State]:
    """Check every 60 min. Triggers: factor_age>30d, degraded>50%,
    expired_no_backup, rolling_holdout(90d), pysr_complete.
    """
    log.info("MONITORING: checking triggers...")

    triggers = []

    # 1. Factor age > 30 days
    oldest_pool = db_scalar(
        "SELECT MIN(created_at) FROM factor_pool"
    )
    if oldest_pool:
        age_days = (datetime.now(timezone.utc) - oldest_pool).days
        if age_days > FACTOR_AGE_DAYS:
            triggers.append(f"factor_age={age_days}d>threshold({FACTOR_AGE_DAYS}d)")
            log.warning("MONITORING: factor pool age %d days > %d threshold", age_days, FACTOR_AGE_DAYS)

    # 2. Degraded cards > 50%
    total_cards = db_scalar(
        "SELECT COUNT(*) FROM strategy_champions WHERE status = 'active'"
    ) or 0
    if total_cards > 0:
        # Check validation_gates for failed champions
        failed = db_scalar(
            "SELECT COUNT(DISTINCT champion_id) FROM validation_gates WHERE passed = false"
        ) or 0
        degraded_pct = failed / total_cards if total_cards > 0 else 0
        if degraded_pct > DEGRADED_THRESHOLD:
            triggers.append(f"degraded={degraded_pct:.0%}>threshold({DEGRADED_THRESHOLD:.0%})")
            log.warning("MONITORING: %.0f%% cards degraded", degraded_pct * 100)

    # 3. No active cards at all
    active_cards = db_scalar(
        "SELECT COUNT(*) FROM strategy_champions "
        "WHERE status = 'active'"
    ) or 0
    passed_gates = db_scalar(
        "SELECT COUNT(DISTINCT champion_id) FROM validation_gates WHERE passed = true"
    ) or 0
    if active_cards > 0 and passed_gates == 0:
        triggers.append("expired_no_backup")
        log.warning("MONITORING: active champions exist but none passed gates")

    # 4. Rolling holdout (90 days since last full pipeline)
    last_deploy = db_scalar(
        "SELECT MAX(created_at) FROM orchestrator_events WHERE event_type = 'deploying_complete'"
    )
    if last_deploy:
        days_since_deploy = (datetime.now(timezone.utc) - last_deploy).days
        if days_since_deploy >= ROLLING_HOLDOUT_DAYS:
            triggers.append(f"rolling_holdout={days_since_deploy}d>={ROLLING_HOLDOUT_DAYS}d")
            log.warning("MONITORING: %d days since last deploy, rolling holdout triggered",
                        days_since_deploy)

    # 5. PySR complete (check if background PySR produced new candidates)
    global _pysr_pid
    if _pysr_pid is not None:
        try:
            os.kill(_pysr_pid, 0)
            # Still running
        except OSError:
            # PySR finished
            triggers.append("pysr_complete")
            log.info("MONITORING: PySR background search completed")
            _pysr_pid = None
            db_log_event("pysr_background_complete", None, {})

    if triggers:
        log.info("MONITORING: triggers fired: %s -> restarting pipeline", triggers)
        db_transition(
            State.IDLE,
            {"triggers": triggers, "triggered_at": datetime.now(timezone.utc).isoformat()},
            "monitoring_triggered",
        )
        return State.IDLE

    log.info("MONITORING: no triggers, sleeping...")
    db_set_state(State.MONITORING, {
        "last_check": datetime.now(timezone.utc).isoformat(),
        "factor_age_days": (datetime.now(timezone.utc) - oldest_pool).days if oldest_pool else None,
        "active_cards": active_cards,
        "passed_gates": passed_gates,
    })
    return None  # stay in MONITORING


# ---------------------------------------------------------------------------
# State dispatch
# ---------------------------------------------------------------------------
STATE_HANDLERS = {
    State.IDLE: handle_idle,
    State.ARENA1_FAST: handle_arena1_fast,
    State.ARENA2: handle_arena2,
    State.ARENA3: handle_arena3,
    State.GATING: handle_gating,
    State.DEPLOYING: handle_deploying,
    State.MONITORING: handle_monitoring,
}


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def main() -> None:
    log.info("=" * 60)
    log.info("Zangetsu V3.2 Orchestrator starting")
    log.info("DB: %s", DB_DSN.replace(DB_DSN.split("password=")[1].split()[0], "***")
             if "password=" in DB_DSN else DB_DSN)
    log.info("Strategies: %s", STRATEGIES_DIR)
    log.info("=" * 60)

    # Crash recovery: read current state from DB
    current_state, details = db_read_state()
    log.info("Resuming from state: %s", current_state.value)
    log.info("Details: %s", json.dumps(details, default=str)[:200])
    db_log_event("orchestrator_start", None, {
        "resumed_state": current_state.value,
        "resumed_details": details,
    })

    while True:
        try:
            handler = STATE_HANDLERS.get(current_state)
            if handler is None:
                log.error("Unknown state: %s, resetting to IDLE", current_state)
                db_transition(State.IDLE, {"error": f"unknown_state_{current_state}"}, "reset_to_idle")
                current_state = State.IDLE
                continue

            next_state = handler(details)

            if next_state is not None:
                current_state = next_state
                # Re-read details from DB (handler already wrote them)
                current_state, details = db_read_state()
                # No sleep on state transition — continue immediately
                continue
            else:
                # Handler returned None = stay in current state, sleep and retry
                sleep_s = LOOP_SLEEP_S
                if current_state == State.MONITORING:
                    sleep_s = 3600  # 60 min in MONITORING
                log.info("Sleeping %ds (state=%s)...", sleep_s, current_state.value)
                time.sleep(sleep_s)
                # Re-read state (could be externally changed)
                current_state, details = db_read_state()

        except KeyboardInterrupt:
            log.info("Keyboard interrupt — shutting down gracefully")
            db_log_event("orchestrator_shutdown", None, {"reason": "keyboard_interrupt"})
            break
        except Exception as e:
            log.error("Unhandled error in state %s: %s\n%s",
                      current_state.value, e, traceback.format_exc())
            db_log_event("orchestrator_error", None, {
                "state": current_state.value,
                "error": str(e),
                "traceback": traceback.format_exc()[-1000:],
            })
            # Don't change state on error — retry after sleep
            time.sleep(LOOP_SLEEP_S)
            current_state, details = db_read_state()


if __name__ == "__main__":
    main()
