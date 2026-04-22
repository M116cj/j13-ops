#!/usr/bin/env python3
"""Volume C6 Wilson WR Floor Trial (0.52 -> 0.48) — telemetry-only re-scoring.

Input: existing volume_active.jsonl (deterministic critical path; no rerun needed).
Output:
  - Table A (from prior counterfactual audit, for reference)
  - NEW survivor detail table (this trial)
  - Boundary pool 0.48 <= wilson_wr < 0.52 detail
  - Classification: Acceptable / Marginal / Fragile per j13 2026-04-22
  - Final verdict per YES/MIXED/NO thresholds

Gate thresholds under this trial:
  val_net_pnl       strict > 0        (unchanged from production)
  val_sharpe        >= 0.3            (unchanged)
  val_wilson_wr     >= 0.48           (RELAXED from 0.52)
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median

# Trial thresholds
WILSON_WR_NEW_FLOOR = 0.48
WILSON_WR_OLD_FLOOR = 0.52
VAL_NEG_PNL_STRICT = 0.0
VAL_LOW_SHARPE_FLOOR = 0.3


def load_rows(path):
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def reached_val(r):
    v = r.get("val") or {}
    return isinstance(v, dict) and bool(v) and "net_pnl" in v


def current_survivor(r):
    return bool(r.get("survived_a1"))


def passes_old_gates(r):
    """Production gates: wilson >= 0.52."""
    if not reached_val(r):
        return False
    v = r["val"]
    if (v.get("trades", 0) or 0) < 15:
        return False
    return (
        float(v["net_pnl"]) > VAL_NEG_PNL_STRICT
        and float(v["sharpe"]) >= VAL_LOW_SHARPE_FLOOR
        and float(v.get("wilson_wr", 0.0)) >= WILSON_WR_OLD_FLOOR
    )


def passes_new_gates(r):
    """Trial gates: wilson >= 0.48, others unchanged."""
    if not reached_val(r):
        return False
    v = r["val"]
    if (v.get("trades", 0) or 0) < 15:
        return False
    return (
        float(v["net_pnl"]) > VAL_NEG_PNL_STRICT
        and float(v["sharpe"]) >= VAL_LOW_SHARPE_FLOOR
        and float(v.get("wilson_wr", 0.0)) >= WILSON_WR_NEW_FLOOR
    )


def classify(r):
    """Acceptable / Marginal / Fragile per j13 2026-04-22 rules."""
    v = r["val"]
    t = r.get("train") or {}
    val_pnl = float(v["net_pnl"])
    val_shp = float(v["sharpe"])
    val_wwr = float(v.get("wilson_wr", 0.0))
    train_pnl = float(t.get("net_pnl", 0.0))
    train_shp = float(t.get("sharpe", 0.0))

    # Fragile first — any axis violation makes it Fragile regardless.
    if val_pnl <= 0 or val_shp <= 0 or val_wwr < WILSON_WR_NEW_FLOOR:
        return "Fragile"
    # At this point val_pnl > 0, val_shp > 0, val_wwr >= 0.48.
    if train_pnl > 0 and train_shp > 0:
        return "Acceptable"
    return "Marginal"


def main():
    src = Path(sys.argv[1])
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    rows = load_rows(src)
    total = len(rows)
    reached = [r for r in rows if reached_val(r)]
    existing_survivors = [r for r in rows if current_survivor(r)]
    # Production re-verification (should match existing_survivors 1:1)
    prod_pass = [r for r in rows if passes_old_gates(r)]
    # New trial survivors
    trial_pass = [r for r in rows if passes_new_gates(r)]
    # NEW under trial that were NOT survivors under production.
    existing_keys = {(r["alpha_hash"], r["symbol"]) for r in existing_survivors}
    new_survivors = [r for r in trial_pass
                     if (r["alpha_hash"], r["symbol"]) not in existing_keys]
    # Boundary pool: 0.48 <= wilson_wr < 0.52
    boundary_pool = [r for r in reached
                     if WILSON_WR_NEW_FLOOR <= float(r["val"].get("wilson_wr", 0.0)) < WILSON_WR_OLD_FLOOR]

    # Classify new survivors
    classifications = {r["alpha_hash"] + ":" + r["symbol"]: classify(r) for r in new_survivors}
    class_counter = Counter(classifications.values())

    # Train↔val sign consistency across new survivors
    def _sgn(x): return 1 if x > 0 else (-1 if x < 0 else 0)
    consistencies = []
    for r in new_survivors:
        v = r["val"]; t = r.get("train") or {}
        pnl_agree = _sgn(float(v["net_pnl"])) == _sgn(float(t.get("net_pnl", 0.0)))
        shp_agree = _sgn(float(v["sharpe"])) == _sgn(float(t.get("sharpe", 0.0)))
        consistencies.append({
            "alpha_hash": r["alpha_hash"], "symbol": r["symbol"],
            "pnl_agree": pnl_agree, "shp_agree": shp_agree,
        })
    pnl_consistency_rate = (sum(1 for c in consistencies if c["pnl_agree"])
                            / max(1, len(consistencies)))
    shp_consistency_rate = (sum(1 for c in consistencies if c["shp_agree"])
                            / max(1, len(consistencies)))
    both_consistency_rate = (sum(1 for c in consistencies if c["pnl_agree"] and c["shp_agree"])
                             / max(1, len(consistencies)))

    # Aggregate quality of new survivors
    def _m(xs, fn): return round(float(fn(xs)), 4) if xs else None
    ns_val_pnl = [float(r["val"]["net_pnl"]) for r in new_survivors]
    ns_val_shp = [float(r["val"]["sharpe"]) for r in new_survivors]
    ns_val_wwr = [float(r["val"].get("wilson_wr", 0.0)) for r in new_survivors]
    ns_symbols = Counter(r["symbol"] for r in new_survivors)

    # ============================================================
    # Outputs
    # ============================================================
    print("=" * 70)
    print("Volume C6 Wilson WR Floor Trial  0.52 -> 0.48")
    print("telemetry-only re-scoring of existing volume_active.jsonl")
    print("=" * 70)
    print(f"input cells total         : {total}")
    print(f"reached val               : {len(reached)}")
    print(f"existing survivors (prod) : {len(existing_survivors)}  "
          f"(re-verified via old-gate predicate: {len(prod_pass)})")
    print(f"trial survivors (0.48)    : {len(trial_pass)}")
    print(f"NEW under trial (Δ)       : {len(new_survivors)}")
    print(f"boundary pool (0.48..0.52): {len(boundary_pool)}")

    # ---- A. NEW survivor detail table
    print("\n" + "=" * 70)
    print("A. NEW SURVIVORS DETAIL (trial - prod)")
    print("=" * 70)
    hdr = f"{'#':<3}{'symbol':<14}{'train_pnl':>10}{'train_shp':>10}{'val_pnl':>10}{'val_shp':>10}{'val_wwr':>10}  class             formula"
    print(hdr)
    print("-" * len(hdr))
    ns_detail = []
    for i, r in enumerate(sorted(new_survivors, key=lambda x: (x["symbol"], -float(x["val"]["wilson_wr"])))):
        v = r["val"]; t = r.get("train") or {}
        cls = classifications[r["alpha_hash"] + ":" + r["symbol"]]
        row = {
            "symbol": r["symbol"],
            "formula": r["formula"],
            "train_net_pnl": round(float(t.get("net_pnl", 0.0)), 4),
            "train_sharpe": round(float(t.get("sharpe", 0.0)), 4),
            "val_net_pnl": round(float(v["net_pnl"]), 4),
            "val_sharpe": round(float(v["sharpe"]), 4),
            "val_wilson_wr": round(float(v.get("wilson_wr", 0.0)), 4),
            "val_trades": int(v.get("trades", 0)),
            "classification": cls,
            "alpha_hash": r["alpha_hash"],
        }
        ns_detail.append(row)
        print(f"{i+1:<3}{r['symbol']:<14}{row['train_net_pnl']:>10.4f}{row['train_sharpe']:>10.4f}"
              f"{row['val_net_pnl']:>10.4f}{row['val_sharpe']:>10.4f}{row['val_wilson_wr']:>10.4f}  "
              f"{cls:<17} {r['formula']}")

    # ---- B. Boundary pool
    print("\n" + "=" * 70)
    print("B. BOUNDARY POOL  0.48 <= wilson_wr < 0.52  (real rescue candidates)")
    print("=" * 70)
    hdr2 = f"{'#':<3}{'symbol':<14}{'train_pnl':>10}{'train_shp':>10}{'val_pnl':>10}{'val_shp':>10}{'val_wwr':>10}  passes_new  class             formula"
    print(hdr2)
    print("-" * len(hdr2))
    boundary_detail = []
    for i, r in enumerate(sorted(boundary_pool, key=lambda x: (x["symbol"], -float(x["val"]["wilson_wr"])))):
        v = r["val"]; t = r.get("train") or {}
        passes = passes_new_gates(r)
        cls = classify(r)
        row = {
            "symbol": r["symbol"],
            "formula": r["formula"],
            "train_net_pnl": round(float(t.get("net_pnl", 0.0)), 4),
            "train_sharpe": round(float(t.get("sharpe", 0.0)), 4),
            "val_net_pnl": round(float(v["net_pnl"]), 4),
            "val_sharpe": round(float(v["sharpe"]), 4),
            "val_wilson_wr": round(float(v.get("wilson_wr", 0.0)), 4),
            "val_trades": int(v.get("trades", 0)),
            "passes_new": passes,
            "classification": cls,
            "alpha_hash": r["alpha_hash"],
        }
        boundary_detail.append(row)
        print(f"{i+1:<3}{r['symbol']:<14}{row['train_net_pnl']:>10.4f}{row['train_sharpe']:>10.4f}"
              f"{row['val_net_pnl']:>10.4f}{row['val_sharpe']:>10.4f}{row['val_wilson_wr']:>10.4f}  "
              f"{str(passes):<10}  {cls:<17} {r['formula']}")

    # ---- Quality summary
    print("\n" + "=" * 70)
    print("NEW SURVIVOR QUALITY SUMMARY")
    print("=" * 70)
    total_new = len(new_survivors) or 1
    print(f"count                  : {len(new_survivors)}")
    print(f"Acceptable             : {class_counter.get('Acceptable', 0)} ({class_counter.get('Acceptable', 0)/total_new:.1%})")
    print(f"Marginal               : {class_counter.get('Marginal', 0)} ({class_counter.get('Marginal', 0)/total_new:.1%})")
    print(f"Fragile                : {class_counter.get('Fragile', 0)} ({class_counter.get('Fragile', 0)/total_new:.1%})")
    print(f"breadth (# symbols)    : {len(ns_symbols)}")
    print(f"symbols                : {dict(ns_symbols)}")
    print(f"mean val_net_pnl       : {_m(ns_val_pnl, mean)}")
    print(f"median val_net_pnl     : {_m(ns_val_pnl, median)}")
    print(f"mean val_sharpe        : {_m(ns_val_shp, mean)}")
    print(f"median val_sharpe      : {_m(ns_val_shp, median)}")
    print(f"mean val_wilson_wr     : {_m(ns_val_wwr, mean)}")
    print(f"median val_wilson_wr   : {_m(ns_val_wwr, median)}")
    print(f"train<->val sign consistency:")
    print(f"  pnl agree            : {pnl_consistency_rate:.1%}")
    print(f"  sharpe agree         : {shp_consistency_rate:.1%}")
    print(f"  both agree           : {both_consistency_rate:.1%}")

    # ---- C. Final verdict
    print("\n" + "=" * 70)
    print("C. FINAL DECISION")
    print("=" * 70)
    n = len(new_survivors)
    breadth = len(ns_symbols)
    acceptable_rate = class_counter.get("Acceptable", 0) / max(1, n)
    mean_shp = _m(ns_val_shp, mean) or 0
    mean_pnl = _m(ns_val_pnl, mean) or 0
    # consistency: use PNL sign as the primary per j13 rules ("train<->val sign consistency >= 80%")
    consistency = pnl_consistency_rate

    yes_conditions = {
        "new_survivors_ge_3": n >= 3,
        "breadth_ge_3": breadth >= 3,
        "acceptable_rate_ge_70pct": acceptable_rate >= 0.70,
        "mean_val_sharpe_gt_0": mean_shp > 0,
        "mean_val_net_pnl_gt_0": mean_pnl > 0,
        "train_val_consistency_ge_80pct": consistency >= 0.80,
    }
    all_yes = all(yes_conditions.values())

    no_conditions = {
        "new_survivors_eq_0": n == 0,
        "majority_fragile": class_counter.get("Fragile", 0) > (n / 2) if n else False,
        "mean_shp_le_0": mean_shp <= 0,
        "mean_pnl_le_0": mean_pnl <= 0,
        "consistency_lt_50pct": consistency < 0.50,
    }
    any_no = any(no_conditions.values())

    if all_yes:
        verdict = "YES — worth trial"
    elif any_no:
        verdict = "NO — keep 0.52"
    else:
        verdict = "MIXED — borderline"

    print(f"new_survivors             : {n}    (YES requires >= 3)")
    print(f"breadth                   : {breadth}    (YES requires >= 3)")
    print(f"Acceptable rate           : {acceptable_rate:.1%}  (YES requires >= 70%)")
    print(f"mean val_sharpe           : {mean_shp}  (YES requires > 0)")
    print(f"mean val_net_pnl          : {mean_pnl}  (YES requires > 0)")
    print(f"train-val pnl consistency : {consistency:.1%}  (YES requires >= 80%)")
    print(f"YES condition breakdown   : {yes_conditions}")
    print(f"NO  condition breakdown   : {no_conditions}")
    print()
    print(f"Wilson WR floor 0.52 -> 0.48 is: {verdict}")

    bundle = {
        "trial": {
            "old_floor": WILSON_WR_OLD_FLOOR,
            "new_floor": WILSON_WR_NEW_FLOOR,
            "other_gates_unchanged": True,
        },
        "population": {
            "total": total,
            "reached_val": len(reached),
            "existing_survivors": len(existing_survivors),
            "prod_pass_reverified": len(prod_pass),
            "trial_pass": len(trial_pass),
            "new_survivors": n,
            "boundary_pool_size": len(boundary_pool),
        },
        "new_survivors_detail": ns_detail,
        "boundary_pool_detail": boundary_detail,
        "classification_counts": dict(class_counter),
        "quality_summary": {
            "breadth": breadth,
            "symbols": dict(ns_symbols),
            "mean_val_net_pnl": _m(ns_val_pnl, mean),
            "median_val_net_pnl": _m(ns_val_pnl, median),
            "mean_val_sharpe": _m(ns_val_shp, mean),
            "median_val_sharpe": _m(ns_val_shp, median),
            "mean_val_wilson_wr": _m(ns_val_wwr, mean),
            "median_val_wilson_wr": _m(ns_val_wwr, median),
            "pnl_consistency": pnl_consistency_rate,
            "sharpe_consistency": shp_consistency_rate,
            "both_consistency": both_consistency_rate,
        },
        "yes_conditions": yes_conditions,
        "no_conditions": no_conditions,
        "verdict": verdict,
    }

    if out_path:
        out_path.write_text(json.dumps(bundle, indent=2))
        print(f"\nwrote: {out_path}")


if __name__ == "__main__":
    main()
