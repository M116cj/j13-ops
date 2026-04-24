# R2 Rollback Contract

**Order**: `/home/j13/claude-inbox/0-1` Phase B action 4
**Produced**: 2026-04-23T01:00Z
**Lead**: Claude
**Status**: DOCUMENTED AND TESTED-IN-PRINCIPLE
**Current recommendation**: **DO NOT EXECUTE rollback**. R2 is making the pipeline honest; rollback re-introduces silent train-leak.

---

## 1. Contract scope

This contract specifies how to revert R2 (commit `bd91face`) if — and only if — rollback becomes the best available option. It exists so the option is concrete and testable, not so that it gets executed.

## 2. Rollback triggers (disjunctive; any one is sufficient)

**Only these trigger rollback**; no ad-hoc rollback without a trigger documented in `docs/decisions/`:

- **T1**: Evidence emerges that the R2 change itself (thresholds OR CD-14 holdout path) is mechanically defective — e.g., `data_cache[symbol]["holdout"]` is populated with TRAIN data due to a split bug, making the "OOS gate" fictional.
- **T2**: D1 audit produces a signal-quality bug fix whose correct validation requires a side-by-side comparison against pre-R2 baseline (train-leak deliberately re-enabled for 1 controlled window, documented).
- **T3**: Ascension Phase 3 replaces arena23_orchestrator with a modular engine; R2's CD-14 site is removed-by-supersession, not rolled back. Contract transfers to successor module.

All three triggers require a same-day decision record in `docs/decisions/YYYYMMDD-r2-rollback-<reason>.md` with j13 sign-off.

## 3. What rollback reverts (code)

**Primary (bundled git operation)**:

```bash
# On Alaya — requires branch cleanliness
ssh j13@100.123.49.102
cd /home/j13/j13-ops
git status   # must be clean on zangetsu/services/
git log --oneline bd91face -1   # confirm SHA lineage
git revert --no-commit bd91face
git commit -m "revert(zangetsu/r2-hotfix): <reason matching T1/T2/T3>" \
    -m "Restores $PARENT_SHA. Reason: <trigger + decision record>."
```

**Alternative (hard reset if main has no downstream commits dependent on bd91face)**:

```bash
# Only if main HEAD is still bd91face OR all subsequent commits are docs-only (per current 2026-04-23 state)
git reset --hard 480976c18a94967ab8b467eddc29c7317faffe0e
git push origin main --force-with-lease   # §17 explicitly permits with trigger decision record
```

**Current main state check (VERIFIED 2026-04-23T00:25Z)**:
- HEAD = `fd7cc34e` (docs)
- Commits between bd91face..fd7cc34e: all `docs(zangetsu/ascension-phase-*)` — NO code dependency
- → hard reset path is technically viable; REVERT path is safer and preferred

**Config rollback** (for env-var defaults):
- If any environment has `ALPHA_ENTRY_THR=0.80` set explicitly (e.g., Alaya systemd drop-in), that env MUST be cleared to `0.95` OR unset before the reverted binary runs, otherwise split-brain (N1.3 Conflict 1) resumes. Verify with `systemctl show arena-* -p Environment` or `env | grep ALPHA_`.

## 4. What rollback reverts (DB state) — HIGH ATTENTION

### 4.1 SQL migration `v0.7.2.3_admission_duplicate_handling.sql`

- **Status**: applied before R2 (R2-N1 §4.1 VERIFIED).
- **Rollback stance**: do NOT roll back the SQL by default. It is not part of R2.
- **If needed** (only under T2 with j13 sign-off):
  ```bash
  docker exec -i deploy-postgres-1 psql -U zangetsu -d zangetsu \
    < /home/j13/claude-inbox/retros/zangetsu-recovery-program-v1/phase2/step1/rollback_v0.7.2.3.sql
  ```
  This drops `admitted_duplicate` from the CHECK constraint and restores pre-v0.7.2.3 `admission_validator()`. It also routes 95 existing `admitted_duplicate` rows back to `pending_validator_error`. The rollback file is tested (at authoring time), verified present at `/home/j13/claude-inbox/retros/zangetsu-recovery-program-v1/phase2/step1/rollback_v0.7.2.3.sql`.

### 4.2 Hidden DB mutation by R2-N3 re-enqueue — CRITICAL

During the 2h G2 observation window, 89 rows in `champion_pipeline_fresh` were re-enqueued from `status='ARENA2_REJECTED'` to `status='ARENA1_COMPLETE'` via UPDATE (Gemini C1 pre-review VERIFIED path). They were subsequently re-rejected at A2 with updated `pos_count=0` pipeline_errors entries AND the `updated_at` timestamp advanced.

**Rollback SHA 480976c1 does NOT undo this UPDATE trail.** The 89 rows today carry status=`ARENA2_REJECTED` (observed post-G2) but their `updated_at` column reflects the 2h window's mutation, not the pre-R2 snapshot.

**If operator wants full pre-R2 DB state restoration** (rare — usually rollback is code-only):

```sql
-- Explicit: restore 89 rows to pre-R2-N3 timestamps IF j13 requires bit-exact replay.
-- Use only if DB is the comparison ground truth (e.g., for forensic signal-sign bug investigation).
-- Template; specific timestamps recovered from R2-N1-BEFORE-SNAPSHOT + pipeline_audit_log.

-- Step 1: inspect current vs pre-R2 updated_at
SELECT champion_id, status, updated_at FROM champion_pipeline_fresh
  WHERE updated_at > '2026-04-22 17:52:00Z' ORDER BY updated_at;

-- Step 2 (SKIP unless explicitly authorized): manual restoration only via j13-approved stored procedure.
--   NOTE: ad-hoc UPDATE to champion_pipeline_fresh.updated_at is BANNED under §17 non-negotiable rule 1.
--   If timestamp restoration is required, it must go through admission_validator() or a new approved path.
```

### 4.3 `pipeline_audit_log` / `pipeline_errors`

- R2-N3/N4 window produced ~416 engine.jsonl reject lines parsed + written into `pipeline_errors` (per G2-FAIL §6.1).
- These rows are **append-only evidence of what happened**. Do NOT delete. They are the diagnostic record that makes R2's honesty visible.
- If rolling back code, keep these rows; annotate a marker row `'R2_ROLLBACK_MARKER'` at rollback time.

### 4.4 `/tmp/calcifer_deploy_block.json`

- RED during R2 window. No rollback action — file is state-derived, will update on next Calcifer poll based on reverted pipeline behavior.

## 5. What rollback reverts (workers)

- Stop current arena (already stopped by Phase A).
- Do NOT restart workers automatically after code rollback. The restart path is governed by `r2_patch_validation_plan.md` §2 (needs Trigger A/B/C).
- If restart IS intended post-rollback under Trigger T2, follow `r2_patch_validation_plan.md` §3 fully — pre-R2 code must pass the same smoke + first-round + recovery-candidate phases.

## 6. Reversibility analysis

| R2 component | Reversible? | Notes |
|---|---|---|
| Threshold env defaults (0.95/0.65) | YES | Trivial — code revert |
| CD-14 hard-fail on missing holdout | YES | Trivial — code revert; data_cache loader will stop populating holdout |
| data_cache train+holdout split | YES | Loader code revert; no DB schema change |
| ARENA2_REJECTED passport patch string | YES | Not consumed anywhere critical; cosmetic |
| Round-log reject-reason counters (per-10-round) | YES | Pure logging; zero downstream consumers VERIFIED |
| 89 rows' `updated_at` advance | NO (see §4.2) | Audit-log evidence, not restored |
| `pipeline_errors` append | NO (see §4.3) | Audit evidence, kept |

**Overall reversibility**: code is fully reversible; DB audit trail is append-only by design. A "rollback" restores the code path but not the DB audit. This is a FEATURE, not a bug — §17's non-negotiable rule 1 forbids silent mutation of audit trails.

## 7. Go / No-Go decision matrix

| Scenario | Code rollback? | SQL rollback? | DB timestamp rollback? |
|---|---|---|---|
| Standard revert under T1 (R2 defect) | YES | NO | NO |
| D1 comparison window under T2 | YES (temporary) | NO | NO |
| Ascension supersession under T3 | NO (superseded, not reverted) | NO | NO |
| j13 explicit forensic request | depends on reason | NO (default) | NO (§17 forbids manual UPDATE to audit cols) |

## 8. Current verdict (2026-04-23)

- **T1 (R2 defect)**: NOT TRIGGERED. R2 mechanically correct per R2-N2 §31–37 + G2-FAIL §4.1.
- **T2 (D1 comparison needs pre-R2 baseline)**: NOT YET TRIGGERED. D1 has not requested it; if it does, rollback is temporary and bounded.
- **T3 (Ascension supersession)**: FUTURE. Months out.

**DO NOT rollback today.** R2 is the honest state.

## 9. Rollback rehearsal (VERIFIED in R2-N1 plan)

The rollback path was pre-rehearsed in R2-N1 §6.1 before R2 went live. It uses commit SHA `480976c18a94967ab8b467eddc29c7317faffe0e` as the tested anchor. The rehearsal confirmed:
- `git reset --hard 480976c1` returns `services/*.py` to pre-R2 content bit-exact.
- `zangetsu_ctl.sh restart` lifecycle works on the reverted tree.
- §17.6 stale-check would hard-fail unless workers restart post-revert.

## 10. Q1 for this contract

| Dim | Assertion | Verdict |
|---|---|---|
| Input boundary | covers T1/T2/T3 + §4.1/4.2/4.3/4.4 DB asymmetries | PASS |
| Silent failure | §4.2 explicit HIGH-ATTENTION for hidden DB mutation (Ch-4 from r2_recovery_review §6.1) | PASS |
| External dep | rollback SQL path checked `ls /home/j13/claude-inbox/retros/…/rollback_v0.7.2.3.sql` pre-contract | PASS |
| Concurrency | workers already stopped (Phase A); restart path governed by validation plan, not this contract | PASS |
| Scope creep | no code written, no rollback executed | PASS |
