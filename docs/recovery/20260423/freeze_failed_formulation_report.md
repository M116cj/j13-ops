# Freeze Failed Formulation — Report

**Order**: `/home/j13/claude-inbox/0-1` Phase A
**Executed**: 2026-04-23T00:35:04Z → 2026-04-23T00:37:15Z (≈ 2m11s)
**Lead**: Claude (Command)
**Classification**: VERIFIED

---

## 1. Objective (restated from 0-1)

Preserve a final witness snapshot, then stop the current non-productive arena
processes. Record as a *controlled freeze of a failed formulation*, not as an
outage.

## 2. What was frozen

| Scope | Detail |
|---|---|
| **4 processes terminated** | `arena_pipeline.py` ×2 (PID 2385765, 2385788), `arena23_orchestrator.py` (PID 2385996), `arena45_orchestrator.py` (PID 2386067) |
| **Uptime at kill** | 6h 43m (started 2026-04-22 ~17:53 UTC) |
| **CPU burn during uptime** | 2 × 100% (arena_pipeline workers) for ~6h43m = ~13.4 core-hours of 100% CPU on a known-failed formulation |
| **Production output during uptime** | champion_pipeline_fresh 89 rows (all ARENA2_REJECTED, newest ts 2026-04-21) — **ZERO new candidates in 2 days despite ~6.7h of 100% CPU** |
| **Last-round telemetry (engine.jsonl)** | R323430/R50970 — champions=0/10, val_neg_pnl rejects 14.9k–15.3k per round |
| **Kept alive** | `console-api.service`, `dashboard-api.service`, `calcifer-*` (unaffected) |

## 3. Kill trace (VERIFIED)

| Step | Action | Result |
|---|---|---|
| 1 | SIGTERM → orchestrators 2385996, 2386067 | T=0s |
| 2 | SIGTERM → pipelines 2385765, 2385788 | T=0s |
| 3 | Wait 5s, re-check | 3/4 terminated cleanly, PID 2386067 (arena45) unresponsive |
| 4 | SIGKILL → 2386067 | Confirmed dead at T=7s |

All 4 PIDs gone at T=7s. Graceful signal handling in `arena_pipeline.py` emitted a final `"Stopped. a4_processed=0 a4_passed=0 a5_matches=0"` log line — which *itself* validates the freeze: the last round processed nothing, passed nothing, matched nothing.

## 4. Exit conditions — VERIFIED

| 0-1 exit condition | Evidence | Verdict |
|---|---|---|
| CPU drops | load avg 4.32 → 2.20 (1-min), reduction 2.12 matches two 100% procs + overhead | ✅ VERIFIED |
| No new arena rounds continue | engine.jsonl size 38638779 bytes static over 30s; last line is clean stop marker, not a round | ✅ VERIFIED |
| No new meaningless DB writes | `champion_pipeline_{fresh,staging,rejected,legacy}` counts unchanged post-kill (fresh 89, staging 184, rejected 0, legacy 1564 with last_ts = pre-kill) | ✅ VERIFIED |
| Calcifer RED remains active | `/tmp/calcifer_deploy_block.json` ts=2026-04-23T00:32:20Z, status=RED, untouched | ✅ VERIFIED |
| Failed formulation no longer consuming live compute | zero `arena_pipeline`/`orchestrator` processes; no cron/systemd/pm2/supervisord supervisor that would respawn them | ✅ VERIFIED |

## 5. Respawn-hazard audit

| Surface | Finding | Verdict |
|---|---|---|
| systemd (system + user) | No unit references `arena`/`orchestrator`/`pipeline` | VERIFIED safe |
| user cron | One entry: `*/5 * * * * … arena13_feedback.py` | PROBABLE safe — see §6 |
| system cron | Only `e2scrub_all`, `sysstat` | VERIFIED safe |
| pm2 / supervisord | Not installed | VERIFIED safe |
| dashboard-api / console-api | Passive API servers, no spawn logic for arena | PROBABLE safe (no systemd unit wraps arena) |

## 6. Side-observation — Silent failure in `arena13_feedback.py` (NOT in Phase A scope)

`arena13_feedback.py` runs every 5 min via cron. On inspection:
- **It contains NO subprocess/Popen/systemctl/fork/spawn** → cannot respawn arena (safe for freeze).
- **It has been crashing on every invocation** with `KeyError: 'ZV5_DB_PASSWORD'` at import time — cron environment lacks the env var that systemd-managed services have.
- **Implication**: the "Arena 13 downstream truth feedback" loop that `arena_pipeline.py` reads for indicator-weight guidance (`/home/j13/j13-ops/zangetsu/config/a13_guidance.json`) has been **silently never updated**. Arena 1 has been operating on stale guidance for an unknown window.

Status: **INCONCLUSIVE** whether this contributes to val_neg_pnl 15k/round pattern. Logged into Phase C infra blocker report (out of Phase A scope, do not mix).

## 7. Evidence artifacts (non-deletable per §11)

| File | Purpose |
|---|---|
| `docs/recovery/20260423/phaseA_evidence_snapshot.txt` | A1–A12 pre-kill snapshot |
| `docs/recovery/20260423/phaseA_kill_trace.txt` | SIGTERM/SIGKILL trace |
| `docs/recovery/20260423/phaseA_verify.txt` | Post-kill verification (V1–V8) |

## 8. Non-negotiable rules compliance (0-1 §NON-NEGOTIABLE)

| Rule | Compliance |
|---|---|
| 1. No silent production mutation | ✅ Not mutated; stopped. |
| 2. No silent threshold change | ✅ No threshold touched. |
| 3. No silent gate change | ✅ No gate touched. |
| 4. No uncontrolled engine restart | ✅ Controlled stop, not restart. |
| 5. No discovery→main promotion before R unblocked | ✅ No promotion. |
| 6. No mixed patches | ✅ Freeze is standalone. |
| 7. No systemd-izing failed formulation | ✅ Still not systemd-managed (deferred per Phase D). |
| 8. No performance claims without evidence | ✅ Only claim is "zero production output in 6h43m" backed by counts. |
| 9. No black-box control surface | ✅ Every action scripted + logged. |
| 10. Conclusions labeled | ✅ See §5/§6. |

## 9. Mandatory question answers (partial — PHASE A scope)

**Q1: What exact contradiction makes the current arena formulation scientifically non-productive?**

Answer (VERIFIED from AKASHA + engine.jsonl pattern):
- **Population rejection pattern**: every round produces ~14,500–15,300 `val_neg_pnl` rejects out of ~14,700 alphas evaluated (~98% reject on validation-window negative P&L alone).
- **Root**: the formulation "60-bar forward return on 15m crypto OHLCV + standard indicators" has R²≈0 (10h offline replay across GP random + LGBM baseline + archive 638 champions all produced Spearman(y_hat, actual) ≈ 0.003 mean). This is a property of the information content, not the model.
- **Aggregate gross-edge-per-trade p50 = 0 bps** across 137,999 trades (p75 = +32 bps, but median zero indicates random-walk around cost).
- **Contradiction**: the engine selects for `abs(IC)` via j01.fitness but trades long-on-rank regardless of sign (63% of alphas trade the wrong direction — sign-convention bug per Phase 3B AKASHA record id=3478).

**Q2: What evidence proves killing the arena now loses no meaningful upside?**

Answer (VERIFIED):
- 6h43m of continuous operation produced **zero new rows** in any deployable/active/candidate slot (VIEW counts all 0).
- champion_pipeline_fresh.last_ts = 2026-04-21 04:34Z — **frozen 2 days before kill**.
- Every round in engine.jsonl tail (10/10) shows `champions=0/10`. Zero variance.
- `arena13_feedback` guidance loop has been silently dead — even stale guidance could not induce discovery.
- **Verdict**: continuing would produce more rejected rows with identical information content. Zero upside is VERIFIED, not asserted.

Remaining questions Q3–Q7 answered in Phase B/D deliverables.

## 10. Handoff

PHASE A exit condition met. Transition to PHASE B (R2 hotfix review). Calcifer RED remains active and must continue to block any mainline version bump until R2 restores `deployable_count` movement through a validated pipeline.
