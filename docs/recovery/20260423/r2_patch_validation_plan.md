# R2 Patch Validation Plan

**Order**: `/home/j13/claude-inbox/0-1` Phase B action 4
**Produced**: 2026-04-23T00:55Z
**Lead**: Claude
**Scope**: defines the validation protocol any future re-activation of arena must pass; records the validation already performed on bd91face during the G2 window.

---

## 1. Current state (RECORDED)

- R2 commit `bd91face` is on main. Production workers were **running R2 code** from 2026-04-22T17:52:30Z through kill at 2026-04-23T00:35:57Z (≈6h43m of live operation).
- Workers are now **stopped** (Phase A). No arena is currently consuming data.
- `zangetsu_status` VIEW values unchanged post-kill.
- Calcifer RED active.

**Implication**: no further validation of R2 itself is needed *today*. This plan governs what must pass **before arena is re-activated** (post-D1 diagnosis, post-Ascension migration, or with a new target formulation).

## 2. When to re-activate arena (gate — three disjunctive triggers)

Arena re-start is BLOCKED unless at least ONE of the following is true:

- **Trigger-A: D1 upstream audit identifies a discrete fixable bug** (sign convention, data-quality, holdout-window mismatch, horizon mismatch) AND the fix is in its own `fix(zangetsu/<bug>)` commit with Phase B-equivalent documentation.
- **Trigger-B: Ascension Phase 3 (Defect Seizure) produces a modular engine** whose control-plane contract has been reviewed and accepted, AND the first module to go live is the Arena 1/2 replacement with new OOS gate semantics.
- **Trigger-C: j13 explicit override** under §17.3 — Telegram `/unblock` with written rationale in `docs/decisions/YYYYMMDD-arena-reactivation-override.md`.

No other path. No "let's just run it for another 24h to see" — disproven (r2_recovery_review §6.1-Ch3).

## 3. Validation protocol — mandatory for ANY arena restart

### 3.1 Pre-restart (Phase 0)

| Step | Action | Acceptance | Fail-action |
|---|---|---|---|
| 0.1 | Capture `zangetsu_status` VIEW | current_state vs recorded snapshot | if drift >0 investigate before restart |
| 0.2 | Capture `champion_pipeline_{fresh,staging,rejected,legacy}` counts + status histogram | match R2-N1-BEFORE + this freeze snapshot | flag any mutation and re-run from Phase A capture |
| 0.3 | Verify HEAD SHA contains R2 fix | `grep 'ENTRY_THR.*0.80' services/arena_pipeline.py` returns match AND `grep 'CD-14' services/arena23_orchestrator.py` returns ≥5 matches | block restart; re-apply R2 |
| 0.4 | Verify `/tmp/calcifer_deploy_block.json` is GREEN or explicit-override | `.status != "RED"` OR `/unblock` decision record dated today | block restart |
| 0.5 | Confirm no uncommitted changes in `zangetsu/services/` | `git -C j13-ops status zangetsu/services/` clean | commit or stash before restart |
| 0.6 | Re-read `docs/decisions/20260422-alpha-os-2.0-charter.md` §2.2 | operator acknowledges which hypothesis the restart tests | block if operator cannot state hypothesis |

### 3.2 Smoke phase (Phase 1 — T+0 to T+5min)

Expected smoke log on launch (from R2-N2 §53–57, use as template):

```
Loaded <SYM>: train=<N> + holdout=<M> bars (70%/30% of <T>)
...
Data loaded: 14 symbols (holdout split only, factor-enriched)
Data cache: 14 symbols loaded (train split only, factor-enriched)
Service loop started
```

**Hard-fail conditions** (any → kill within 60s):
- Missing `holdout` partitioning log line → CD-14 load path broken.
- `data_cache: 14 symbols` count off → data-loader regression.
- Any `Traceback` in first 60s → crash loop.
- §17.6 stale-check: `systemctl show --value ActiveEnterTimestamp` < source mtime for any restarted worker → STALE failure.

### 3.3 First-round phase (Phase 2 — T+5min to T+30min)

**Expected** (based on R2 window observed values):
- First round complete in 13–16s per symbol×regime combo.
- Per-round log emits full reject histogram: `rejects: few_trades=X val_few=Y val_neg_pnl=Z val_sharpe=W val_wr=V`.
- `few_trades_ratio` < 5% (holdout window should produce ≥25 trades for most alphas).

**Soft-fail (investigate; may continue)**:
- `few_trades_ratio` > 30% — suggests holdout window too narrow for this target; flag for Phase D1 review.
- `val_neg_pnl` > 98% of rejects — matches R2 window pattern; EXPECTED if formulation unchanged; HARD-FAIL if formulation was supposed to be fixed.

### 3.4 Recovery-candidate phase (Phase 3 — T+30min to T+2h)

Charter G2 recovery criteria (≥2/4 must move):

| Criterion | Target | R2 window baseline | Post-fix-restart acceptance |
|---|---|---|---|
| `deployable_count` persistent >0 | >0 | 0/120min | ≥1 sustained 30min |
| fresh % ARENA2_REJECTED | <100% | 100% (89/89) | <80% |
| `champions_last_1h` | >0 | 0 | ≥1 |
| `last_live_at_age_h` | interpretable | NULL | non-NULL |

**If 0/4 move in 2h** → same G2 FAIL pattern as R2 → restart was diagnostic-only, **do not claim success**, write a new G2-FAIL-style verdict.

**If 2+/4 move in 2h** → G2 PROBABLE PASS → continue observation 24h before declaring recovery.

**If 1/4 moves** → INCONCLUSIVE → extend observation 4–8h.

### 3.5 Stability phase (Phase 4 — T+2h to T+24h)

Only entered if Phase 3 passes. Continuous monitoring for:
- `a2_pass_rate` trend (should stabilize >5%, ideally >15% — noise-fitting signature >30% per Gemini pre-review — investigate if exceeded)
- `a4_processed / a5_matches` ratio drift
- DB table growth sanity (no runaway writes)
- §17.4 auto-regression watchdog does not fire (deployable_count does not drop back to 0; last_live_at_age_h does not exceed 12h)

### 3.6 Mainline graduation (Phase 5 — after T+24h)

Mainline consideration requires ALL of:
- 24h+ observation with ≥2 G2 criteria holding
- At least one `deployable_live_proven > 0` (paper-trade or live-fill confirmed)
- Decision record `docs/decisions/YYYYMMDD-arena-restart-validation.md`
- Retrospective `docs/retros/YYYYMMDD.md` (required by §17.7 if `/team` was used)
- AKASHA witness record per §17.2
- `bin/bump_version.py` auto-emits `feat(zangetsu/vX.Y)` — NO human-written version commits (§17.5)

## 4. Before/After evidence schema (mandatory for every restart)

A restart that does not produce ALL of the following in `docs/recovery/YYYYMMDD/` is not a valid restart:

| Artifact | Contents | Reference template |
|---|---|---|
| `phaseA_evidence_snapshot.txt` | VIEW, counts, git SHA, Calcifer state pre-restart | this freeze's `phaseA_evidence_snapshot.txt` |
| `smoke_log_<timestamp>.txt` | first 5min of engine.jsonl | R2-N2 §52–58 |
| `phase2_first_rounds.json` | first 30min of per-round reject histograms | new format — schema: `{ts, round_id, symbol, regime, champions, rejects:{few_trades,val_few,val_neg_pnl,val_sharpe,val_wr}}` |
| `phase3_recovery_trajectory.jsonl` | 2h @ 5min poll of G2 criteria | R2-N4-observation-log.jsonl |
| `phase4_stability_trace.jsonl` | 24h @ 15min poll | new — extends phase3 format |
| `validation_verdict.md` | Q1 5-dim check, pass/fail per phase, consequences | R2 phase2/G2-FAIL-verdict.md |

## 5. Shadow/staged validation option

If operator wants to test a restart without mutating live DB:

### 5.1 Staged mode (VERIFIED safe pattern — R2-N2 used a near-variant)

1. Create worktree branch `test/arena-restart-<yyyymmdd>` (avoid LFS materialization — use same-branch direct approach per R2-N2 §83).
2. Launch workers with `ZV5_READONLY=1` (assert: workers only run `SELECT`, no `INSERT/UPDATE/DELETE`). If env-flag not implemented, add minimal hook before restart.
3. Run 30min smoke.
4. Compare produced round logs against live-mode baseline.
5. Tear down worktree; **no DB delta** should exist.

### 5.2 Shadow mode (NOT YET IMPLEMENTED — deferred)

True shadow would require: duplicate DB, replay realtime data into shadow, zero writes to prod DB. Today Zangetsu does not have an isolated shadow DB. Adding one is Phase D/E Ascension work (new control-plane module). **Do not attempt shadow mode today.**

## 6. What R2 window validation already PROVED (retrospective)

Already-executed validation of bd91face during 2026-04-22T17:52→19:56Z:

- R2-N2 §31–37: `git apply --check` + `ast.parse` + grep ENTRY_THR + grep CD-14 + services mtime + §17.6 FRESH across 6 PIDs.
- R2-N2 §51–58: smoke log confirmed CD-14 holdout split active + 14 symbols loaded.
- R2-N4-observation-log.jsonl: 25 polls × 5min, full G2 criteria tracking, 2h watchdog deadline hit with 3 alert gates evaluated.
- G2-FAIL-verdict.md §4.1: R2-N2 patches applied correctly, holdout active, §17.6 FRESH verified, re-enqueue via UPDATE not INSERT (Gemini C1 verified).

**Verdict on R2 itself**: patch is VALIDATED as correctly-applied and mechanically-sound. The G2 FAIL is on the UNDERLYING FORMULATION, not on R2. R2 does what R2 said it would.

## 7. Non-negotiable rules compliance

| 0-1 rule | Plan compliance |
|---|---|
| No silent production mutation | §3 pre-restart gates + §4 artifacts prevent silent mutation |
| No silent threshold change | §3.1 step 0.3 verifies thresholds against decision record |
| No silent gate change | §3.2 smoke log asserts CD-14 presence |
| No uncontrolled engine restart | §2 triggers + §3 protocol make "uncontrolled" impossible |
| No discovery into main before Track R cleared | §2 Trigger-A requires discrete bug fix, not discovery payload |
| No mixed patches | §3.1 step 0.5 blocks uncommitted services/ |
| No systemd-izing failed formulation | §5 systemd deferral memo controls; this plan doesn't change it |
| No perf claims without evidence | §4 mandatory artifacts |
| No black-box | every criterion has a tool-verified acceptance |
| Labels applied | §3/§4/§6 all use VERIFIED/PROBABLE/INCONCLUSIVE/DISPROVEN |

## 8. Q1 for this plan

| Dim | Assertion | Verdict |
|---|---|---|
| Input boundary | covers 4 phases × 3 triggers × 6 artifacts | PASS |
| Silent failure | §4 artifacts force explicit output for every restart phase | PASS |
| External dep | AKASHA/Postgres/Calcifer states checked in §3.1 | PASS |
| Concurrency | §3.1 step 0.5 forces clean tree; §3.2 §17.6 FRESH check | PASS |
| Scope creep | explicitly defers shadow DB to Ascension; no code written | PASS |
