# 07 — Governance Approval Matrix (CANARY-phase extension)

## 1. Purpose

本檔為 **PR-D / 0-9S-READY** 的 governance approval matrix。它**不**取代
0-9R 的 base permission matrix（`docs/recovery/20260424-mod-7/0-9r/06_governance_permission_matrix.md`），
而是把該 17-task base matrix 延伸到 CANARY phase，補上：

1. **誰需要核准**（Operator / j13 / Calcifer / AKASHA / GitHub branch
   protection / Gate-A / Gate-B）。
2. **何種 j13 授權句式為必要**（不可由泛化授權推導）。
3. **何種 audit trail 必須存在**（pre / during / post 三段）。
4. **每個 phase 允許的 action 邊界**（docs only / metadata-only /
   offline / dry-run / live-cohort / production）。

0-9R base matrix 的 17 條 task type 與其 risk 分級在此**仍完全有效**；
本檔不重複該表，僅在「task type × phase」交集點加註 CANARY-specific
gate。Base matrix 條目仍以 `0-9R/06 #N` 形式引用。

PR-D 本身為 documentation-only（base matrix #1 / Low risk），不啟動
CANARY、不修改 runtime、不寫 AKASHA witness、不發 Telegram alert。

## 2. CANARY phase-gate model

CANARY 不是一個 binary 開關，是七個 phase 的階梯。每跨一階都需要
一個獨立 j13 order，並都受 §17 hard rule 約束。

```
Design (0-9R)                            ← MERGED
  ↓ docs only — no runtime change
Passport persistence (0-9P)              ← MERGED a8a8ba9
  ↓ metadata-only — no apply
Attribution audit (0-9P-AUDIT)           ← MERGED 3219b805
  ↓ offline tool only — no runtime hook
Dry-run consumer (0-9R-IMPL-DRY)         ← MERGED fe3075f
  ↓ dry-run only — record to *_dry_run table
CANARY readiness (0-9S-READY)            ← THIS PR (PR-D, docs only)
  ↓ docs only — no apply path wired
CANARY activation (0-9S-CANARY)          ← future j13 order required
  ↓ small cohort live — apply path wired for limited cohort
Production rollout (0-9T)                ← future j13 order required
  ↓ full production — apply path wired across all cohorts
```

每個 ↓ 箭頭都是**獨立** authorization gate；前一階通過不自動授權下一
階。0-9S-READY 通過**僅**意味著「CANARY 啟動的最低門檻已具備」，不
等於 CANARY 可以啟動。

## 3. Per-phase governance table

下表把 0-9R base matrix 17 條 task type 投影到上述七個 phase。
「Allowed task types」欄位以 `#N` 引用 base matrix 的編號。

| Phase | Risk | Required authorization | Branch protection | Signed PR-only | Allowed task types (base #N) | Required evidence | Pre-action audit | Rollback obligation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Design (0-9R) | Low | current order scope sufficient | intact | YES | #1 only | 11 design docs in `0-9r/` | controlled-diff EXPLAINED | revert PR (docs only) |
| Passport persistence (0-9P) | Medium | explicit j13 order (already given) | intact | YES | #1, #2, #3 (passport metadata only) | `audit/attribution_closure_view`, migration log | controlled-diff EXPLAINED_TRACE_ONLY for the metadata SHAs | revert SHA + downgrade migration |
| Attribution audit (0-9P-AUDIT) | Low | explicit j13 order (already given) | intact | YES | #1, #2 (offline) | audit verdict (GREEN/YELLOW/RED) reports | offline tool, no runtime touch | drop offline tool, no runtime impact |
| Dry-run consumer (0-9R-IMPL-DRY) | Medium | explicit dry-run-only j13 order (already given) | intact | YES | #1, #4 (dry-run scope) | `feedback_decision_record_dry_run` 7-day series | controlled-diff EXPLAINED_TRACE_ONLY for `feedback_budget_consumer.py` | disable dry-run job; no runtime weight change |
| CANARY readiness (0-9S-READY) | Low | current order scope sufficient | intact | YES | #1 only | this design package (07 docs) | controlled-diff EXPLAINED | revert PR (docs only) |
| CANARY activation (0-9S-CANARY) | **High** | **explicit j13 order + CANARY readiness pass (CR1–CR15 all PASS)** | intact (verified pre + post) | YES | #5 (real budget reweighting, scoped to cohort), #15 (CANARY itself) | evidence package per `0-9s-ready/01_canary_readiness_gate.md §5` | controlled-diff EXPLAINED_TRACE_ONLY scoped to runtime SHAs listed in order; Calcifer GREEN verified ≤ 5 min before activation | F1–F9 trigger → automatic revert + Telegram + AKASHA witness |
| Production rollout (0-9T) | **Critical** | **explicit j13 order + CANARY pass (full N-day evidence)** | intact (verified pre + post) | YES | #5 (full cohort), #16 (production) | full CANARY evidence + production order package | controlled-diff EXPLAINED_TRACE_ONLY for production SHAs; §17.2 AKASHA witness required | rollout aborts on §17.3 RED; multi-rollback policy on regression |

說明：

- **Allowed task types** 嚴格遵守 0-9R base matrix `#N`。任何不在
  該欄位列出的 task type 在該 phase 內**禁止**執行；越界即視為 scope
  creep（Q1 dim 5）→ STOP。
- **CANARY activation 的 #5** 永遠 scoped to「per-cohort apply」，
  不是 global apply；global apply 只屬於 production rollout（0-9T）。
- 任一 phase 的 branch protection 都「always intact」。任何弱化
  branch protection 之需求 → 落入 base matrix #17 Critical / governance-only
  order 路徑，與 CANARY 無關。

## 4. CANARY-specific approval gates (CR1–CR15 extended)

延伸 `0-9s-ready/01_canary_readiness_gate.md` 的 CR1–CR15。下表為每個
CR 標明六個 actor 的責任：

- **Operator**：Lead（Claude）執行人或代理人。
- **j13**：人類最終授權者。
- **Calcifer**：自動化 outcome watchdog（每 5 min poll）。
- **AKASHA witness**：自動化 §17.2 獨立 service，產生 `before/after`
  記錄與 commit_sha 對應。
- **GitHub branch protection**：自動化 GitHub-side gate。
- **Gate-A / Gate-B**：CI gate（A = controlled-diff classification；
  B = decision-record + version-bump-gate composite）。

| CR | Operator | j13 | Calcifer | AKASHA witness | Branch protection | Gate-A | Gate-B |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CR1 attribution closure complete | runs `audit/attribution_closure_view`, attaches result | reviews verdict | polls `unknown_origin_count` daily | n/a (no version bump on this gate alone) | enforces signed PR for any audit job change | EXPLAINED on audit job code | n/a |
| CR2 audit GREEN or YELLOW+mitigations | gathers verdict, drafts mitigations if YELLOW | accepts/rejects YELLOW limitation | publishes verdict snapshot | n/a | n/a | n/a | n/a |
| CR3 dry-run consumer complete | verifies `fe3075f` merged + tests green | n/a (already approved 0-9R-IMPL-DRY) | n/a | confirms `fe3075f` recorded | enforces signed merge of `fe3075f` | EXPLAINED_TRACE_ONLY on consumer SHA | required-status-checks pass |
| CR4 no runtime apply path | runs grep / import-graph; attaches output | reviews adversarial sweep result | n/a | n/a | enforces no force-push that could sneak apply path | EXPLAINED on every diff to runtime tree | rejects PR adding apply hook |
| CR5 consumer no runtime import | runs grep; attaches dependency graph | reviews | n/a | n/a | n/a | EXPLAINED on imports to consumer | rejects PR introducing runtime import |
| CR6 ≥ 7-day stable dry-run output | gathers 7-day series; or requests j13 override | grants override only on Telegram + commit + AKASHA all three | reports daily green/red | records override (if any) with SHA + ts | n/a | n/a | n/a |
| CR7 UNKNOWN_REJECT < 0.05 | reads `arena_batch_metrics`; attaches 7-day series | reviews trend | **authoritative** poller every 5 min; writes `/tmp/calcifer_deploy_block.json` if RED | n/a | n/a | n/a | rejects activation order if Calcifer RED present |
| CR8 A2 sparse trend baseline | writes `baseline_snapshot.md` | reviews baseline | confirms metric exists | records baseline doc SHA | n/a | EXPLAINED on baseline doc | required if baseline doc missing |
| CR9 A3 pass_rate non-degradation | reads metric; attaches | reviews | **authoritative** poller; RED if drop ≥ 5 pp | n/a | n/a | n/a | rejects if Calcifer RED |
| CR10 deployable_count non-degradation | queries `<proj>_status` VIEW | reviews | **authoritative** poller per §17.3; RED on drop or `last_live_at_age_h > 6` | required (§17.2) before any version bump | n/a | n/a | rejects if Calcifer RED or witness missing |
| CR11 rollback plan documented | writes `03_rollback_plan.md`; runs end-to-end drill | final approve | n/a | records drill log SHA | n/a | EXPLAINED on rollback doc | required if drill log missing |
| CR12 alert path defined | writes `04_alert_path.md` + Telegram template | approve | confirms chat_id reachable | records doc SHA | n/a | EXPLAINED on alert doc | required if doc missing |
| CR13 branch protection intact | runs `gh api repos/.../branches/main/protection` baseline diff | reviews | n/a | n/a | **authoritative**; rejects PR that mutates protection settings | n/a | rejects if diff != 0 |
| CR14 signed PR-only flow intact | scans 30-day commit log for unsigned / hand-written `feat(.../vN)` | reviews | n/a | n/a | enforces signed commits, required signatures | n/a | pre-receive regex rejects manual `feat(.../vN)` |
| CR15 j13 CANARY authorization | drafts authorization block for activation order | **authoritative** — must produce ED25519 signature + Telegram + AKASHA witness (three-channel) | n/a (informed) | records authorization SHA + ts | n/a | n/a | rejects activation if any of three channels missing |

說明：

- **「authoritative」** 表示該 actor 的判定為終局；其他 actor 不得
  override（除非 j13 顯式 STOP）。
- **CR7 / CR9 / CR10** 由 Calcifer 持續 poll；Calcifer RED 即等同
  Gate-B FAIL，無人類繞過權限（j13 STOP 覆蓋例外見 §7）。
- **CR15** 三通道（j13 ED25519 commit + Telegram + AKASHA witness）
  缺一即 BLOCK；本 PR-D 並未取得此授權，亦不需要。

## 5. j13 authorization sentence template

下列為 0-9S-CANARY activation 必須**逐字**出現於 j13 授權 commit 與
Telegram 訊息中的句式。任何缺漏 / 改寫即視為授權無效。

```
j13 authorizes TEAM ORDER 0-9S-CANARY: Sparse-Candidate Dry-Run
CANARY Activation. Execute under signed PR-only governance. Scope is
limited cohort live activation of feedback_budget_consumer for {{N}}
profile(s) in cohort {{cohort_id}} with PB-FLOOR + PB-DIV +
PB-SHIFT (dry-run apply transitioning to live apply). Preserve
branch protection (enforce_admins / required_signatures /
linear_history / no force-pushes / no deletions). Do NOT modify
alpha generation, formula generation, mutation/crossover, search
policy, real generation budget {{except per cohort}}, sampling
weights {{except per cohort}}, thresholds, A2_MIN_TRADES (still
25), Arena pass/fail, rejection semantics, champion promotion,
deployable_count semantics, execution, capital, risk, or production
rollout. Authorize controlled-diff for {{specific runtime SHAs}}
under EXPLAINED_TRACE_ONLY pathway. Roll back automatically if any
F1-F9 criterion triggered. STOP after CANARY {{duration}} days,
evidence package, j13 review, and local main sync.
```

欄位來源說明：

| Token | Type | Filled by | Notes |
| --- | --- | --- | --- |
| `0-9S-CANARY` | constant | — | order id 永久固定 |
| `Sparse-Candidate Dry-Run CANARY Activation` | constant | — | title 永久固定 |
| `signed PR-only governance` | constant | — | governance posture，不可移除 |
| `{{N}}` | variable | order writer | profile 數量；建議 ≤ 3 起步 |
| `{{cohort_id}}` | variable | order writer | cohort 識別碼，e.g. `canary-2026Q2-a` |
| `PB-FLOOR + PB-DIV + PB-SHIFT` | constant | — | 三 treatment 組合，固定 |
| `dry-run apply transitioning to live apply` | constant | — | 行為描述，固定 |
| `enforce_admins / required_signatures / linear_history / no force-pushes / no deletions` | constant | — | 五項 branch protection 屬性，全保留 |
| `Do NOT modify` 整段 | constant | — | hard limit，不可刪減；列舉 base matrix #5–#16 不允許之變更 |
| `A2_MIN_TRADES (still 25)` | constant | — | §17 forbidden lowering，數值需逐字 |
| `{{except per cohort}}` | variable | order writer | 在 #5、sampling weights 後標明此例外，僅 per-cohort 有效 |
| `{{specific runtime SHAs}}` | variable | order writer | 由 controlled-diff 提供之 hash 列表 |
| `EXPLAINED_TRACE_ONLY` | constant | — | controlled-diff classification，固定 |
| `F1-F9` | constant | — | rollback trigger 由 `0-9s-ready/03_rollback_plan.md` 定義 |
| `{{duration}}` | variable | order writer | CANARY 視窗，建議 7–14 days |
| `STOP after ... local main sync` | constant | — | exit condition，固定 |

operator 不得自行決定 variable 欄位；所有 `{{...}}` 必須在 j13 commit
訊息中已被填妥，operator 僅 verify。

## 6. Required signatures at activation

CANARY activation 必須同時出具下列四簽：

| # | Signature | Source | Verification |
| --- | --- | --- | --- |
| 1 | **j13 ED25519** | j13 SSH key (commit signature) + Telegram message signed via j13 key | `git verify-commit` returns ED25519 fingerprint match; Telegram message includes signature line that can be cross-verified |
| 2 | **GitHub PGP merge commit** | GitHub merge commit `verified=true` (PGP) | `gh api repos/.../commits/<sha>` → `verification.verified == true` and `verification.reason == "valid"` |
| 3 | **Calcifer service token** | Calcifer service signs activation freshness check | service token presented within 5 min of activation; signed payload includes `<proj>_status.deployable_count`, `last_live_at_age_h` |
| 4 | **AKASHA witness checksum** | independent AKASHA service per §17.2; checksum over `{commit_sha, before, after, ts}` | record retrievable via AKASHA `/witness/{sha}`; checksum matches |

四簽缺一即 **BLOCK**。簽名順序為 1 → 2 → 3 → 4；任何 reorder 必須在
order 中註記原因。

驗證腳本骨架（operator 在 activation 前 ≤ 5 min 跑一次）：

```bash
# 1. j13 ED25519 commit signature
git verify-commit "$ACTIVATION_COMMIT_SHA" || { echo "j13 sig FAIL"; exit 1; }

# 2. GitHub PGP merge commit
gh api "repos/$REPO/commits/$ACTIVATION_COMMIT_SHA" \
  --jq '.commit.verification | select(.verified==true and .reason=="valid")' \
  | grep -q . || { echo "GitHub verified FAIL"; exit 1; }

# 3. Calcifer freshness
curl -fsS "http://100.123.49.102:CALCIFER_PORT/freshness?proj=zangetsu" \
  | jq -e '.deployable_count > 0 and .last_live_at_age_h <= 6' \
  || { echo "Calcifer NOT GREEN"; exit 1; }

# 4. AKASHA witness
curl -fsS "http://100.123.49.102:8769/witness/$ACTIVATION_COMMIT_SHA" \
  | jq -e '.checksum_ok == true' \
  || { echo "AKASHA witness FAIL"; exit 1; }

# Stale-service check (§17.6)
~/.claude/hooks/pre-done-stale-check.sh feedback_budget_consumer \
  zangetsu/services/feedback_budget_consumer.py \
  --remote j13@100.123.49.102 \
  --remote-source-path /home/j13/zangetsu/services/feedback_budget_consumer.py \
  || { echo "Stale service"; exit 1; }
```

任一行 exit != 0 → activation 立即 ABORT；operator 不得 retry，需先
通報 j13 並寫 incident record。

## 7. Authorization revocation paths

CANARY 一旦啟動，下列任何訊號皆可立即撤銷授權，operator 必須執行
rollback（而非 acknowledge after the fact）：

| # | Trigger | Channel | Action |
| --- | --- | --- | --- |
| 1 | **j13 STOP via Telegram** | `/stop` 或 「STOP CANARY」明文 | operator 立即執行 `0-9s-ready/03_rollback_plan.md` 的 rollback 流程；不需 j13 二次確認 |
| 2 | **Calcifer outcome watchdog RED** | `/tmp/calcifer_deploy_block.json` 出現 | operator 不得發出新 commit；如 CANARY 已 live → 觸發 §17.4 auto-regression revert |
| 3 | **Branch protection drift** | `gh api repos/.../branches/main/protection` baseline diff != 0 | operator 立即 freeze，回報 j13；視同 §17 critical violation |
| 4 | **Multi-rollback policy** | 同一 cohort 內 ≥ 2 次 F1–F9 trigger | 自動進入 `cohort_quarantine`，48h cooldown，需新 j13 order 才能再啟動同一 cohort |

revocation 觸發後的 audit trail 必須包含：

- trigger 時刻（UTC）。
- trigger 來源（Telegram message id / Calcifer record / gh api response /
  rollback log path）。
- operator 採取之 action 與 timestamp。
- AKASHA witness `revocation` 段（new entry，非 amend）。

## 8. What this PR (0-9S-READY) does NOT authorize

PR-D 是 documentation-only。下列**全部**不在本 PR 授權範圍內，未來
若任一條被 operator 執行，視為 scope creep 並觸發 0-9R red-team STOP：

- **CANARY activation** — 不寫 apply path、不開 cohort、不發
  Telegram「CANARY started」。
- **Production rollout** — 0-9T 必須另發 order，且必先 CANARY pass。
- **Modification of CODE_FROZEN runtime SHAs** — generation runtime /
  Arena runtime / champion pipeline / execution 任一 SHA 修改皆禁止。
- **Lowering `A2_MIN_TRADES`** — 永久禁止（任何 phase）；數值固定為
  25，僅可在獨立 threshold order（base matrix #9 Critical）下調整，且
  與 sparse intervention 互斥。
- **Weakening Arena pass/fail** — `arena2_pass` / `arena3_pass` /
  `arena4_pass` 條件不得放寬（base matrix #10 Critical）。
- **Changing `deployable_count` semantics** — VIEW 定義與 status
  enumeration 凍結（base matrix #12 Critical + §17.1）。
- **Touching execution / capital / risk** — broker integration / 倉位
  sizing / live trading 任一改動皆禁止（base matrix #14 Critical）。

操作面更具體的禁令：不得啟動 hot-swap、不得發 AKASHA witness 寫入、
不得 mutate Telegram chat / thread 的 alert wiring、不得改 GitHub
branch protection、不得 force-push、不得 amend 已 merged commit、不得
delete branch、不得繞過 pre-commit / pre-receive。

## 9. Cross-project hard rules cited (CLAUDE.md §17)

下列 §17 條款於 0-9S-CANARY 啟動時生效；本表列明 0-9S-CANARY future
order **將繼承（inherit）或延伸（extend）** 哪些行為：

| § | Rule | 0-9S-CANARY future order behavior |
| --- | --- | --- |
| §17.1 | **Single Truth (`<proj>_status` VIEW with `deployable_count`)** | **Inherit YES** — CANARY evidence package 直接引用 `zangetsu_status.deployable_count`；不重定義、不替代。CR10 已對齊。 |
| §17.2 | **Mandatory Witness (independent AKASHA service)** | **Extend** — 在 CANARY activation commit 必須附 AKASHA witness `{commit_sha, before, after, ts}`；額外加註 `cohort_id` + `treatment_set`（PB-FLOOR/PB-DIV/PB-SHIFT）作為 CANARY-specific metadata。 |
| §17.3 | **Calcifer Outcome Watch (5-min poll, RED → block)** | **Extend** — 沿用 5-min poll；額外把 CR7 / CR9 / CR10 三項對齊到 watchdog；任一 RED → 寫 `/tmp/calcifer_deploy_block.json`，operator 不得 commit。 |
| §17.4 | **Auto-Regression Revert (12h freeze + revert + force-with-lease)** | **Extend** — 對 CANARY 縮短窗口至 6h（與 CR10 `last_live_at_age_h <= 6` 對齊），其他流程（revert、force-with-lease、Telegram alert）完全沿用。 |
| §17.5 | **Version Bump is Bot Action (`bin/bump_version.py` only)** | **Inherit YES** — 任何 `feat(zangetsu/vN)` commit 仍只能由 `bin/bump_version.py` 產生；CANARY activation 本身**不**以 version bump 表達，而是以獨立 order commit + AKASHA witness。 |
| §17.6 | **Stale-Service Check (running ≥ source mtime)** | **Inherit YES** — activation 前 5 min 必跑 `~/.claude/hooks/pre-done-stale-check.sh feedback_budget_consumer ...`；exit != 0 → ABORT。已寫入 §6 驗證腳本。 |
| §17.7 | **Decision Record CI Gate** | **Inherit YES** — 0-9S-CANARY activation 必有 `docs/decisions/YYYYMMDD-0-9s-canary-activation.md`；若 /team 模式則同步要求 `docs/retros/YYYYMMDD-0-9s-canary.md`；CI 缺檔即 BLOCK。 |
| §17.8 | **Scratch → Tests Integration** | **Inherit YES** — CANARY 過程中產生的 smoke / probe script 必須在 7 天內遷入 `tests/`，否則 cron 自動刪除並寫 retro 條目。 |

每條 §17 rule 在 CANARY 期間「inherit YES」即表示**直接套用、無寬鬆**；
標 「Extend」 者代表在 base 規則之上再附加 CANARY-specific 條件。

## 10. Audit trail per CANARY phase

CANARY 三段 audit trail；任何缺段即視為「未發生」（與 0-9R/06 §10
audit trail 政策一致）。

### 10.1 Pre-activation

路徑：`docs/governance/canary-evidence/YYYYMMDD-canary-N/`

必含：

- `evidence_package.md` — CR1–CR15 逐項勾選 + 證據連結。
- `baseline_snapshot.md` — 對應 CR8 / CR9 / CR10 的數值（median + IQR
  + outlier）。
- `j13_authorization.md` — §5 授權句式之三通道紀錄（commit SHA +
  Telegram screenshot + AKASHA witness id）。
- `rollback_drill_log.md` — rollback 端到端演練紀錄（CR11 補強）。
- `signature_verification.log` — §6 驗證腳本之輸出。

retention：**non-deletable**（與 `.claude/scratch/research-*.md` 同級
語意）；任何 mv / rm 操作須先寫 decision record 並取得 j13 授權。

### 10.2 During CANARY

路徑：`docs/governance/canary-runtime/YYYYMMDD-canary-N/`

必含：

- **Calcifer hourly snapshots** — `<proj>_status.deployable_count`、
  `last_live_at_age_h`、CR7 / CR9 / CR10 即時值；每小時 1 筆，CANARY
  期間連續。
- **AKASHA witness records** — 每次 cohort weight 重算寫一筆 witness
  record（`before/after/ts/commit_sha`）；不允許 amend。
- **Daily audit** — 每日 1 筆 `daily_review_YYYYMMDD.md`，列明：
  Calcifer state、CR7/CR9/CR10 24h 趨勢、F1–F9 觸發次數、operator
  action、j13 review note（若有）。

任一日缺 daily audit → 視同 CANARY 失格 → 立即 rollback。

### 10.3 Post-activation

路徑：`docs/governance/canary-evidence/YYYYMMDD-canary-N/post/`

必含：

- `incident_reports/` — 任何 F1–F9 trigger 觸發之 incident，每件一檔；
  即便最終結果為「false positive」亦必須留檔。
- `evidence_package_final.md` — CANARY 結束時的最終評估（pass /
  partial pass / fail），含：
  - CR1–CR15 在 CANARY 結束時的狀態（與 pre-activation 對比）。
  - F1–F9 觸發事件次數與每件 root cause。
  - Calcifer / AKASHA / Telegram audit trail 完整性檢查結果。
  - 是否建議進入 0-9T production rollout（含 j13 review note）。
- `final_signatures.log` — j13 ED25519 + GitHub PGP + Calcifer +
  AKASHA 四簽再次驗證輸出。

retention：**non-deletable**；CANARY 完成 90 天內任何 production
rollout (0-9T) order 必須引用此 evidence package final。

## 11. Final approval matrix table

下表將 §3 phase + §4 actor 整合為單一 matrix。`Authorized` 欄位答
「在當前 governance 框架下，該 phase 是否已被 PR-D 授權執行」：

| Phase | Risk | Operator | j13 | Calcifer | AKASHA | Branch protection | Gate-A | Gate-B | Authorized |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Design (0-9R) | Low | execute (docs) | review (already done) | n/a | n/a | enforce | EXPLAINED | required-checks | YES (merged) |
| Passport persistence (0-9P) | Medium | execute (metadata migration) | review (already done) | poll attribution closure | record migration SHA | enforce | EXPLAINED_TRACE_ONLY | required-checks | YES (merged `a8a8ba9`) |
| Attribution audit (0-9P-AUDIT) | Low | execute (offline) | review (already done) | n/a | record verdict snapshot SHA | enforce | EXPLAINED | required-checks | YES (merged `3219b805`) |
| Dry-run consumer (0-9R-IMPL-DRY) | Medium | execute (dry-run only) | review (already done) | confirm 7-day green | record consumer SHA | enforce | EXPLAINED_TRACE_ONLY | required-checks | YES (merged `fe3075f`) |
| CANARY readiness (0-9S-READY) | Low | execute (docs only) — **this PR** | review (this PR) | n/a | n/a | enforce | EXPLAINED | required-checks | YES (this PR) |
| CANARY activation (0-9S-CANARY) | High | execute only after CR1–CR15 PASS + four signatures | **must produce** §5 sentence + §6 four signatures | poll CR7/CR9/CR10 every 5 min; RED blocks | record activation `before/after/ts/commit_sha` | enforce; baseline diff = 0 required | EXPLAINED_TRACE_ONLY for runtime SHAs in order | required-checks + decision-record + version-bump-gate | **NO** (future order required) |
| Production rollout (0-9T) | Critical | execute only after full CANARY evidence + j13 order | **must produce** new authorization sentence + four signatures (re-issued) | poll continuously; RED blocks; multi-rollback policy applies | record rollout commit + before/after | enforce; baseline diff = 0 required | EXPLAINED_TRACE_ONLY for production SHAs | all CI gates + post-rollout daily audit | **NO** (future order required) |

PR-D 至此交付完畢；本檔僅延伸 0-9R/06 至 CANARY phase，
不啟動 CANARY、不修改 runtime、不寫入 AKASHA witness、不發
Telegram alert。任何越界即 STOP。

未來 0-9S-CANARY activation order 應引用本檔（07）+ readiness gate
（01）+ rollback plan（03）+ alert path（04）為 evidence package 的
四份基底文件。
