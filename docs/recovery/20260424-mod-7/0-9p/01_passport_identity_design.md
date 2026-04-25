# 01 — Passport Identity Persistence Design

## 1. Background

P7-PR4B 已上線 A2/A3 aggregate `arena_batch_metrics`，並讀取
`passport.arena1.generation_profile_id` 作為首選識別來源。
0-9O-A 已交付 `generation_profile_identity` 與 A1 telemetry 的
profile id wiring。**現存 gap**：A1 雖然 emit 帶 profile_id 的
batch event，卻沒把 profile_id 寫入 passport，導致 A2/A3 reader
都落到 orchestrator consumer fallback。

0-9P 補完這個 gap：在 A1 admit 時間將 `generation_profile_id` 與
`generation_profile_fingerprint` 持久化到 candidate passport，使
P7-PR4B 既有 reader 真正能拾取上游身分。

## 2. Scope（metadata-only）

允許動的 runtime files（per TEAM ORDER 0-9P §4 / §5）：

- `zangetsu/services/arena_pipeline.py` — 在 A1 V10 passport 構造
  block（`passport = { ... "arena1": { ... } }`）內加兩個 metadata
  欄位。
- `zangetsu/services/generation_profile_identity.py` — 新增純
  Python 工具函數 `resolve_attribution_chain` 暴露 4 級 precedence
  契約給 tests / docs。

不動：

- `arena23_orchestrator.py` — P7-PR4B 既有 reader
  `_p7pr4b_resolve_passport_profile` 已先讀 `passport.arena1.generation_profile_id`，零變更即可拾取新欄位。
- `arena45_orchestrator.py` — 不在 A2/A3 attribution 鏈上。
- `arena_pass_rate_telemetry.py` — schema 已支援 `generation_profile_id` /
  `generation_profile_fingerprint` 欄位（P7-PR4-LITE 即定義）。
- `generation_profile_metrics.py` — 已能消化帶 profile_id 的 batch
  event。
- `arena_gates.py`、`zangetsu/config/`、threshold、A2_MIN_TRADES、
  champion promotion、deployable_count 全部不變。

## 3. Data flow（after 0-9P）

```
A1 worker boot
  └─ _gen_profile_identity = safe_resolve_profile_identity({knobs})
                                     │
A1 admit time (per-candidate)        ▼
  └─ passport["arena1"]["generation_profile_id"]          ← NEW
     passport["arena1"]["generation_profile_fingerprint"] ← NEW
                                     │
DB write (champion_pipeline_staging.passport JSONB)        ▼
                                     │
A2/A3 orchestrator pickup            ▼
  └─ _p7pr4b_resolve_passport_profile(passport)
        precedence:
          1. passport.arena1.generation_profile_id    ← now populated
          2. passport.generation_profile_id           (rare; future schemas)
          3. orchestrator consumer profile            (existing fallback)
          4. UNKNOWN_PROFILE / UNAVAILABLE            (final fallback)
                                     │
A2/A3 batch metrics emission         ▼
  └─ ArenaBatchMetrics(generation_profile_id=..., ...)
                                     │
generation_profile_metrics aggregate ▼
  └─ correctly groups A1+A2+A3 batches by upstream profile id
```

## 4. Schema delta

`passport["arena1"]` 之前 24 欄位，0-9P 後 26 欄位（+2）：

```json
{
  "arena1": {
    "alpha_expression": {...},
    "alpha_hash": "...",
    "formula": "...",
    ...

    // 0-9P additions (additive, metadata-only):
    "generation_profile_id": "gp_aaaa1111bbbb2222",
    "generation_profile_fingerprint": "sha256:..."
  },
  "market_state": {...},
  "data_split": {...},
  "val_metrics": {...}
}
```

兩欄位永遠存在（即便 fallback 也是 `UNKNOWN_PROFILE` /
`UNAVAILABLE`）。Caller 可依此判斷 attribution 是否來自 A1
producer。

## 5. Failure handling

passport 寫入路徑用 try/except 包裹：

```python
try:
    _passport_profile_id = (
        _gen_profile_identity.get("profile_id") or _UNKNOWN_PROFILE_ID
    )
    _passport_profile_fingerprint = (
        _gen_profile_identity.get("profile_fingerprint")
        or _UNAVAILABLE_FINGERPRINT
    )
except Exception:
    _passport_profile_id = _UNKNOWN_PROFILE_ID
    _passport_profile_fingerprint = _UNAVAILABLE_FINGERPRINT
```

任何 identity 解析失敗 → 安全 fallback；不阻塞 candidate 寫入；
不影響 Arena 決策。

## 6. resolve_attribution_chain helper

新增 `zangetsu/services/generation_profile_identity.resolve_attribution_chain`：

```
resolve_attribution_chain(
    passport,
    *, orchestrator_profile_id, orchestrator_profile_fingerprint,
) -> {
    "profile_id":          str,
    "profile_fingerprint": str,
    "source": "passport_arena1" | "passport_root" | "orchestrator" | "fallback",
}
```

純 Python；不 import runtime 模組；不引入 IO；never raises。
是 0-9P attribution 契約的單一可測試入口。

## 7. Non-goals

- 不引入 per-alpha lineage。
- 不引入 parent-child mutation ancestry。
- 不引入 formula explainability。
- 不修改 candidate admission gate。
- 不修改 Arena pass/fail。
- 不修改 deployable_count semantics。
- 不修改 sampling weights / 真實 generation budget。

## 8. Testability

由於 `arena_pipeline.py` 與 `arena23_orchestrator.py` 模組頂端執行
`os.chdir('/home/j13/j13-ops')`，local Mac 不能直接 import。0-9P
測試策略：

1. **Source-text checks** — 對 `arena_pipeline.py` 字串掃描確認
   passport literal 含新欄位、failure fallback 路徑存在、且
   `admission_validator` SQL INSERT 不包含 profile_id（仍只在 JSONB
   blob 內）。
2. **Pure-Python helper tests** — 對
   `resolve_attribution_chain` 全面 precedence + edge case 測試。
3. **Reader compatibility checks** — 對 `arena23_orchestrator.py`
   字串掃描確認 P7-PR4B reader 順序仍是 arena1 → root → orchestrator
   → fallback。
4. **Behavior invariance checks** — 對 `arena_gates.py` /
   `arena45_orchestrator.py` / `arena_rejection_taxonomy.py` 字串
   掃描確認沒有任何 `generation_profile_id` 引用（=未把 identity
   洩入 Arena 決策）。

完整測試清單見 `05_test_results.md`。
