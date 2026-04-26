# 01 — Patch Summary

## 1. Target

| Field | Value |
| --- | --- |
| File | `zangetsu/services/arena_pipeline.py` |
| Function | `main()` (declared at line 411) |
| Insertion line | between `round_champions = 0` and `for alpha_result in alphas:` (per-round init) |

## 2. Verbatim Diff

```diff
diff --git a/zangetsu/services/arena_pipeline.py b/zangetsu/services/arena_pipeline.py
index 877bd370..dd049753 100644
--- a/zangetsu/services/arena_pipeline.py
+++ b/zangetsu/services/arena_pipeline.py
@@ -905,6 +905,13 @@ async def main():
             continue
 
         round_champions = 0
+        # 0-9W-A1-PB-SCOPE-FIX: initialize _pb to None so the per-round
+        # batch metrics emit at line 1218 (getattr(_pb, "run_id", "") or "")
+        # never raises UnboundLocalError when no candidate in this round
+        # passes the 9-stage val-filter chain (lines 950-1100). Existing
+        # line 1116 _pb = _get_or_build_provenance(...) overwrites this
+        # default whenever a candidate reaches the INSERT block.
+        _pb = None
         for alpha_result in alphas:
             stats["alphas_evaluated"] += 1
```

## 3. Diff Stat

| Metric | Value |
| --- | --- |
| Files changed | 1 |
| Insertions | 7 (1 code + 6 comment lines explaining why this default exists) |
| Deletions | 0 |
| Behavior change | `_pb` is initialized to `None` at the start of every per-symbol round. The existing `_pb = _get_or_build_provenance(...)` at line 1116 still overwrites this default for any candidate that reaches the INSERT block. |
| Existing line-1218 use of `getattr(_pb, "run_id", "") or ""` | already correctly returns `""` when `_pb is None` — no change needed there |

## 4. What This Patch Does NOT Change

| Item | Status |
| --- | --- |
| Alpha formula generation | UNCHANGED |
| Mutation logic | UNCHANGED |
| Crossover logic | UNCHANGED |
| Search policy | UNCHANGED |
| Generation budget (`POP_SIZE`, `N_GEN`, `TOP_K`) | UNCHANGED |
| Sampling weights | UNCHANGED |
| Validation filter thresholds (the 9-stage chain) | UNCHANGED |
| `A2_MIN_TRADES` (= 25) | UNCHANGED |
| Arena pass/fail semantics | UNCHANGED |
| Champion promotion | UNCHANGED |
| `deployable_count` semantics | UNCHANGED |
| Telemetry schema | UNCHANGED |
| A13 / A23 / A45 logic | UNCHANGED |

## 5. Syntax Check

```
$ python3 -c 'import ast; ast.parse(open("zangetsu/services/arena_pipeline.py").read()); print("syntax OK")'
syntax OK
```

## 6. Phase 1 Verdict

PASS. Smallest possible scope-initialization patch. No semantic change to Arena behavior; only prevents the local-variable lookup from raising before `getattr` can apply its default.
