#!/usr/bin/env python3
"""Arena 3 V3.2+F8: Regime-conditional backtest on FULL timeline.

System B canonical implementation with:
  - DB logging to search_candidates + indicator_candidates (ported from System A)
  - Trade-level fitness (W6)
  - F8 engine versioning
  - CLI --regime arg for orchestrator integration
"""
import sys, os, time, json, subprocess, logging, argparse
import numpy as np
sys.path.insert(0, os.path.expanduser("~/j13-ops/zangetsu_v3"))
os.chdir(os.path.expanduser("~/j13-ops/zangetsu_v3"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("arena3rc")

DB = os.environ.get("ZV3_DB_DSN",
    "dbname=zangetsu user=zangetsu password=9c424966bebb05a42966186bb22d7480 host=127.0.0.1 port=5432")
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
COST_BPS = {"BTCUSDT": 4, "ETHUSDT": 4, "BNBUSDT": 5, "SOLUSDT": 6, "XRPUSDT": 7, "DOGEUSDT": 8}
TAKER_BPS = {s: v * 2.5 for s, v in COST_BPS.items()}
GENERATIONS = 1000
N_SETS_TO_SCREEN = 10
N_TOP_SETS = 3
N_IND = 15
GRACE_PERIOD = 6

REGIME_IDS = {
    "BULL_TREND": 0, "BEAR_TREND": 1, "BULL_PULLBACK": 2, "BEAR_RALLY": 3,
    "DISTRIBUTION": 4, "ACCUMULATION": 5, "CONSOLIDATION": 6,
    "CHOPPY_VOLATILE": 7, "SQUEEZE": 8, "TOPPING": 9, "BOTTOMING": 10,
}

WORKER = r'''
import sys, os, time, json, hashlib, uuid, numpy as np, polars as pl, psycopg2
import psycopg2.extras
sys.path.insert(0, os.path.expanduser("~/j13-ops/zangetsu_v3"))
os.chdir(os.path.expanduser("~/j13-ops/zangetsu_v3"))
import zangetsu_indicators as zi
from zangetsu_v3.regime.rule_labeler import label_symbol, resample_to_4h
from backtest_regime import (
    backtest_regime_conditional, compute_fold_fitness, compute_regime_fitness,
    extract_trades_from_backtest, compute_trade_level_metrics,
)
from scripts.engine_version import compute_engine_hash

DB = "{db}"
REGIME = "{regime}"
RID = {rid}
SYMBOLS = {symbols}
COST = {cost}
TAKER = {taker}
GENS = {gens}
N_SETS = {n_sets}
N_TOP = {n_top}
N_IND = {n_ind}
SEED = {seed}
GRACE = {grace}

# [F8] Lock engine hash at WORKER start
ENGINE_HASH = compute_engine_hash()
POOL_VERSION = None

def get_db():
    return psycopg2.connect(DB)

def load_1m(sym):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT timestamp,open,high,low,close,volume FROM ohlcv_1m WHERE symbol=%s ORDER BY timestamp", (sym,))
    rows = cur.fetchall(); conn.close()
    df = pl.DataFrame(rows, schema=["ts","open","high","low","close","volume"], orient="row")
    return df.with_columns(
        pl.from_epoch(pl.col("ts"), time_unit="ms").alias("timestamp"),
        pl.col("open").cast(pl.Float64), pl.col("high").cast(pl.Float64),
        pl.col("low").cast(pl.Float64), pl.col("close").cast(pl.Float64),
        pl.col("volume").cast(pl.Float64),
    ).drop("ts").sort("timestamp")

def compute_trade_fitness(pnl, pos, exit_type, close, regime_labels, target_regime, pos_frac, maker_bps, taker_bps):
    """Trade-level fitness: trade_sharpe x WR x log1p(tpd). Returns (fitness, metrics_dict)."""
    in_regime = regime_labels == target_regime
    regime_bars = int(np.sum(in_regime))
    if regime_bars < 1440:
        return -999.0, {{}}

    trades = extract_trades_from_backtest(pnl, pos, close, pos_frac, maker_bps, taker_bps, exit_type)
    if len(trades) < 2:
        return -999.0, {{"n_trades": len(trades)}}

    years = regime_bars / (1440.0 * 365.0)
    trades_fmt = [{{"pnl": t["net_pnl"], "cost": 0.0, "funding": 0.0,
                    "position_size": t["position_size"]}} for t in trades]
    m = compute_trade_level_metrics(trades_fmt, years)

    n_days = max(regime_bars / 1440.0, 1e-6)
    tpd = len(trades) / n_days

    m["tpd"] = tpd

    # Note: sharpe > 0 is implied by expectancy > 0 (mean > 0).
    # No separate sharpe gate needed. Do not re-add.
    # n_trades >= 80 on TRAIN ensures roughly 30+ trades on HOLDOUT
    # given the 70/30 train/holdout split. Matches V4-FINAL A1 gate.
    if m["expectancy"] <= 0 or m["n_trades"] < 80:
        return -999.0, m

    fitness = float(m["trade_level_sharpe"] * m["win_rate"] * np.log1p(max(tpd, 0.1)))
    return fitness, m

def classify_strategy(metrics):
    """Classify strategy by alpha source profile."""
    expectancy = metrics.get("expectancy", 0)
    if expectancy <= 0:
        return None, None
    wr = metrics.get("win_rate", 0.5)
    avg_win = metrics.get("avg_win", 0)
    avg_loss = metrics.get("avg_loss", 0)
    if avg_loss < 1e-9:
        return "SYMMETRIC_WINNER", float("inf")
    ratio = avg_win / avg_loss
    if wr > 0.52 and 0.8 <= ratio <= 1.5:
        return "SYMMETRIC_WINNER", ratio
    if wr < 0.50 and ratio > 1.5:
        return "ASYMMETRIC_WINNER", ratio
    if 0.50 <= wr <= 0.52:
        return "BALANCED_WINNER", ratio
    if 1.5 <= ratio <= 2.0 and 0.45 <= wr <= 0.55:
        return "BALANCED_WINNER", ratio
    return "MARGINAL_WINNER", ratio

# Load data
print(f"[{{REGIME}}] Loading full timeline...")
t0 = time.monotonic()

btc_df = load_1m("BTCUSDT")
btc_labels, _, btc_4h = label_symbol(btc_df)
btc_close = btc_df["close"].to_numpy().astype(np.float64)
n_total = len(btc_close)
n_train = int(n_total * 0.7)
train_labels = btc_labels[:n_train]
train_close = btc_close[:n_train]

o4 = btc_4h["open"].to_numpy().astype(np.float64)
h4 = btc_4h["high"].to_numpy().astype(np.float64)
l4 = btc_4h["low"].to_numpy().astype(np.float64)
c4 = btc_4h["close"].to_numpy().astype(np.float64)
v4 = btc_4h["volume"].to_numpy().astype(np.float64)

fwd = np.zeros(len(c4))
for hz in [1, 3, 5]:
    fr = np.zeros(len(c4)); fr[:-hz] = (c4[hz:] - c4[:-hz]) / c4[:-hz]
    fwd += fr
fwd /= 3

regime_bars_count = np.sum(train_labels == RID)
print(f"[{{REGIME}}] Loaded in {{time.monotonic()-t0:.1f}}s, total={{n_total}}, train={{n_train}}, regime_bars={{regime_bars_count}}")
print(f"[{{REGIME}}] Engine hash: {{ENGINE_HASH[:20]}}...")

if regime_bars_count < 1440:
    print(f"RESULT:{{REGIME}}:fitness=-999:pnl=0:trades=0:wr=0:sharpe=0:sharpe_pt=0:regime_bars={{regime_bars_count}}")
    sys.exit(0)

# [W3] Screen indicator sets + register in indicator_candidates
print(f"[{{REGIME}}] Screening {{N_SETS}} indicator sets (seed={{SEED}})...")
labels_4h = btc_labels[::240][:len(c4)]
regime_mask_4h = labels_4h == RID
POOL_VERSION = time.strftime("%Y-%m-%d %H:%M:%S+00:00")

set_results = []
for set_idx in range(N_SETS):
    engine = zi.IndicatorEngine(seed=SEED + set_idx * 1000)
    cj = engine.generate_random_set(N_IND)
    try:
        matrix, names = zi.compute_indicator_set(o4, h4, l4, c4, v4, cj)
    except: continue
    matrix = np.nan_to_num(matrix, nan=0.0)
    if regime_mask_4h.sum() < 100: continue
    corrs = []
    for j in range(matrix.shape[1]):
        col = matrix[:, j]
        if np.std(col[regime_mask_4h]) < 1e-10: continue
        r = np.abs(np.corrcoef(col[regime_mask_4h], fwd[regime_mask_4h])[0, 1])
        if np.isfinite(r): corrs.append(r)
    if corrs:
        set_id = str(uuid.uuid4())
        avg_corr = float(np.mean(corrs))
        set_results.append((avg_corr, cj, matrix, names, set_id))
        # [W3] Write indicator set to indicator_candidates
        try:
            conn = get_db()
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO indicator_candidates
                    (regime, set_id, indicators, n_indicators, avg_abs_corr, screening_pass, engine_hash)
                    VALUES (%s, %s, %s::jsonb, %s, %s, TRUE, %s)
                    ON CONFLICT (set_id) DO NOTHING
                """, (REGIME, set_id, cj, N_IND, avg_corr, ENGINE_HASH))
            conn.commit(); conn.close()
        except Exception as e:
            print(f"[{{REGIME}}] WARNING: indicator_candidates INSERT failed: {{e}}")

set_results.sort(key=lambda x: -x[0])
if not set_results:
    print(f"RESULT:{{REGIME}}:fitness=-999:pnl=0:trades=0:wr=0:sharpe=0:sharpe_pt=0:regime_bars={{regime_bars_count}}")
    sys.exit(1)

print(f"[{{REGIME}}] Top {{min(N_TOP, len(set_results))}} sets: " +
    ", ".join(f"corr={{r[0]:.4f}}" for r in set_results[:N_TOP]))

# CMA-MAE search on FULL TRAIN TIMELINE
best_overall_fitness = -999
best_overall_pnl = 0
best_overall_wr = 0
best_overall_sharpe = 0
best_overall_sharpe_pt = 0
best_overall_trades = 0
best_overall_expectancy = 0
best_w = None
med = None
mad = None
best_indicator_set_id = None
best_indicator_configs = None
best_indicator_names = None

for set_rank, (set_corr, cj, matrix_4h, names, set_id) in enumerate(set_results[:N_TOP]):
    fm = np.nan_to_num(matrix_4h, nan=0.0)
    n_train_4h = n_train // 240
    train_fm = fm[:n_train_4h]
    _med = np.median(train_fm[50:], axis=0)
    _mad = np.median(np.abs(train_fm[50:] - _med), axis=0)
    _mad[_mad < 1e-10] = 1.0
    fm_norm = np.clip((fm - _med) / _mad, -5, 5)

    fm_1m_train = np.repeat(fm_norm[:n_train_4h], 240, axis=0)
    n_eval = len(fm_1m_train)
    n_factors = fm_1m_train.shape[1]
    eval_close = train_close[:n_eval]
    eval_labels = train_labels[:n_eval]
    rng = np.random.default_rng(SEED + set_rank)

    best_fitness = -999
    best_w_set = None
    maker_f = float(COST.get("BTCUSDT", 4))
    taker_f = float(TAKER.get("BTCUSDT", 10))

    for gen in range(GENS):
        w = rng.standard_normal(n_factors) * 0.3
        signal = fm_1m_train @ w
        s = np.std(signal) + 1e-12

        pnl, pos, exit_type = backtest_regime_conditional(
            signal, eval_close, eval_labels.astype(np.int8), np.int8(RID),
            0.7 * s, 0.3 * s, 2.0, 0.05, 480, GRACE,
            maker_f, taker_f, 0.0001,
        )

        # [W6] Trade-level fitness
        fitness, m = compute_trade_fitness(
            pnl, pos, exit_type, eval_close, eval_labels, RID,
            0.05, maker_f, taker_f,
        )

        strat_class, wl_ratio = classify_strategy(m) if m else (None, None)

        # [W4] Persist candidate to search_candidates
        try:
            conn = get_db()
            with conn.cursor() as cur:
                # Legacy per-bar sharpe for comparison
                _, wr_bar, tpd_bar, trades_bar = compute_regime_fitness(pnl, eval_labels, RID)
                in_regime = eval_labels == RID
                active = pnl[in_regime]; active = active[active != 0]
                if len(active) > 10:
                    active_py = len(active) / (np.sum(in_regime) / (1440.0 * 365.0))
                    sharpe_bar = float(np.mean(active) / (np.std(active) + 1e-15) * np.sqrt(active_py))
                else:
                    sharpe_bar = 0.0

                cur.execute("""
                    INSERT INTO search_candidates
                    (regime, generation, pool_version, weights_json, params_json,
                     trimmed_min_fitness, median_sharpe, median_win_rate,
                     median_tpd, median_hold_bars, rung, survived_rung0, is_elite,
                     sharpe_per_trade, expectancy_per_trade,
                     indicator_set_id, indicator_set_dim, search_seed, engine_hash,
                     strategy_class, avg_win_loss_ratio)
                    VALUES (%s,%s,%s,%s::jsonb,%s::jsonb,
                            %s,%s,%s,%s,%s,%s,%s,%s,
                            %s,%s,%s,%s,%s,%s,
                            %s,%s)
                """, (
                    REGIME, gen, POOL_VERSION,
                    json.dumps(w.tolist()),
                    json.dumps({{"entry_thr": 0.7*s, "exit_thr": 0.3*s, "stop_mult": 2.0,
                                "pos_frac": 0.05, "hold_max": 480}}),
                    fitness,  # -999 for gated candidates, real value for viable
                    sharpe_bar if sharpe_bar != 0 else None,
                    m.get("win_rate") if m else None,
                    m.get("tpd") if m else None,
                    None,
                    0, True, False,
                    m.get("trade_level_sharpe") if m else None,
                    m.get("expectancy") if m else None,
                    set_id, n_factors, SEED + set_rank, ENGINE_HASH,
                    strat_class, wl_ratio,
                ))
            conn.commit(); conn.close()
        except Exception as e:
            print(f"[{{REGIME}}] WARNING: search_candidates INSERT gen={{gen}}: {{e}}")

        if fitness > best_fitness:
            best_fitness = fitness
            best_w_set = w.copy()

        if (gen + 1) % 200 == 0:
            print(f"[{{REGIME}}] set#{{set_rank}} gen={{gen+1}} fitness={{best_fitness:.6f}}")

    if best_w_set is not None and best_fitness > best_overall_fitness:
        signal_full = fm_1m_train @ best_w_set
        s = np.std(signal_full) + 1e-12
        pnl_full, pos_full, et_full = backtest_regime_conditional(
            signal_full, eval_close, eval_labels.astype(np.int8), np.int8(RID),
            0.7 * s, 0.3 * s, 2.0, 0.05, 480, GRACE,
            maker_f, taker_f, 0.0001,
        )

        fit_final, m_final = compute_trade_fitness(
            pnl_full, pos_full, et_full, eval_close, eval_labels, RID,
            0.05, maker_f, taker_f,
        )

        dp = [np.sum(pnl_full[d:d+1440]) for d in range(0, len(pnl_full), 1440)]
        sharpe_daily = float(np.mean(dp) / (np.std(dp) + 1e-10) * np.sqrt(365)) if len(dp) > 10 else 0

        best_overall_fitness = fit_final
        best_overall_pnl = float(np.sum(pnl_full))
        best_overall_wr = m_final.get("win_rate", 0)
        best_overall_sharpe = sharpe_daily
        best_overall_sharpe_pt = m_final.get("trade_level_sharpe", 0)
        best_overall_trades = m_final.get("n_trades", 0)
        best_overall_expectancy = m_final.get("expectancy", 0)
        best_w = best_w_set.copy()
        med = _med.copy()
        mad = _mad.copy()
        best_indicator_set_id = set_id
        best_indicator_configs = cj
        best_indicator_names = list(names)

        champ_class, champ_wl_ratio = classify_strategy(m_final) if m_final else (None, None)

        # [W4] Champion as is_elite=TRUE
        try:
            conn = get_db()
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO search_candidates
                    (regime, generation, pool_version, weights_json, params_json,
                     trimmed_min_fitness, median_sharpe, median_win_rate,
                     median_tpd, median_hold_bars, rung, survived_rung0, is_elite,
                     sharpe_per_trade, expectancy_per_trade,
                     indicator_set_id, indicator_set_dim, search_seed, engine_hash,
                     strategy_class, avg_win_loss_ratio)
                    VALUES (%s,%s,%s,%s::jsonb,%s::jsonb,
                            %s,%s,%s,%s,%s,%s,%s,%s,
                            %s,%s,%s,%s,%s,%s,
                            %s,%s)
                """, (
                    REGIME, -1, POOL_VERSION,
                    json.dumps(best_w.tolist()),
                    json.dumps({{"entry_thr_mult": 0.7, "exit_thr_mult": 0.3,
                                "stop_mult": 2.0, "pos_frac": 0.05, "hold_max": 480}}),
                    fit_final, sharpe_daily, best_overall_wr,
                    m_final.get("tpd"), None, -1, True, True,
                    best_overall_sharpe_pt, best_overall_expectancy,
                    best_indicator_set_id, len(best_w), SEED + set_rank, ENGINE_HASH,
                    champ_class, champ_wl_ratio,
                ))
            conn.commit(); conn.close()
        except Exception as e:
            print(f"[{{REGIME}}] WARNING: champion INSERT: {{e}}")

    print(f"[{{REGIME}}] set#{{set_rank}} DONE: fitness={{best_fitness:.6f}}")

print(f"RESULT:{{REGIME}}:fitness={{best_overall_fitness:.6f}}:pnl={{best_overall_pnl:.6f}}:trades={{best_overall_trades}}:wr={{best_overall_wr:.3f}}:sharpe={{best_overall_sharpe:.2f}}:sharpe_pt={{best_overall_sharpe_pt:.4f}}:regime_bars={{regime_bars_count}}")

# [F8] Final engine hash integrity check
final_hash = compute_engine_hash()
if final_hash != ENGINE_HASH:
    print(f"CRITICAL: engine modified mid-search! start={{ENGINE_HASH}} end={{final_hash}}")
    sys.exit(2)

# SAVE CHAMPION TO FILE
if best_overall_fitness > -999 and best_w is not None:
    _save_data = {{
        "version": "3.2+F8",
        "regime": REGIME, "regime_id": RID,
        "indicator_configs": json.loads(best_indicator_configs) if best_indicator_configs else [],
        "indicator_names": best_indicator_names or [],
        "indicator_set_id": best_indicator_set_id,
        "weights": best_w.tolist(),
        "normalization": {{"medians": med.tolist(), "mads": mad.tolist()}},
        "entry_thr_mult": 0.7, "exit_thr_mult": 0.3,
        "stop_mult": 2.0, "pos_frac": 0.05, "hold_max": 480,
        "grace_period": GRACE,
        "cost_bps": COST, "taker_bps": TAKER,
        "seed": SEED, "symbols": SYMBOLS,
        "engine_hash": ENGINE_HASH,
        "train": {{
            "fitness": float(best_overall_fitness),
            "pnl": float(best_overall_pnl),
            "trades": int(best_overall_trades),
            "wr": float(best_overall_wr),
            "sharpe_daily": float(best_overall_sharpe),
            "sharpe_per_trade": float(best_overall_sharpe_pt),
            "expectancy_per_trade": float(best_overall_expectancy),
            "regime_bars": int(regime_bars_count),
        }},
    }}
    _sdir = os.path.expanduser(f"~/j13-ops/zangetsu_v3/strategies/{{REGIME}}_expert")
    os.makedirs(_sdir, exist_ok=True)
    _spath = os.path.join(_sdir, "card.json")
    with open(_spath, "w") as _sf:
        json.dump(_save_data, _sf, indent=2)
    _cs = hashlib.sha256(json.dumps(_save_data, sort_keys=True).encode()).hexdigest()
    with open(os.path.join(_sdir, "checksum.sha256"), "w") as _sf:
        _sf.write(_cs)
    print(f"SAVED:{{REGIME}}:{{_spath}}")
'''


def launch_regime(regime_name, gens_override=None):
    rid = REGIME_IDS[regime_name]
    seed = hash(regime_name) % (2**63)
    gens = gens_override if gens_override is not None else GENERATIONS
    script = WORKER.format(
        db=DB, regime=regime_name, rid=rid,
        symbols=json.dumps(SYMBOLS), cost=json.dumps(COST_BPS),
        taker=json.dumps(TAKER_BPS),
        gens=gens, n_sets=N_SETS_TO_SCREEN, n_top=N_TOP_SETS,
        n_ind=N_IND, seed=seed, grace=GRACE_PERIOD,
    )
    return subprocess.Popen(
        [sys.executable, "-u", "-c", script],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        env={**os.environ, "ZV3_DB_DSN": DB}
    )


def main():
    parser = argparse.ArgumentParser(description="Arena 3 V3.2+F8 Regime Search")
    parser.add_argument("--regime", type=str, default=None,
                        help="Run single regime (e.g. BULL_TREND). If omitted, run all.")
    parser.add_argument("--gens", type=int, default=None,
                        help="Override generation count (default: 1000)")
    args = parser.parse_args()

    if args.regime:
        if args.regime not in REGIME_IDS:
            log.error(f"Unknown regime: {args.regime}. Valid: {list(REGIME_IDS.keys())}")
            sys.exit(1)
        regimes = [args.regime]
    else:
        regimes = list(REGIME_IDS.keys())

    log.info("=== Arena 3 V3.2+F8: Regime-Conditional Full-Timeline Backtest ===")
    log.info(f"Regimes={regimes}, Gens={args.gens or GENERATIONS}, Sets={N_SETS_TO_SCREEN}, "
             f"Top={N_TOP_SETS}, Ind={N_IND}, Grace={GRACE_PERIOD}")

    all_results = {}
    for regime_name in regimes:
        log.info(f"\n=== Running: {regime_name} ===")
        proc = launch_regime(regime_name, args.gens)
        stdout, _ = proc.communicate(timeout=7200)
        for line in stdout.strip().split("\n"):
            if line.startswith("RESULT:") or line.startswith("SAVED:") or line.startswith("CRITICAL:"):
                log.info(f"  {line}")
                if line.startswith("RESULT:"):
                    parts = {}
                    for p in line.split(":")[2:]:
                        if "=" in p:
                            k, v = p.split("=", 1)
                            parts[k] = v
                    all_results[regime_name] = parts
            elif "[" in line and ("gen=" in line or "Top" in line or "Loading" in line
                                  or "DONE" in line or "Engine" in line or "WARNING" in line):
                log.info(f"  {line}")

    log.info("\n=== SUMMARY ===")
    log.info(f"{'Regime':20s} {'Fitness':>10s} {'PnL':>10s} {'Trades':>8s} {'WR':>6s} {'SR_daily':>8s} {'SR_trade':>10s}")
    for name in regimes:
        r = all_results.get(name, {})
        log.info(f"{name:20s} {r.get('fitness','?'):>10s} {r.get('pnl','?'):>10s} "
                 f"{r.get('trades','?'):>8s} {r.get('wr','?'):>6s} "
                 f"{r.get('sharpe','?'):>8s} {r.get('sharpe_pt','?'):>10s}")

    saved = sum(1 for name in regimes
                if os.path.exists(os.path.expanduser(f"~/j13-ops/zangetsu_v3/strategies/{name}_expert/card.json")))
    log.info(f"\n{saved}/{len(regimes)} cards saved")


if __name__ == "__main__":
    main()
