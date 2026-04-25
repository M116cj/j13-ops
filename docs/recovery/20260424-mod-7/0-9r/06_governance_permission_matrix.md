# 06 — Governance Permission Matrix

## 1. 範圍

把 sparse-candidate intervention 涉及的所有任務類型，按 governance
risk 分級。每一類標明：

- **Risk** 等級（Low / Medium / High / Critical）
- **是否要單獨的 j13 授權**
- **是否在 0-9R 範圍**（YES / NO）
- **典型範例**

本檔僅為設計目錄，不啟動任何 task。

## 2. Permission matrix

| # | Task type | 範例 | Risk | 需獨立 j13 授權？ | 在 0-9R 範圍 |
| --- | --- | --- | --- | --- | --- |
| 1 | Documentation-only | design report、roadmap、red-team register、future order draft | Low | 在當前 order 範圍即可 | **YES** |
| 2 | Offline analytics | summarize dry-run allocator output、generate weekly report | Low | 在當前 order 範圍即可（純 docs） | **YES** if docs only |
| 3 | Runtime telemetry | new metrics emission、新 reject reason mapping | Medium | separate trace-only order（如 P7-PR4-LITE / P7-PR4B 模式） | NO |
| 4 | Dry-run allocator scoring change | 修 allocator's `compute_profile_score` 權重、加新 confidence state | Medium | separate dry-run-only order（如 0-9O-A / 0-9O-B 模式） | NO |
| 5 | Real budget reweighting | apply `proposed_profile_weights_dry_run` to live generation | **High** | explicit 0-9R-IMPL order + CANARY pass | NO |
| 6 | Sampling policy change | 改 generator profile activation probability | **High** | explicit generation-policy order | NO |
| 7 | Candidate prefilter change | pre-A2 density screen、Bloom-filter dedup tweak | **High** | explicit generation-policy order | NO |
| 8 | Profile quarantine | per-profile cooldown / re-entry rule | **High** | explicit 0-9R-IMPL order；must include resurrection rule | NO |
| 9 | Threshold change | A2_MIN_TRADES、ATR_STOP_MULTS、TRAIL_PCTS、FIXED_TARGETS | **Critical** | explicit threshold order；不可作為 sparse intervention 的副產品 | NO |
| 10 | Arena pass/fail change | `arena2_pass`、`arena3_pass`、`arena4_pass` 條件 | **Critical** | explicit Arena order | NO |
| 11 | Champion promotion change | CANDIDATE → DEPLOYABLE gate、Wilson LB、PROMOTE_MIN_TRADES | **Critical** | explicit promotion order | NO |
| 12 | Deployable_count semantics | VIEW 定義、status enumeration | **Critical** | explicit deployable-semantics order | NO |
| 13 | Rejection semantics | `arena_rejection_taxonomy` enum / RAW_TO_REASON | Medium | trace-only order（taxonomy completeness） | NO（但 0-9R 可建議補強） |
| 14 | Execution / capital / risk | live trading、broker integration、position sizing | **Critical** | execution / risk order | NO |
| 15 | CANARY | limited-cohort production deployment | **High** | explicit CANARY order (0-9S) + 0-9R-IMPL pass | NO |
| 16 | Production rollout | full production deployment | **Critical** | explicit production order (0-9T) + CANARY pass | NO |
| 17 | Branch protection / governance config | `enforce_admins`、`required_signatures`、`linear_history` | **Critical** | governance-only order；極少數情況才允許 | NO |

## 3. 「Critical」級規則

- 必須有獨立的 order document（非 sparse-candidate 子任務）。
- 必須有 j13 顯式授權字句（不可從泛化授權推導）。
- 必須附 controlled-diff snapshot（pre + post）。
- 必須通過 Gate-A + Gate-B。
- 必須有可逆的 rollback path。
- merge 必須 GitHub-signed verified=true。

## 4. 「High」級規則

- 必須有獨立的 order document。
- 必須有 j13 顯式授權。
- 必須通過 dry-run 階段才能進 CANARY。
- 必須有 A/B 評估設計（見 §05）。
- merge 必須 GitHub-signed verified=true。

## 5. 「Medium」級規則

- 可作為既有 phase / mod 的延伸 order。
- 必須通過 controlled-diff（trace-only / dry-run only）。
- 必須有完整測試。
- merge 必須 signed。

## 6. 「Low」級規則

- 可在當前 order 範圍內完成（如 0-9R 本身就是 Low）。
- 仍須 signed merge。
- 仍須 Gate-A + Gate-B pass。

## 7. 0-9R 自身 governance

**0-9R 屬於 Low（documentation-only）**。

- 範圍：design package 11 份 markdown。
- 不修改 runtime code。
- controlled-diff 預期 EXPLAINED（無 CODE_FROZEN runtime SHA 變動）。
- 必須通過 Gate-A + Gate-B。
- 必須 signed merge（用 j13 ED25519 SSH key）。

## 8. 「不在 0-9R 範圍」清單（給未來 order writer 參考）

以下任務**全部不屬於** 0-9R；任一任務若被誤納入 sparse-candidate
intervention，0-9R red-team 將標 STOP：

- 改 alpha / formula / mutation / crossover / search policy
- 改 generation budget / sampling weight
- 改 thresholds（A2_MIN_TRADES 等）
- 改 Arena pass/fail logic
- 改 champion promotion logic
- 改 deployable_count semantics
- 改 execution / capital / risk
- 啟動 CANARY / production rollout
- 連接 dry-run allocator 到 runtime
- 引入 apply path
- 引入 per-alpha lineage
- 把 formula explainability 設為強制需求

## 9. j13 授權句式

每個未來 order 啟動前需有形如以下的明確授權句：

```
j13 authorizes TEAM ORDER <id> — <title>. Execute under signed PR-only
governance. Scope is <scope>. <hard limits>. <stop conditions>. STOP
after signed merge, evidence report, and local main sync.
```

任何「泛化授權」（如「全權處理 sparse 問題」）**不**等同 j13 顯式
order。0-9R 設計者應拒絕此類泛化授權。

## 10. Audit trail

所有 sparse-candidate intervention 的決策軌跡必須沉澱在：

- `docs/recovery/20260424-mod-7/0-9r/` — 設計（本 PR）
- `docs/recovery/20260424-mod-7/0-9r-impl/` — 實作（未來，需 j13 order）
- `docs/governance/snapshots/` — controlled-diff snapshot
- `docs/governance/reports/` — A/B evaluation 結果
- `docs/governance/incidents/` — rollback / failure record
- AKASHA `_global` segment — 跨 session 持久記憶

任何決策若無 audit trail 即視為未發生；後續 review 不予承認。
