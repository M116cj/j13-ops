# Decision Memo — When Systemd Formalization of Arena is Allowed

**Order**: `/home/j13/claude-inbox/0-1` Phase D deliverable
**Produced**: 2026-04-23T01:38Z
**Author**: Claude (Lead)
**Charter reference**: Alpha OS 2.0 v3.1 §2.2 (do not keep optimizing a failed formulation) + §2.5 (no mixed patches) + Constitution §17.

---

## 1. Decision

**Arena processes (`arena_pipeline.py`, `arena23_orchestrator.py`, `arena45_orchestrator.py`) MUST NOT be placed under systemd management until ALL THREE conditions hold simultaneously.**

This memo is the single source of the gating rule. Any proposal to systemd-ize arena without satisfying all three conditions is rejected at doc-review time.

## 2. The three gating conditions (conjunctive)

### 2.1 **Condition-1: A valid recovery baseline exists**

Defined as: `zangetsu_status.deployable_count` has moved off zero via a VALID pipeline (not bypass) AND sustained for ≥24 hours AND `last_live_at_age_h` became interpretable (non-NULL).

VERIFIED by: `/tmp/calcifer_deploy_block.json` going GREEN AND staying GREEN for 24h AND `champion_pipeline_fresh` showing entries that reached `status='DEPLOYABLE'` or downstream.

This condition answers 0-1 non-negotiable rule #7: "No systemd-izing a known failed formulation."

### 2.2 **Condition-2: The formulation under which deployable_count moved is explicit**

Defined as: `docs/decisions/YYYYMMDD-<formulation-change>.md` exists recording which of H1–H6 was the active change when `deployable_count` moved. Acceptable values:

- H2 pset-primitive fix (D1-F)
- H4 signal-sign-convention fix (D1-C)
- H5 horizon pivot (D1-E)
- Ascension modular-engine replacement
- New target formulation (Charter §2.4 Target Gate)

NOT acceptable:
- "runs without code change" — implies either (a) market regime shift, which is not a systemd prerequisite because nothing has been verified to survive another regime shift, or (b) an invisible change somewhere (env var, data, timing) which violates §17 rule 1.

### 2.3 **Condition-3: A rollback-tested systemd unit definition passes review**

Defined as: `/etc/systemd/system/zangetsu-arena-*.service` drafted AND reviewed AND containing:

- `ExecStart=` with explicit path to the current-main-branch binary (not a worktree path).
- `EnvironmentFile=/home/j13/.env.global` OR explicit `Environment=` lines for all required vars (`ZV5_DB_PASSWORD`, `ALPHA_ENTRY_THR`, `ALPHA_EXIT_THR`, `TRAIN_SPLIT_RATIO`).
- `Restart=on-failure` with `StartLimitBurst=3` and `StartLimitIntervalSec=600` (no restart-storm).
- `RestartSec=30` minimum (not 0 — allow supervisor to observe failure).
- `TimeoutStopSec=60` (SIGTERM grace matching Phase A kill trace observation).
- `StandardOutput=append:/home/j13/j13-ops/zangetsu/logs/arena-<role>.jsonl` (no unbounded /tmp writes).
- A companion `.timer` unit if the process is episodic; absent if it's a daemon.

AND:

- Unit tested via `systemd-analyze verify` passes.
- Rollback plan present: `systemctl stop + disable + rm` sequence documented with expected side-effects.
- §17.6 stale-service-check template included.
- Gemini pre-review passed (Mandatory per CLAUDE.md §5).

## 3. What systemd-ization would DO today if conditions not met (the risk)

If arena goes under systemd in the current state (RED + G2 FAIL + no valid formulation):

1. **Auto-restart loop of known failure**: `Restart=on-failure` would respawn arena every time it exits, burning CPU on known-zero-edge formulation (Charter §2.2 violation amplified).
2. **Obscures diagnostic signals**: systemd-managed means the process appears "healthy" to monitoring even when producing 0% champions. The Phase A snapshot showed 6h43m of "running" that was really 0-output. Systemd would make that state invisible past 5min in `systemctl is-active`.
3. **Higher friction to kill**: Phase A was `kill -TERM` + one `kill -KILL`. Under systemd: `sudo systemctl stop` (requires privileges) + possibly `sudo systemctl disable` + possibly `sudo systemctl mask` to prevent autorestart. Adds rollback friction.
4. **Implies endorsement**: systemd-ization is socially read as "this is the canonical way to run arena" — misleading until recovery proof exists.

## 4. When to REVISIT this memo

Mandatory revisit triggers:

- Condition-1 AND Condition-2 both met → initiate Condition-3 draft.
- D1 audit identifies a concrete bug fix that, once applied, restores `deployable_count > 0` → this memo's conditions re-enter relevance.
- Ascension Phase 3 (Defect Seizure) produces a modular engine whose runtime lifecycle management differs from the current `services/arena*.py` pattern → this memo is superseded by Ascension's systemd plan.
- j13 explicit override via decision record `docs/decisions/YYYYMMDD-systemd-override.md` with written rationale + rollback plan. Override path exists, but uses it sparingly.

## 5. Interim replacement for the "I need reliable arena restart" use case

Until Conditions are met, if operator needs a reproducible arena restart path for D1 shadow testing:

- Use `zangetsu_ctl.sh` (already exists, not systemd-wrapped).
- `zangetsu_ctl.sh status` / `restart` / `stop` — scripted but manually-invoked.
- Add a `stop-for-good` mode that writes a breadcrumb `.arena_frozen_YYYYMMDD` so any reviewer knows the freeze is intentional.

This is the manual-but-disciplined path. Sufficient for the remaining Recovery + D1 phase.

## 6. Q1 adversarial for this memo

| Dim | Assertion | Verdict |
|---|---|---|
| Input boundary | Three conditions cover the shape (pipeline output + cause attribution + engineering correctness) of "is it safe to autorestart?" | PASS |
| Silent failure | §3.2 explicitly names the hide-failure-under-systemd-healthy risk | PASS |
| External dep | Condition-3 cross-refs `.env.global` from Binance-keys memory; if that file moves, memo is brittle | INCONCLUSIVE — reviewed, acceptable because §13 storage rule marks it stable |
| Concurrency | Restart-storm guard in Condition-3 addresses concurrency | PASS |
| Scope creep | Memo writes no code, creates no unit file, takes no action | PASS |

## 7. Non-negotiable rules compliance

All 10 rules of 0-1 are upheld by this memo because the memo is a **deferral rule**, not an action. The deferral is itself consistent with:
- Rule 4 (no uncontrolled engine restart) — we forbid autorestart until proof.
- Rule 5 (no discovery promoted before Track R cleared) — by blocking systemd, we prevent "we autorestarted our way to discovery" pattern.
- Rule 7 (no systemd-izing failed formulation) — this memo IS the implementation of Rule 7.
