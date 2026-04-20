import os
#!/usr/bin/env python3
"""V10 IC Distribution Analysis - per-regime, per-symbol.
Computes: IC histogram, DSR (Deflated Sharpe Ratio), p-value distribution.
"""
import sys, os
from pathlib import Path
sys.path.insert(0, '/home/j13/j13-ops')

import numpy as np
import psycopg2
import psycopg2.extras
from scipy.stats import norm

DSN = os.environ.get('ZV5_DSN',
    os.environ['ZV5_DSN'])


def deflated_sharpe_ratio(observed_sr: float, sr_std: float, num_trials: int, T: int,
                           skew: float = 0.0, kurt: float = 3.0) -> float:
    """Bailey-Lopez de Prado DSR. Returns probability observed SR is genuine."""
    if num_trials <= 1 or sr_std < 1e-10 or T <= 1:
        return 0.0
    gamma = 0.5772156649015329
    z = norm.ppf(1 - 1.0 / num_trials)
    sr0 = sr_std * ((1 - gamma) * z + gamma * norm.ppf(1 - 1.0 / (num_trials * np.e)))
    sr_var = (1 - skew * observed_sr + ((kurt - 1) / 4) * observed_sr ** 2) / (T - 1)
    return float(norm.cdf((observed_sr - sr0) / max(np.sqrt(sr_var), 1e-10)))


def main():
    conn = psycopg2.connect(DSN)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    print("# V10 Alpha IC Distribution Analysis\n")

    # Overall IC distribution
    cur.execute("""
        SELECT arena1_score FROM champion_pipeline
        WHERE engine_hash = 'zv5_v10_alpha' AND card_status IN ('DISCOVERED', 'SEED')
    """)
    ics = np.array([r['arena1_score'] for r in cur.fetchall() if r['arena1_score'] is not None])

    if len(ics) == 0:
        print("No alphas to analyze yet.")
        return

    print(f"## Overall IC Statistics ({len(ics)} alphas)")
    print(f"- Mean: {ics.mean():.4f}")
    print(f"- Std: {ics.std():.4f}")
    print(f"- Median: {np.median(ics):.4f}")
    print(f"- p25: {np.percentile(ics, 25):.4f}")
    print(f"- p75: {np.percentile(ics, 75):.4f}")
    print(f"- p90: {np.percentile(ics, 90):.4f}")
    print(f"- Max: {ics.max():.4f}")
    print(f"- Count IC > 0.02: {(ics > 0.02).sum()}")
    print(f"- Count IC > 0.05: {(ics > 0.05).sum()}")

    # DSR for top alpha
    num_trials = len(ics)
    T = 100000  # assumed bar count
    top_sr = ics.max() * np.sqrt(T)  # rough conversion
    dsr = deflated_sharpe_ratio(top_sr, ics.std() * np.sqrt(T), num_trials, T)
    print(f"\n## Deflated Sharpe Ratio (top alpha)")
    print(f"- Observed SR (scaled): {top_sr:.2f}")
    print(f"- Num trials: {num_trials}")
    print(f"- DSR: {dsr:.4f}")
    print(f"- Significance: {'PASS (>0.95)' if dsr > 0.95 else 'FAIL - need more alphas or higher IC'}")

    # Per-regime breakdown
    print("\n## Per-Regime IC Distribution")
    cur.execute("""
        SELECT regime,
               COUNT(*) as n,
               AVG(arena1_score) as mean_ic,
               STDDEV(arena1_score) as std_ic,
               PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY arena1_score) as p90_ic
        FROM champion_pipeline
        WHERE engine_hash = 'zv5_v10_alpha' AND card_status IN ('DISCOVERED', 'SEED')
        GROUP BY regime ORDER BY n DESC
    """)
    rows = cur.fetchall()
    print("| Regime | N | Mean IC | Std IC | p90 IC |")
    print("|--------|---|---------|--------|--------|")
    for r in rows:
        std_val = r['std_ic'] if r['std_ic'] else 0.0
        print(f"| {r['regime']} | {r['n']} | {r['mean_ic']:.4f} | {std_val:.4f} | {r['p90_ic']:.4f} |")

    conn.close()


if __name__ == "__main__":
    main()
