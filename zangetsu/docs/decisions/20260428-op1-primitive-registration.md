# 20260428 — OP1: 9 GP Primitives × 3 Periods Registration

**TEAM ORDER**: 0-9Y-OP1-PRIMITIVE-REGISTRATION
**Master Mission**: 0-9Y-FINAL-ZANGETSU-ALPHA-EDGE-RESTORATION-PROGRAM
**Allowed redesign axis (§MASTER ORDER 5-1)**: #2 Feature-space expansion
**Base HEAD**: `3bf5c1113b9204ff7965109ae9e39cfbf1298082`

## What was decided
在 `engine/components/alpha_engine.py:_build_pset()` 中註冊 9 個 GP primitives：
`ts_sum, ts_mean, ts_std, ts_argmax, ts_argmin, rolling_scale, covariance, log_x, exp_x`

帶 window 參數的 7 個 primitives 各以 `(20, 60, 240)` 三個 period 註冊；`log_x` / `exp_x` 為 pointwise（無 window）。共 **23 個新 GP operators**：

- 6 unary windowed × 3 periods = 18
- 1 binary windowed (covariance) × 3 periods = 3
- 2 pointwise unary (log_x, exp_x) = 2

並在 `_FallbackPrims` class 加上 9 個 numpy-only stub 實作，數值與 numba 版本等價（max |delta| ≤ 2.44e-4 in float32）。

## Why
- **MASTER ORDER 0-9Y-C 結論**：FINAL_VERDICT = `DECOMPOSED_GROSS_EDGE_LOST_TO_COST`
- 106 post-restart batches: train_gross_pnl_median = +2.46 bps, cost/gross = 1.54x → gross edge 為正但被 cost 吃掉
- 唯一允許的修補軸是 alpha generation；其中 feature-space 擴張是最低 risk 的選項（不動 validation/cost/gate）
- Phase 7 feature-space audit 預期會檢查 "missing primitives" — OP1 提前補齊基礎時序算子，避免 audit blocked
- Gemini /review APPROVE_WITH_NIT：要求修補 `_FallbackPrims` 的 graceful-fallback 設計不變式 → 已修補

## What was rejected
| 拒絕方案 | 理由 |
|---|---|
| 廣譜 primitive set（含 microstructure/orderbook）| 違反 MASTER ORDER「Phase E5/F 才開」的階段門禁 |
| 單一 period（如僅 60）| 60-bar 已是現行 horizon，無法測 horizon expansion 假說（需 240 等更長窗）|
| 留 fallback 缺口（接受 nit）| §5 規定 Gemini finding 必修或必文件化；本 nit 影響 graceful-degradation 設計不變式，現補成本最低 |
| 動態 period（runtime tunable）| OP1 是 registration 階段；tunable 屬 HE2/HE3 範疇，本階段保持靜態 |

## Adversarial voice (Q1, all 5 dimensions)
1. **Input boundary** — PASS：所有 stubs 對 `d<=0/1` guard，對 NaN/empty 產生 zeros；所有 numba primitives 已具備此守衛
2. **Silent failure propagation** — PASS：23 個 operator name 唯一（`set==list==23`）；DEAP `addPrimitive` 對重名會 raise；`_FallbackPrims` 缺方法的 silent AttributeError 路徑已封閉
3. **External dependency** — PASS：`alpha_primitives` import 失敗時 `HAS_PRIMS=False` → `prims=_FallbackPrims`，全部 9 個 ops 仍可工作（純 numpy，無 numba 依賴）
4. **Concurrency / race** — PASS：pset 在 `AlphaEngine._build_pset` 中一次建構，無共享 mutable state；numba njit 函式對 read-only ndarray thread-safe
5. **Scope creep** — PASS：diff stat = +257 LOC additive，1 file；`grep -iE 'A2_MIN_TRADES|alpha_zoo|CANARY|validat|cost|deployable|champion|fee|slippage|production|kill|watchdog'` → `NO_FORBIDDEN_TOUCHES`

## External research
- DEAP issues #219/#291/#334/#425：strongly-typed GP type signature pitfalls — N/A，本 engine 用 untyped GP
- DEAP PR #53：gp.generate fallback to terminal — 本 OP1 未改 generation
- Lambda capture pattern `dd=d`：Python 標準慣用法（避免 late-binding closure bug）— ✓ TEST3 驗證
- 文件：`.claude/scratch/research-op1-primitives-20260428.md`（待補）

## Q1/Q2/Q3 status
- **Q1**: PASS — 5 個 adversarial 維度逐項記錄，full verification suite (TEST1-4) 全綠
- **Q2**: PASS — additive registration，無 error path 變更；`_FallbackPrims` 補齊後 graceful-degradation 不變式恢復
- **Q3**: PASS — `dd=d` default-arg 是規範寫法；fallback stubs 性能犧牲僅在 numba 不可用的災難場景

## Verification suite (all PASS)
1. `git diff --stat` → +257 / -0 / 1 file
2. AST parse → AST_OK
3. Forbidden-grep → `NO_FORBIDDEN_TOUCHES`
4. TEST1 fallback import-failure sim → 9 stubs callable, no NaN
5. TEST2 numba primitive smoke → 9 primitives ndarray→ndarray
6. TEST3 lambda capture distinctness → ts_sum_{20,60,240}.first_nz = {19,59,239}
7. TEST4 fallback ≈ numba parity → max |delta| = 2.44e-4 (exp_x), median <1e-6

## Consequences
- A1 GP search 可使用 ts_*/covariance/rolling_scale/log_x/exp_x 構建 alpha 表達式
- Phase 7 feature-space audit 可進入：用 (20, 60, 240) 量測 unique formula count / operator frequency / tree-depth distribution
- HE2/HE3 horizon-aware generation/telemetry 仍待後續 OP step
- Fallback 路徑現為 graceful（之前若 numba 失效會 silent AttributeError mid-evolution）

## REUSABLE
```
# REUSABLE: deap-windowed-primitive-registration | use-when: 在 untyped DEAP GP 註冊多 period 同 primitive | extract-if: used in >= 2 projects
```
慣用法：`pset.addPrimitive((lambda x, dd=d: prims.fn(x, dd)), 1, name=f"fn_{d}")` — 默認參數捕捉避免 late-binding；name 必須唯一。

## Verdict
**COMPLETE_OP1_PRIMITIVES_REGISTERED**
