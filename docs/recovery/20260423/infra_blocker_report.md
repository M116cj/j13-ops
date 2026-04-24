# Infrastructure Blocker Report

**Order**: `/home/j13/claude-inbox/0-1` Phase C (umbrella)
**Produced**: 2026-04-23T01:33Z
**Lead**: Claude
**Scope**: enumerate every infra blocker found during Phase A+B+C execution; each tagged with severity, owner-action, whether blocking-R2, and current status.

---

## 1. Summary table

| ID | Blocker | Severity | Blocks R2? | Fix path | Status |
|---|---|---|---|---|---|
| B1 | Alaya GPU driver not loaded | HIGH (Katen, Calcifer LLM) | NO | sudo apt install + j13 present | DIAGNOSED, repair authorized-pending |
| B2 | Calcifer working-tree polluted with runtime state | LOW | NO | gitignore + rm --cached + code commit | **FIXED — commit ae738e37** |
| B3 | `d-mail-miniapp` not under version control | CRITICAL (production command center) | NO | `git init` + push to new repo | NOTED, needs j13 decision on repo |
| B4 | `calcifer-miniapp` not under version control | HIGH | NO | same pattern | NOTED, same |
| B5 | `arena13_feedback.py` silent-failing every 5 min (cron env KeyError) | MEDIUM | NO (arena down), but re-enables when arena restarts | add `ZV5_DB_PASSWORD` to cron env | NOTED, deferred |
| B6 | Arena processes not under systemd | MEDIUM | NO (intentional per 0-1 Phase D) | `/etc/systemd/system/arena-*.service` after recovery proof | DEFERRED — see `systemd-deferral-memo.md` |
| B7 | Gemini CLI broken on Mac (keytar.node + EPERM on .Trash + silent exit) | MEDIUM (reduces adversarial review capacity) | NO | `brew reinstall gemini-cli` and/or reset keytar | NOTED, flagged |
| B8 | Gate/deploy-block logic fully version-controlled | — | — | — | **VERIFIED OK** (post-commit ae738e37) |
| B9 | `wd_keepalive.service` failed | TRIVIAL | NO | hardware watchdog daemon, pre-existing unrelated | IGNORED |
| B10 | `supervisor.py` running stale binary (not restarted post-commit) | LOW | NO | `sudo systemctl restart calcifer-supervisor` | NOTED, post-report |

## 2. Per-blocker detail

### B1 — GPU driver
See `gpu_driver_repair_report.md` (full diagnostic + repair protocol).

### B2 — Calcifer state pollution — **FIXED**
See `calcifer_state_formalization.md`. Commit `ae738e37` is live on `main`.

### B3 — d-mail-miniapp outside git (**CRITICAL**)

**Location**: `/home/j13/d-mail-miniapp/`
**Contents**: `server.py` (1047 lines per AKASHA v0.5.5 record; serves `/dmail/` Caddy route on port 8771; absorbs calcifer Ops stack directly), plus `calcifer-miniapp.service`-style systemd unit, `.env`, HTML frontend.
**Systemd unit**: `d-mail-miniapp.service` — `ExecStart=/home/j13/d-mail-miniapp/.venv/bin/python server.py`.
**Current state**: `fatal: not a git repository (or any of the parent directories): .git`.

**Why CRITICAL**:
- This is the **primary Claude Command Center**: Current Task + Session Health + Shortcut Grid + Pending Tasks + AKASHA + Upload. j13 opens `/dmail/` on mobile for all ops.
- Zero history. Zero peer review trail. A `rm -rf /home/j13/d-mail-miniapp/` or disk failure = full rebuild.
- v0.5.5 refactor that absorbed calcifer Ops stack (456→1047 lines) has NO reviewable diff against v0.5.4.
- `.env` is symlinked to `/home/j13/alaya/calcifer/.env` — credentials NOT in miniapp repo even once it exists.

**Fix plan**:
1. Decide on GitHub target: `M116cj/d-mail-miniapp` (private, owner-only) recommended.
2. Write `.gitignore`: `.venv/`, `__pycache__/`, `*.pyc`, `.env`, `.env.*`, `server.py.bak_*` → all excluded.
3. `cd /home/j13/d-mail-miniapp && git init && git add . && git status` → verify no secrets tracked before first commit.
4. Initial commit: `feat(d-mail-miniapp): import v0.5.5 self-contained systemd service state (2026-04-18)`.
5. Create GitHub repo (gh api), push.
6. Add `d-mail-miniapp` to Alaya backup cron (nightly `git bundle create` or `git push`).

**Not executed here** — requires j13 decision on repo owner/visibility + sign-off on commit message.

### B4 — calcifer-miniapp outside git (HIGH)

Same shape as B3, lower criticality because `/dmail/` front-end is the current active UX (v0.5.5 absorbed calcifer Ops UI; `/calcifer/` UI is diagnostic fallback only).

**Location**: `/home/j13/calcifer-miniapp/` — `server.py` 38KB, `server.py.bak_v03_20260419_003612` as de-facto version history, `calcifer-miniapp.service`, `.env` → symlink to `/home/j13/alaya/calcifer/.env`, `deploy.sh`, `requirements.txt`.

**Fix plan**: same as B3 (repo `M116cj/calcifer-miniapp`).

### B5 — arena13_feedback.py silent failure (MEDIUM)

**Discovered**: during Phase A respawn-hazard audit.
**Mechanism**:
- Cron entry: `*/5 * * * * cd ~/j13-ops/zangetsu && .venv/bin/python services/arena13_feedback.py >> /tmp/zangetsu_a13fb.log 2>&1`
- `zangetsu/config/settings.py:99`: `DB_PASSWORD: str = os.environ["ZV5_DB_PASSWORD"]  # no fallback — must be set in env`
- Cron environment does NOT inherit interactive shell env; `ZV5_DB_PASSWORD` unset → `KeyError` at import.
- Effect: `arena13_feedback` guidance loop has been silently non-functional; arena 1 reads stale `/home/j13/j13-ops/zangetsu/config/a13_guidance.json` (last rewrite timestamp unknown, likely pre-G2 window).
- **Unknown duration**: `stat -c %y /tmp/zangetsu_a13fb.log` would show, but also log is traceback-only — no success markers.

**Impact on recovery**: during the G2 window (2026-04-22T17:52→19:56Z), arena 1 was evolving on stale guidance. Whether guidance freshness would have meaningfully altered the G2 FAIL verdict is INCONCLUSIVE (PROBABLE low — the `val_neg_pnl` 100% pattern is population-level, not guidance-level).

**Fix options** (pick one; NOT executed):

A. **Crontab env inject** (simplest):
   ```cron
   */5 * * * * ZV5_DB_PASSWORD=... cd ~/j13-ops/zangetsu && .venv/bin/python services/arena13_feedback.py >> /tmp/zangetsu_a13fb.log 2>&1
   ```
   Risk: env var in crontab = visible in `crontab -l` and process listing. Not best practice for credentials.

B. **Read env from file** (safer):
   ```cron
   */5 * * * * cd ~/j13-ops/zangetsu && . /home/j13/.env.global && .venv/bin/python services/arena13_feedback.py ...
   ```
   Requires `/home/j13/.env.global` (verified exists per AKASHA Binance keys memory) to contain `ZV5_DB_PASSWORD`.

C. **Move to systemd oneshot + timer** (most systematic):
   Create `zangetsu-arena13-feedback.service` (Type=oneshot, EnvironmentFile=/home/j13/.env.global) + `.timer` (OnCalendar=*:0/5).
   Benefits: explicit env, logged in journal, survives crontab loss.

**Recommendation**: C, paired with B6 systemd formalization when that unlocks.

**Deferral rationale**: arena is frozen; feedback loop irrelevant until arena restarts. Fix when arena restart is authorized (Trigger-A/B/C per `r2_patch_validation_plan.md` §2).

### B6 — Arena not under systemd (MEDIUM but DEFERRED)

Explicit per 0-1 Phase D "do not execute as mainline changes yet: systemd service formalization for arena". See `systemd-deferral-memo.md`.

### B7 — Gemini CLI broken on Mac (MEDIUM)

**Symptoms during Phase B**:
- Keychain init error: `Cannot find module '../build/Release/keytar.node'` → FileKeychain fallback
- `Error getting folder structure for /Users/a13: EPERM: scandir '/Users/a13/.Trash'`
- Silent exit after MCP context refresh — no LLM response written to stdout

**Impact**: Phase B adversarial review had to be done by Claude (self-adversarial voice) instead of Gemini. Per §5 "Mandatory Gemini review before: major arch changes, prod deploys" — this is a degraded state. Claude acted as both constructive AND adversarial voice with explicit labeling (`r2_recovery_review.md` §6.1).

**Fix**:
```bash
brew reinstall gemini-cli   # rebuild keytar.node against current Node ABI
# OR
cd $(brew --prefix)/Cellar/gemini-cli/0.35.3/libexec/lib/node_modules/@google/gemini-cli && npm rebuild keytar
```

Also consider granting Claude Code harness permission to Full Disk Access for `/Users/a13/.Trash` if `.Trash` scan is not opt-outable.

**NOT executed here** — outside Alaya scope, Mac-side toolchain maintenance. Flagged for j13 Mac session.

### B8 — Deploy-block logic version-controlled — VERIFIED

Post-commit `ae738e37`, the entire §17.3 gate pipeline is in git:

| Component | Location | Status |
|---|---|---|
| VIEW definition (§17.1) | `/home/j13/j13-ops/zangetsu/migrations/*.sql` (applied to deploy-postgres-1) | tracked |
| Calcifer outcome watch code | `/home/j13/j13-ops/calcifer/zangetsu_outcome.py` | tracked (ae738e37) |
| Calcifer supervisor wiring | `/home/j13/j13-ops/calcifer/supervisor.py` | tracked (ae738e37) |
| Flag file write path | `/tmp/calcifer_deploy_block.json` | ephemeral (correct) |
| State persistence | `/home/j13/j13-ops/calcifer/deploy_block_state.json` | gitignored (correct) |
| stale-check hook | `~/.claude/hooks/pre-done-stale-check.sh` | Mac-side, tracked in claude-os backup per §13 |

No local-only gate-path code remains. VERIFIED safe.

### B9 — wd_keepalive.service failed

Pre-existing hardware watchdog daemon, unrelated to Zangetsu. Explicitly ignored per 0-1 scope.

### B10 — Calcifer supervisor running stale binary

After `ae738e37` commit, `calcifer-supervisor.service` still runs the pre-commit supervisor.py (service loaded into memory at its original ActiveEnterTimestamp). The new `check_zangetsu_outcome` tool registration won't take effect until restart.

**§17.6 pre-done stale-check**: if anyone claims "calcifer outcome watch is formalized and active", that is STALE until restart.

**Action**: `sudo systemctl restart calcifer-supervisor.service` + verify `FRESH` via `pre-done-stale-check.sh`. Requires sudo. **NOT executed here.**

## 3. Deferred to j13

| # | Decision required | Recommendation |
|---|---|---|
| 1 | Authorize B1 GPU driver install (sudo + possible reboot) | Option A `ubuntu-drivers install` |
| 2 | Approve B3 `M116cj/d-mail-miniapp` repo creation (visibility: private) | Create ASAP, highest-priority infra formalization |
| 3 | Approve B4 `M116cj/calcifer-miniapp` repo creation | Same pattern as B3 |
| 4 | Authorize B10 `sudo systemctl restart calcifer-supervisor` | Requires sudo; low-risk (3-5s downtime) |
| 5 | B5 fix — when arena is authorized to restart (Trigger-A/B/C) | Option C systemd timer, paired with B6 |
| 6 | B7 Gemini CLI repair — trivial, when j13 has Mac session time | `brew reinstall gemini-cli` |

## 4. Q1 adversarial (for this report)

| Dim | Assertion | Verdict |
|---|---|---|
| Input boundary | 10 blockers enumerated with severity/status/owner; covers all findings from Phase A/B/C evidence capture | PASS |
| Silent failure | B5, B7, B10 each identify the silent-failure shape explicitly | PASS |
| External dep | B3/B4 identify external dependency on GitHub (repo creation) | PASS |
| Concurrency | B10 §17.6 stale-service concurrency risk flagged | PASS |
| Scope creep | No fixes executed beyond B2 (already scoped-authorized by "徹底執行") | PASS |
