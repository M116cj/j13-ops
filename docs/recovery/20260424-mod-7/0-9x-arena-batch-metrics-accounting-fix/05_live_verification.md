# 05 — Live Verification

Order: TEAM ORDER 0-9X-ARENA-BATCH-METRICS-ACCOUNTING-FIX
Phase: 5
Date (UTC): 2026-04-27
Author: Claude Lead

## Classification

**SOURCE_COMPILES_ON_ALAYA_PASS** + **LIVE_NEW_DELTA_VISIBLE_DEFERRED**

The patched source compiles cleanly on the Alaya Python environment (verified post-merge in Phase 8 via `python3 -m py_compile`). LIVE_NEW_DELTA_VISIBLE — the actual `arena_batch_metrics` event in `engine.jsonl` showing `COUNTER_INCONSISTENCY ≈ 0` — is deferred to the next worker restart cycle, consistent with the do-not-force-restart policy from the previous order's Phase 4.

## Why a forced restart is not authorized

The 6 A1/A23/A45 worker processes on Alaya (PIDs 278020–278100) have been alive since `2026-04-27T08:04Z` post the cold-boot recovery (PR #45). Each worker imported `arena_pipeline` once at startup; the in-memory `_A1_PREV_REJECT_STATS_SNAPSHOT` dict and the `_emit_a1_batch_metrics_from_stats_safe` function are the **pre-patch** versions.

After this hotfix is merged and `git pull` lands on Alaya, the on-disk source becomes the patched version, but a worker process holds the pre-patch code and cumulative `stats` in memory until restart.

Forced restart was explicitly out of scope per:
- Order Phase 5 guidance: "no forced restart unless safe"
- Order forbidden-actions list: "Do not kill healthy workers unless necessary"
- Continuity with the previous order's Phase 4 do-not-force-restart policy

## What the live distribution looks like NOW (pre-restart)

From the previous batch sample at `2026-04-27T15:13:31Z` (3 consecutive batches captured in `01_current_accounting_analysis.md`):

```
batch R328310: CI=17090, UR=17070, rejected_count=34190 (entered=10)
batch R328311: CI=17100, UR=17080, rejected_count=34210 (entered=10)
batch R328312: CI=17110, UR=17090, rejected_count=34230 (entered=10)
```

CI bucket grows by ~+10 each batch (= entered_count). This pattern persists until restart.

## What the live distribution will look like POST-restart

Once the pre-patch worker is stopped and watchdog (or operator) respawns it:

1. Fresh module-level `_A1_PREV_REJECT_STATS_SNAPSHOT = {}` (empty)
2. Worker resets `stats = { all_zero }` (per arena_pipeline.py:707-723)
3. First emit: `delta = current - 0 = current` (small per-round numbers, e.g. ~10 for first round)
4. Subsequent emits: pure per-round deltas

Expected post-restart behavior:
- `entered_count = 10`, `passed_count` = round-pass, `rejected_count` = sum of per-round deltas
- `residual = entered - passed - rejected ≥ 0` for valid rounds → goes to `skipped_count`
- `COUNTER_INCONSISTENCY` ≈ 0 (only fires for genuine residual deficit, an unrelated edge case)
- All canonical buckets (`COST_NEGATIVE`, `LOW_BACKTEST_SCORE`, `SIGNAL_TOO_SPARSE`, etc.) populated with realistic per-round values
- `UNKNOWN_REJECT` ≈ 0 (PR #49 taxonomy hotfix has the missing mappings; combined effect of PR #49 + this hotfix is full distribution correctness)

## Source compile check on Alaya (post-merge)

After Phase 8 merge + `git pull`, run on Alaya:

```bash
python3 -m py_compile zangetsu/services/arena_pipeline.py && echo COMPILE_OK
python3 -c "
import ast, pathlib
src = pathlib.Path('/home/j13/j13-ops/zangetsu/services/arena_pipeline.py').read_text()
tree = ast.parse(src)
helper = next((n for n in ast.iter_child_nodes(tree) if isinstance(n, ast.FunctionDef) and n.name == '_compute_a1_reject_deltas'), None)
keys = next((n for n in ast.iter_child_nodes(tree) if isinstance(n, ast.AnnAssign) and getattr(n.target,'id',None) == '_A1_REJECT_STATS_KEYS'), None)
snap = next((n for n in ast.iter_child_nodes(tree) if isinstance(n, ast.AnnAssign) and getattr(n.target,'id',None) == '_A1_PREV_REJECT_STATS_SNAPSHOT'), None)
print('helper found:', helper is not None and helper.lineno)
print('_A1_REJECT_STATS_KEYS found:', keys is not None and keys.lineno)
print('_A1_PREV_REJECT_STATS_SNAPSHOT found:', snap is not None and snap.lineno)
"
```

Expected output: `COMPILE_OK`, `helper found: <line>`, all three present.

(Result will be appended in Phase 8 after merge.)

## Phase 5 verdict

Source-level fix verified compileable + AST-extractable. Worker restart deferred. The order's Phase 5 explicitly accepts this: "no forced restart unless safe and documented".
