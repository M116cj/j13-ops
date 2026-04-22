#!/usr/bin/env python3
"""Resolver A/B/C/D validation — task 421-4 §13.2.

A. family_id=volume, mode=research          -> active,   validated=True,  250x0.90x60x0.50
B. family_id=breakout, mode=research        -> active,   validated=True,  500x0.80x60x0.50
C. family_id=mean_reversion, mode=research  -> fallback, validated=False, 500x0.80x60x0.50
D. family_id=mean_reversion, mode=production -> blocked, validated=False, no params
Extras:
  E. alias volume_family -> volume          -> normalization_applied=True
  F. alias mr -> mean_reversion (research)  -> fallback with alias trail
  G. unrecognized zzzz (production)         -> blocked
"""
import json
import sys

sys.path.insert(0, "/home/j13/j13-ops")

from zangetsu.engine.policy.family_strategy_policy_v0 import (
    PolicyRegistryError,
    resolve_family_strategy_policy,
)

CASES = [
    ("A", "volume", "research"),
    ("B", "breakout", "research"),
    ("C", "mean_reversion", "research"),
    ("D", "mean_reversion", "production"),
    ("E", "volume_family", "research"),
    ("F", "mr", "research"),
    ("G", "zzzz", "production"),
]

EXPECT = {
    "A": {"route_status": "active", "validated": True,
          "rank_window": 250, "entry_threshold": 0.90,
          "min_hold": 60, "exit_threshold": 0.50,
          "normalization_applied": False},
    "B": {"route_status": "active", "validated": True,
          "rank_window": 500, "entry_threshold": 0.80,
          "min_hold": 60, "exit_threshold": 0.50,
          "normalization_applied": False},
    "C": {"route_status": "fallback", "validated": False,
          "rank_window": 500, "entry_threshold": 0.80,
          "min_hold": 60, "exit_threshold": 0.50,
          "normalization_applied": False},
    "D": {"route_status": "blocked", "validated": False,
          "rank_window": None, "entry_threshold": None,
          "min_hold": None, "exit_threshold": None,
          "normalization_applied": False},
    "E": {"route_status": "active", "validated": True,
          "rank_window": 250, "entry_threshold": 0.90,
          "min_hold": 60, "exit_threshold": 0.50,
          "normalization_applied": True},
    "F": {"route_status": "fallback", "validated": False,
          "rank_window": 500, "entry_threshold": 0.80,
          "min_hold": 60, "exit_threshold": 0.50,
          "normalization_applied": True},
    "G": {"route_status": "blocked", "validated": False,
          "rank_window": None, "entry_threshold": None,
          "min_hold": None, "exit_threshold": None,
          "normalization_applied": True},
}


def main() -> int:
    results = []
    all_pass = True
    for label, fam, mode in CASES:
        try:
            pol = resolve_family_strategy_policy(fam, mode=mode)
        except PolicyRegistryError as e:
            print(f"[{label}] RESOLVER RAISED: {e}")
            all_pass = False
            continue
        exp = EXPECT[label]
        checks = []
        for k, v in exp.items():
            actual = pol.get(k)
            ok = actual == v
            checks.append((k, v, actual, ok))
            if not ok:
                all_pass = False
        status = "PASS" if all(ok for _, _, _, ok in checks) else "FAIL"
        print(f"[{label}] family_id={fam!r} mode={mode!r} -> {status}")
        print(f"     normalized={pol['normalized_family_id']!r} "
              f"route_status={pol['route_status']!r} reason={pol['route_reason']!r} "
              f"norm_reason={pol['normalization_reason']!r}")
        for k, expected, actual, ok in checks:
            mark = "  " if ok else "!!"
            print(f"  {mark} {k}: expected={expected!r} actual={actual!r}")
        results.append({"label": label, "family_id": fam, "mode": mode,
                        "policy": pol, "status": status})
    print("\n==========================================")
    print(f"overall: {'ALL PASS' if all_pass else 'FAIL'}  ({len(results)} cases)")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
