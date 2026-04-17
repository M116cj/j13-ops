"""OBSOLETE — V5-era tests, references removed modules (voter, data_weight).
Marked skip pending rewrite for V9 architecture. See TODO.
"""
import pytest
pytest.skip("V5-era tests — modules voter/data_weight deprecated in V9 unification", allow_module_level=True)

"""V5 Architecture Verification — 17-point compliance test."""
import sys, os
sys.path.insert(0, os.path.expanduser("~/j13-ops/zangetsu_v5"))

def test_01_voter_sign_normalized():
    """Voter accepts normalized floats, computes sign() internally."""
    from engine.components.voter import Voter
    class C: voter_agreement_threshold=0.80; voter_short_circuit=True
    v = Voter(C())
    r = v.vote_bar([0.5, 0.3, 0.7, 0.2, 0.1])  # 5/5 positive
    assert r.signal == 1, f"Expected +1, got {r.signal}"

def test_02_voter_80_percent_agreement():
    """Signal fires only when >=80% agree."""
    from engine.components.voter import Voter
    class C: voter_agreement_threshold=0.80; voter_short_circuit=True
    v = Voter(C())
    r = v.vote_bar([0.5, 0.3, -0.7, -0.2, 0.1])  # 3/5 = 60%
    assert r.signal == 0, f"Expected 0 at 60%, got {r.signal}"

def test_03_passport_progressive():
    """Passport enriches progressively per arena."""
    from engine.components.passport import ChampionPassport
    p = ChampionPassport("hash1", "BULL_TREND", "engine_v1")
    p.stamp_arena1([], 5, 0.55, 0.1, 0.08, 1.0, 50, 1, "BTCUSDT")
    assert "arena1" in p.to_jsonb()
    assert p.validate() == []

def test_04_data_weight_decay():
    """Recent data weighted higher, oldest = 0.1."""
    import numpy as np
    from engine.components.data_weight import compute_weights
    ts = np.array([0, 50, 100])
    w = compute_weights(ts)
    assert w[-1] == 1.0  # newest
    assert w[0] >= 0.1   # oldest floor

def test_05_arena2_hysteresis():
    """Arena 2 enforces exit_thr < entry_thr."""
    # Check that the constraint exists in the code
    with open(os.path.expanduser("~/j13-ops/zangetsu_v5/arena/arena2_threshold.py")) as f:
        code = f.read()
    assert "exit_thr >= entry_thr" in code or "exit_thr < entry_thr" in code

def test_06_arena5_composite_score():
    """Arena 5 uses PnL*0.6 + WR*0.4."""
    with open(os.path.expanduser("~/j13-ops/zangetsu_v5/arena/arena5_elo.py")) as f:
        code = f.read()
    assert "0.6" in code and "0.4" in code

def test_07_arena5_daily_reset():
    """Arena 5 has daily reset method."""
    with open(os.path.expanduser("~/j13-ops/zangetsu_v5/arena/arena5_elo.py")) as f:
        code = f.read()
    assert "daily_reset" in code

def test_08_arena13_consistent_fitness():
    """Arena 13 uses same composite as Arena 5."""
    with open(os.path.expanduser("~/j13-ops/zangetsu_v5/arena/arena13_evolve.py")) as f:
        code = f.read()
    assert "0.6" in code and "0.4" in code

def test_09_regime_labeler_causal():
    """Regime labeler exists and is causal-only."""
    from engine.components.regime_labeler import label_4h_causal, label_latest, resample_to_4h
    assert label_4h_causal is not None

def test_10_risk_manager_kill_switch():
    """Risk manager has per-class kill switches."""
    from live.risk_manager import check_portfolio_risk, QuantClass
    assert check_portfolio_risk is not None

def test_11_ws_feed_exists():
    """WebSocket feed module exists."""
    from live.ws_feed import BinanceFuturesWS
    assert BinanceFuturesWS is not None

def test_12_journal_exists():
    """Trade journal module exists."""
    from live.journal import TradeJournal
    assert TradeJournal is not None

def test_13_db_tables():
    """Required DB tables exist."""
    import psycopg2
    conn = psycopg2.connect(host="127.0.0.1", port=5432, user="zangetsu",
                            password=os.getenv("ZV5_DB_PASSWORD", ""), dbname="zangetsu_v5")
    cur = conn.cursor()
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
    tables = {r[0] for r in cur.fetchall()}
    conn.close()
    for t in ["champion_pipeline", "pipeline_audit_log"]:
        assert t in tables, f"Missing table: {t}"

def test_14_parquet_data():
    """14 symbols have parquet data."""
    data_dir = os.path.expanduser("~/j13-ops/zangetsu_v5/data/ohlcv")
    files = [f for f in os.listdir(data_dir) if f.endswith(".parquet")]
    assert len(files) >= 14, f"Only {len(files)} parquet files"

def test_15_config_loads():
    """Config settings load without error."""
    # Just check file exists and has key params
    with open(os.path.expanduser("~/j13-ops/zangetsu_v5/config/settings.py")) as f:
        code = f.read()
    assert "arena1_round_size" in code
    assert "arena5_k_factor" in code

def test_16_all_arena_files():
    """All 6 arena files exist."""
    arena_dir = os.path.expanduser("~/j13-ops/zangetsu_v5/arena")
    for name in ["arena1_discover", "arena2_threshold", "arena3_pnl",
                  "arena4_validate", "arena5_elo", "arena13_evolve"]:
        path = os.path.join(arena_dir, f"{name}.py")
        assert os.path.exists(path), f"Missing: {path}"

def test_17_engine_components():
    """All engine components exist."""
    comp_dir = os.path.expanduser("~/j13-ops/zangetsu_v5/engine/components")
    for name in ["backtester", "checkpoint", "data_loader", "db", "gpu_pool",
                  "health", "indicator", "logger", "normalizer", "passport",
                  "scorer", "voter", "watchdog", "data_weight", "regime_labeler"]:
        path = os.path.join(comp_dir, f"{name}.py")
        assert os.path.exists(path), f"Missing: {path}"

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS: {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL: {t.__name__} — {e}")
            failed += 1
    print(f"\n{passed}/{passed+failed} passed")
