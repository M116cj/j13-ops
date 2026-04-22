#!/usr/bin/env python3
"""Val-Gate Counterfactual Truth Audit — post-processing analyzer.

Produces three tables (A/B/C) and answers the 4 required questions for
task "Volume C6 Val-Gate Counterfactual Truth Audit" (2026-04-22 extension).

A1 gate thresholds (from scripts/cold_start_hand_alphas.py + shadow_control_suite.py):
  val_neg_pnl     : val.net_pnl   > 0     (fail if <= 0)
  val_low_sharpe  : val.sharpe    >= 0.3  (fail if < 0.3)
  val_low_wr      : val.wilson_wr >= 0.52 (fail if < 0.52)
Eval order in scs short-circuits val_neg_pnl -> val_low_sharpe -> val_low_wr.

Approach:
  - Only cells that reached val contribute to val-gate counterfactuals
    (train-blocked cells cannot be unlocked by val-gate changes).
  - For each val-reaching cell we re-evaluate all three gate predicates
    independently from the raw val block (net_pnl, sharpe, wilson_wr).
  - Then we enumerate 8 counterfactuals G0..G7 (bitmask over which gates
    are "removed").

Outputs:
  - report/counterfactual_tables.json (machine-readable)
  - stdout: formatted tables
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median

VAL_NEG_PNL_THR = 0.0      # fail if net_pnl <= 0
VAL_LOW_SHARPE_THR = 0.3   # fail if sharpe  < 0.3
VAL_LOW_WR_THR = 0.52      # fail if wilson_wr < 0.52


def load_rows(path):
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def classify_cell(r):
    """Return a dict describing each cell's val-gate failure profile.
    Only meaningful for cells that reached val (val block non-empty).
    """
    val = r.get("val") or {}
    train = r.get("train") or {}
    reached_val = isinstance(val, dict) and bool(val) and "net_pnl" in val
    out = {
        "alpha_hash": r.get("alpha_hash"),
        "formula": r.get("formula"),
        "symbol": r.get("symbol"),
        "first_gate_reached": r.get("first_gate_reached"),
        "survived_a1": bool(r.get("survived_a1")),
        "reached_val": reached_val,
    }
    if reached_val:
        net = float(val.get("net_pnl", 0.0))
        shr = float(val.get("sharpe", 0.0))
        wwr = float(val.get("wilson_wr", 0.0)) if "wilson_wr" in val else None
        # Some older runs may miss wilson_wr; fall back to raw win_rate if so.
        if wwr is None and "win_rate" in val:
            wwr = float(val["win_rate"])
        fail_neg = net <= VAL_NEG_PNL_THR
        fail_shp = shr < VAL_LOW_SHARPE_THR
        fail_wr = (wwr is not None) and (wwr < VAL_LOW_WR_THR)
        val_few_trades = (val.get("trades", 0) or 0) < 15
        out.update({
            "val_net_pnl": net,
            "val_sharpe": shr,
            "val_wilson_wr": wwr,
            "val_trades": val.get("trades"),
            "val_win_rate": val.get("win_rate"),
            "train_net_pnl": train.get("net_pnl"),
            "train_sharpe": train.get("sharpe"),
            "train_win_rate": train.get("win_rate"),
            "train_trades": train.get("trades"),
            "fail_val_neg_pnl": fail_neg,
            "fail_val_low_sharpe": fail_shp,
            "fail_val_low_wr": fail_wr,
            "val_few_trades": val_few_trades,
        })
    return out


def classify_quality(cell):
    """Classify an (unlocked) cell into clearly_viable / borderline / likely_junk
    based on train-val consistency + absolute metrics.

    Every val-reaching cell already passed train_net_pnl > 0 by construction,
    so train positivity is a given; we focus on the val expression.

    Rules:
      clearly_viable:
        val_net_pnl > 0 AND val_sharpe > 0 AND (val_wilson_wr >= 0.50 if known)
        => Train and val align positive on ALL three axes.
      likely_junk:
        val_net_pnl <= -0.05 OR val_sharpe <= -0.5
        => Val-side catastrophic break; train positivity was overfit/regime.
      borderline:
        everything else (positive train but marginal or mixed val expression).
    """
    net = cell.get("val_net_pnl")
    shr = cell.get("val_sharpe")
    wwr = cell.get("val_wilson_wr")
    if net is None or shr is None:
        return "unknown"
    if (net > 0) and (shr > 0) and (wwr is None or wwr >= 0.50):
        return "clearly_viable"
    if (net <= -0.05) or (shr <= -0.5):
        return "likely_junk"
    return "borderline"


def gate_set(flags):
    """flags = (fail_neg, fail_shp, fail_wr) -> frozenset of failed gate names."""
    s = set()
    if flags[0]:
        s.add("val_neg_pnl")
    if flags[1]:
        s.add("val_low_sharpe")
    if flags[2]:
        s.add("val_low_wr")
    return frozenset(s)


def main():
    src = Path(sys.argv[1])
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    rows = load_rows(src)
    cells = [classify_cell(r) for r in rows]

    total = len(cells)
    train_blocked = [c for c in cells if not c["reached_val"]]
    reached_val = [c for c in cells if c["reached_val"]]
    existing_survivors = [c for c in reached_val if c["survived_a1"]]

    # Val-blocked pool = reached val but did NOT survive (failed >=1 val gate).
    val_blocked = [c for c in reached_val if not c["survived_a1"]]

    print(f"\n==================== INPUT SUMMARY ====================")
    print(f"total cells            : {total}")
    print(f"train-blocked          : {len(train_blocked)}")
    print(f"reached val            : {len(reached_val)}")
    print(f"  existing A1 survivors: {len(existing_survivors)}")
    print(f"  val-blocked          : {len(val_blocked)}")

    # ============================================================
    # Table A — Gate attribution
    # ============================================================
    # Classify each val-blocked cell by WHICH subset of val gates it fails.
    attribution_counter = Counter()
    for c in val_blocked:
        gs = gate_set((c["fail_val_neg_pnl"], c["fail_val_low_sharpe"], c["fail_val_low_wr"]))
        if not gs:
            # Passed all three val gates but also not survived? Likely val_few_trades or val_eval_err.
            key = "no_val_gate_failed (edge)"
        else:
            key = "|".join(sorted(gs))
        attribution_counter[key] += 1

    # Unique / overlap slicing
    unique_neg = sum(1 for c in val_blocked
                     if c["fail_val_neg_pnl"]
                     and not c["fail_val_low_sharpe"]
                     and not c["fail_val_low_wr"])
    unique_shp = sum(1 for c in val_blocked
                     if c["fail_val_low_sharpe"]
                     and not c["fail_val_neg_pnl"]
                     and not c["fail_val_low_wr"])
    unique_wr = sum(1 for c in val_blocked
                    if c["fail_val_low_wr"]
                    and not c["fail_val_neg_pnl"]
                    and not c["fail_val_low_sharpe"])
    any_neg = sum(1 for c in val_blocked if c["fail_val_neg_pnl"])
    any_shp = sum(1 for c in val_blocked if c["fail_val_low_sharpe"])
    any_wr = sum(1 for c in val_blocked if c["fail_val_low_wr"])
    overlap_neg_shp = sum(1 for c in val_blocked
                          if c["fail_val_neg_pnl"] and c["fail_val_low_sharpe"]
                          and not c["fail_val_low_wr"])
    overlap_neg_wr = sum(1 for c in val_blocked
                         if c["fail_val_neg_pnl"] and c["fail_val_low_wr"]
                         and not c["fail_val_low_sharpe"])
    overlap_shp_wr = sum(1 for c in val_blocked
                         if c["fail_val_low_sharpe"] and c["fail_val_low_wr"]
                         and not c["fail_val_neg_pnl"])
    overlap_all3 = sum(1 for c in val_blocked
                       if c["fail_val_neg_pnl"] and c["fail_val_low_sharpe"]
                       and c["fail_val_low_wr"])
    passes_all_val_gates = sum(1 for c in val_blocked
                               if not c["fail_val_neg_pnl"]
                               and not c["fail_val_low_sharpe"]
                               and not c["fail_val_low_wr"])
    table_a = {
        "total_val_blocked": len(val_blocked),
        "by_exclusive_gate": {
            "val_neg_pnl_only": unique_neg,
            "val_low_sharpe_only": unique_shp,
            "val_low_wr_only": unique_wr,
        },
        "by_overlap": {
            "neg_pnl_AND_low_sharpe_only": overlap_neg_shp,
            "neg_pnl_AND_low_wr_only": overlap_neg_wr,
            "low_sharpe_AND_low_wr_only": overlap_shp_wr,
            "all_three": overlap_all3,
        },
        "any_gate_hit": {
            "any_val_neg_pnl": any_neg,
            "any_val_low_sharpe": any_shp,
            "any_val_low_wr": any_wr,
        },
        "val_blocked_that_pass_all_three_gates": passes_all_val_gates,
        "full_attribution": dict(attribution_counter),
    }

    print(f"\n==================== TABLE A — Gate Attribution (val-blocked only) ====================")
    print(f"val-blocked total             : {len(val_blocked)}")
    print(f"  EXCLUSIVE val_neg_pnl       : {unique_neg}")
    print(f"  EXCLUSIVE val_low_sharpe    : {unique_shp}")
    print(f"  EXCLUSIVE val_low_wr        : {unique_wr}")
    print(f"  neg_pnl + low_sharpe only   : {overlap_neg_shp}")
    print(f"  neg_pnl + low_wr only       : {overlap_neg_wr}")
    print(f"  low_sharpe + low_wr only    : {overlap_shp_wr}")
    print(f"  all three                   : {overlap_all3}")
    print(f"ANY hits:")
    print(f"  any val_neg_pnl             : {any_neg}")
    print(f"  any val_low_sharpe          : {any_shp}")
    print(f"  any val_low_wr              : {any_wr}")
    print(f"val-blocked that pass all 3   : {passes_all_val_gates}  (edge: few_trades or eval_err)")

    # ============================================================
    # Table B — Counterfactual survivors under G0..G7
    # ============================================================
    # G0..G7 = 3-bit mask over (neg_pnl, low_sharpe, low_wr), bit=1 means
    # the gate is REMOVED (counterfactually).
    scenarios = [
        ("G0", (False, False, False), "current (no gate removed) - baseline"),
        ("G1", (True,  False, False), "remove val_neg_pnl only"),
        ("G2", (False, False, True ), "remove val_low_wr only"),
        ("G3", (False, True,  False), "remove val_low_sharpe only"),
        ("G4", (True,  False, True ), "remove val_neg_pnl + val_low_wr"),
        ("G5", (True,  True,  False), "remove val_neg_pnl + val_low_sharpe"),
        ("G6", (False, True,  True ), "remove val_low_sharpe + val_low_wr"),
        ("G7", (True,  True,  True ), "remove all three"),
    ]
    existing_sym = Counter(c["symbol"] for c in existing_survivors)
    existing_keys = {(c["alpha_hash"], c["symbol"]) for c in existing_survivors}
    table_b = []
    unlocked_by_scenario = {}

    for sid, (rm_neg, rm_shp, rm_wr), desc in scenarios:
        # Under this counterfactual, a val-reaching cell counts as survivor iff
        # none of the NOT-removed gates fail.
        new_surv = []
        for c in reached_val:
            # Exclude val_few_trades (always lethal, not a counterfactual target).
            if c.get("val_few_trades"):
                continue
            # Gate checks (True means fails this gate; if removed, we treat as pass)
            fails = (
                (c["fail_val_neg_pnl"] and not rm_neg),
                (c["fail_val_low_sharpe"] and not rm_shp),
                (c["fail_val_low_wr"] and not rm_wr),
            )
            if not any(fails):
                new_surv.append(c)
        new_keys = {(c["alpha_hash"], c["symbol"]) for c in new_surv}
        new_syms = Counter(c["symbol"] for c in new_surv)
        overlap_with_existing = len(new_keys & existing_keys)
        net_new = len(new_keys - existing_keys)
        unlock_rate = (net_new / max(1, len(val_blocked)))
        entry = {
            "id": sid,
            "description": desc,
            "counterfactual_survivors": len(new_surv),
            "net_new_vs_G0": net_new,
            "symbols_with_new_survivor": sum(1 for s in new_syms if new_syms[s] >= 1),
            "overlap_with_existing_survivors": overlap_with_existing,
            "unlock_rate_over_val_blocked": round(unlock_rate, 4),
        }
        table_b.append(entry)
        unlocked_by_scenario[sid] = [c for c in new_surv
                                     if (c["alpha_hash"], c["symbol"]) not in existing_keys]

    print(f"\n==================== TABLE B — Counterfactual Survivors ====================")
    print(f"{'G':<4}{'desc':<42}{'surv':>5}{'net_new':>9}{'syms':>6}{'overlap':>8}{'unlock_rate':>12}")
    for e in table_b:
        print(f"{e['id']:<4}{e['description']:<42}{e['counterfactual_survivors']:>5}"
              f"{e['net_new_vs_G0']:>9}{e['symbols_with_new_survivor']:>6}"
              f"{e['overlap_with_existing_survivors']:>8}{e['unlock_rate_over_val_blocked']:>12.4f}")

    # ============================================================
    # Table C — Unlocked quality (per scenario)
    # ============================================================
    table_c = {}
    print(f"\n==================== TABLE C — Unlocked Quality ====================")
    print(f"{'G':<4}{'unlocked':>9}{'viable':>8}{'borderline':>11}{'junk':>6}"
          f"{'mean_val_pnl':>14}{'med_val_pnl':>13}{'mean_val_shp':>14}{'med_val_shp':>13}"
          f"{'mean_wwr':>10}{'med_wwr':>10}")
    for sid, new_cells in unlocked_by_scenario.items():
        if not new_cells:
            table_c[sid] = {"unlocked": 0,
                            "viable": 0, "borderline": 0, "junk": 0}
            continue
        quals = [classify_quality(c) for c in new_cells]
        qc = Counter(quals)
        pnl = [c["val_net_pnl"] for c in new_cells if c.get("val_net_pnl") is not None]
        shp = [c["val_sharpe"] for c in new_cells if c.get("val_sharpe") is not None]
        wwr = [c["val_wilson_wr"] for c in new_cells if c.get("val_wilson_wr") is not None]
        def _m(xs, fn): return round(float(fn(xs)), 4) if xs else None
        table_c[sid] = {
            "unlocked": len(new_cells),
            "clearly_viable": qc.get("clearly_viable", 0),
            "borderline": qc.get("borderline", 0),
            "likely_junk": qc.get("likely_junk", 0),
            "mean_val_net_pnl": _m(pnl, mean),
            "median_val_net_pnl": _m(pnl, median),
            "mean_val_sharpe": _m(shp, mean),
            "median_val_sharpe": _m(shp, median),
            "mean_val_wilson_wr": _m(wwr, mean),
            "median_val_wilson_wr": _m(wwr, median),
        }
        tc = table_c[sid]
        print(f"{sid:<4}{tc['unlocked']:>9}{tc['clearly_viable']:>8}"
              f"{tc['borderline']:>11}{tc['likely_junk']:>6}"
              f"{(tc['mean_val_net_pnl'] or 0):>14.4f}{(tc['median_val_net_pnl'] or 0):>13.4f}"
              f"{(tc['mean_val_sharpe'] or 0):>14.4f}{(tc['median_val_sharpe'] or 0):>13.4f}"
              f"{(tc['mean_val_wilson_wr'] or 0):>10.4f}{(tc['median_val_wilson_wr'] or 0):>10.4f}")

    # ============================================================
    # 4 Required Questions
    # ============================================================
    # Q1. Which val gate blocks the most "not-obviously-junk" cells?
    # Evaluate by exclusive-gate hit counts weighted by viability distribution.
    answers = {}
    # Construct per-exclusive-gate unlock populations for quality breakdown.
    def pop_for(flag_filter):
        return [c for c in val_blocked if flag_filter(c) and not c.get("val_few_trades")]
    def qual_profile(pop):
        if not pop:
            return {"n": 0, "viable": 0, "borderline": 0, "junk": 0}
        quals = Counter(classify_quality(c) for c in pop)
        return {
            "n": len(pop),
            "viable": quals.get("clearly_viable", 0),
            "borderline": quals.get("borderline", 0),
            "junk": quals.get("likely_junk", 0),
        }
    q1 = {
        "val_neg_pnl_exclusive": qual_profile([c for c in val_blocked
            if c["fail_val_neg_pnl"] and not c["fail_val_low_sharpe"] and not c["fail_val_low_wr"]]),
        "val_low_sharpe_exclusive": qual_profile([c for c in val_blocked
            if c["fail_val_low_sharpe"] and not c["fail_val_neg_pnl"] and not c["fail_val_low_wr"]]),
        "val_low_wr_exclusive": qual_profile([c for c in val_blocked
            if c["fail_val_low_wr"] and not c["fail_val_neg_pnl"] and not c["fail_val_low_sharpe"]]),
    }
    answers["Q1_which_gate_blocks_most_nonjunk"] = q1

    # Q2. Does removing val_neg_pnl alone materially increase survivors?
    g0 = next(e for e in table_b if e["id"] == "G0")
    g1 = next(e for e in table_b if e["id"] == "G1")
    answers["Q2_remove_val_neg_pnl_alone"] = {
        "delta_survivors": g1["counterfactual_survivors"] - g0["counterfactual_survivors"],
        "delta_symbols": g1["symbols_with_new_survivor"] - g0["symbols_with_new_survivor"],
        "net_new_cells": g1["net_new_vs_G0"],
        "unlock_rate_over_val_blocked": g1["unlock_rate_over_val_blocked"],
    }

    # Q3. Are unlocked things mostly viable, borderline, or junk? (Aggregate over G7.)
    g7_c = table_c.get("G7", {})
    answers["Q3_unlock_quality_profile_G7"] = {
        "unlocked": g7_c.get("unlocked", 0),
        "clearly_viable": g7_c.get("clearly_viable", 0),
        "borderline": g7_c.get("borderline", 0),
        "likely_junk": g7_c.get("likely_junk", 0),
        "mean_val_net_pnl": g7_c.get("mean_val_net_pnl"),
        "mean_val_sharpe": g7_c.get("mean_val_sharpe"),
    }

    # Q4. Residual dominant blocker: gate-too-strict or upstream-signal-quality?
    # Heuristic: if G7's unlocked pool has mean_val_net_pnl > 0 and majority viable,
    # the answer skews toward gate-too-strict. If the unlocked pool is majority
    # junk / negative pnl, the answer skews toward upstream-signal-quality.
    g7 = answers["Q3_unlock_quality_profile_G7"]
    total_g7 = g7["unlocked"] or 1
    viable_frac = g7["clearly_viable"] / total_g7
    junk_frac = g7["likely_junk"] / total_g7
    mean_pnl = g7.get("mean_val_net_pnl") or 0
    answers["Q4_residual_blocker"] = {
        "g7_unlocked": g7["unlocked"],
        "viable_frac": round(viable_frac, 4),
        "junk_frac": round(junk_frac, 4),
        "mean_val_net_pnl_unlocked": mean_pnl,
    }

    print(f"\n==================== 4 REQUIRED QUESTIONS ====================")
    print(f"Q1 — which val gate blocks the most non-junk cells (exclusive populations):")
    for k, v in q1.items():
        print(f"     {k:<32} n={v['n']:<3} viable={v['viable']:<3} borderline={v['borderline']:<3} junk={v['junk']}")
    print(f"Q2 — remove val_neg_pnl ALONE: Δsurv={answers['Q2_remove_val_neg_pnl_alone']['delta_survivors']} "
          f"net_new={answers['Q2_remove_val_neg_pnl_alone']['net_new_cells']} "
          f"unlock_rate={answers['Q2_remove_val_neg_pnl_alone']['unlock_rate_over_val_blocked']:.4f}")
    print(f"Q3 — G7 unlock quality: unlocked={g7['unlocked']} viable={g7['clearly_viable']} "
          f"borderline={g7['borderline']} junk={g7['likely_junk']} "
          f"mean_val_pnl={mean_pnl}")
    print(f"Q4 — residual blocker signal: viable_frac={viable_frac:.2%} junk_frac={junk_frac:.2%} "
          f"mean_unlocked_val_pnl={mean_pnl}")

    bundle = {
        "input_summary": {
            "total": total,
            "train_blocked": len(train_blocked),
            "reached_val": len(reached_val),
            "existing_survivors": len(existing_survivors),
            "val_blocked": len(val_blocked),
        },
        "existing_survivor_keys": [{"alpha_hash": c["alpha_hash"], "symbol": c["symbol"],
                                    "formula": c["formula"]}
                                   for c in existing_survivors],
        "thresholds": {
            "val_neg_pnl_strict_gt": VAL_NEG_PNL_THR,
            "val_low_sharpe_gte": VAL_LOW_SHARPE_THR,
            "val_low_wr_gte": VAL_LOW_WR_THR,
        },
        "table_a_gate_attribution": table_a,
        "table_b_counterfactual_survivors": table_b,
        "table_c_unlock_quality": table_c,
        "answers_4q": answers,
    }

    if out_path:
        out_path.write_text(json.dumps(bundle, indent=2))
        print(f"\nwrote: {out_path}")


if __name__ == "__main__":
    main()
