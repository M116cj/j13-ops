# 06 — Numerical Stability Audit

## 1. Observed RuntimeWarnings

`/tmp/zangetsu_a1_w2.log` and `/tmp/zangetsu_a1_w3.log` emit numpy RuntimeWarnings on every cron cycle (workers w0 and w1 also emit them, but interleaved with INFO lines at higher density):

```
/home/j13/j13-ops/zangetsu/.venv/lib/python3.12/site-packages/numpy/_core/_methods.py:190:
RuntimeWarning: overflow encountered in square
  x = um.square(x, out=x)

/home/j13/j13-ops/zangetsu/.venv/lib/python3.12/site-packages/numpy/_core/_methods.py:201:
RuntimeWarning: overflow encountered in reduce
  ret = umr_sum(x, axis, dtype, out, keepdims=keepdims, where=where)
```

| Field | Value |
| --- | --- |
| Source line of warning emit | `numpy/_core/_methods.py:190 (square)`, `:201 (reduce sum)` |
| User-code call site | not directly captured in stack — emerges from numpy internal, presumably during `np.std(av_val)` or backtester compute (Z-scoring, variance) |
| Frequency | non-empty per cycle (multiple per worker) |
| Behavior | RuntimeWarning is **non-fatal** by default in numpy; result becomes `inf` / `NaN` |
| Conversion to exception | NO (numpy default policy is `warn`, not `raise`) |
| Filter at `np.nan_to_num(av_val, nan=0.0, posinf=0.0, neginf=0.0)` (line 1003) | catches NaN/inf and clamps to 0 |
| Filter at `if np.std(av_val) < 1e-10: stats["reject_val_constant"] += 1; continue` (line 998) | rejects constant signal |

→ The numpy overflow likely turns the val signal into all-zeros (after `nan_to_num`), which `np.std()` reports as 0.0, which fails the `1e-10` threshold → `reject_val_constant`.

This explains WHY all candidates likely fail val gates → which means `_pb` never gets assigned in any iteration → which causes the line-1218 crash.

## 2. Per-Candidate vs Per-Batch Effect

| Scope | Effect of overflow |
| --- | --- |
| Single candidate | `nan_to_num` clamps to 0 → `std=0` → `reject_val_constant` → next candidate |
| Whole batch | If ALL candidates' val signals overflow into NaN, ALL are rejected → no INSERT → `_pb` unset → line-1218 crash |
| Whole worker | Crash kills asyncio.run; worker exits; cron respawns 5 min later; same overflow → same crash |

→ The overflow is a **per-candidate** event but its 100% rejection rate combined with the line-1218 source bug produces a **whole-worker** crash.

## 3. Is the Overflow the Real Root Cause?

**No.** The numerical overflow is a **legitimate runtime hazard** that the source code already guards against (via `nan_to_num` + `reject_val_constant`). The strategy filter chain WORKS — it correctly rejects the bad candidates.

The actual bug is the line-1218 source code that **assumes at least one candidate per round passes all filters** and crashes when zero candidates pass. Even without the numpy overflow, any other condition that causes `passed_count=0` for a round (e.g. all candidates being too sparse on a quiet market day, all candidates duplicating bloom entries) would trigger the same crash.

## 4. Phase 6 Classification

Per order §11:

| Verdict | Match? |
| --- | --- |
| NUMERIC_WARNING_NON_BLOCKING (warning emitted but doesn't block) | partial — warning itself is non-blocking, but downstream rejection makes it indirectly contribute to the line-1218 crash |
| **NUMERIC_WARNING_CANDIDATE_LEVEL_REJECT** (warning causes single-candidate reject via reject_val_constant) | **YES — exact match for the per-candidate effect** |
| NUMERIC_WARNING_BATCH_LEVEL_REJECT | partial (when all candidates in a round overflow) |
| NUMERIC_WARNING_LOOP_LEVEL_BLOCK | partial (combined with line-1218 source bug) |
| **NUMERIC_WARNING_NOT_RELEVANT** (warning is genuine but not the materialization root cause) | **YES — also true; the source bug is the actual blocker** |
| NUMERIC_WARNING_UNKNOWN | NO |

→ **Phase 6 verdict: NUMERIC_WARNING_CANDIDATE_LEVEL_REJECT (proximate)** + **NUMERIC_WARNING_NOT_RELEVANT (root cause is line-1218 source bug, not numpy)**.
