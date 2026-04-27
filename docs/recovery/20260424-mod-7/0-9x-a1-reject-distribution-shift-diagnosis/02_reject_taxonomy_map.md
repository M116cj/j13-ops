# 02 — Reject Taxonomy Map

**Subagent:** taxonomy-tracer
**Repo state:** `/Users/a13/dev/j13-ops` @ `b1615c67` on `main`
**Mode:** READ-ONLY. No source modified, no commit.
**Live observed reject distribution (input from Lead):**
`COUNTER_INCONSISTENCY: 13350, UNKNOWN_REJECT: 13350, SIGNAL_TOO_SPARSE: 8, COST_NEGATIVE: 2`

---

## 1. Canonical taxonomy — single source of truth

File: `zangetsu/services/arena_rejection_taxonomy.py` (introduced in P7-PR1, commit `8e75826`).

### 1.1 `RejectionReason(str, Enum)` — 18 mandatory members

| # | Member | Value | Default stage | File:line |
|---|---|---|---|---|
| 1 | INVALID_FORMULA | "INVALID_FORMULA" | A0 | services/arena_rejection_taxonomy.py:37 |
| 2 | UNSUPPORTED_OPERATOR | "UNSUPPORTED_OPERATOR" | A0 | :38 |
| 3 | WINDOW_INSUFFICIENT | "WINDOW_INSUFFICIENT" | A0 | :39 |
| 4 | NON_CAUSAL_RISK | "NON_CAUSAL_RISK" | A0 | :40 |
| 5 | NAN_INF_OUTPUT | "NAN_INF_OUTPUT" | A0 | :41 |
| 6 | LOW_BACKTEST_SCORE | "LOW_BACKTEST_SCORE" | A1 | :42 |
| 7 | HIGH_DRAWDOWN | "HIGH_DRAWDOWN" | A1 | :43 |
| 8 | HIGH_TURNOVER | "HIGH_TURNOVER" | A1 | :44 |
| 9 | COST_NEGATIVE | "COST_NEGATIVE" | A2 | :45 |
| 10 | FRESH_FAIL | "FRESH_FAIL" | A2 | :46 |
| 11 | OOS_FAIL | "OOS_FAIL" | A2 | :47 |
| 12 | REGIME_FAIL | "REGIME_FAIL" | A4 | :48 |
| 13 | SIGNAL_TOO_SPARSE | "SIGNAL_TOO_SPARSE" | A2 | :49 |
| 14 | SIGNAL_TOO_DENSE | "SIGNAL_TOO_DENSE" | A2 | :50 |
| 15 | CORRELATION_DUPLICATE | "CORRELATION_DUPLICATE" | A2 | :51 |
| 16 | PROMOTION_BLOCKED | "PROMOTION_BLOCKED" | A3 | :52 |
| 17 | GOVERNANCE_BLOCKED | "GOVERNANCE_BLOCKED" | UNKNOWN | :53 |
| 18 | UNKNOWN_REJECT | "UNKNOWN_REJECT" | UNKNOWN | :54 |

### 1.2 `RAW_TO_REASON: Dict[str, RejectionReason]` (services/arena_rejection_taxonomy.py:241-275)

| Raw key | → Canonical | File:line |
|---|---|---|
| `too_few_trades` | SIGNAL_TOO_SPARSE | :243 |
| `non_positive_pnl` | COST_NEGATIVE | :244 |
| `wrong_segment_count` | WINDOW_INSUFFICIENT | :245 |
| `reject_few_trades` | SIGNAL_TOO_SPARSE | :247 |
| `reject_neg_pnl` | COST_NEGATIVE | :248 |
| `reject_val_constant` | INVALID_FORMULA | :249 |
| `reject_val_error` | INVALID_FORMULA | :250 |
| `reject_val_few_trades` | SIGNAL_TOO_SPARSE | :251 |
| `reject_val_neg_pnl` | COST_NEGATIVE | :252 |
| `reject_val_low_sharpe` | LOW_BACKTEST_SCORE | :253 |
| `reject_val_low_wr` | LOW_BACKTEST_SCORE | :254 |
| `alpha_invalid_or_flat` | INVALID_FORMULA | :256 |
| `no economically valid combos` | COST_NEGATIVE | :257 |
| `all ATR+TP combos non-positive` | COST_NEGATIVE | :258 |
| `validation split fail` | OOS_FAIL | :259 |
| `train/val PnL divergence` | OOS_FAIL | :260 |
| `zero-MAD filter` | SIGNAL_TOO_SPARSE | :261 |
| `alpha_compile_error` | INVALID_FORMULA | :262 |
| `a13_weight_sanity_rejected` | GOVERNANCE_BLOCKED | :264 |
| `weight sanity REJECTED` | GOVERNANCE_BLOCKED | :265 |
| `[V10]: pos_count` (prefix) | SIGNAL_TOO_SPARSE | :273 |
| `[V10]: trades` (prefix) | SIGNAL_TOO_SPARSE | :274 |

> No `TRAIN_NEG_PNL` enum exists. No mapping for `reject_train_neg_pnl`. No mapping for `reject_combined_sharpe_low`.

### 1.3 Aliases / fallbacks (where the strings actually originate)

- `services/arena_pass_rate_telemetry.py:177,194,333` — `RejectReasonCounter.add(reason)` substitutes `"UNKNOWN_REJECT"` when reason is `None` / non-str / empty.
- `services/arena_pass_rate_telemetry.py:235` — `ArenaBatchMetrics.top_reject_reason: str = "UNKNOWN_REJECT"` (hardcoded default for empty events).
- `services/arena23_orchestrator.py:264-277` — `_p7pr4b_canonicalize_reason(...)` returns `"UNKNOWN_REJECT"` whenever taxonomy unavailable, raw_reason None, classify() returns None, or any exception.

---

## 2. Per-key emit-site map — only the four observed reasons

### 2.1 `UNKNOWN_REJECT` — every emit site

| File:line | Context (1-line) | Nature |
|---|---|---|
| services/arena_pass_rate_telemetry.py:177 | `if not isinstance(reason, str) or not reason: reason = "UNKNOWN_REJECT"` | **Fallback** when caller passes None/empty |
| services/arena_pass_rate_telemetry.py:194 | `RejectReasonCounter.top_reason()` returns `"UNKNOWN_REJECT"` for empty counter | **Fallback** display only |
| services/arena_pass_rate_telemetry.py:235 | `top_reject_reason: str = "UNKNOWN_REJECT"` dataclass default | **Fallback** display |
| services/arena_pass_rate_telemetry.py:333 | `acc.reject_counter.add(reason or "UNKNOWN_REJECT")` in `on_rejected` | **Fallback** None→bucket |
| services/arena23_orchestrator.py:265 | early-return `"UNKNOWN_REJECT"` if raw_reason is None | **Fallback** |
| services/arena23_orchestrator.py:268 | early-return when taxonomy module unavailable | **Fallback** |
| services/arena23_orchestrator.py:273 | classify outcome None → `"UNKNOWN_REJECT"` | **Fallback** |
| services/arena23_orchestrator.py:277 | `except Exception: return "UNKNOWN_REJECT"` | **Fallback** |
| services/arena_rejection_taxonomy.py:54 | `UNKNOWN_REJECT = "UNKNOWN_REJECT"` enum declaration | Definition |
| services/arena_rejection_taxonomy.py:228-234 | `REJECTION_METADATA[UNKNOWN_REJECT] = …` | Definition |
| services/arena_rejection_taxonomy.py:308 | `classify()` returns UNKNOWN_REJECT when raw_reason is empty | **Fallback** |
| services/arena_rejection_taxonomy.py:328 | `classify()` returns UNKNOWN_REJECT when no exact + no substring match | **Fallback (terminal)** |
| services/arena_pipeline.py:217 (indirect via classify) | `_emit_a1_batch_metrics_from_stats_safe` calls `classify(stats_key, "A1")` for each `reject_*` stats key | Indirect emitter |
| tools/replay_sparse_canary_observation.py:204,211 | offline replay default | offline tool only |

> **Conclusion: `UNKNOWN_REJECT` is NOT a real classification produced by a specific code path.** It is *only* a fallback bucket for: (a) `reason is None`/empty/non-str, (b) taxonomy import failure, (c) `classify()` exhausted both exact-key and substring lookups, (d) generic exception. There is no Arena gate or A1/A2/A3/A4 logic that ever explicitly emits `UNKNOWN_REJECT` as its decision.

### 2.2 `COUNTER_INCONSISTENCY` — every emit site

| File:line | Context | Nature |
|---|---|---|
| services/arena_pipeline.py:231 | `acc.reject_counter.add("COUNTER_INCONSISTENCY", abs(residual))` when `entered − passed − sum(reject_*) < 0` | **Live emitter (only one)** |
| services/feedback_budget_allocator.py:97 | `REASON_COUNTER_INCONSISTENCY = "COUNTER_INCONSISTENCY"` | constant |
| services/feedback_budget_allocator.py:311 | `reasons.append(REASON_COUNTER_INCONSISTENCY)` when `unknown_rate >= UNKNOWN_REJECT_VETO` | **Downstream consumer** (treats high UNKNOWN_REJECT as proxy for counter inconsistency) |
| services/feedback_budget_consumer.py:91,158,495,500,578-579 | `BLOCK_COUNTER_INCONSISTENCY` block reason; `_has_counter_inconsistency()` predicate | **Downstream consumer** |

> `COUNTER_INCONSISTENCY` is **synthesised inside the same emitter** that fires UNKNOWN_REJECT (`_emit_a1_batch_metrics_from_stats_safe`, services/arena_pipeline.py:167-239). Only one runtime production site exists.

### 2.3 `SIGNAL_TOO_SPARSE` — emit sites

| File:line | Context |
|---|---|
| services/arena_rejection_taxonomy.py:49 | enum decl |
| services/arena_rejection_taxonomy.py:193-199 | metadata |
| services/arena_rejection_taxonomy.py:243,247,251,261,273,274 | RAW_TO_REASON mappings (`too_few_trades`, `reject_few_trades`, `reject_val_few_trades`, `zero-MAD filter`, `[V10]: pos_count`, `[V10]: trades`) |
| services/arena_pipeline.py:206,975 | stats key `reject_few_trades` incremented at `len(trades) < min_trades` gate |
| services/arena_pipeline.py:207,1048 | stats key `reject_val_few_trades` incremented at val gate |
| services/arena23_orchestrator.py | log strings `[V10]: pos_count=…`, `[V10]: trades=… < 25` (substring-matched) |

### 2.4 `COST_NEGATIVE` — emit sites

| File:line | Context |
|---|---|
| services/arena_rejection_taxonomy.py:45 | enum decl |
| services/arena_rejection_taxonomy.py:165-171 | metadata |
| services/arena_rejection_taxonomy.py:244,248,252,257,258 | RAW_TO_REASON (`non_positive_pnl`, `reject_neg_pnl`, `reject_val_neg_pnl`, `no economically valid combos`, `all ATR+TP combos non-positive`) |
| services/arena_pipeline.py:712,717,1051 | `reject_neg_pnl` / `reject_val_neg_pnl` stats keys |
| services/arena23_orchestrator.py / arena45_orchestrator.py | A2/A3 economic-validity log strings |

---

## 3. `val_neg_pnl` history — was it renamed to `TRAIN_NEG_PNL`?

**Answer: NO.**

Evidence:

- `git log --all -S 'val_neg_pnl' -- zangetsu` shows it appears in commits `2e38509`, `8e75826`, `58c8b29` (P7-PR1 / phase7 telemetry), `bd91fac` (R2 hotfix), `7c0ee52` (engine split). It has been a **stable runtime stats key**, not renamed.
- `git log --all -S 'TRAIN_NEG_PNL' -- zangetsu` returns only `c873857` (a SYSTEM_MASTER_BLOCKED_DB consolidation commit, unrelated to the taxonomy file).
- `RejectionReason` enum has **never** contained a `TRAIN_NEG_PNL` member. Grep across `zangetsu/` for `TRAIN_NEG_PNL` finds zero hits in the canonical taxonomy.
- `val_neg_pnl` **lives on** as the runtime stats key (`stats["reject_val_neg_pnl"]` at services/arena_pipeline.py:712, 717, 1051, 1240, 1286). It is mapped — explicitly — to canonical `COST_NEGATIVE` in `RAW_TO_REASON` at services/arena_rejection_taxonomy.py:252.
- `reject_train_neg_pnl` (a sibling stats key, services/arena_pipeline.py:713, 988, 1238, 1284) has **NO entry** in `RAW_TO_REASON`. It also does not match any substring key. Therefore `classify("reject_train_neg_pnl", "A1")` falls through both stages of the lookup and returns `UNKNOWN_REJECT` (taxonomy.py:328).
- VERSION_LOG.md:4 and docs/decisions/20260420-arena-reconstruction.md:5 both still talk about `val_neg_pnl` and `train_neg_pnl` as the LIVE rejection categories; no renaming ADR exists.

---

## 4. Where `arena_batch_metrics.reject_reason_distribution` is computed

Aggregator chain (single authoritative path for A1):

1. **Counter** — `RejectReasonCounter` (services/arena_pass_rate_telemetry.py:161-199). Map of `str → int`. Only `add()` writes; only `as_dict()` reads.
2. **Owner** — `ArenaStageMetrics.reject_counter` (services/arena_pass_rate_telemetry.py:313). Per-batch mutable accumulator.
3. **Population (A1, per round)** — `_emit_a1_batch_metrics_from_stats_safe()` (services/arena_pipeline.py:167-239), called from arena_pipeline.py:1255. Walks the fixed stats-key tuple at lines 205-209, calls `classify()` per key, calls `acc.reject_counter.add(canonical, n)`. Then computes `residual` and emits `COUNTER_INCONSISTENCY` for negative residuals (line 231).
4. **Population (A2/A3, per candidate)** — `_p7pr4b_record_outcome()` (services/arena23_orchestrator.py:280-345). Calls `acc.on_rejected(canonical)` which delegates to `reject_counter.add()` (services/arena_pass_rate_telemetry.py:329-333).
5. **Freeze** — `build_arena_batch_metrics()` (services/arena_pass_rate_telemetry.py:368-409). Reads `stage_metrics.reject_counter.as_dict()` into `ArenaBatchMetrics.reject_reason_distribution` at line 385/404; reads `top_reason()` into `top_reject_reason` at line 386/403.
6. **Run-level rollup** — `build_arena_stage_summary()` (services/arena_pass_rate_telemetry.py:412 onward). Sums per-batch dicts at line 433 (`for reason, cnt in b.reject_reason_distribution.items()`).

There is no other writer to `reject_reason_distribution` in the live pipeline. (Tests and offline replay tools — `tools/replay_sparse_canary_observation.py`, `tools/profile_attribution_audit.py` — read or fabricate distributions, never write to live event flow.)

---

## 5. Initial finding — is COUNTER_INCONSISTENCY = UNKNOWN_REJECT the same root event counted twice?

**Strongly suspect: same upstream phenomenon, two distinct symptoms, double-booked into the distribution.** Reasoning chain (to be confirmed in Phase 3):

The A1 emitter (services/arena_pipeline.py:202-232) does the following per round:

```
reject_total = 0
for stats_key in (... 10 keys ...):       # only 10 hardcoded keys walked
    n = stats[stats_key]
    if n <= 0: continue
    canonical = classify(stats_key, "A1")  # may return UNKNOWN_REJECT
    acc.reject_counter.add(canonical, n)
    reject_total += n
residual = entered_count - passed_count - reject_total
if residual < 0:
    acc.reject_counter.add("COUNTER_INCONSISTENCY", abs(residual))
```

Two independent contributors to the observed distribution:

**(A) UNKNOWN_REJECT spike** — `reject_train_neg_pnl` (services/arena_pipeline.py:713, incremented at :988 inside the A1 train-side gate) is in the emitter's stats-key tuple at :206 but **has no `RAW_TO_REASON` entry**. `classify("reject_train_neg_pnl", "A1")` falls all the way through to taxonomy.py:328 and returns `UNKNOWN_REJECT`. Every A1 train_neg_pnl rejection lands in the UNKNOWN_REJECT bucket. Given the historical dominance pattern (VERSION_LOG.md:4, decisions/20260420-arena-reconstruction.md:5, decisions/20260422-valgate-counterfactual-audit.md:24 — "72% cells died from train_neg_pnl"), this single missing taxonomy entry plausibly accounts for **all 13350** UNKNOWN_REJECT rows.

**(B) COUNTER_INCONSISTENCY spike** — fires when `len(alphas) > round_champions + sum(stats[reject_*])`. The 10 keys walked at :205-209 are NOT the only places an alpha disappears. Lines 904, 908, 935, 948-949 (bloom_hits), 962, 972, 994, 1005, 1021, 1041, 1055, 1059 all `continue` past the round loop without incrementing any of the 10 tracked stats keys (alphas dropped on bloom-filter hits, NaN-Inf output, zero-variance, compile errors counted in `alpha_compile_errors` not in any `reject_*`, etc.). Each silent drop adds 1 to the residual. So COUNTER_INCONSISTENCY ≈ count of alphas eliminated by un-tracked filters.

**Why the two counts are equal (13350 = 13350):** if the dominant un-tracked silent-drop path also corresponds to the same A1 stage where `reject_train_neg_pnl` would normally be the explicit bucket, *or* if a refactor moved `train_neg_pnl` out of the emitter's stats-key list (so it's both untracked AND silently dropped on the same code path), every train_neg_pnl event would simultaneously (i) miss the `reject_total` accumulation → bump `residual` → bump COUNTER_INCONSISTENCY by 1, and (ii) since stats[`reject_train_neg_pnl`] is in the walked list and IS being incremented at :988, classify() returns UNKNOWN_REJECT → bump UNKNOWN_REJECT by 1.

> **Hypothesis to confirm in Phase 3:** every A1 round currently rejects on `reject_train_neg_pnl`, which is BOTH (a) walked by the emitter and bucketed into UNKNOWN_REJECT (because no taxonomy mapping), AND (b) somehow not contributing to `reject_total` (e.g. the increment at :988 is gated/skipped under the current strategy/horizon configuration, leaving `len(alphas) − round_champions` entirely as residual). Either way, the equality `COUNTER_INCONSISTENCY == UNKNOWN_REJECT` is consistent with **one underlying class of rejections being double-booked: once as an "unmapped reason" and once as an "unaccounted-for residual"**.

> **Q1 adversarial flag:** the current taxonomy + emitter contract violates §17.6-style "no silent failure propagation" — `classify()`'s UNKNOWN_REJECT fallback was designed to be terminal, but the emitter at services/arena_pipeline.py:202-222 silently widens it by feeding *every* stats-key directly into classify(), including keys that lack mappings. There is no warning, no log, no test asserting that every walked stats-key has a `RAW_TO_REASON` entry. Recommend Phase 3 add a contract test: `set(emitter_stats_keys) ⊆ set(RAW_TO_REASON.keys())` — fail-loud if a stats key has no canonical mapping.

---

## 6. Artefacts produced

- `/tmp/0_9x_reject_taxonomy_refs.txt` — 1326 lines, full grep dump of all reject-taxonomy refs across `zangetsu/`, `tests/`, `scripts/`, `docs/`. Available for cross-check.
- This file: `docs/recovery/20260424-mod-7/0-9x-a1-reject-distribution-shift-diagnosis/02_reject_taxonomy_map.md`.

No source files modified. No git operations. Read-only mission complete.
