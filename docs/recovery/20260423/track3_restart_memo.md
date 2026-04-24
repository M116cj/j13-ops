# Decision Memo — When Track 3 Discovery Can Restart

**Order**: `/home/j13/claude-inbox/0-1` Phase D/E deliverable
**Produced**: 2026-04-23T01:42Z
**Author**: Claude (Lead)
**Charter reference**: Alpha OS 2.0 v3.1 §Track 3 (Gated Discovery) + §2.4 (Target Gate → Feature Gate → Model Gate → Deployment Gate).

---

## 1. Decision

**Track 3 (Gated Discovery) restart is BLOCKED until at least ONE of three path-conditions is met and the corresponding prerequisites pass review.**

Restart is NOT about resuming GP search on the existing 60-bar forward-return target. That path is explicitly closed per Charter §2.2. Restart means **initiating the first D1 Tier-1 experiment on a NEW hypothesis**.

## 2. The three path-conditions (disjunctive — any one enables Track 3)

### 2.1 Path-A: D1 upstream audit identifies a discrete bug in evaluation code

Trigger: D1-C (signal-sign convention reject-pattern analysis) or D1-B (holdout-window reject-pattern) produces evidence (Spearman ≥ +0.15, or per-symbol signed reject counts showing asymmetry ≥2:1) that the existing code has a bug, not that the market lacks edge.

Prerequisite before Track 3 can restart:
- Bug fix is in its own `fix(zangetsu/<name>)` commit with Phase B-equivalent documentation (recovery review + validation plan + rollback contract).
- Commit passes mechanical review (Codex) + adversarial review (Gemini, when B7 fixed).
- Fix has Q1/Q2/Q3 pass.
- `r2_patch_validation_plan.md` §3 protocol executed fresh on the bug-fix restart.
- Only after bug-fix restart shows G2-style evidence (`deployable_count > 0` sustained) can Track 3 layer on top.

**Time cost**: 2-5 days from D1 result.

### 2.2 Path-B: New target formulation replaces 60-bar forward return

Trigger: Charter §2.4 Target Gate approves a replacement target candidate (explicit examples in Charter + AKASHA):
- Triple-barrier labeling
- Volatility-normalized return
- Regime-conditional prediction
- Different horizon (5-bar micro-structure requires tick data per 0-1 Phase D defer list)

Prerequisite before Track 3 can restart:
- Written Target Gate brief (`docs/decisions/YYYYMMDD-target-gate-<name>.md`) with:
  - Theoretical rationale for why this target is more predictable
  - Label construction code, reviewed (Gemini must)
  - Offline feasibility check showing non-zero information content over ≥1 historical regime
  - Evaluation protocol that does NOT reuse any data already consumed by the 60-bar effort (or explicit rationale for why reuse is acceptable)
- Feature Gate pass (OR explicit waiver with rationale if features are reused)
- Fresh arena code path (may reuse existing modules but MUST have explicit config surface per Charter §Ascension control-plane)

**Time cost**: 1-2 weeks for target change; 1-2 weeks additional if new features/data required.

### 2.3 Path-C: Ascension Phase 3 (Defect Seizure) replaces the execution core

Trigger: Ascension Phase 3 produces a modular engine kernel with explicit module boundaries per Charter §Ascension §target-layered-architecture 1-10. First module to go live is Arena 1/2 replacement.

Prerequisite before Track 3 can restart:
- Module boundary contracts reviewed (Gemini must)
- Control-plane interface review passed
- Migration plan shadow-tested on historical data
- Old `services/arena*.py` deprecated but retained as rollback target for ≥30 days after Track 3 first success on new modules

**Time cost**: 4-8 weeks.

## 3. What is permanently forbidden (independent of which path)

Per Charter §2.2 + 0-1 non-negotiable rules 5 and 7:

- Running ANY discovery work on the 60-bar forward-return target ON the 15m crypto OHLCV+indicator pset — formulation has been falsified across GP + LGBM + archive replay + R2 live. Retrying it is optimizing a known-failed formulation.
- Mixing Track R (recovery fix) with Track 3 (discovery experiment) in a single patch.
- Systemd-izing any arena variant before the systemd-deferral memo conditions clear.
- Using `/tmp` or working-tree config to bypass charter gates ("I'll just test it real quick").
- Promoting any discovery branch into `main` before its `docs/decisions/` + retro + validation trace exist.

## 4. Interim allowed work (Track-3-adjacent, explicitly NOT a restart)

These CAN proceed under current freeze without triggering Track 3:

- D1 audit scripts (read-only) in `/Users/a13/.claude/scratch/zangetsu-r2-20260423/d1_shadow/{a,b,c,d,e,f}.py` per G2-FAIL §8 deliverables.
- Offline analysis of existing `engine.jsonl` and `champion_pipeline_*` data.
- Writing new Target Gate briefs without executing.
- Ascension Phase 0-2 documents are complete; Phase 3 (implementation) can **plan** but not **run new arena code** until Track 3 gate clears.
- `tests/test_*_smoke.py` in sandbox without DB writes.

## 5. Trigger revisit conditions

Mandatory revisit:

- D1 Tier-1 result drops → re-evaluate Path-A.
- j13 approves a Target Gate brief → Path-B unlocks and this memo updates.
- Ascension Phase 3 starts → Path-C timeline added.
- 30 days elapse without any path progressing → retrospective required per §11.

## 6. Relationship to Calcifer RED

Track 3 restart does NOT clear Calcifer RED automatically. `deployable_count > 0` is the single truth (§17.1). Track 3 restart only enables the *possibility* of `deployable_count` moving — it does not satisfy §17.3.

Explicit: any Track 3 path can fire successfully and produce `deployable_count > 0` → RED clears → THEN `feat(zangetsu/vN)` is unblocked per §17.2 AKASHA witness requirement.

## 7. Q1 adversarial for this memo

| Dim | Assertion | Verdict |
|---|---|---|
| Input boundary | 3 disjunctive paths cover discrete bug / target change / structural change — spans the legitimate restart motivations | PASS |
| Silent failure | §3 enumerates forbidden patterns that would produce silent failure (un-documented formulation tweaks, etc.) | PASS |
| External dep | Path-B/C depend on j13 decisions (target approval, Ascension scheduling) — correctly external, no Claude-side side channel | PASS |
| Concurrency | §4 interim list explicitly separates read-only from executable work | PASS |
| Scope creep | This memo prescribes no code, schedules no work, requires no tool invocation | PASS |

## 8. Non-negotiable rules compliance

| 0-1 rule | Compliance |
|---|---|
| 5. No discovery promoted before Track R cleared | ENFORCED — this memo is the mechanism |
| 6. No mixed patches | §3 forbids |
| 10. Labels applied | §2/§3/§6 use VERIFIED/INCONCLUSIVE where relevant |

## 9. Current status (2026-04-23)

- **Path-A**: D1 Tier-1 scripts written (per G2-FAIL §8) but NOT executed. `/Users/a13/.claude/scratch/zangetsu-r2-20260423/d1_shadow/README.md` exists. Awaiting run-authorization.
- **Path-B**: 3 candidate target formulations named in Charter §2.2 / AKASHA id=394. No brief written.
- **Path-C**: Ascension Phase 0–2 docs accepted (round-2 by Gemini, v2.1 hygiene patched). Phase 3 not started.

**Track 3 remains BLOCKED. No action to take today.**
