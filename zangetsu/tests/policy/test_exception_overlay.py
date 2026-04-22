#!/usr/bin/env python3
"""Unit tests for candidate_exception overlay + resolve_with_allow_list.

Test cases:
  U1. HIT (symbol + formula both match)
      -> exception_allow_list_hit=True, route_status=candidate_exception,
         params 250x0.90x60x0.50, fallthrough_to_main=False.
  U2. MISS (wrong symbol)
      -> fallthrough to main 'volume' active route.
  U3. MISS (wrong formula)
      -> fallthrough to main 'volume' active route.
  U4. HIT with hash MATCH
      -> same as U1, overlay_warnings empty.
  U5. HIT with hash MISMATCH (formula-ok, hash-wrong)
      -> still HIT (pass by primary key), but overlay_warnings contains hash warning.
  U6. HASH-ONLY match (formula doesn't match, but someone fed the hash)
      -> NOT a valid pass; returns fallthrough + warning about hash-only.
  U7. Direct invocation of candidate_exception as family_id -> PolicyRegistryError.
  U8. Expired overlay (simulated) -> exception NOT applied; falls through with warning.
"""
import json
import sys
import datetime as _dt
import copy

sys.path.insert(0, "/home/j13/j13-ops")

from zangetsu.engine.policy.family_strategy_policy_v0 import (
    DEFAULT_REGISTRY_PATH,
    PolicyRegistryError,
    load_registry,
    resolve_with_allow_list,
)

OVERLAY_PATH = "/home/j13/j13-ops/zangetsu/config/volume_c6_exceptions_overlay.yaml"

main_reg = load_registry(DEFAULT_REGISTRY_PATH, overlay=False)
overlay = load_registry(OVERLAY_PATH, overlay=True)


def run(label, **kwargs):
    try:
        r = resolve_with_allow_list(
            registry=main_reg,
            overlay_registry=overlay,
            overlay_registry_path=OVERLAY_PATH,
            **kwargs,
        )
        print(f"[{label}] OK:")
    except PolicyRegistryError as e:
        print(f"[{label}] RAISED PolicyRegistryError: {e}")
        return None
    for k in ("exception_allow_list_hit", "route_status", "route_reason",
              "rank_window", "entry_threshold", "min_hold", "exit_threshold",
              "fallthrough_to_main", "overlay_warnings"):
        print(f"     {k:<32} = {r.get(k)!r}")
    return r


def check(label, r, **expectations):
    if r is None:
        print(f"  [{label}] FAIL (resolver raised)")
        return False
    all_ok = True
    for k, v in expectations.items():
        actual = r.get(k)
        ok = actual == v
        if not ok:
            print(f"  [{label}] FAIL on {k}: expected={v!r} actual={actual!r}")
            all_ok = False
    print(f"  [{label}] {'PASS' if all_ok else 'FAIL'}")
    return all_ok


all_pass = True

# U1: HIT
print("\n=== U1: HIT on BTCUSDT decay_20(volume) ===")
r1 = run("U1", family_id="volume", mode="research",
         symbol="BTCUSDT", formula="decay_20(volume)",
         alpha_hash="0cea1d5ad3806aba")
all_pass &= check("U1", r1,
    exception_allow_list_hit=True,
    route_status="candidate_exception",
    rank_window=250, entry_threshold=0.9,
    min_hold=60, exit_threshold=0.5,
    fallthrough_to_main=False)

# U2: MISS wrong symbol
print("\n=== U2: MISS wrong symbol (ETHUSDT decay_20(volume)) ===")
r2 = run("U2", family_id="volume", mode="research",
         symbol="ETHUSDT", formula="decay_20(volume)",
         alpha_hash="0cea1d5ad3806aba")
all_pass &= check("U2", r2,
    exception_allow_list_hit=False,
    route_status="active",
    rank_window=250, entry_threshold=0.9,
    fallthrough_to_main=True)

# U3: MISS wrong formula
print("\n=== U3: MISS wrong formula (BTCUSDT ts_rank_20(volume)) ===")
r3 = run("U3", family_id="volume", mode="research",
         symbol="BTCUSDT", formula="ts_rank_20(volume)",
         alpha_hash=None)
all_pass &= check("U3", r3,
    exception_allow_list_hit=False,
    route_status="active",
    fallthrough_to_main=True)

# U4: HIT with correct hash
print("\n=== U4: HIT DOTUSDT decay_20(volume) with correct hash ===")
r4 = run("U4", family_id="volume", mode="research",
         symbol="DOTUSDT", formula="decay_20(volume)",
         alpha_hash="0cea1d5ad3806aba")
all_pass &= check("U4", r4,
    exception_allow_list_hit=True,
    route_status="candidate_exception")
w_u4 = r4.get("overlay_warnings", []) if r4 else []
if len([w for w in w_u4 if "alpha_hash mismatch" in w]) != 0:
    print("  [U4] UNEXPECTED hash mismatch warning with correct hash"); all_pass = False
else:
    print("  [U4] hash mismatch warning check: PASS")

# U5: HIT with WRONG hash
print("\n=== U5: HIT BTCUSDT decay_20(volume) but WRONG alpha_hash ===")
r5 = run("U5", family_id="volume", mode="research",
         symbol="BTCUSDT", formula="decay_20(volume)",
         alpha_hash="deadbeefdeadbeef")
all_pass &= check("U5", r5,
    exception_allow_list_hit=True,
    route_status="candidate_exception")
w_u5 = r5.get("overlay_warnings", []) if r5 else []
if any("alpha_hash mismatch" in w for w in w_u5):
    print("  [U5] hash mismatch warning present: PASS")
else:
    print("  [U5] hash mismatch warning MISSING: FAIL"); all_pass = False

# U6: HASH-only (formula miss, hash present)
print("\n=== U6: HASH-ONLY (BTCUSDT wrong formula but real hash) ===")
r6 = run("U6", family_id="volume", mode="research",
         symbol="BTCUSDT", formula="neg(zscore_50)",
         alpha_hash="0cea1d5ad3806aba")
all_pass &= check("U6", r6,
    exception_allow_list_hit=False,
    fallthrough_to_main=True)
w_u6 = r6.get("overlay_warnings", []) if r6 else []
if any("hash-only match" in w for w in w_u6):
    print("  [U6] hash-only warning present: PASS")
else:
    print("  [U6] hash-only warning MISSING: FAIL"); all_pass = False

# U7: direct invocation of candidate_exception family -> PolicyRegistryError
print("\n=== U7: Direct invocation of candidate_exception family ===")
r7 = run("U7", family_id="volume_c6_approved_exceptions",
         mode="research", symbol="BTCUSDT", formula="decay_20(volume)",
         alpha_hash=None)
if r7 is None:
    print("  [U7] PolicyRegistryError raised (expected): PASS")
else:
    print("  [U7] FAIL: candidate_exception invoked directly, no error raised"); all_pass = False

# U8: Expired overlay - simulate by mutating overlay copy
print("\n=== U8: Expired overlay (simulated) ===")
overlay_expired = copy.deepcopy(overlay)
fam = overlay_expired["families"]["volume_c6_approved_exceptions"]
fam["expires_at"] = "2026-01-01T00:00:00Z"
try:
    r8 = resolve_with_allow_list(
        family_id="volume", mode="research",
        symbol="BTCUSDT", formula="decay_20(volume)",
        alpha_hash="0cea1d5ad3806aba",
        registry=main_reg,
        overlay_registry=overlay_expired,
        overlay_registry_path=OVERLAY_PATH,
    )
    print(f"     exception_allow_list_hit = {r8.get('exception_allow_list_hit')!r}")
    print(f"     fallthrough_to_main      = {r8.get('fallthrough_to_main')!r}")
    print(f"     overlay_warnings         = {r8.get('overlay_warnings')!r}")
    if not r8["exception_allow_list_hit"] and r8["fallthrough_to_main"]:
        if any("expired" in w for w in r8["overlay_warnings"]):
            print("  [U8] expired overlay correctly falls through with warning: PASS")
        else:
            print("  [U8] fallthrough correct but no expired warning: FAIL"); all_pass = False
    else:
        print("  [U8] FAIL: expired overlay was still applied"); all_pass = False
except Exception as e:
    print(f"  [U8] UNEXPECTED exception: {e}"); all_pass = False

print("\n==========================================")
print(f"overall: {'ALL PASS' if all_pass else 'SOME FAILED'}")
sys.exit(0 if all_pass else 1)
