# Zangetsu — Production Safety Contract

**Program:** Zangetsu Engine Ascension v1
**Phase:** 0
**Date:** 2026-04-23
**Author:** Claude Lead
**Status:** BINDING — once approved by j13, violations must be flagged before any such action is taken.

---

## §0 — Precedence

1. Ascension non-negotiable rules (Ascension spec §4) override everything below.
2. Charter §17 constitution rules (CLAUDE.md §17.1–17.8) override everything below §0.
3. This contract refines both into per-operation rules.

---

## §1 — FORBIDDEN actions (must never occur without explicit j13 override)

- **F1** Silent production mutation of any shared DB table / file / service state. ("Silent" = without docs/decisions/YYYYMMDD-*.md + Q1 audit + commit message naming it.)
- **F2** Threshold or gate change outside `services/` or `config/` without ADR + before/after evidence + shadow validation + explicit disclosure in commit body.
- **F3** Direct INSERT/UPDATE into `champion_pipeline_fresh` bypassing `admission_validator`. (v0.7.1 governance rule.)
- **F4** Direct SELECT/FROM on bare `champion_pipeline` except by files on the `verify_no_archive_reads.sh` whitelist (seed / alpha_discovery / factor_zoo / rescan / verify).
- **F5** `feat(zangetsu/vX.X)` commit while Calcifer deploy block is RED (§17.3) — enforced by pre-receive hook.
- **F6** `feat(zangetsu/vX.X)` commit authored by any path other than `bin/bump_version.py` (§17.5).
- **F7** `git reset --hard` on main / `git push --force` to shared branches / `git clean -f` in engine dirs — any of these unless j13 explicitly authorises with scope.
- **F8** Service restart (`zangetsu_ctl.sh restart`) without first running §17.6 stale-service check pre-flight.
- **F9** Destructive command via `@macmini13bot` without the `/confirm` owner-fresh 2-step token flow.
- **F10** Commit that drops tests (`tests/`) without a passing replacement and an ADR explaining why.
- **F11** Addition of a black-box component without a wrapper contract (Ascension §3.6: input/output/config/state/health/version/failure/rollback schema all required).
- **F12** Efficiency optimization that changes scientific semantics without explicit disclosure + before/after IC/PnL delta evidence.
- **F13** Performance claim without an evidence file (benchmark run, JSONL output, or measurable metric).
- **F14** Hidden agent disagreement — if Claude / Gemini / Codex diverge, the disagreement MUST be logged in `docs/decisions/YYYYMMDD-disagreement-*.md` and escalated to j13.
- **F15** Silent rollout of a modularization that hides (rather than reveals) scientific drift.
- **F16** (added v2 per Gemini §C.1) Unbounded flush / retry loop that can DoS the DB, AKASHA, or Telegram. Any producer writing to `engine_telemetry`, `pipeline_audit_log`, AKASHA `/memory`, or Telegram at > 50 calls / minute sustained must have an explicit rate-limit + circuit-breaker + dropped-on-overflow policy. Unbounded writes with no backpressure are FORBIDDEN.
- **F17** (added v2 per Gemini §C.2) Silent high-frequency retry on failed external POST. Any failing POST to AKASHA / Telegram / Claude Inbox must have (a) exponential backoff with upper bound, (b) max-attempts cap, (c) dead-letter path. Retry storms (>10 attempts in 60s) are FORBIDDEN.
- **F18** (added v2 per Gemini §D.3) Silent replacement of `admission_validator` PL/pgSQL body without migration + ADR + hash attestation in the v0.7.2.X+ migration file.
- **F19** (added v2 per Gemini §A.3) Direct `docker exec deploy-postgres-1 psql -c 'UPDATE/INSERT/DELETE …'` outside an approved migration path. Ad-hoc operator SQL inside the container MUST go through a named migration file with rollback, committed to git before execution.
- **F20** (added v2 per Gemini §A.1) Unsupervised call to AKASHA `POST /compact`. This endpoint is currently ungated and may delete chunks globally. Any `/compact` invocation requires explicit owner sign-off + pre-flight chunk-count snapshot.
- **F21** (added v2 per Gemini §D.1) TOCTOU bypass of `/tmp/calcifer_deploy_block.json`. The block file alone is insufficient; version-bump gate should also consume a signed nonce from Calcifer that is invalidated on any state change. Until such a nonce exists, this rule stands as a known gap — any agent noticing block-file deletion within 60s of a `feat(/v` commit attempt MUST alert.

---

## §2 — GATED actions (allowed only with the specific gate)

| Action | Required gate(s) | Where enforced |
|---|---|---|
| `feat(zangetsu/vX.X)` version bump | (a) Calcifer GREEN, (b) `bin/bump_version.py` with pre-flight checks, (c) matching ADR dated same day | pre-commit + CI (§17.7) |
| Hotfix (non-version-bump): `fix(…)` | Adversarial review by Gemini OR Q1 self-audit, + commit message explains risk + rollback | human discipline |
| Edit `services/` in prod | (1) Isolated worktree or branch; (2) ff-merge to main; (3) §17.6 stale-check post-restart; (4) ADR file MUST exist and have `YYYYMMDD` matching commit date (not just linked — presence + date verified by pre-commit); (5) ADR body ≥ 400 bytes (no placeholder stubs) | §17.6 hook + strengthened §17.7 CI |
| Edit `~/.claude/hooks/*.sh` or `.plist` (added v2) | (1) Integrity hash in `.claude/hooks/.integrity` updated same commit; (2) Gemini review of the diff; (3) ADR documenting what behavior changed | manual discipline + future integrity check |
| Run AKASHA `POST /compact` (added v2 per F20) | Explicit owner command; pre-flight chunk count snapshot; post-compact chunk count delta reported | manual |
| `docker exec deploy-postgres-1 psql` for admin work (added v2 per F19) | Only via named migration file in repo; rollback file paired; ADR dated same day | code review |
| Schema migration | SQL file pair: `vX.Y.Z_*.sql` + `rollback_*.sql`. Idempotent. Live verify in state-of-truth before next task. | manual discipline |
| Manual seed / reseed | `admission_validator` trigger; `--i-know-deprecated-v071` flag if legacy | code guard |
| Reaping stuck rows | `zangetsu_ctl.sh reap` with `--dry-run` first | ctl script |
| Writing to `champion_pipeline_fresh.status` | Only via orchestrator `release_champion` code path OR explicit `--reenqueue` SQL review | §17.7 ADR |
| Restart workers | §17.6 stale-check must PASS on all restarted services | hook |
| Writing to `/tmp/calcifer_deploy_block.json` | Only Calcifer daemon itself. Manual override by `/unblock` telegram command from j13. | Calcifer daemon |
| Publishing to Telegram | Only via `calcifer/notifier.py::notify_telegram()` or documented alert hooks | shared infra |
| Destructive miniapp shortcut | Owner-fresh (1h) + 2-step confirm_token + owner whitelist | `require_owner_fresh` + `_confirm_tokens` |
| AKASHA `/memory` write | Independent from the committing agent (§17.2 mandatory witness) for version bumps | AKASHA API + audit |

---

## §3 — FREE actions (no gate beyond normal discipline)

- Read-only SQL queries (SELECT …) on any table including archive.
- Reading parquet / JSONL / markdown files under repo.
- Running `gemini`, `codex`, `markl`, `calcifer` CLIs for analysis.
- Writing to `.claude/scratch/`, `docs/` (including decisions / retros / ascension).
- Writing to non-production paths under `/tmp/claude-*`, `/tmp/zangetsu-r2-*`.
- Shadow worktree creation under `/tmp/` (with LFS awareness — see `R2-N2-REPORT.md` §"Adversarial findings").
- Creating new markdown/yaml files anywhere in `docs/` with clear scope.
- `pytest` execution on test-only code paths (no DB writes).
- Reading `engine.jsonl`, `zangetsu_live.json`, calcifer log.
- Probe-style SNR / audit scripts that run read-only on parquet data.

---

## §4 — Required evidence for Ascension actions

Per Ascension §4 rule "All conclusions must be labeled":

| Claim type | Minimum evidence |
|---|---|
| "This is how it works today" | Cite `state_of_truth.md` section OR pg_proc function body OR services/ file:line + commit SHA |
| "This change is safe" | Q1 5-dim pass + rollback path + before/after metrics (VIEW / file / engine.jsonl) |
| "This mutation is reversible" | Rollback command or migration pair + tested on a worktree or shadow DB |
| "This optimization preserves semantics" | Before/after evidence file at `docs/decisions/YYYYMMDD-*.md` OR `results/*/final_report.md` |
| "No edge at 60-bar" | ≥ 3 independent probe sources (e.g. LGBM + GP + archive replay + D1 SNR sweep) |
| "Module is complete" | Ascension §3.4 checklist: inputs / outputs / config / state / metrics / errors / rollback / test / replacement boundaries all documented |

Every claim in a decision doc or PR body must carry one of the 4 labels: **VERIFIED**, **PROBABLE**, **INCONCLUSIVE**, **DISPROVEN**.

---

## §5 — Agent decision rights (Ascension §12)

| Decision | Who decides |
|---|---|
| Architecture / module boundaries | Claude Lead after integrating Gemini / Codex |
| Adversarial blocker ("this change is not safe") | Gemini (veto power on safety) |
| Implementation specifics (code / SQL / tests) | Codex under Claude Lead scope |
| Go / no-go on production apply | Claude Lead + j13 final |
| Rollback trigger in observation window | j13 (per R2-N4 "NO auto-revert" rule) |
| Declaring a phase complete | Claude Lead after evidence checks; Gemini may contest |
| Closing a disagreement | j13 after reading the disagreement memo |

All unresolved disagreements escalate to j13 **with a written memo**, not verbally.

---

## §6 — Rollback expectations

Every mutation-class action MUST document:
1. Pre-mutation snapshot path / SHA
2. Rollback command (single line if possible)
3. Blast radius (per `mutation_surface_map.md` classification)
4. Expected reversibility time (< 1 min for code / config ff-merge; < 5 min for schema; < 15 min for workers)

Examples already in-hand:
- R2-N2: `git reset --hard 480976c1 && bash zangetsu_ctl.sh restart` — tested, ready.
- v0.7.2.3 SQL: `rollback_v0.7.2.3.sql` — ready.
- Any future migration: must pair with rollback SQL in same step0/step1 layout.

---

## §7 — Stop conditions (per Ascension §13)

STOP and escalate to j13 immediately if:
- An action is proposed that mutates production silently
- A threshold / gate change is proposed without disclosure
- An optimization claims perf gain by changing semantics without ADR
- A modularization proposal HIDES drift rather than clarifying it
- A black-box component is proposed without wrapper contract
- A fix is proposed without validation path
- A migration is proposed without rollback path

---

## §8 — Concrete "this means"

For day-to-day operation while this contract is in force:

- **If you (any agent) want to edit `services/*.py`**: create branch → apply → commit `fix(...)` → ff-merge → §17.6 check → ADR. If Calcifer RED, must not emit `feat(…)`.
- **If you want to DELETE a row from fresh**: STOP. File ADR stating why + blast radius. Wait for j13.
- **If you want to change an env default**: SEARCH first — scattered-config map (Phase 1 output). Change in the canonical location only. ADR.
- **If you want to introduce a new worker**: must include pidlock, FOR UPDATE SKIP LOCKED for DB reads/writes, release_champion on exit path. Write module contract (Ascension §3.4 checklist).
- **If a live worker behaves oddly**: read engine.jsonl → check Calcifer block → check reap_expired_leases → ONLY THEN consider intervention. Intervention requires owner-fresh equivalent (j13 sign-off).
- **If you want to commit while Calcifer RED**: `fix(…)` / `docs(…)` / `chore(…)` are OK (not feat/vN). Any `feat(…)` without vN is OK so long as it doesn't match the CI regex `^feat\([^)]+/v`.

---

## §9 — Contract maintenance

This contract is updated only by ADR at `docs/decisions/YYYYMMDD-safety-contract-*.md`. Updates require:
- Motivation
- Diff vs previous version
- Adversarial review
- Q1 5-dim self-audit
- j13 approval

Version history:
- v1 — 2026-04-23 initial
- v2 — 2026-04-23 Gemini adversarial integration: added F16 (telemetry spam), F17 (retry bombs), F18 (validator body swap), F19 (docker psql bypass), F20 (AKASHA compact), F21 (TOCTOU block file). Tightened §2 GATED rules for services/ edits (ADR presence + size check), added hook/plist + /compact + docker psql gate rows.

## §10 — POST-violation detection (added v2 per Gemini §D.4)

Pre-execution gates are insufficient. The following DETECTION mechanisms must be added in Phase 6 (observability) or Phase 7 (patch queue):

| Rule | Detection signal | Cadence |
|---|---|---|
| BL-F-003 (direct fresh INSERT) | Periodic reconciliation: count fresh rows where `admitted_at` is NULL or missing staging predecessor | every 5 min |
| BL-F-005 (feat/vN + Calcifer RED) | Post-commit CI scan: for each pushed commit matching `^feat\([^)]+/v`, verify block file state at commit-ts was GREEN (requires Calcifer log retention) | per commit |
| BL-F-018 (validator body swap) | Periodic hash of `pg_proc.prosrc` for `admission_validator`, compared to expected SHA from migration file | every 10 min |
| BL-F-016 (telemetry spam) | Row-count delta on `engine_telemetry` and `pipeline_audit_log`: alert if > 10,000 rows / min | continuous |
| BL-F-017 (retry bombs) | Structured-log scan: alert on same `error_code` appearing > 50 times in 60s from same `service` | continuous |
| HOOK-001/002 integrity | SHA-256 comparison with `.claude/hooks/.integrity` | on every shell / CLI launch |
| File producer freshness (XPD-001/002) | Compare writer mtime to expected cadence; alert if writer silent > 2× cadence | per-file, minute cadence |
| DKR-001 ad-hoc docker exec | Enable `pg_stat_statements` + query-audit; alert on any DDL or DML from localhost outside known migration paths | continuous |
| EXT-003 AKASHA /compact | Before/after chunk count delta; alert if delta > 1000 without matching ADR | per-invocation |

Until these detectors exist, the contract is **PRE-only**. This is an acknowledged weakness (labeled DISPROVEN in `state_of_truth.md` §8).
