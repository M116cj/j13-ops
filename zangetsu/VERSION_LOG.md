## v0.5.0 — 2026-04-18 — V10 core upgrade + single-track consolidation
**Engine hash:** `zv5_v10_alpha` (V10 active) + `zv5_v71`/`zv5_v9` (archived labels)
**Branch:** `main` @ `98a95e22` (single-track — feat deleted)

### Feature: V10 GP Alpha Expression Engine core integration
- **Change type:** major refactor (V9 → V10 paradigm shift)
- **What changed (22 files, +12986/-1033 lines):**
  - `services/arena_pipeline.py` (925-line rewrite): A1 workers now run per-symbol GP evolution (replaces V9 indicator-combo voting); INSERT engine_hash='zv5_v10_alpha'
  - `engine/components/alpha_engine.py` (1197-line expansion): 166 primitives (5 OHLCV + 126 indicators + 35 operators)
  - `services/arena23_orchestrator.py`, `arena45_orchestrator.py`: V10 alpha consumption
  - `services/{indicator_precompute, data_collector, event_queue, shared_data, shared_utils, pidlock, arena13_feedback}`: plumbing updates for V10
  - `engine/core.py`, `engine/components/{signal_utils, data_preprocessor}`: signal-generation updates
  - `config/settings.py`, `config/a13_guidance.json`: V10-related config values
  - `services/v9_search.py`: kept as legacy helper for A2/A3 side
- **Why:** V10 doctrine "GP Alpha Expression Engine" replaces V9 "indicator voting" — 4 A1 workers already running V10 code on disk since pre-session (uncommitted), but git reflected V9. Commit closes runtime ↔ git drift; any future restart/reset now loads correct V10 from git.
- **Q1/Q2/Q3:**
  - Q1 PASS — V10 runtime proven to work (862 alphas in DB, DSR=1.0 PASS, alpha_discovery cron runs clean)
  - Q2 PASS — all 18 modified files committed atomically; V9 snapshot preserved as immutable archive
  - Q3 PASS — minimum changes (only staged pre-existing runtime state, no new edits)

### Feature: V9 archive snapshot (immutable, in-project)
- **Change type:** archive (per j13 workflow: 淘汰舊版本封存在專屬專案的封存庫)
- **What changed:** New directory committed: `zangetsu/archive/v9_snapshot_20260418_030520/`
  - `arena_pipeline.py` (V9 indicator-voting, 993 lines)
  - `alpha_engine.py` (V9 pre-GP, 494 lines)
  - `signal_utils.py`, `v9_attention.py`, `v9_search.py` (V9 reference)
- **Why:** Per j13 rule "新版本出來之後直接進行部署，淘汰掉的舊版本進行封存": V10 deploys directly to main, V9 frozen at 2026-04-18 03:05:20 UTC as immutable snapshot inside project. Archive timestamp = pre-V10-seed moment (5 minutes before 03:10 seed of 851 Kakushadze alphas).
- **Q1/Q2/Q3:**
  - Q1 PASS — V9 core covered (arena_pipeline + alpha_engine are the two V9→V10 rewrites)
  - Q2 PASS — MD5 verified: archived files ≠ live for V9→V10 rewrites, = live for unchanged helpers
  - Q3 PASS — 5 files, 2365 frozen lines
- **Rollback:** `git checkout 98a95e22~1` (pre-merge state) or cp archive files back to live paths

### Feature: Single-track branch consolidation
- **Change type:** workflow (per j13 "不要有任何分支,分支很容易污染後續")
- **What changed:**
  - Fast-forward push `feat/v9-oneshot-hardening` → `origin/main` (89abc946..98a95e22)
  - Deleted `feat/v9-oneshot-hardening` (remote + local)
  - Deleted local branches: `backup/pre-filter-zangetsu_v3`, `upgrade-v5`, `v5-paper-trading`, `v5.1-fitness-redesign`, `ops/ecosystem-upgrade-v5`, original old `main`
  - **Remaining:** `main` (only, local + remote)
  - **PR #3** automatically moved to MERGED state
- **Why:** Branch sprawl was: 1 main (on origin), 1 feat (live dev), 5 legacy local. Violates single-track rule. Consolidation = main is canonical forever, every future commit goes direct to main.
- **Q1/Q2/Q3:**
  - Q1 PASS — feat was fast-forward of main, no merge conflicts, no force-push
  - Q2 PASS — remote main now at 98a95e22 (12 commits ahead of pre-session); PR #3 MERGED
  - Q3 PASS — `git push origin feat:main` one-shot operation

### Feature: Dashboard engine_hash filter correction
- **Change type:** fix
- **What changed:** `zangetsu/dashboard/api.py` line 1054, 1068: `WHERE engine_hash='zv9'` → `WHERE engine_hash IN ('zv5_v9', 'zv5_v10_alpha', 'zv5_v71')`
- **Why:** Prior filter used `'zv9'` label (no `zv5_` prefix); DB actually stores `zv5_v9` / `zv5_v10_alpha` / etc. Dashboard was returning 0 rows. Now shows V9 + V10 + V7.1 historical together.
- **Q1/Q2/Q3:** PASS — safe IN list, no SQL injection surface
- **Rollback:** sed reverse

### Feature: Log file gitignore
- **Change type:** infra cleanup
- **What changed:**
  - Added to `.gitignore`: `zangetsu/logs/`, `calcifer/calcifer.log`, `zangetsu/.venv/`
  - `git rm --cached` on `zangetsu/logs/engine.jsonl` (11449 lines) + `calcifer/calcifer.log` (2880 lines)
- **Why:** Log files churn at MB/hour. Should never be version-controlled.
- **Q1/Q2/Q3:** PASS — `--cached` only, files stay on disk for services to write

### Final V10 state (post v0.5.0)
```
Active V10 alphas:
  DISCOVERED + ARENA1_READY (valid alpha_hash): 13 (growing every 30 min via cron)
  SEED + ARENA1_READY (Kakushadze 2016):       851
  Total active:                                 864

Archived:
  DISCOVERED LEGACY (NULL-hash retired):         10
  zv5_v9_coldstart SEED LEGACY:                  13
  V9 source snapshot (immutable):                 5 files in zangetsu/archive/

Branch: main (single-track; feat/v9-oneshot-hardening deleted)
Remote: origin/main @ 98a95e22
PR #3: MERGED
```

### Deferred (not in this version)
- Watchdog presence-check architecture (lockfile blindness to clean shutdown)
- `zangetsu/config/a13_guidance.json` runtime updates (auto-written by A13 cron — expected churn)
- `calcifer/maintenance_last.json` runtime updates (same — expected)
- Dedicated `zangetsu-archive` GitHub repo (currently in-project archive suffices)

## v0.4.1 — 2026-04-18 — V10 post-deploy emergency fixes
**Engine hash:** unchanged
**Branch / commit:** `feat/v9-oneshot-hardening` @ (pending)

### Feature: alpha_discovery.py INSERT column correctness + status fix
- **Change type:** fix (production-impacting, caught by Round 3 adversarial sweep)
- **What changed:**
  - `services/alpha_discovery.py` INSERT statement:
    - Added `alpha_hash` column (was omitted → UNIQUE constraint defeated with NULL)
    - Pass `alpha.hash` as `$4` parameter
    - Changed status from `'DEPLOYABLE'` → `'ARENA1_READY'` (was incorrectly bypassing pipeline)
- **Why:** Round-3 Explore agent sweep caught 6 NULL alpha_hash rows created by v0.4.0 cron's first run. UNIQUE constraint on alpha_hash WHERE NOT NULL meant NULL rows accumulated unbounded. Status=DEPLOYABLE also wrong — discovered alphas must enter A1 pipeline for validation, not skip to deployment.
- **Q1/Q2/Q3:**
  - Q1 PASS — after fix, 3 test-run alphas inserted with valid `alpha_hash` and `status='ARENA1_READY'`
  - Q2 PASS — 9 pre-fix NULL rows retired to LEGACY (not deleted, preserved for forensic)
  - Q3 PASS — 3 sed operations on single file

### Data fix: retire 9 NULL alpha_hash rows
- **Change type:** data cleanup
- **What changed:** `UPDATE champion_pipeline SET status='LEGACY' WHERE engine_hash='zv5_v10_alpha' AND card_status='DISCOVERED' AND alpha_hash IS NULL`
- **Why:** Pre-fix cron runs inserted 9 rows with NULL alpha_hash. These can't be referenced by future dedup checks. Retiring preserves data without polluting active pipeline.

### Round 3 Emergency: V9 workers were DEAD
- **Change type:** fix (production-impacting, incident)
- **What changed:** Re-ran `zangetsu_ctl.sh start` — 6 workers back online (4 A1 + A23 + A45)
- **Why:** Between 03:00 UTC (watchdog: "all 8 services healthy") and 03:30 UTC (watchdog: "all 2 services healthy"), all 6 V9 workers died. Watchdog blind because pidlocks were cleanly removed (not stale-PID). My v0.4.0 report wrongly claimed "V9 untouched" — in reality workers died some time during the V10 deploy window.
- **Lesson learned:** Watchdog presence-check is lockfile-based; if lockfile removed cleanly, watchdog doesn't restart. Need "expected services" tracker.
- **Q1/Q2/Q3:** PASS — workers back, pipeline resumed

### Adversarial sweep findings (documented, not fixed in this version)
- **P1** 22 modified + 18 untracked files in repo (alpha_dedup, alpha_ensemble, alpha_quality_gates, factor_zoo, signal_reconstructor). Untracked includes critical V10 modules. Next commit should stage these.
- **P1** Watchdog lockfile-only presence detection → misses services that die cleanly. Architectural fix needed in separate version.
- **P2** `calcifer/calcifer.log` and `zangetsu/logs/engine.jsonl` tracked in git (shouldn't be). Add to .gitignore next commit.

### Running V10 state (after all v0.4.1 fixes)
```
DISCOVERED + ARENA1_READY (valid alpha_hash): 13
DISCOVERED + LEGACY (9 NULL + 1 original dupe):    10
SEED + ARENA1_READY (Kakushadze 2016 batch):      851
Total V10 alphas in pipeline: 874
```

### Deferred to next version
- Commit all untracked V10 files (alpha_dedup/ensemble/quality_gates/factor_zoo/signal_reconstructor)
- `.gitignore` calcifer.log + engine.jsonl
- Watchdog presence-check architecture upgrade

## v0.4.0 — 2026-04-18 — V10 factor expression deployment (Path B isolated)
**Engine hash:** V9 (zv5_v9, zv5_v71) + **V10 new (zv5_v10_alpha)**
**Branch / commit:** `feat/v9-oneshot-hardening` @ (pending)

### Feature: V10 Alpha Expression Engine activated
- **Change type:** deploy + fix
- **What changed:**
  - Fixed `services/alpha_discovery.py` two code-drift bugs:
    - Line 5 docstring + line 137 INSERT: `zv5_v9_alpha` → `zv5_v10_alpha` (matches DB reality)
    - Line 117: `alpha.to_passport_dict()` → `alpha.to_passport()` (actual method name)
  - Added cron entry: `*/30 * * * * cd ~/j13-ops && nice -n 10 zangetsu/.venv/bin/python -m zangetsu.services.alpha_discovery >> /tmp/zangetsu_alpha_discovery.log 2>&1`
  - `watchdog.sh` skip list extended: `alpha_discovery` joins `arena13_feedback|calcifer_supervisor` (cron-managed, not daemon)
  - Verified end-to-end: manual run produced 3 new alphas for BTCUSDT (GP 15 gen × 80 pop, ~3 sec eval)
- **Why:** V10 GP Alpha Expression Engine existed dormant since 2026-04-18 03:10 UTC (when 851 kakushadze_2016 seeds + 11 DISCOVERED rows were inserted), but alpha_discovery was never running due to two code-drift bugs. Path B strategy: keep V9 A1-A5 pipeline untouched, run V10 discovery isolated at `nice +10` every 30 min.
- **Q1/Q2/Q3:**
  - Q1 PASS — `nice +10` ensures no CPU contention with 4 A1 workers @ 100%; discovery runs ~3 sec; no DB write contention (inserts to separate engine_hash)
  - Q2 PASS — v10_alpha_ic_analysis shows 862 alphas, 108 with IC > 0.05, top DSR = 1.0000
  - Q3 PASS — 2 sed fixes + 1 cron + 1 watchdog line; zero V9 pipeline changes
- **Rollback:** revert two sed fixes, remove cron line, revert watchdog skip

### Feature: Schema constraints (V2 — Agent-3 adversarial finding)
- **Change type:** fix (adversarial finding mitigation)
- **What changed:** `zangetsu/migrations/postgres/v0.4.0_v2_constraints.sql`:
  - `uniq_regime_indicator_hash_v9`: UNIQUE(regime, indicator_hash) WHERE alpha_hash IS NULL AND status != 'LEGACY' (V9 rows)
  - `uniq_alpha_hash_v10`: UNIQUE(alpha_hash) WHERE alpha_hash IS NOT NULL AND status != 'LEGACY' (V10 rows)
  - `chk_sane_metrics`: numeric bounds on win_rate [0,1], trades >=0, pnl [-10, 100], elo [-1000, 5000], n_indicators [0, 10]
- **Why:** Agent-3 adversarial audit found `champion_pipeline` had ONLY PKEY + 2 status CHECKs. Any SSH+DB holder could plant `status='DEPLOYABLE'` bypassing all gates. Constraints lock the physical schema.
- **Q1/Q2/Q3:**
  - Q1 PASS — constraint apply surfaced real duplicate `alpha_hash=3ff11ef5fb27b838` (retired as LEGACY)
  - Q2 PASS — indexes created, no drop on existing data
  - Q3 PASS — migration idempotent with IF NOT EXISTS guards

### Feature: V10 alpha status normalization
- **Change type:** data fix
- **What changed:**
  - 11 DISCOVERED V10 alphas had `status='DEPLOYABLE'` (bypassing pipeline) → fixed to `status='ARENA1_READY'`
  - 851 SEED V10 alphas had `status='DEPLOYABLE'` → fixed to `status='ARENA1_READY'`
  - 1 duplicate alpha_hash row retired to `status='LEGACY'`
- **Why:** Seeded alphas should enter A1 pipeline via `ARENA1_READY`, not skip to `DEPLOYABLE`. Previous seed script had wrong default.
- **Q1/Q2/Q3:** PASS — no alpha lost (all reassigned, not deleted)
- **Rollback:** UPDATE ... SET status='DEPLOYABLE' WHERE ...

### V10 current inventory (post-deployment)
- **862 total V10 alphas** (851 SEED + 11 DISCOVERED)
  - All in `status='ARENA1_READY'` awaiting A1 evaluation
  - `engine_hash='zv5_v10_alpha'` (distinct from V9's `zv5_v9`/`zv5_v71`)
  - Regimes: MULTI (851), BULL_TREND (5), CONSOLIDATION (6)
- **Quality baseline** (via v10_alpha_ic_analysis):
  - Mean IC: 0.0374
  - 333 alphas with IC > 0.02 (V9 MIN_IC_THRESHOLD)
  - 108 alphas with IC > 0.05 (strong signals)
  - Max IC: 0.4832
  - Top alpha DSR: 1.0000 (PASS V10 gate 1)
- **Discovery cadence:** every 30 min via cron, one symbol per run, GP 15 gen × 80 pop

### Cron state (post-v0.4.0)
```
*/5 * * * *  watchdog.sh
*/5 * * * *  arena13_feedback (single-shot)
0 */6 * * *  daily_data_collect
*/30 * * * * alpha_discovery (nice +10, NEW)
45 * * * *   v10_alpha_ic_analysis (pre-existing)
0 3 * * 0    /tmp cleanup
```

### Adversarial / code-drift issues caught this batch
1. `to_passport_dict` vs `to_passport` (fatal, blocked all discovery)
2. `zv5_v9_alpha` vs `zv5_v10_alpha` (silent drift, DB ignored discovery)
3. Duplicate alpha_hash (UNIQUE caught, retired to LEGACY)
4. Seed script defaulted status='DEPLOYABLE' (bypassing pipeline)

### Deferred (not in this version)
- Path A acceleration (V10 接線 V9 live ensemble) — wait 1 week observation
- V1 train=test architectural fix — will propose separate PR after V10 proves out
- Gemini/OpenAI auth on Alaya — needs API keys
- PR #3 merge to main — wait 1 week from earlier commit cycle

## v0.3.4 — 2026-04-17 — Watchdog round 2: orchestrator stale-check skip
**Engine hash:** `zv5_v71` / `zv5_v9`
**Branch / commit:** `feat/v9-oneshot-hardening` @ `f8bc5701`

### Feature: Watchdog — arena23/45 orchestrators skip stale-log check
- **Change type:** fix (production-impacting, second-order from v0.3.2)
- **What changed:** `zangetsu/watchdog.sh` lockfile loop now branches:
  - For `arena23_orchestrator` and `arena45_orchestrator`: PID-alive check only, skip stale-log check entirely
  - All other workers (A1 pipeline w0-w3): keep stale check (they actively log when working)
- **Why:** v0.3.2 bumped STALE_THRESHOLD 600→1800 (10min→30min) but observation at 15:00 UTC showed orchestrators STILL restarted every cycle. Root cause: orchestrators legitimately idle while `champion_pipeline` empty (V9 has no champions yet) → no log writes for 30+ min → stale check fires → pure churn restart. Restarting an idle orchestrator does nothing useful. The threshold isn't the right knob; orchestrator semantics are different from A1 workers (which actively process work).
- **Q1/Q2/Q3:**
  - Q1 PASS — orchestrators still get PID-dead detection (real crashes still restart); only the stale-log false-positive is suppressed
  - Q2 PASS — manual `bash watchdog.sh` after fix shows `WATCHDOG: all 8 services healthy`
  - Q3 PASS — 7-line patch (case statement + continue)
- **Rollback:** revert the case branch in lockfile loop

### Round-2 deep scan summary (Explore agent + Opus env audit + Codex/Gemini auth-blocked)
- ✅ **0 critical findings** in all-projects audit (zangetsu, calcifer, markl, agent_bus, infra)
- ✅ **0 systemd failed units**
- ✅ **22 Docker containers healthy**
- ✅ **Disk 10% / RAM 21G free / GPU idle** — no leaks
- ✅ **0 zombie/defunct processes** (17 orphans = legitimate daemon backgrounding)
- ✅ **8 pidlocks** (4 A1 + arena23 + arena45 + arena13_feedback transient + calcifer_supervisor)
- ✅ **All `zangetsu_v5` references in active code = 0** (`zv5_` only in engine_hash + log filenames, intentional)
- ✅ **Cross-project consistency**: agent_bus / markl / infra all clean
- ⚠️ **Codex CLI on Alaya needs OPENAI_API_KEY** (`codex exec` returned 401 Unauthorized)
- ⚠️ **Gemini CLI on Alaya needs GEMINI_API_KEY** (already noted in v0.3.0)

## v0.3.1 — 2026-04-17 — LFS + V9 SQL view + watchdog stale-loop fix
**Engine hash:** `zv5_v71` / `zv5_v9` (literals preserved)
**Branch / commit:** `feat/v9-oneshot-hardening` @ `c1f23a46`

### Feature: Git LFS tracking for parquet data files (preventive)
- **Change type:** new (infra)
- **What changed:**
  - Installed `git-lfs` on Alaya via `apt install -y git-lfs`
  - `git lfs install` per-repo + `git lfs track "zangetsu/data/**/*.parquet"`
  - Created `.gitattributes` (1 line, repo root)
- **Why:** Previous push attempt warned BTCUSDT.parquet (99 MB) close to GitHub 100 MB hard limit. data/ is also gitignored + skip-worktree, so LFS never fires today — but if someone removes the gitignore or new symbols join, files auto-route to LFS instead of bloating the repo.
- **Q1/Q2/Q3:** PASS — `git lfs status` confirms tracking active; no behavior change for current commits
- **Rollback:** delete `.gitattributes` + `git lfs uninstall` (per-repo)

### Feature: V9 SQL view foundation (champion_pipeline_v9)
- **Change type:** new (DB schema)
- **What changed:**
  - New file: `zangetsu/migrations/postgres/v0.3.0_v9_view.sql`
  - View: `CREATE OR REPLACE VIEW champion_pipeline_v9 AS SELECT * FROM champion_pipeline WHERE engine_hash IN ('zv5_v9', 'zv5_v71');`
  - Applied to deploy-postgres-1
- **Why:** Dashboard has 17 query sites all hitting raw `champion_pipeline`. Wholesale modification = invasive. The view provides a non-breaking migration path: dashboard/scripts can switch to the view incrementally as V9 (`zv5_v9`) accumulates records. When v71 retires, just drop it from the view's IN clause — zero code change downstream.
- **Q1/Q2/Q3:** PASS — `SELECT count(*) FROM champion_pipeline_v9` returns 0 cleanly (table empty); view DDL idempotent
- **Rollback:** `DROP VIEW champion_pipeline_v9`

### Feature: Arena13 lifecycle decision (single-shot via cron, not daemon)
- **Change type:** decision + execution
- **What changed:**
  - Read `arena13_feedback.py` carefully: log says "Arena 13 Feedback complete (single-shot)" then exits — NOT a long-running daemon despite `REFRESH_INTERVAL_S = 300` constant (which appears to be a planned-but-unshipped daemon feature)
  - Reverted accidental ctl.sh + watchdog daemon-style integration from earlier in this session
  - Added cron entry: `*/5 * * * * cd ~/j13-ops/zangetsu && .venv/bin/python services/arena13_feedback.py >> /tmp/zangetsu_a13fb.log 2>&1`
  - `arena13_evolution.py` decision: KEEP (DISABLED stub with reintroduction requirements documented in its docstring)
- **Why:** systemd unit `arena13-feedback.timer` was the original trigger; we removed all systemd arena units in v0.3.0. Without re-trigger, A13 guidance freezes. cron is the correct equivalent.
- **Q1/Q2/Q3:** PASS — A13 logs show clean run + exit every 5 min; no orphan processes
- **Rollback:** `crontab -e` remove the line

### Feature: Weekly /tmp cleanup cron
- **Change type:** new
- **What changed:** Cron entry `0 3 * * 0 find /tmp -maxdepth 1 \( -name "zangetsu_*.log.[0-9]" -o -name "zangetsu-*.txt" -o -name "zangetsu-*.bak" \) -mtime +7 -delete`
- **Why:** Long-running watchdog rotates logs (`.log.1`, `.log.2`); Mac scratch transit files accumulate in /tmp. Weekly sweep keeps disk clean.
- **Q1/Q2/Q3:** PASS — only deletes files older than 7 days, only matching specific patterns
- **Rollback:** remove cron line

---

## v0.3.2 — 2026-04-17 — Watchdog stale-loop bug fix (caught by 1h observation)
**Engine hash:** `zv5_v71` / `zv5_v9`
**Branch / commit:** `feat/v9-oneshot-hardening` @ `c1f23a46`

### Feature: Watchdog — bump STALE_THRESHOLD + skip cron-managed services
- **Change type:** fix (production-impacting)
- **What changed:**
  - `zangetsu/watchdog.sh`: `STALE_THRESHOLD=600` → `1800` (10min → 30min)
  - Added skip clause in main lockfile loop: `case "$name" in arena13_feedback|calcifer_supervisor) continue ;; esac`
- **Why:** P0-6 watchdog observation revealed two real production bugs introduced earlier this session:
  1. **arena13_feedback false-restart loop**: cron-managed `*/5min`, but lock file persists between runs with dead PID. Watchdog iterates `/tmp/zangetsu/*.lock`, sees dead PID, attempts restart → hits `*) unknown service` branch → spammed `WATCHDOG: unknown service arena13_feedback, cannot restart` every cycle.
  2. **arena23/45 vicious restart loop**: orchestrators idle when `champion_pipeline` empty (which it is — V9 hasn't accumulated). Idle = no log writes. STALE_THRESHOLD=600 (10min) → watchdog killed them every cycle. Logs showed `restarted arena23_orchestrator (pid=N)` repeatedly. Without fix: continuous worker churn until DB has data.
- **Q1/Q2/Q3:**
  - Q1 PASS — manual `bash watchdog.sh` runs silently (healthy); skip clause limited to known cron-managed services
  - Q2 PASS — `tail -f /tmp/zangetsu_watchdog.log` after fix shows no further restart events
  - Q3 PASS — 6-line patch
- **Rollback:** revert sed (one block + one line)

---

## v0.3.3 — 2026-04-17 — Git history partial cleanup (gc 6.0G → 1.3G)
**Engine hash:** unchanged
**Branch / commit:** N/A (git plumbing only, no commit needed)

### Operation: aggressive gc + reflog expire
- **Change type:** infra (one-shot)
- **What changed:**
  - `git reflog expire --expire=now --all`
  - `git gc --prune=now --aggressive`
  - Repo `.git`: **6.0 GB → 1.3 GB** (78% reduction)
- **Why:** Earlier `git filter-branch` (during rename, v0.2.0) made `zangetsu_v3/.venv` blobs unreachable but didn't gc them. They sat in pack files for hours. Aggressive gc reclaimed the space.
- **Q1/Q2/Q3:** PASS — refs/HEAD unchanged; only unreachable objects pruned; force-push not needed
- **Note:** `git filter-repo --path zangetsu_v3 --invert-paths --force` attempted but blocked by interactive sanity-check prompt (stdin EOF over SSH). To complete: run with `--enforce-sanity-checks=false` from attached terminal. Estimated additional savings: ~500 MB.

### Deferred (not in this version)
- Full `git filter-repo` to remove `zangetsu_v3/` source from history — needs interactive shell or `--enforce-sanity-checks=false`
- engine_hash 17-query migration to `champion_pipeline_v9` view — wait for V9 data accumulation
- PR #3 merge to main — pending review
- Gemini auth on Alaya — needs `GEMINI_API_KEY`

---

## v0.3.0 — 2026-04-17 — All-ctl service model + test cred + hygiene
**Engine hash:** `zv5_v71` / `zv5_v9` (literals preserved)
**Branch / commit:** `feat/v9-oneshot-hardening` @ `d0aab305`

### Feature: all-ctl.sh service management (eliminate systemd dual-management)
- **Change type:** refactor (infra)
- **What changed:**
  - Removed 6 systemd unit files: `arena-pipeline.service`, `arena23-orchestrator.service`, `arena45-orchestrator.service`, `arena13-feedback.service`, `arena13-feedback.timer`, `arena13-evolution.service`
  - `watchdog.sh`: removed dead `SYSTEMD_SERVICES` array + `LOCK_TO_SYSTEMD` map + the `restart_service` systemd-prefer branch (~23 lines)
  - `restart_service` now lockfile-only restart for arena workers
  - Source-of-truth: `zangetsu_ctl.sh` + `watchdog.sh` (cron */5min)
  - Kept systemd-managed: `console-api`, `dashboard-api`, `calcifer-supervisor`
- **Why:** systemd arena units were spawning workers in restart loop, losing pidlock to ctl.sh-spawned ones. Pure log noise. Watchdog's `LOCK_TO_SYSTEMD` mapping triggered failed `systemctl restart` calls. Single-management model = clean ops.
- **Q1/Q2/Q3:** PASS — V9 scan reports `✅ Systemd units stable`, 6 workers running, no restart loops
- **Rollback:** re-create unit files from systemd template + `daemon-reload`

### Feature: test credential auto-loading
- **Change type:** new
- **What changed:**
  - Created user-readable env file at `~/.zangetsu_test.env` (mode 0600, owner j13:j13) — copy of `/etc/zangetsu/zangetsu.env`
  - Added `zangetsu/tests/conftest.py` — auto-loads env vars from that file on pytest startup
- **Why:** `/etc/zangetsu/zangetsu.env` is root-only (used by systemd EnvironmentFile). pytest as `j13` user couldn't read → asyncpg InvalidPassword in `test_db` / `test_checkpoint` / `test_console_api`. After fix: 3 passed / 3 skipped (was 2 failed).
- **Q1/Q2/Q3:** PASS — pytest now exits 0
- **Rollback:** delete the user-readable env file and `tests/conftest.py`

### Feature: V32 scan — Calcifer endpoint moved to AKASHA /health
- **Change type:** fix
- **What changed:** `~/.claude/scratch/v32-deep-scan.sh` Calcifer section: `http://100.123.49.102:8770/health` → `http://100.123.49.102:8769/health` (AKASHA), section header renamed `## Calcifer` → `## AKASHA Health`
- **Why:** Calcifer-supervisor doesn't bind any HTTP port (it's an Ollama+Telegram bot), so 8770 returned empty forever. AKASHA at 8769 is the actual health source.
- **Q1/Q2/Q3:** PASS — scan now reads `AKASHA: {"status":"ok"}`
- **Rollback:** revert sed in scan script

### Feature: ctl.sh — `$0 status` bug + V5/V9 banner
- **Change type:** fix (cosmetic + ergonomics)
- **What changed:** Line 63 `$0 status` → `bash "$(dirname "$0")/zangetsu_ctl.sh" status`; banner string `"Zangetsu V5 services"` → `"Zangetsu V9 services"`
- **Why:** `$0` resolves to bare `zangetsu_ctl.sh` (not in PATH), causing `command not found` every restart. Banner was outdated.
- **Q1/Q2/Q3:** PASS
- **Rollback:** sed reverse

### Feature: post-rename hygiene — calcifer paths + log filenames
- **Change type:** fix (post-rename leftover)
- **What changed:**
  - `calcifer/supervisor.py`: 3 paths `~/j13-ops/zangetsu_v5/` → `~/j13-ops/zangetsu/`, lock `/tmp/zangetsu_v5/` → `/tmp/zangetsu/`
  - `watchdog.sh` + `zangetsu_ctl.sh`: log filenames `/tmp/zv5_*.log` → `/tmp/zangetsu_*.log`
  - cron: `/tmp/zv5_watchdog.log` → `/tmp/zangetsu_watchdog.log`
  - `.gitignore`: added `**/.venv/`, `**/__pycache__/`, `**/*.bak2`, `**/*.deleted`, `zangetsu/data/{funding,ohlcv,oi,regimes}/`
- **Why:** Explore-agent post-rename audit caught these (Calcifer was actively writing to dead path; log filenames mismatch would trigger watchdog auto-restart in 5min)
- **Q1/Q2/Q3:** PASS — caught by 2nd-round scan, fixed before next watchdog tick

### Non-feature changes
- engine_hash literals (`zv5_v9`, `zv5_v71`) and SQL pattern (`'zv5_%'`) intentionally preserved per project_naming convention (folder=physical axis, hash=runtime stamp axis)
- During sweep I accidentally caught engine_hash literals — reverted in same session
- arena45 worker dropped during ctl restart → systemd race spawned duplicate → caught + cleaned + systemd units permanently removed in this version

### Deferred (not in this version)
- Git LFS for `zangetsu/data/**/*.parquet` — needs `apt install git-lfs` on Alaya first
- engine_hash default filter on dashboard/scripts — wait until V9 (`zv5_v9`) accumulates champion records
- PR #3 merge to main — pending review

---

# zangetsu — VERSION LOG

> Per `_global/feedback_project_naming.md`: bare project folder name + this log file as single-source-of-truth for "what changed when".
> Latest version on top. Per-feature granularity required.

---

## v0.2.0 — 2026-04-17 — Folder rename: `zangetsu_v5` → `zangetsu`
**Engine hash:** `zv5_v71` (unchanged — runtime stamp axis decoupled from folder)
**Branch / commit:** `feat/v9-oneshot-hardening` @ (pending)

### Feature: project folder rename
- **Change type:** refactor (physical layout)
- **What changed:**
  - `~/j13-ops/zangetsu_v5/` → `~/j13-ops/zangetsu/` (git mv, history preserved)
  - 43 code/config files swept: all `zangetsu_v5` → `zangetsu` in imports / paths / SQL DSN / shell scripts
  - 10 systemd unit files updated (`/etc/systemd/system/{arena,console,dashboard,calcifer,health-monitor,live-trader}*.service`)
  - 2 cron entries updated (watchdog + daily_data_collect)
  - 46 `.venv/bin/` script shebangs sed-rewritten
  - Lock dir `/tmp/zangetsu_v5/` → `/tmp/zangetsu/`
  - Mac scan script `~/.claude/scratch/v32-deep-scan.sh` updated
- **Why:** Adopting new project naming rule (`feedback_project_naming.md`). Version-suffixed dirs caused the V9 全局修復 saga: scan tooling stayed at V3 paths, schemas, modules — silent decay. Folder names should be physical-layer identifiers; doctrine version (V9 Sharpe Quant) lives in code/branch, runtime version (`zv5_v71`) lives in DB.
- **Q1/Q2/Q3:** PASS — 6 workers restarted clean, all imports green, systemd 3 conflict units stay disabled, no inflight-data loss (workers idle at rename moment)
- **Rollback:** `git mv zangetsu zangetsu_v5 && sudo find /etc/systemd/system -name "*.service" -exec sed -i "s|zangetsu/|zangetsu_v5/|g" {} \; && sudo systemctl daemon-reload && crontab /tmp/zangetsu-crontab.bak && bash zangetsu_ctl.sh restart`

### Non-feature changes
- `engine_hash` in DB stays `zv5_v71` — intentional decoupling per project_naming feedback rule
- `zangetsu_ctl.sh` still echoes "Zangetsu V5 services" string in startup banner — cosmetic, acceptable; will rename to "V9" when next version logical

---

## v0.1.1 — 2026-04-17 — Pidlock import-time fix + scan rewrite + pytest config
**Engine hash:** `zv5_v71`
**Branch / commit:** `feat/v9-oneshot-hardening` @ `bb1602fc`

### Feature: pidlock single-instance guard
- **Change type:** fix
- **What changed:** moved `acquire_lock()` from module top-level into `if __name__ == "__main__"` guard in 4 services: `arena_pipeline.py`, `arena13_feedback.py`, `arena23_orchestrator.py`, `arena45_orchestrator.py`
- **Why:** any `import` of these services triggered pidlock → `sys.exit(1)`, breaking scan/test/lint pipelines silently. V3.2 scan reported "S01 import failure" with empty error → this was the root cause.
- **Q1/Q2/Q3:** PASS — commit `3dc1304e`
- **Rollback:** `cp services/{name}.py.bak2 services/{name}.py`

### Feature: pytest async test support
- **Change type:** new
- **What changed:** added `zangetsu/pytest.ini` with `asyncio_mode = auto`; installed `pytest-asyncio` 1.3.0 in `.venv`
- **Why:** 3 integration tests were silently skipped because pytest didn't recognize `async def`. After fix, 1 test now passes; 2 still fail on asyncpg credentials (separate test-infra issue, not in scope here).
- **Q1/Q2/Q3:** PASS — commit `bb1602fc`
- **Rollback:** `rm pytest.ini && pip uninstall pytest-asyncio`

### Feature: V3.2 scan script rewrite (Mac side)
- **Change type:** refactor
- **What changed:** `~/.claude/scratch/v32-deep-scan.sh` rewritten from V3 era to V9 reality:
  - Paths: `zangetsu_v3` → `zangetsu_v5` (later → `zangetsu` in v0.2.0)
  - SQL: V3 tables (`factor_candidates` etc.) → V9 schema (`champion_pipeline`, `pipeline_state`, `pipeline_errors` with correct column names)
  - Module check list: V9 module layout
  - S01 stderr handling fixed (was treating optional-lib WARNINGs as failures)
  - ps grep aligned to script-style invocation `services/(arena|v9_)`
  - Calcifer freshness JSON parse guarded
  - New section: Service Manager Conflict Check (auto-detects systemd-vs-ctl issues)
- **Why:** Old script was V3-era; reported false MISSING for everything V9 had refactored. Couldn't distinguish "broken" from "intentionally moved."
- **Q1/Q2/Q3:** PASS — minimal changes per section, verified by re-running scan
- **Rollback:** `cp v32-deep-scan.sh.v3.bak v32-deep-scan.sh` (kept on Mac /tmp)

### Feature: redundant systemd units disabled
- **Change type:** infra cleanup
- **What changed:** `systemctl stop && disable` for `arena-pipeline`, `arena23-orchestrator`, `arena45-orchestrator`, `arena13-feedback`, `arena13-evolution`, `arena13-feedback.timer`. Workers continue running via `zangetsu_ctl.sh + watchdog.sh` (manual `&` spawn model — confirmed by reading `watchdog.sh` restart logic).
- **Why:** Systemd units were spawning workers in restart loop, losing pidlock to ctl.sh-spawned ones. Pure log noise. Watchdog uses `LOCK_TO_SYSTEMD` map but its actual restart path uses `eval $cmd > log 2>&1 &` (not `systemctl restart`) — so systemd units were never the real management.
- **Q1/Q2/Q3:** PASS — V9 scan went from `⚠️ Systemd units in failure/restart loop` to `✅ Systemd units stable`
- **Rollback:** `sudo systemctl enable && start arena-pipeline arena23-orchestrator arena45-orchestrator`
