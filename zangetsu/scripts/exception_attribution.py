#!/usr/bin/env python3
"""Exception-overlay full-verify attribution (j13 hard rule C).

Input: full-run JSONL written by the integration wrapper with --exception-overlay.
Output: machine-readable + human-readable attribution table.

Required per j13 2026-04-22 boundary §C:
  - allow_list pairs enumerated: was each hit? was each overridden?
  - non-allow_list cells: all fallthrough confirmed (count, no exception hits)?
  - total exception hits, unexpected exception hits (must be 0)
"""
import json
import sys
from collections import Counter
from pathlib import Path


ALLOW_LIST = [
    ("BTCUSDT", "decay_20(volume)"),
    ("DOTUSDT", "decay_20(volume)"),
]


def load(path):
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def main():
    src = Path(sys.argv[1])
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    rows = load(src)
    total = len(rows)

    # Classify rows into allow_list / non-allow_list
    allow_set = set(ALLOW_LIST)
    allow_hits = []      # (symbol, formula) IS in allow_list, was exception applied
    allow_no_hits = []   # IS in allow_list, but exception wasn't applied
    non_allow_exc = []   # NOT in allow_list, yet exception was marked
    non_allow_ok = []    # NOT in allow_list, fallthrough as expected
    for r in rows:
        sym = r.get("symbol")
        fml = r.get("formula")
        in_allow = (sym, fml) in allow_set
        exc_hit = bool(r.get("exception_allow_list_hit"))
        fallthrough = bool(r.get("fallthrough_to_main"))
        override = bool(r.get("exception_override_applied"))
        if in_allow:
            if exc_hit:
                allow_hits.append(r)
            else:
                allow_no_hits.append(r)
        else:
            if exc_hit:
                non_allow_exc.append(r)
            else:
                non_allow_ok.append(r)

    unexpected = len(non_allow_exc)

    print(f"\n==================== FULL VERIFY — EXCEPTION ATTRIBUTION ====================")
    print(f"total cells                        : {total}")
    print(f"allow_list pairs (declared)        : {len(ALLOW_LIST)}")
    print(f"cells matching allow_list pair(s)  : {len(allow_hits) + len(allow_no_hits)}")
    print(f"  of which exception_hit=True      : {len(allow_hits)}")
    print(f"  of which exception_hit=False     : {len(allow_no_hits)}  (investigate if >0)")
    print(f"cells NOT matching allow_list      : {len(non_allow_exc) + len(non_allow_ok)}")
    print(f"  with exception_hit=True          : {len(non_allow_exc)}  <-- MUST be 0")
    print(f"  with fallthrough_to_main=True    : {len(non_allow_ok)}  (expected = total - allow_list hits)")

    # ------------------------------------------------------------------
    # Per allow_list pair table
    # ------------------------------------------------------------------
    print(f"\n-- Per allow_list pair ({len(ALLOW_LIST)} pairs) --")
    hdr = f"{'#':<3}{'symbol':<12}{'formula':<25}{'in_run':>8}{'exc_hit':>10}{'override':>10}{'first_gate':>20}{'surv':>6}"
    print(hdr)
    print("-" * len(hdr))
    per_pair_table = []
    for i, (sym, fml) in enumerate(ALLOW_LIST):
        matched = [r for r in rows if r.get("symbol") == sym and r.get("formula") == fml]
        for r in matched:
            entry = {
                "idx": i,
                "symbol": sym,
                "formula": fml,
                "in_run": True,
                "exception_hit": bool(r.get("exception_allow_list_hit")),
                "override_applied": bool(r.get("exception_override_applied")),
                "first_gate": r.get("first_gate_reached"),
                "survived_a1": bool(r.get("survived_a1")),
                "route_status": r.get("route_status"),
                "exception_overlay_name": r.get("exception_overlay_name"),
                "exception_pair_key": r.get("exception_pair_key"),
                "exception_evidence_tag": r.get("exception_evidence_tag"),
            }
            per_pair_table.append(entry)
            print(f"{i+1:<3}{sym:<12}{fml:<25}{'YES':>8}"
                  f"{str(entry['exception_hit']):>10}{str(entry['override_applied']):>10}"
                  f"{str(entry['first_gate']):>20}{str(entry['survived_a1']):>6}")
        if not matched:
            entry = {"idx": i, "symbol": sym, "formula": fml, "in_run": False}
            per_pair_table.append(entry)
            print(f"{i+1:<3}{sym:<12}{fml:<25}{'NO':>8}")

    # ------------------------------------------------------------------
    # Sanity: non-allow_list cells, sample + totals
    # ------------------------------------------------------------------
    print(f"\n-- Non-allow_list cells fallthrough check --")
    print(f"total non-allow_list            : {len(non_allow_exc) + len(non_allow_ok)}")
    print(f"fallthrough_to_main=True        : {len(non_allow_ok)}")
    print(f"exception_allow_list_hit=True   : {len(non_allow_exc)}  (expected 0)")
    # Verify attributes were attached
    fallthrough_count = sum(1 for r in (non_allow_exc + non_allow_ok)
                            if r.get("fallthrough_to_main") is True)
    print(f"rows with fallthrough_to_main=True flag : {fallthrough_count} / {len(non_allow_exc)+len(non_allow_ok)}")

    if unexpected > 0:
        print("\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("UNEXPECTED EXCEPTION HITS DETECTED ON NON-ALLOW_LIST CELLS:")
        for r in non_allow_exc[:10]:
            print(f"  {r['symbol']} / {r['formula']}  ->  first_gate={r.get('first_gate_reached')!r}")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")

    # ------------------------------------------------------------------
    # Gate-outcome counters (before vs after exception)
    # ------------------------------------------------------------------
    print(f"\n-- Gate-outcome summary (post-exception) --")
    by_gate = Counter()
    for r in rows:
        fg = r.get("first_gate_reached")
        if fg:
            by_gate[fg] += 1
    print(f"survived_a1 total            : {sum(1 for r in rows if r.get('survived_a1'))}")
    for g, n in sorted(by_gate.items(), key=lambda x: -x[1]):
        print(f"  {g:<25} : {n}")

    # ------------------------------------------------------------------
    # Verdict
    # ------------------------------------------------------------------
    exc_hits_total = len(allow_hits) + len(non_allow_exc)
    expected_hits = len(ALLOW_LIST)  # 2 allow_list pairs, both appear in run
    all_pairs_hit_and_overridden = all(
        entry.get("in_run") and entry.get("exception_hit") and entry.get("override_applied")
        for entry in per_pair_table
    )
    verdict = (
        "PASS" if (unexpected == 0 and all_pairs_hit_and_overridden and exc_hits_total == expected_hits)
        else "FAIL"
    )
    print(f"\n==================== VERIFY VERDICT ====================")
    print(f"total exception hits   : {exc_hits_total} (expected = {expected_hits})")
    print(f"unexpected hits        : {unexpected} (must be 0)")
    print(f"every allow_list pair matched + overridden: {all_pairs_hit_and_overridden}")
    print(f"VERIFY VERDICT: {verdict}")

    bundle = {
        "total_cells": total,
        "allow_list_declared": len(ALLOW_LIST),
        "allow_list_pairs": [{"symbol": s, "formula": f} for s, f in ALLOW_LIST],
        "allow_list_hits": len(allow_hits),
        "allow_list_no_hits": len(allow_no_hits),
        "non_allow_list_cells": len(non_allow_exc) + len(non_allow_ok),
        "non_allow_list_fallthrough": len(non_allow_ok),
        "unexpected_exception_hits": unexpected,
        "total_exception_hits": exc_hits_total,
        "expected_exception_hits": expected_hits,
        "per_pair_detail": per_pair_table,
        "gate_outcome_counts": dict(by_gate),
        "verdict": verdict,
    }
    if out_path:
        out_path.write_text(json.dumps(bundle, indent=2))
        print(f"\nwrote: {out_path}")
    sys.exit(0 if verdict == "PASS" else 1)


if __name__ == "__main__":
    main()
