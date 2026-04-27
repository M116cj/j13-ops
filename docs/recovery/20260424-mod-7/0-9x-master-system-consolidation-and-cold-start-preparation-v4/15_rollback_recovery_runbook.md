# 42-15 Rollback and Recovery Runbook — ZANGETSU Master Consolidation 4-2 / Track P

**Status:** Design / Reference
**Owner:** Track P (Recovery & Safety)
**Audience:** Operators, on-call, Lead reviewing live incidents
**Scope:** Mac mirror `/Users/a13/dev/j13-ops` + Alaya `/home/j13/j13-ops` (Tailscale `100.123.49.102`)
**Constitution refs:** §17.1 VIEW-based status, §17.4 auto-revert, §17.6 stale-service rule, §17.7 decision record gate

> **First principle:** never force-push, never `git rm` evidence, never restart a stale service. Every recovery action terminates in (1) Telegram notification to thread 356, (2) decision record in `docs/decisions/YYYYMMDD-recovery-*.md`, (3) preserved evidence in `docs/recovery/`.

---

## 0. Quick-glance decision matrix

| Symptom                        | Section | First action                                        |
|--------------------------------|---------|-----------------------------------------------------|
| DB migration mid-apply failure | §1      | Check `pg_stat_activity` for in-flight tx           |
| DB schema diverged from repo   | §2      | Restore from latest pg_dump snapshot                |
| Bad commit on `main`           | §3, §4  | `git revert` + signed commit + new PR (admin merge) |
| A1/A23/A45 worker dead         | §5      | Wait 5 min for watchdog OR run `watchdog.sh`        |
| Cron broken                    | §6      | Restore `crontab.snapshot`                          |
| Watchdog itself broken         | §7      | Manual launch, then re-enable cron                  |
| `~/.env.global` corrupted      | §8      | Copy from `~/.env.global.bak.*`                     |
| A1 crash w/ `_pb` UnboundLocal | §9      | Confirm PR #37 fix, stale-service check             |
| A13 feedback failing           | §10     | DB connectivity + JSON file perms                   |
| A23/A45 idle                   | §11     | Check `champion_pipeline_fresh` rows                |
| Validation contract regression | §12     | git revert PR adding new gate                       |
| `alpha_zoo` unsafe rerun       | §13     | DO NOT run unflagged; revert PR if needed           |
| Gate-A failed                  | §14     | `gh run view`; check decision record + branch name  |
| Gate-B failed                  | §15     | Identify affected module; fix module test           |
| Pre-commit forbidden-diff      | §16     | Abort commit, examine diff                          |
| Live PnL anomaly               | §19     | EMERGENCY STOP, no restart                          |

---

## 1. DB migration rollback — `v0.7.1`

**When:** `migrations/postgres/v0.7.1.sql` was applied and produced an unintended schema state.

**Pre-apply discipline (mandatory before every migration):**
```bash
ssh j13@100.123.49.102 "docker exec deploy-postgres-1 pg_dump -U zangetsu zangetsu_v5 \
  > /home/j13/backups/zangetsu_v5_pre_v0.7.1_$(date +%Y%m%d_%H%M%S).sql"
```

**Rollback path A — designed inverse exists:**
```bash
docker exec -i deploy-postgres-1 psql -U zangetsu -d zangetsu_v5 \
  < /home/j13/j13-ops/zangetsu/migrations/postgres/rollback_v0.7.1.sql
```

**Rollback path B — inverse failed or absent:**
```bash
# Restore full snapshot taken in pre-apply step
docker exec -i deploy-postgres-1 psql -U zangetsu -d zangetsu_v5 \
  < /home/j13/backups/zangetsu_v5_pre_v0.7.1_<TS>.sql
```

**Decision tree — "DB migration failed midway":**
1. Check tx state: `SELECT pid, state, query FROM pg_stat_activity WHERE datname='zangetsu_v5' AND state <> 'idle';`
2. If active tx → it auto-rolls-back on disconnect (PostgreSQL is transactional DDL when wrapped in `BEGIN;...COMMIT;`).
3. If `COMMIT` already executed but later step failed → migration is partially applied → use rollback path B.
4. Verify post-rollback: `SELECT version FROM zangetsu_schema_version ORDER BY applied_at DESC LIMIT 1;`
5. Telegram BLOCKED notification (template §17).

---

## 2. DB snapshot save / restore

**Save:**
```bash
ssh j13@100.123.49.102 \
  "docker exec deploy-postgres-1 pg_dump -U zangetsu zangetsu_v5" \
  > snap_$(date +%Y%m%d_%H%M%S).sql
```

**Restore (destructive — confirms required):**
```bash
ssh j13@100.123.49.102 \
  "docker exec -i deploy-postgres-1 psql -U zangetsu -d zangetsu_v5" \
  < snap_YYYYMMDD_HHMMSS.sql
```

**Verification:**
- `SELECT count(*) FROM champion_pipeline_fresh;` (must be ≥ pre-restore state)
- `SELECT * FROM zangetsu_status;` (the §17.1 VIEW)
- Telegram SUCCESS once both checks pass.

---

## 3. `git revert` — for any signed PR

> **Rule (§17.4 + branch protection):** never force-push to `main`. Every revert is a *new* signed commit landing through the standard admin-squash-delete-branch merge.

```bash
# Option A — gh native
gh pr revert <PR>           # creates a revert PR; review and merge

# Option B — manual
git checkout -b revert/PR-<N>-<short-reason>
git revert --signoff --gpg-sign <SHA>
git push -u origin HEAD
gh pr create --title "revert: PR #<N> — <reason>" \
  --body "Reverts #<N>. Reason: <one-line>. Decision record: docs/decisions/$(date +%Y%m%d)-revert-PR<N>.md"
```

Decision record under `docs/decisions/` is mandatory (Gate-A enforces — §17.7).

---

## 4. Branch rollback

- Always revert through a PR (see §3).
- Never `git push --force` against `main` (branch protection blocks anyway, but do not request waivers).
- If multiple PRs need reverting → revert in reverse-merge order, one PR each, to keep history linear and preserve bisect.

---

## 5. Runtime service recovery — A1 / A23 / A45

**Step 1 — find PIDs (Alaya):**
```bash
ssh j13@100.123.49.102 "ps -ef | grep -E 'a1_worker|a23_|a45_' | grep -v grep"
```

**Step 2 — kill (graceful first, then KILL):**
```bash
ssh j13@100.123.49.102 "kill <PID>; sleep 5; kill -9 <PID> 2>/dev/null"
```

**Step 3 — wait or force respawn:**
- **Wait:** cron-driven watchdog runs every 5 min and restarts dead workers.
- **Force:** `ssh j13@100.123.49.102 "bash /home/j13/j13-ops/zangetsu/watchdog.sh"`

**Step 4 — §17.6 stale-service check (mandatory before declaring recovery):**
```bash
~/.claude/hooks/pre-done-stale-check.sh zangetsu_a1 \
  /Users/a13/dev/j13-ops/zangetsu/engine/a1/worker.py \
  --remote j13@100.123.49.102 \
  --remote-source-path /home/j13/j13-ops/zangetsu/engine/a1/worker.py
```
Exit `0` = FRESH. Exit `1` = STALE → process started before source mtime → kill again, restart.

---

## 6. Cron recovery

**If `crontab -l` returns garbage or empty unexpectedly:**
```bash
ssh j13@100.123.49.102 "test -f /home/j13/j13-ops/zangetsu/crontab.snapshot && \
  crontab /home/j13/j13-ops/zangetsu/crontab.snapshot && \
  crontab -l"
```
If `crontab.snapshot` missing → reconstruct from `docs/decisions/*-cron-*.md` (snapshot of approved cron lines).

After every successful crontab change:
```bash
ssh j13@100.123.49.102 "crontab -l > /home/j13/j13-ops/zangetsu/crontab.snapshot"
```

---

## 7. Watchdog recovery

If `watchdog.sh` is itself broken (syntax error, dead bash):
```bash
# 1. Disable cron entry temporarily
ssh j13@100.123.49.102 "crontab -l | grep -v watchdog.sh | crontab -"

# 2. Manual single launch to validate
ssh j13@100.123.49.102 "bash -x /home/j13/j13-ops/zangetsu/watchdog.sh 2>&1 | tail -50"

# 3. Re-enable cron once green
ssh j13@100.123.49.102 "crontab /home/j13/j13-ops/zangetsu/crontab.snapshot"
```

---

## 8. `~/.env.global` recovery

`~/.env.global` is local-only on Alaya, never in git. Backups exist at `~/.env.global.bak.0-9v-env-config` (and possibly `.bak.1`, `.bak.2`).

```bash
ssh j13@100.123.49.102 "ls -la ~/.env.global*"
ssh j13@100.123.49.102 "cp ~/.env.global.bak.0-9v-env-config ~/.env.global"
ssh j13@100.123.49.102 "chmod 600 ~/.env.global"
```

Validate by sourcing in a sub-shell:
```bash
ssh j13@100.123.49.102 "(set -a; . ~/.env.global; set +a; printenv | grep -E '^(BINANCE|TG_|PG_)' | wc -l)"
```

---

## 9. A1 crash recovery

**Symptom:** `/tmp/zangetsu_a1_w*.log` shows `UnboundLocalError: local variable '_pb' referenced before assignment`.

1. Confirm fix is on `main`: `gh pr view 37 --json state,mergedAt`
2. Confirm Alaya checkout has the fix:
   ```bash
   ssh j13@100.123.49.102 "cd /home/j13/j13-ops && git log --oneline -5 -- zangetsu/engine/a1/worker.py"
   ```
3. §17.6 stale check (see §5 step 4) — running process must be ≥ source mtime.
4. If stale → kill, watchdog respawn.
5. Tail log; the crash signature must not reappear within 10 min.

---

## 10. A13 feedback recovery

A13 is single-shot, cron-driven (`*/5`).

If A13 logs show repeated failure:
1. **DB connectivity:**
   ```bash
   ssh j13@100.123.49.102 "docker exec deploy-postgres-1 pg_isready -U zangetsu"
   ```
2. **`a13_guidance.json` perms:**
   ```bash
   ssh j13@100.123.49.102 "ls -la /home/j13/j13-ops/zangetsu/a13_guidance.json"
   ```
   Owner must be `j13`, mode `0644`.
3. If both pass and A13 still fails → escalate, do not silently restart.

---

## 11. A23 / A45 idle recovery

A23 and A45 consume `champion_pipeline_fresh`. Empty pipeline → idle by design.

Diagnostic:
```bash
ssh j13@100.123.49.102 "docker exec deploy-postgres-1 psql -U zangetsu -d zangetsu_v5 \
  -c 'SELECT count(*) FROM champion_pipeline_fresh;'"
```

- count = 0 → expected idle, no action.
- count > 0 AND A23/A45 still idle → check row visibility (transaction isolation, missing index) before restart. Restart alone won't fix a logical bug.

---

## 12. Validation contract rollback

The validation gate set is *additive*: new gates appended, existing untouched.

If a new gate over-rejects (e.g., today's A1 reject COUNTER_INCONSISTENCY 50% + COST_NEGATIVE 50% drift):
1. Identify the PR that added the gate.
2. `gh pr revert <PR>` (see §3).
3. Existing gates remain in force; rejection mix returns to prior baseline.
4. Decision record must capture: which gate, false-positive evidence, plan for redesigning before reland.

---

## 13. `alpha_zoo` tooling rollback

Rollback only the safety-flag PR:
```bash
gh pr revert <safety-flag-PR>
```

> **CRITICAL:** without the safety flags, `alpha_zoo` falls back to its previous state, which is **unsafe** to execute. **Do not run** the unflagged script under any circumstance. The rollback is purely to restore the codebase mechanically; operationally `alpha_zoo` is paused until a redesigned safe version lands.

---

## 14. Failed Gate-A handling

Gate-A (`phase-7-gate.yml`) checks Phase 7 prereqs.

```bash
gh run list --workflow=phase-7-gate.yml --limit 5
gh run view <run-id> --log-failed
```

Common causes:
- Missing `docs/decisions/YYYYMMDD-*.md` matching `feat(zangetsu/v*)` commit (§17.7).
- Branch name not matching pattern (e.g., `feat/`, `fix/`, `chore/`).
- VERSION_LOG.md not updated.

Fix the underlying issue. **Never** disable the workflow.

---

## 15. Failed Gate-B handling

Gate-B (`module-migration-gate.yml`) is per-module.

```bash
gh run view <run-id> --log-failed
```

The "Identify affected modules" job lists the modules touched. Each affected module has its own test set; fix the module-specific test, push, re-run.

---

## 16. Controlled-diff forbidden handling

Pre-commit hook blocks edits to fields marked controlled (e.g., schema version, gate sequence).

```
ABORT.
1. git diff --staged                  # examine
2. Decide: legitimate change requiring decision record? Or accidental?
3. Legitimate → write docs/decisions/YYYYMMDD-controlled-<field>.md FIRST,
   then re-stage and commit (hook re-checks).
4. Accidental → git restore --staged <file>; git checkout -- <file>.
```

---

## 17. Telegram notification templates

Chat `-1003601437444`, thread `356`.

### SUCCESS
```
[SUCCESS] zangetsu/<scope> — <one-line>
context: <PR/run/migration ref>
verification: <command + result>
next: <none | follow-up step>
```

### BLOCKED
```
[BLOCKED] zangetsu/<scope> — <one-line>
reason: <root cause>
blast radius: <what is affected>
mitigation: <immediate stopgap>
owner: <agent / human>
ETA to unblock: <duration | unknown>
```

### EMERGENCY_STOP
See `/tmp/emergency_stop_template.md`.

---

## 18. Evidence preservation

`docs/recovery/` is **append-only**. Rules:
- Never `git rm` files under `docs/recovery/`.
- Never rewrite an existing file; create `docs/recovery/YYYYMMDD-<slug>-v2.md` for updates.
- Each incident must produce at minimum: timeline, commands run, log excerpts, Telegram message IDs, links to decision record + retro.
- pre-receive hook on `main` rejects deletions under `docs/recovery/`.

---

## 19. Emergency stop procedure

Trigger: live PnL anomaly, suspected silent corruption, unknown-state production.

> **Do NOT restart anything until the investigation closes.**

Sequence:
1. **Kill workers:**
   ```bash
   ssh j13@100.123.49.102 "pkill -f 'a1_worker|a23_|a45_'"
   ```
2. **Disable cron entries (watchdog + A13):**
   ```bash
   ssh j13@100.123.49.102 "crontab -l > /tmp/crontab.preEMERGENCY && \
     crontab -l | sed 's|^[^#].*\\(watchdog.sh\\|a13_\\)|# EMERGENCY_STOP \\0|' | crontab -"
   ```
3. **Confirm no canary / production order in flight:**
   - DB: `SELECT * FROM live_orders WHERE state IN ('OPEN','PENDING');` → must be 0.
   - Exchange API (read-only key): query open orders for the master sub-account; must be 0 or only legacy.
4. **Telegram emergency_stop notification** (`/tmp/emergency_stop_template.md`).
5. **Incident record:** `docs/recovery/YYYYMMDD-emergency-stop-<slug>.md` populated with timeline + decision tree position + evidence.
6. **Decision tree — "Live PnL anomaly":**
   - Anomaly observed → emergency stop (steps 1–5).
   - Investigate offline (read-only).
   - Root cause identified + fix designed + decision record + retro → only then plan re-enable through normal /team flow.
   - **Do not** restart "to see if it recurs". That destroys evidence.

Re-enable preconditions:
- All 5 quality flags green.
- Decision record + retro written.
- Smoke test passed in shadow mode for ≥ 1 full canary window.
- j13 explicit approval.

---

## Appendix A — Decision tree quick lookup

| Scenario                             | First check                              | If yes → action                          | If no → action                          |
|--------------------------------------|------------------------------------------|------------------------------------------|-----------------------------------------|
| DB migration failed midway           | tx still active (pg_stat_activity)?      | wait for auto-rollback, verify schema    | restore from pg_dump (§2)               |
| Service won't start after PR merge   | source mtime > process start?            | kill + watchdog respawn (§5)             | inspect logs; not a stale-service issue |
| Live PnL anomaly                     | open orders > 0?                         | EMERGENCY STOP (§19), do NOT restart     | EMERGENCY STOP (§19), do NOT restart    |
| A1 reject mix drift                  | new validation gate added recently?      | revert that PR (§12)                     | open a /debug — feature drift, not gate |
| Gate-A red on PR                     | decision record file present?            | examine `gh run view --log-failed`       | add decision record, re-push            |
| Gate-B red on PR                     | which module(s) affected?                | fix module test, re-push                 | escalate, possible workflow bug         |
| Watchdog log silent for > 10 min     | cron entry intact?                       | restore from snapshot (§6)               | manual run watchdog (§7)                |

---

## Appendix B — Pre-done verification checklist (every recovery)

- [ ] §17.6 stale-service check passed (or N/A documented)
- [ ] §17.1 VIEW `zangetsu_status` queried live; `deployable_count` not regressed
- [ ] No `/tmp/calcifer_deploy_block.json` present
- [ ] Telegram notification sent
- [ ] Decision record written under `docs/decisions/YYYYMMDD-recovery-*.md`
- [ ] Evidence preserved under `docs/recovery/YYYYMMDD-*.md`
- [ ] If /team session was used → retro under `docs/retros/YYYYMMDD-*.md`

---
*End of runbook. Total: 19 sections + 2 appendices, designed against §17 constitution.*
