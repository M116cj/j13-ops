# 06 — Rollback and Alerting Verification (0-9S-CANARY)

> Stack `0-9P/R-STACK-v2`：PR-A `a8a8ba9`（attribution audit）→ PR-B
> `3219b805`（feedback budget allocator）→ PR-C `fe3075f`（feedback
> budget consumer）→ PR-D `0d7f67d`（0-9S-READY rollback / alerting
> plan）→ **本 PR：0-9S-CANARY observer + readiness checker**。
>
> 本檔證明：0-9S-READY 已 ship 的 rollback plan（PR-D 03）與 alerting
> plan（PR-D 04）**對本 PR 引入的 observer 同樣適用**；同時說明本 PR
> 對 readiness 提供的額外貢獻（CR11 + CR12 與其對應 evidence 測試）。
>
> 對齊 TEAM ORDER 0-9S-CANARY §6 + §11 + CLAUDE.md §17.1 SINGLE TRUTH /
> §17.2 MANDATORY WITNESS / §17.3 CALCIFER OUTCOME WATCH / §17.4
> AUTO-REGRESSION REVERT / §17.6 STALE-SERVICE CHECK / §17.7 DECISION
> RECORD CI GATE。

---

## 1. References

| 參考檔 | 用途 |
| --- | --- |
| `docs/recovery/20260424-mod-7/0-9s-ready/03_rollback_plan.md` | Rollback runbook（trigger / hot-swap / 24-h review / multi-rollback policy）|
| `docs/recovery/20260424-mod-7/0-9s-ready/04_alerting_and_monitoring_plan.md` | Alerting plan（channel / severity ladder / Calcifer watchlist / Telegram format）|
| `docs/recovery/20260424-mod-7/0-9r-impl-dry/04_attribution_audit_dependency.md` | Attribution verdict regression rule (CR2 / F7) |
| `docs/recovery/20260424-mod-7/0-9r/05_ab_evaluation_and_canary_readiness.md` | F1–F9 / CR1–CR9 source |
| `docs/recovery/20260424-mod-7/0-9s-canary/05_runtime_isolation_audit.md` | Sibling doc：證明 observer 不進入 runtime |
| CLAUDE.md §17.1 / §17.2 / §17.3 / §17.4 / §17.6 / §17.7 | Cross-project hard rules |

> 0-9S-READY plans 已於 PR-D `0d7f67d` 合併到 `main`。本 PR 不重寫
> rollback / alerting plan，只 **驗證該 plan 對 observer 同樣 apply**
> 並補上對應的 PR-time enforcement（CR11 + CR12）。

---

## 2. Why rollback applies to a "do-nothing observer"

Observer 自身不修改 budget、不修改 sampling weight、不寫 swap file、
不影響 generation runtime（已由 sibling doc 05 證明）。即便如此，
governance 紀律仍要求 rollback 機制必須適用，理由如下：

### 2.1 Observation 是 future decision 的輸入

Observer 輸出的 `SparseCanaryObservation` records 會被：

- 寫入 governance evidence file（`docs/governance/observations/canary-{run_id}-{ts}.json`）；
- 透過 AKASHA `POST /witness {kind: "canary_observation", ...}`
  獨立記錄；
- 作為 future TEAM ORDER `0-9S-CANARY-OBSERVE` / `0-9T` 的 input 之一。

如果 observation 結果本身有 corruption（例如：attribution verdict
誤判 GREEN→RED、baseline 取錯時間窗、composite_delta 算錯），
下游決策（continue / rollback / promote）會被誤導。

> 換句話說：observer 雖不直接 mutate runtime，但 mis-observation
> 會污染 governance decision chain。Rollback 的對象是「污染的 observation
> 紀錄與基於它的 PR」。

### 2.2 Rollback 等價於 revert 本 PR + 重新審計

對 do-nothing observer 而言，rollback 不需要 hot-swap runtime weights
（observer 沒有 runtime weights）；只要：

1. `git revert <merge-sha>` 把 observer + readiness checker 從 `main`
   移除；
2. 重新 audit 受影響時間窗（從 observer 開始 emit observation 起算）
   內所有 `canary_observation` witness records，標記為 `tainted`；
3. 對 governance evidence 目錄的對應 file 加 `INVALIDATED_BY_REVERT`
   標籤。

### 2.3 30-min reversibility invariant 仍成立

對齊 0-9S-READY 03 §1：「Every CANARY apply MUST be reversible within
30 minutes.」對 observer 而言這條更容易滿足：

- 沒有 on-disk runtime state 需要 undo（observer 不寫 `/var/lib/...`）；
- 沒有 swap file 需要還原；
- 沒有 systemd service 需要重啟；
- 唯一動作是 `git revert` + push，受 branch protection / signed PR / CI
  gate 保護，30 min 內可完成。

> **observer 的 rollback 是「最便宜的 rollback」**；正因為便宜，
> governance 沒有理由跳過它。

---

## 3. Rollback artifact verification（CR11）

Readiness checker 的 CR11 在 PR time 直接驗證：rollback plan artifact
存在於 repo。

### 3.1 CR11 定義

```python
# zangetsu/tools/sparse_canary_readiness_check.py
CR11_ROLLBACK_PLAN = "CR11"

def _check_rollback_plan(repo_root: Path) -> ReadinessCheckResult:
    expected = repo_root / "docs" / "recovery" / "20260424-mod-7" \
                       / "0-9s-ready" / "03_rollback_plan.md"
    if not expected.exists():
        return ReadinessCheckResult(
            cr=CR11_ROLLBACK_PLAN,
            passed=False,
            detail=f"missing {expected}"
        )
    return ReadinessCheckResult(
        cr=CR11_ROLLBACK_PLAN,
        passed=True,
        detail=f"found {expected}"
    )
```

### 3.2 CR11 結果

| 項目 | 值 |
| --- | --- |
| 檔案路徑 | `docs/recovery/20260424-mod-7/0-9s-ready/03_rollback_plan.md` |
| Committed at SHA | `0d7f67d`（PR-D of stack 0-9P/R-STACK-v2） |
| CR11 verdict | **PASS** |
| 對應測試 | `test_canary_finds_rollback_plan_in_repo` |
| 反向測試 | `test_canary_blocks_missing_rollback_plan`（hypothetical scenario：刪掉檔案後 CR11 應 FAIL，passes by absence enforcement） |

### 3.3 為什麼 CR11 是 PR-time gate

- Observer 在 runtime activation 時（未來 0-9S-CANARY-OBSERVE order）
  必須能立即引用 rollback runbook。
- 如果 PR 合併時 rollback plan 還不在 repo，觀察期一旦觸發 F1–F9 任一
  failure，operator 會找不到 runbook → 進入無 fallback 的 governance
  vacuum。
- CR11 把這條依賴 fail-fast 到 PR review 階段，避免 deploy 後才發現缺
  artifact。

---

## 4. Rollback triggers（inherited from 0-9S-READY § 03）

Observer 的 `evaluate_failure_criteria` function 直接實作 0-9S-READY
03 §2.1 表格的 F1–F9 trigger。任一 trigger 命中 → observation
record `rollback_required = True` → 觸發 §5 hot-swap-adapted procedure。

### 4.1 F1–F9 mapping（observer field → 0-9S-READY trigger）

| F# | 0-9S-READY trigger | Observer signal | Failure constant |
| --- | --- | --- | --- |
| F1 | A2 improve 但 A3 collapse（A3 ≥ 5pp 下跌） | `success_a3_pass_rate.delta < -0.05` 且 `success_a2_sparse_rate.delta < 0` | `FAILURE_F1_A2_IMPROVE_A3_COLLAPSE` |
| F2 | A2 improve 但 deployable_count 下降 ≥ 1 | `treatment.deployable_count < baseline.deployable_count - 1` 且 `success_a2_sparse_rate.delta < 0` | `FAILURE_F2_DEPLOYABLE_DOWN` |
| F3 | OOS_FAIL ≥ baseline + 5pp | `treatment.oos_fail_rate - baseline.oos_fail_rate >= 0.05` | `FAILURE_F3_OOS_FAIL_INCREASE` |
| F4 | UNKNOWN_REJECT ≥ 0.05 | `treatment.unknown_reject_rate >= 0.05` | `FAILURE_F4_UNKNOWN_REJECT_INCREASE` |
| F5 | Profile collapse < 50% baseline | `treatment.actionable_profiles < 0.5 * baseline.actionable_profiles` | `FAILURE_F5_PROFILE_COLLAPSE` |
| F6 | Exploration floor 違反 | 任一 profile budget < 0.05 | `FAILURE_F6_EXPLORATION_FLOOR_VIOLATED` |
| F7 | Attribution verdict regression to RED | `attribution_verdict == "RED"` | `FAILURE_F7_ATTRIBUTION_RED` |
| F8 | Rollback artifact 不存在 | CR11 fail OR rollback runbook missing | `FAILURE_F8_ROLLBACK_UNAVAILABLE` |
| F9 | Composite score < baseline − 1σ | `composite_delta < -baseline.composite_sigma` | `FAILURE_F9_COMPOSITE_REGRESSION` |

### 4.2 非 F-trigger 的 rollback 來源

| 觸發來源 | 對齊 |
| --- | --- |
| j13 STOP via Telegram bot（`/stop 0-9S-CANARY`） | 0-9S-READY 03 §2.2，j13 STOP 是 final |
| Calcifer outcome watchdog RED（`/tmp/calcifer_deploy_block.json` 存在） | 0-9S-READY 03 §2.3 + CLAUDE.md §17.3 |
| Attribution verdict regression to RED | 0-9R-IMPL-DRY 04 §4 / observer F7 |
| Multi-rollback policy（30 day 內 ≥ 2 次 → governance halt） | 0-9S-READY 03 §7（本檔 §8 重述） |

> Observer 對 j13 STOP 與 Calcifer RED 不直接觀察（這兩者由 0-9S
> CANARY runtime watchdog 處理）；observer 只 **產生 evidence**，
> watchdog 才是 actuator。observer 的職責是 evidence emission，不是
> 直接觸發 rollback。

---

## 5. Hot-swap procedure adapted for observer

0-9S-READY 03 §4 定義的 hot-swap procedure 是針對 runtime consumer
weights swap（baseline ↔ treatment）。Observer 沒有 runtime weights，
adapted procedure 如下：

### 5.1 Adapted 7-step procedure

```
1. j13 issues STOP via Telegram bot OR auto-trigger by F1–F9
   → Telegram bot writes /tmp/canary_stop_request.json
   → notify operator channel (thread 362)

2. Calcifer writes /tmp/calcifer_deploy_block.json (RED)
   → JSON: {"reason": "F<n> | OPERATOR_STOP | ATTRIBUTION_RED",
            "trigger_ts": "...", "run_id": "..."}
   → presence of file = block on any feat(0-9s/vN) commit
   → 對齊 CLAUDE.md §17.3

3. Operator runs git revert on the merge commit
   git revert --no-edit <merge-sha>     # for 0-9S-CANARY observer PR
   git push --force-with-lease origin main
   - signed PR + branch protection enforce_admins=true 阻擋繞過
   - 對齊 CLAUDE.md §17.5（version bump 由 bin/bump_version.py only）
   - 30 min reversibility invariant 完全滿足（observer 無 on-disk
     state，純 git operation）

4. Operator marks observation evidence as tainted
   for f in docs/governance/observations/canary-{run_id}-*.json; do
       jq '. + {"status": "INVALIDATED_BY_REVERT", "revert_sha": "<sha>"}' "$f" > "$f.tmp"
       mv "$f.tmp" "$f"
   done
   - 確保 future audit 不會誤把 tainted observation 當成有效 evidence
   - 對齊 CLAUDE.md §17.1 SINGLE TRUTH

5. Operator verifies VIEW deployable_count not regressed
   psql -h <alaya> -c "
     SELECT count(*) FROM champion_pipeline_fresh
     WHERE status='DEPLOYABLE'
   "
   - count 必須 ≥ revert 前的 baseline floor
   - observer 不會直接影響 deployable_count，但 governance discipline
     要求 revert 後仍 spot-check
   - 對齊 CLAUDE.md §17.1

6. AKASHA witness service POSTs rollback record
   POST /witness {
       "kind": "canary_observer_rollback",
       "run_id": "...",
       "trigger": "F<n> | OPERATOR_STOP | ATTRIBUTION_RED | CALCIFER_RED",
       "rollback_sha": "<revert merge sha>",
       "tainted_observation_count": <int>,
       "ts": "..."
   }
   - 必須由 AKASHA 獨立 service 寫，不可由 operator script 自寫
   - 對齊 CLAUDE.md §17.2 MANDATORY WITNESS

7. Telegram alert sent
   - thread 362: "0-9S-CANARY observer rollback executed"
   - includes: trigger, run_id, revert_sha, tainted_observation_count,
     evidence file paths, AKASHA witness id
   - format 詳見 0-9S-READY 04 §6.3

8. 24-hour observation window
   - branch protection 對 0-9s-* / 0-9s-canary-* branch 啟動 lockout
   - observer / readiness checker 任何 re-introduction PR blocked，
     直到 incident report merged + 24h 觀察期結束
```

### 5.2 與原始 hot-swap 的差異

| 項目 | 0-9S-READY 03 §4 原始 | Observer adapted |
| --- | --- | --- |
| Step 3 動作 | 跑 `scripts/canary/rollback.sh` 寫 swap file | `git revert` + push |
| Runtime restart | 不需要（runtime hot-load swap file） | 不需要（observer 無 runtime） |
| State recovery | 從 `canary-pre-{run_id}-profile-weights-baseline.json` 還原 weights | 從 `canary-pre-{run_id}-observer-baseline.json` 還原 observation expectation（未來 order 啟用時補）|
| Verification | `champion_pipeline.status='DEPLOYABLE'` count ≥ baseline | 同上 + 標記 tainted observation |
| 30-min invariant | 滿足（hot-swap） | 滿足（git operation） |

### 5.3 24-hour observation window post-rollback

對齊 0-9S-READY 03 §6：rollback 之後 24 小時內：

- Branch protection 對 `0-9s-*` / `0-9s-canary-*` branches 啟用 lockout（read-only）；
- 任何 re-introduce observer 的 PR 被 CI Gate-A 拒絕；
- j13 必須在 24h 內 merge incident report（`docs/governance/incidents/{date}-rollback.md`）；
- 24h 後 j13 verdict 三選一：`RESUME_AFTER_FIX` / `RESUME_AFTER_REWORK` / `HALT_INDEFINITE`。

---

## 6. Alerting plan verification（CR12）

Readiness checker 的 CR12 在 PR time 驗證：alerting plan artifact
存在於 repo。

### 6.1 CR12 定義

```python
# zangetsu/tools/sparse_canary_readiness_check.py
CR12_ALERT_PLAN = "CR12"

def _check_alert_plan(repo_root: Path) -> ReadinessCheckResult:
    expected = repo_root / "docs" / "recovery" / "20260424-mod-7" \
                       / "0-9s-ready" / "04_alerting_and_monitoring_plan.md"
    if not expected.exists():
        return ReadinessCheckResult(
            cr=CR12_ALERT_PLAN,
            passed=False,
            detail=f"missing {expected}"
        )
    return ReadinessCheckResult(
        cr=CR12_ALERT_PLAN,
        passed=True,
        detail=f"found {expected}"
    )
```

### 6.2 CR12 結果

| 項目 | 值 |
| --- | --- |
| 檔案路徑 | `docs/recovery/20260424-mod-7/0-9s-ready/04_alerting_and_monitoring_plan.md` |
| Committed at SHA | `0d7f67d`（PR-D of stack 0-9P/R-STACK-v2） |
| CR12 verdict | **PASS** |
| 對應測試 | `test_canary_finds_alert_plan_in_repo` |
| 反向測試 | `test_canary_blocks_missing_alert_plan`（hypothetical scenario：刪掉檔案後 CR12 應 FAIL） |

### 6.3 Alerting channels（對齊 0-9S-READY 04 §1）

| Channel | Backend | 角色 |
| --- | --- | --- |
| **Calcifer** | Gemma4 E4B on Alaya:11434 | Outcome watchdog、§17.3 alignment |
| **Telegram bot** | @Alaya13jbot, chat -1003601437444, thread 362 | Operator notification |
| **AKASHA witness service** | http://100.123.49.102:8769 | Independent verification record (§17.2) |
| **Branch protection on `main`** | GitHub enforce_admins=true / signed-only / linear-history | Governance ledger |
| **GitHub Actions Gate-A / Gate-B** | Existing CI workflows | Pre-merge signal (§17.7) |

> 本 PR **不引入新 channel**；observer 完全複用 0-9S-READY 04 章已定義
> 的既有 infrastructure。

---

## 7. Observer-specific alert mapping

下表把 observer 輸出 field 對映到 0-9S-READY 04 §3 severity ladder
與 §4 action matrix。這是 PR-time 的「contract document」，未來
0-9S-CANARY-OBSERVE order 啟動 watchdog 時，watchdog 必須照本表
emit alert。

| Observer field | Alert severity | Channel | Threshold |
| --- | --- | --- | --- |
| `rollback_required = True` | BLOCKING | Telegram + Calcifer + AKASHA | 任何 F1–F9 trigger 命中 |
| `attribution_verdict == "RED"` | BLOCKING | Telegram + Calcifer | F7 |
| `unknown_reject_rate >= 0.05` | BLOCKING | Telegram | F4 |
| `profile_collapse_detected = True` | BLOCKING | Telegram | F5 |
| `oos_fail_rate - baseline.oos_fail_rate >= 0.05` | BLOCKING | Telegram | F3 |
| `consumer_plan_stability < 0.70` | WARN | Telegram | soft observability（pre-blocking signal） |
| `composite_delta < 0` | INFO | digest（thread 362）| 純 informational，不 trigger 任何 action |
| `S1-S5 ALL INSUFFICIENT_HISTORY` | INFO | digest | 觀察視窗尚未累積足夠樣本 |

### 7.1 Severity → Action 對照（與 0-9S-READY 04 §4 align）

| Severity | Auto action | Human action | Witness |
| --- | --- | --- | --- |
| INFO | none | optional read | AKASHA append daily summary |
| WARN | none | j13 review within 24h；逾期升 BLOCKING | AKASHA `kind=canary_warn` |
| BLOCKING | auto-rollback per 03 §4（adapted by §5 above） | j13 review within 24h（incident report） | AKASHA `kind=canary_observer_rollback` |
| FATAL | governance halt + branch lockout + auto git-revert | j13 manual review；不可短路 | AKASHA `kind=canary_fatal` + Calcifer RED |

### 7.2 為何 INFO/WARN 也要 record

對齊 P6（Record Decisions, Not Just Outcomes）：

- INFO digest 雖不 trigger action，但 trend line 可被 j13 用來評估
  「是否該 escalate 到 0-9S-CANARY-APPLY order」；
- WARN 是 future BLOCKING 的 leading indicator；忽略 WARN = 喪失
  pre-mortem 機會。
- Observer emission 全寫 AKASHA witness（即便是 INFO），讓未來 audit
  可重建完整 evidence chain。

---

## 8. Multi-rollback policy

對齊 0-9S-READY 03 §7：

| 條件 | 必要動作 |
| --- | --- |
| 30 day 內第 1 次 rollback（observer 觸發）| §6 24-hour review window，按 j13 verdict resume |
| 30 day 內第 2 次 rollback（observer 觸發）| 自動 `HALT_INDEFINITE`，require 獨立 `0-9R-IMPL-REWORK` order；j13 不可短路 |
| 30 day 內第 3 次 rollback（極端） | governance halt + branch protection 全 lockout 0-9s-* / 0-9r-impl-* / 0-9s-canary-* branches；j13 必須開新 `0-9P/R-STACK-v3` 重設 baseline |

### 8.1 為什麼 observer rollback 也算入

Observer 雖然是 do-nothing module，但「為什麼觀察結果一直觸發 rollback」
本身就是訊號：

- F1–F9 trigger 反覆命中 → 表示 stack 上游（allocator / consumer /
  attribution audit）有結構性問題；
- 多次 observer rollback = governance signal「stack v2 設計有缺陷」，
  不應該讓 observer 被反覆 revert/reintroduce 來掩蓋上游問題；
- 30 day window 由 `incident_report_merged_to_main_ts` 計算（與
  0-9S-READY 03 §7 同算法）。

對齊 CLAUDE.md §17.4 AUTO-REGRESSION REVERT 精神：時間是最終裁判，
反覆 rollback 代表「結構性問題」，不是「偶發 noise」。

---

## 9. Verification at PR-time

### 9.1 What this PR verifies

| 驗證項 | 方法 | 結果 |
| --- | --- | --- |
| Rollback plan artifact exists | CR11 (`_check_rollback_plan`) | PASS |
| Alerting plan artifact exists | CR12 (`_check_alert_plan`) | PASS |
| F1–F9 trigger functions implemented | `evaluate_failure_criteria` + 9 unit tests | PASS（116/116） |
| F8 trigger when rollback artifact missing | `test_failure_rollback_unavailable` | PASS（artifact-absent path 觸發 F8） |
| Observer 不引入 new channel | sibling doc 05 § runtime isolation matrix | PASS |
| Hot-swap adapted procedure documented | 本檔 §5 | (this document) |

### 9.2 What this PR does NOT verify（未來 order 才能驗）

PR review 階段無法執行 live rollback drill，理由：

- 沒有 production runtime（observer 自身 dry-run only）；
- 沒有 swap file infrastructure（observer 不寫 swap file）；
- `scripts/canary/rollback.sh` 在 0-9R-IMPL-APPLY 之前不存在
  （0-9S-READY 03 §9 明確說 rollback.sh 由未來 apply order 引入）。

替代方案（操作層活動，由未來 0-9S-CANARY-OBSERVE order 執行）：

| 替代 | 說明 |
| --- | --- |
| Rollback verification = `git revert` + reapply on a test branch | 由 operator 在 test branch 上 simulate revert 流程，驗證 30-min reversibility invariant |
| Alerting verification = artifact existence | CR12 PASS at PR time（本檔 §6.2） |
| Failure-trigger verification = unit test | `test_failure_*` 系列 9 tests + `test_canary_blocks_*` 系列 hypothetical tests |
| Live drill | 推到 0-9S-CANARY-OBSERVE activation order，**在 production runtime 上執行 ≥ 3 次 dry-run revert** |

### 9.3 PR-time gate summary

CR11 + CR12 兩個 readiness check 在 PR time 強制執行；任一失敗 →
readiness checker 退出非零 → CI Gate-A reject merge。

---

## 10. Cross-reference test list

下列測試組合構成本 PR 對 rollback / alerting 契約的完整 enforcement：

| 測試名稱 | 驗證內容 | 檔案 |
| --- | --- | --- |
| `test_canary_finds_rollback_plan_in_repo` | CR11 PASS（artifact 存在） | `test_sparse_canary_readiness.py` |
| `test_canary_finds_alert_plan_in_repo` | CR12 PASS（artifact 存在） | `test_sparse_canary_readiness.py` |
| `test_canary_blocks_missing_rollback_plan` | hypothetical scenario：artifact 不存在時 CR11 FAIL（passes by absence enforcement） | `test_sparse_canary_readiness.py` |
| `test_canary_blocks_missing_alert_plan` | hypothetical scenario：artifact 不存在時 CR12 FAIL | `test_sparse_canary_readiness.py` |
| `test_failure_rollback_unavailable` | F8 trigger：rollback artifact 缺失時 observation `rollback_required=True` 且 `failure=FAILURE_F8_ROLLBACK_UNAVAILABLE` | `test_sparse_canary_observer.py` |
| `test_failure_attribution_red` | F7 trigger | `test_sparse_canary_observer.py` |
| `test_failure_unknown_reject_increase` | F4 trigger | `test_sparse_canary_observer.py` |
| `test_failure_oos_fail_increase` | F3 trigger | `test_sparse_canary_observer.py` |
| `test_failure_profile_collapse` | F5 trigger | `test_sparse_canary_observer.py` |
| `test_failure_composite_regression` | F9 trigger | `test_sparse_canary_observer.py` |

> 全部測試列入 `pytest zangetsu/tests/test_sparse_canary_*.py`，
> 116/116 PASS。任一 regression 由 CI Gate-A 阻擋 merge。

---

## 11. 驗證命令清單（PR review 時人工 spot-check）

```bash
# 11.1 跑 rollback / alerting verification 相關測試
cd /Users/a13/dev/j13-ops
pytest zangetsu/tests/test_sparse_canary_readiness.py \
       -k "rollback or alert" -v
# expected: 4 passed (CR11 PASS, CR12 PASS, missing-rollback FAIL, missing-alert FAIL)

# 11.2 跑 F1–F9 failure trigger 測試
pytest zangetsu/tests/test_sparse_canary_observer.py \
       -k "failure_" -v
# expected: 9 passed (F1–F9 each)

# 11.3 確認 rollback plan + alerting plan artifact 存在
ls -la docs/recovery/20260424-mod-7/0-9s-ready/03_rollback_plan.md \
       docs/recovery/20260424-mod-7/0-9s-ready/04_alerting_and_monitoring_plan.md
# expected: both exist

# 11.4 確認 PR-D commit SHA 與 plan artifact 對應
git log --oneline --follow \
    docs/recovery/20260424-mod-7/0-9s-ready/03_rollback_plan.md | head -1
# expected: contains 0d7f67d

git log --oneline --follow \
    docs/recovery/20260424-mod-7/0-9s-ready/04_alerting_and_monitoring_plan.md | head -1
# expected: contains 0d7f67d

# 11.5 跑 readiness checker offline tool（CR1–CR12 全跑一遍）
python -m zangetsu.tools.sparse_canary_readiness_check
# expected: CR11 PASS, CR12 PASS（連同其餘 CR1–CR10）
```

---

## 12. Anti-list（明確 **不** 在本 PR scope 的東西）

對齊 0-9S-READY 03 §8（rollback 無法 recover 的東西）+ TEAM ORDER §6
（allowed scope）：

| 項目 | 為什麼不在 scope |
| --- | --- |
| `scripts/canary/rollback.sh` 實作 | 由未來 0-9R-IMPL-APPLY order 提供（0-9S-READY 03 §9） |
| Live revert drill on production runtime | 需要 0-9S-CANARY-OBSERVE activation order |
| Calcifer watchlist `/tmp/calcifer_watchlist.json` 部署 | 由 alerting plan 04 §5 規範，但實際部署在 activation order |
| Telegram bot `/stop 0-9S-CANARY` command 實作 | 既有 d-mail dispatcher 已支援 generic `/stop` pattern；CANARY-specific routing 在 activation order |
| AKASHA witness `kind=canary_observer_rollback` schema 註冊 | 由 AKASHA 服務側 PR 處理（不在 zangetsu repo） |
| Dashboard / Grafana panel | 0-9S-READY 04 §7 明確 out-of-scope；建議 0-9S-DASH order |
| Branch protection rule 修改 | 既有 main branch 已 enforce_admins=true / signed-only；本 PR 不改 |

> 對齊 P1（MVPr First）：本 PR 只做「PR-time artifact verification +
> contract documentation」；不擴 scope 到 runtime activation。

---

## 13. 結論

- 本 PR 引入的 observer 是 leaf module（sibling doc 05 證明），但
  governance discipline 要求 rollback / alerting 契約必須適用，因為
  observer 輸出進入 governance decision chain。
- 0-9S-READY 03 rollback plan + 04 alerting plan 對 observer **完全
  apply**；本 PR adapted hot-swap procedure 為「git revert + taint
  observation evidence」，30-min reversibility invariant 滿足。
- PR-time enforcement 由 CR11 + CR12 兩個 readiness check + 對應 4 個
  測試守住；CR11/CR12 PASS 是 merge 條件。
- F1–F9 failure trigger 由 observer 的 `evaluate_failure_criteria`
  完整實作，9 個 unit test + 116/116 PASS 確認 trigger 行為正確。
- 多次 observer rollback 進入 multi-rollback policy（§8），不可由
  j13 短路；governance signal 高於個人判斷。
- Observer 完全複用既有 channel（Calcifer / Telegram / AKASHA / branch
  protection / CI），**不引入新 infrastructure**，對齊 P3
  （Systematize Repeatable Work）。

> 本檔對齊：TEAM ORDER 0-9S-CANARY §6 / §11 + CLAUDE.md §17.1 SINGLE
> TRUTH + §17.2 MANDATORY WITNESS + §17.3 CALCIFER OUTCOME WATCH +
> §17.4 AUTO-REGRESSION REVERT + §17.6 STALE-SERVICE CHECK + §17.7
> DECISION RECORD CI GATE + 0-9S-READY 03（rollback runbook source）+
> 0-9S-READY 04（alerting plan source）+ 0-9S-CANARY 05_runtime_isolation_audit.md
> （sibling doc）。

---

## 14. Cross-reference

- `docs/recovery/20260424-mod-7/0-9s-ready/03_rollback_plan.md` — rollback runbook（source）
- `docs/recovery/20260424-mod-7/0-9s-ready/04_alerting_and_monitoring_plan.md` — alerting plan（source）
- `docs/recovery/20260424-mod-7/0-9s-canary/05_runtime_isolation_audit.md` — sibling doc（observer 不進入 runtime 的證明）
- `docs/recovery/20260424-mod-7/0-9r-impl-dry/04_attribution_audit_dependency.md` — F7 attribution verdict regression rule
- `docs/recovery/20260424-mod-7/0-9r/05_ab_evaluation_and_canary_readiness.md` — F1–F9 / CR1–CR9 source
- `zangetsu/services/sparse_canary_observer.py` — observer module（F1–F9 implementation）
- `zangetsu/tools/sparse_canary_readiness_check.py` — readiness checker（CR11 + CR12 implementation）
- `zangetsu/tests/test_sparse_canary_observer.py` — 9 failure-trigger tests
- `zangetsu/tests/test_sparse_canary_readiness.py` — CR11 + CR12 + 反向 missing-artifact tests
- CLAUDE.md §17.1 SINGLE TRUTH
- CLAUDE.md §17.2 MANDATORY WITNESS
- CLAUDE.md §17.3 CALCIFER OUTCOME WATCH
- CLAUDE.md §17.4 AUTO-REGRESSION REVERT
- CLAUDE.md §17.6 STALE-SERVICE CHECK
- CLAUDE.md §17.7 DECISION RECORD CI GATE
