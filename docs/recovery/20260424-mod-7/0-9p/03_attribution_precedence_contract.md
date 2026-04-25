# 03 — Attribution Precedence Contract

## 1. 4-level precedence

| 優先級 | 來源 | 定義 |
| --- | --- | --- |
| 1 | `passport["arena1"]["generation_profile_id"]` | A1 producer 生成 candidate 時寫入。0-9P 起永遠存在（fallback 也會寫 UNKNOWN）。 |
| 2 | `passport["generation_profile_id"]` | 根層 override，預留給未來 schema 變體。0-9P 不主動寫此欄位。 |
| 3 | `orchestrator_profile_id` | A2/A3 orchestrator boot 時用 V10 entry/exit/min_hold/cooldown knobs 推導的 consumer profile（P7-PR4B 既有）。 |
| 4 | `UNKNOWN_PROFILE_ID` / `UNAVAILABLE_FINGERPRINT` | 全部缺漏；最終 fallback。Telemetry 仍會 emit，僅 profile 欄位是 UNKNOWN。 |

### 1.1 為何 arena1 比 root 優先

A1 producer 是 identity 的真實來源；root passport 留給未來 schema
擴充使用。除非別處有更明確的需求，**永遠**先選 A1 字段。

### 1.2 為何 orchestrator 比 UNKNOWN 優先

orchestrator 的 V10 knobs 在運轉中是穩定常數，可作為「資料齊全前的
最佳猜測」。比直接 UNKNOWN 多一份 traceability。

### 1.3 為何 UNKNOWN 是最後 fallback

確保 telemetry 永不 block，無論 identity 多缺。Allocator / consumer
日後讀到 UNKNOWN 自動 mark NON_ACTIONABLE（0-9O-B 已實作）。

## 2. Helper 實作

`zangetsu/services/generation_profile_identity.resolve_attribution_chain`
（純 Python，never raises）：

```python
def resolve_attribution_chain(
    passport: Optional[Mapping[str, Any]] = None,
    *,
    orchestrator_profile_id: Optional[str] = None,
    orchestrator_profile_fingerprint: Optional[str] = None,
) -> dict:
    """Returns:
       {"profile_id": str,
        "profile_fingerprint": str,
        "source": "passport_arena1" | "passport_root" | "orchestrator" | "fallback"}
    """
```

返回 `source` 字段使 caller 能判斷 identity 從哪一級拾取。
allocator / audit tool / dashboards 應記錄 source 統計，便於監控
attribution coverage。

## 3. Falsy 值規則

下列輸入視為「該級缺漏」並 fall through 到下一級：

- `None`
- 空字串 `""`
- 整數 `0`、`False`
- 非 mapping 的 `passport["arena1"]`（例：corrupt 字串）

明確拒絕的 anti-pattern：把空字串 `""` 視為「身分為空字串」。
`""` 永遠視為缺漏。

## 4. 安全保證

| 保證 | 機制 |
| --- | --- |
| 永不 raise | 全函式 try/except 包裹；exception path 直接回 fallback |
| 永遠回三欄位 | 任何分支都返回 `profile_id`、`profile_fingerprint`、`source` |
| 不 mutate 輸入 | 只 `.get(...)`；不寫回 |
| Deterministic | 同樣 input 永遠同樣 output |
| 不 import runtime 模組 | helper 只 import 本模組常數 |

## 5. 測試覆蓋（部分）

`tests/test_passport_profile_attribution.py`：

- `test_passport_arena1_identity_takes_precedence`
- `test_passport_root_identity_used_if_arena1_missing`
- `test_orchestrator_fallback_when_passport_missing_identity`
- `test_unknown_profile_fallback_when_all_identity_missing`
- `test_unavailable_fingerprint_fallback`
- `test_resolve_attribution_chain_handles_non_mapping_passport`
- `test_resolve_attribution_chain_handles_non_mapping_arena1`
- `test_resolve_attribution_chain_never_raises`
- `test_passport_arena1_empty_string_id_falls_through`
- `test_passport_identity_round_trips_through_attribution_chain`
- `test_resolve_attribution_chain_with_only_orchestrator`
- `test_resolve_attribution_chain_with_passport_arena1_no_fingerprint`
- `test_resolve_attribution_chain_orchestrator_fingerprint_preserved`

## 6. Coverage 訊號

0-9P-AUDIT（PR-B）會用此 helper 在 batch event log 上做 attribution
coverage 統計，產出 `passport_identity_rate` /
`orchestrator_fallback_rate` / `unknown_profile_rate` 等指標，
用作後續 0-9R-IMPL-DRY 啟動門檻（GREEN / YELLOW / RED 分級）。
