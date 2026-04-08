#!/usr/bin/env python3
"""Phase B: Full stage 2 rerun — dynamic 2-parallel across 11 regimes."""
import sys, os, time, subprocess, json, logging

sys.path.insert(0, os.path.expanduser("~/j13-ops/zangetsu_v3"))
os.chdir(os.path.expanduser("~/j13-ops/zangetsu_v3"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [PhaseB] %(message)s")
log = logging.getLogger("phase_b")

# Launch order: descending by train bar count
REGIMES_ORDERED = [
    "BULL_TREND",       # 448080
    "BEAR_TREND",       # 386023
    "SQUEEZE",          # 202560
    "TOPPING",          # 186480
    "CONSOLIDATION",    # 182880
    "BOTTOMING",        # 180000
    "BULL_PULLBACK",    # 127920
    "BEAR_RALLY",       # 124320
    "CHOPPY_VOLATILE",  # 75600
    "DISTRIBUTION",     # 33840
    "ACCUMULATION",     # 33360
]

MAX_PARALLEL = 2
GENS = 1000

def launch_regime(regime_name):
    """Launch arena3 for one regime as subprocess."""
    cmd = [
        sys.executable, "scripts/arena3_regime.py",
        "--regime", regime_name,
        "--gens", str(GENS),
    ]
    log_path = f"logs/phase_b_{regime_name}.log"
    log_file = open(log_path, "w")
    proc = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        cwd=os.path.expanduser("~/j13-ops/zangetsu_v3"),
        env={**os.environ},
    )
    return proc, log_file, log_path


def main():
    log.info(f"=== Phase B: {len(REGIMES_ORDERED)} regimes, {GENS} gens, {MAX_PARALLEL}-parallel ===")

    queue = list(REGIMES_ORDERED)
    active = {}  # regime -> (proc, log_file, log_path, start_time)
    completed = {}  # regime -> (returncode, duration, log_path)

    t0 = time.monotonic()

    while queue or active:
        # Fill slots
        while queue and len(active) < MAX_PARALLEL:
            regime = queue.pop(0)
            proc, lf, lp = launch_regime(regime)
            active[regime] = (proc, lf, lp, time.monotonic())
            log.info(f"LAUNCHED: {regime} (pid={proc.pid}) — {len(queue)} remaining in queue")

        # Check for completions
        finished = []
        for regime, (proc, lf, lp, t_start) in active.items():
            ret = proc.poll()
            if ret is not None:
                lf.close()
                duration = time.monotonic() - t_start
                completed[regime] = (ret, duration, lp)
                log.info(f"COMPLETED: {regime} — exit={ret}, duration={duration/60:.1f}min")

                # Parse RESULT from log
                try:
                    with open(lp) as f:
                        for line in f:
                            if "RESULT:" in line or "SAVED:" in line:
                                log.info(f"  {line.strip()}")
                except:
                    pass

                finished.append(regime)

        for r in finished:
            del active[r]

        if active:
            time.sleep(5)

    total_time = time.monotonic() - t0

    log.info(f"\n{'='*60}")
    log.info(f"  PHASE B COMPLETE — {total_time/60:.1f} minutes total")
    log.info(f"{'='*60}")
    log.info(f"{'Regime':>20s} {'Exit':>5s} {'Duration':>10s} {'Log':>40s}")
    for regime in REGIMES_ORDERED:
        ret, dur, lp = completed.get(regime, (-1, 0, "?"))
        log.info(f"{regime:>20s} {ret:>5d} {dur/60:>8.1f}min  {lp}")

    failures = [r for r, (ret, _, _) in completed.items() if ret != 0]
    if failures:
        log.warning(f"FAILURES: {failures}")
    else:
        log.info("ALL 11 REGIMES COMPLETED SUCCESSFULLY")


if __name__ == "__main__":
    main()
