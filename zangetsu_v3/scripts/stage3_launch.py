#!/usr/bin/env python3
"""Stage 3: Reproducibility gate — 9 regimes × 3 seeds, dynamic 2-parallel.

Uses arena3_regime.py WORKER with 500 gens per run.
Median run becomes canonical champion.
"""
import sys, os, time, json, subprocess, logging
import numpy as np

sys.path.insert(0, os.path.expanduser("~/j13-ops/zangetsu_v3"))
os.chdir(os.path.expanduser("~/j13-ops/zangetsu_v3"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [Stage3] %(message)s")
log = logging.getLogger("stage3")

from scripts.engine_version import compute_engine_hash

REGIMES = [
    "BULL_PULLBACK", "BEAR_RALLY", "BULL_TREND", "BEAR_TREND",
    "TOPPING", "CHOPPY_VOLATILE", "BOTTOMING", "SQUEEZE", "CONSOLIDATION",
]

GENS = 500
MAX_PARALLEL = 4
SEED_OFFSETS = [1, 2, 3]

ENGINE_HASH = compute_engine_hash()
log.info(f"F8 engine hash: {ENGINE_HASH[:20]}...")


def launch_repro_run(regime, seed_offset):
    """Launch one reproducibility run."""
    base_seed = hash(regime) % (2**63)
    seed = base_seed + seed_offset * 777777
    cmd = [
        sys.executable, "scripts/arena3_regime.py",
        "--regime", regime, "--gens", str(GENS),
    ]
    log_path = f"logs/stage3_{regime}_seed{seed_offset}.log"
    log_file = open(log_path, "w")
    env = {**os.environ, "ZV3_REPRO_SEED": str(seed)}
    proc = subprocess.Popen(
        cmd, stdout=log_file, stderr=subprocess.STDOUT,
        cwd=os.path.expanduser("~/j13-ops/zangetsu_v3"), env=env,
    )
    return proc, log_file, log_path, seed


def parse_result(log_path):
    """Parse RESULT line from log."""
    try:
        with open(log_path) as f:
            for line in f:
                if "RESULT:" in line:
                    # Extract from log line
                    result_part = line[line.index("RESULT:"):]
                    parts = {}
                    for p in result_part.strip().split(":")[2:]:
                        if "=" in p:
                            k, v = p.split("=", 1)
                            parts[k] = v
                    return {
                        "fitness": float(parts.get("fitness", -999)),
                        "pnl": float(parts.get("pnl", 0)),
                        "trades": int(parts.get("trades", 0)),
                        "wr": float(parts.get("wr", 0)),
                        "sharpe": float(parts.get("sharpe", 0)),
                        "sharpe_pt": float(parts.get("sharpe_pt", 0)),
                    }
    except Exception as e:
        log.error(f"Parse failed for {log_path}: {e}")
    return None


def main():
    log.info(f"=== Stage 3: {len(REGIMES)} regimes × 3 seeds, {GENS} gens ===")

    # Build task queue: (regime, seed_offset)
    tasks = []
    for regime in REGIMES:
        for offset in SEED_OFFSETS:
            tasks.append((regime, offset))

    active = {}  # key -> (proc, log_file, log_path, seed, regime, offset, t_start)
    completed = {}  # (regime, offset) -> result_dict
    t0 = time.monotonic()

    while tasks or active:
        # Fill slots
        while tasks and len(active) < MAX_PARALLEL:
            regime, offset = tasks.pop(0)
            proc, lf, lp, seed = launch_repro_run(regime, offset)
            key = f"{regime}_s{offset}"
            active[key] = (proc, lf, lp, seed, regime, offset, time.monotonic())
            log.info(f"LAUNCHED: {key} (pid={proc.pid}, seed={seed}) — {len(tasks)} remaining")

        # Check completions
        finished = []
        for key, (proc, lf, lp, seed, regime, offset, ts) in active.items():
            ret = proc.poll()
            if ret is not None:
                lf.close()
                dur = time.monotonic() - ts
                result = parse_result(lp)
                completed[(regime, offset)] = result
                status = f"fitness={result['fitness']:.4f}" if result else "PARSE_FAIL"
                log.info(f"DONE: {key} — {status}, {dur/60:.1f}min")
                finished.append(key)

        for k in finished:
            del active[k]

        if active:
            time.sleep(5)

    total_time = time.monotonic() - t0
    log.info(f"\nAll runs complete in {total_time/60:.1f} min")

    # ═══ REPRODUCIBILITY GATES ═══
    log.info(f"\n{'='*60}")
    log.info(f"  STAGE 3 REPRODUCIBILITY REPORT")
    log.info(f"{'='*60}")

    regime_results = {}
    for regime in REGIMES:
        runs = []
        for offset in SEED_OFFSETS:
            r = completed.get((regime, offset))
            if r and r["fitness"] > -999:
                runs.append(r)

        if len(runs) < 3:
            log.warning(f"\n{regime}: INCOMPLETE ({len(runs)}/3 viable runs)")
            regime_results[regime] = {"pass": False, "reason": f"only {len(runs)}/3 viable runs"}
            continue

        pnls = [r["pnl"] for r in runs]
        sharpes = [r["sharpe_pt"] for r in runs]
        trades = [r["trades"] for r in runs]

        # R1: PnL direction
        r1 = all(p > 0 for p in pnls)
        r1_str = "PASS" if r1 else "FAIL"

        # R2: Sharpe CV < 0.50
        s_mean = np.mean(sharpes)
        s_std = np.std(sharpes)
        cv = s_std / (abs(s_mean) + 1e-10)
        r2 = cv < 0.50
        r2_str = "PASS" if r2 else "FAIL"

        # R3: min > 0.5 * max
        s_min, s_max = min(sharpes), max(sharpes)
        r3 = s_min > 0.5 * s_max if s_max > 0 else False
        r3_ratio = s_min / s_max if s_max > 0 else 0
        r3_str = "PASS" if r3 else "FAIL"

        # R4: trade counts within 2x
        t_min, t_max = min(trades), max(trades)
        r4 = t_max <= 2 * t_min if t_min > 0 else False
        r4_str = "PASS" if r4 else "FAIL"

        all_pass = r1 and r2 and r3 and r4

        # Median run
        median_idx = np.argsort(sharpes)[1]  # middle of 3

        log.info(f"\n{regime}:")
        for i, r in enumerate(runs):
            marker = " ← MEDIAN" if i == median_idx else ""
            log.info(f"  Run {i+1}: pnl={r['pnl']:.4f} sharpe_pt={r['sharpe_pt']:.4f} trades={r['trades']}{marker}")
        log.info(f"  R1 PnL direction: {r1_str} ({'all positive' if r1 else 'MIXED'})")
        log.info(f"  R2 Sharpe CV:     {r2_str} (CV={cv:.4f})")
        log.info(f"  R3 min/max ratio: {r3_str} (min={s_min:.4f}, max={s_max:.4f}, ratio={r3_ratio:.4f})")
        log.info(f"  R4 trade count:   {r4_str} (min={t_min}, max={t_max})")
        if all_pass:
            log.info(f"  === ALL GATES PASS ===")
            log.info(f"  Champion: Run {median_idx+1} (median sharpe_pt={sharpes[median_idx]:.4f})")
        else:
            log.info(f"  === REPRO FAIL ===")

        regime_results[regime] = {
            "pass": all_pass,
            "runs": runs,
            "cv": cv,
            "min_max_ratio": r3_ratio,
            "median_idx": median_idx,
            "median_sharpe_pt": sharpes[median_idx],
            "r1": r1, "r2": r2, "r3": r3, "r4": r4,
        }

    # Summary
    passed = [r for r, v in regime_results.items() if v["pass"]]
    failed = [r for r, v in regime_results.items() if not v["pass"]]
    log.info(f"\n{'='*60}")
    log.info(f"  SUMMARY: {len(passed)} PASS, {len(failed)} FAIL")
    log.info(f"  PASS: {passed}")
    log.info(f"  FAIL: {failed}")
    log.info(f"  Total time: {total_time/60:.1f} min")
    log.info(f"{'='*60}")

    # Save results
    with open("logs/stage3_results.json", "w") as f:
        # Convert for JSON serialization
        out = {}
        for r, v in regime_results.items():
            v2 = {k: v2 for k, v2 in v.items() if k != "runs"}
            if "runs" in v:
                v2["runs"] = v["runs"]
            out[r] = v2
        json.dump(out, f, indent=2, default=str)
    log.info("Results saved to logs/stage3_results.json")


if __name__ == "__main__":
    main()
