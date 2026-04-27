# 42-19 — Gemini Final Adversarial Review (Track T)

**Order**: TEAM ORDER 0-9X-MASTER-SYSTEM-CONSOLIDATION-AND-COLD-START-PREPARATION-v4
**Track**: T — Independent Adversarial Verifier
**Date**: 2026-04-27
**Reviewer**: Gemini-equivalent (called via Lead delegation)
**Scope**: 13 evidence files (41-00…42-16) + arena_pipeline.py + alpha_zoo_injection.py
**Stance**: Skeptical. Lead is biased toward GREEN.

---

## Overall Verdict: **APPROVE_WITH_WARNINGS** — bordering BLOCK on findings F1, F2, F4

I endorse status `CONSOLIDATION_COMPLETE_BUT_RUNTIME_BLOCKED_BY_TRACK_A`. I REJECT
any status of "GREEN" or "READY FOR CANARY". I REJECT any claim that the
cold-start path is "default-safe by code" until F1+F2 fixed.

The evidence collection is broad and honest about the DB block. However, three
implementation defects in the cold-start safety flags would, if unaddressed,
permit unsafe DB writes the moment Track A unblocks. Two architectural claims
(combined-Sharpe → SOL-artifact-blocked; train-neg-pnl gate placement) are
weaker than the documents assert.

---

## Findings

### F1 — `--no-db-write` and `--dry-run` are dead flags. **HIGH**

**Claim in evidence (41-01, 41-05, 41-06)**: "defense-in-depth ladder:
inspect-only ⊂ dry-run ⊂ no-db-write ⊂ confirm-write"; "I8 OK post-PR — default-deny enforced".

**Critique**: In `alpha_zoo_injection.py:run()`, the effective control flow is:

```
if inspect_only:    return                   # OK
if not confirm_write: sys.exit(2)            # OK
# proceed to DB write
```

`args.dry_run` and `args.no_db_write` are **never consulted**. A user passing
`--dry-run` alone will fall into the `confirm_write` abort by accident, but the
flag does nothing. `--no-db-write` defaulting True is cosmetic — there is no
`if args.no_db_write: refuse_writes` gate. The "defense-in-depth ladder" is a
single check on `confirm_write`. The documented contract overstates the code.

**Must resolve**: Either (a) implement the dry-run path (compile + validation
simulation, no asyncpg call) and the no-db-write assertion (raise on any
INSERT), or (b) remove the flags and rewrite docs to reflect single-gate model.

---

### F2 — `--inspect-only` default mismatch. **MEDIUM**

**Claim in evidence (41-01)**: "`--inspect-only` (default ON)".

**Critique**: argparse declares `action="store_true"` without `default=True`.
Effective default is `False`. The boundary map states default ON; the code
defaults OFF. A user invoking `python alpha_zoo_injection.py` with no flags
will hit the `confirm_write` abort, which is safe by accident — but the map's
"default ON inspect-only" is false. Anyone trusting the map could plan a
"default invocation = inspect" flow that does not exist.

**Must resolve**: Either set `default=True` (match documented behavior) or
correct the map.

---

### F3 — Combined-Sharpe gate is single-symbol-blind. **HIGH (architectural overclaim)**

**Claim (41-05 §8)**: "SOL-only artifact blocked — partially".

**Critique**: The `(train_sharpe + val_sharpe) / 2 >= 0.4` gate is computed on
a single (symbol, alpha) cell. An alpha with train_sharpe=0.5 + val_sharpe=0.5
on SOL only — the exact PR #41 artifact — passes trivially. The gate filters
single-slice favoured artifacts WITHIN one symbol; it does NOT block
cross-symbol artifacts. The doc concedes this in §3 ("Cross-symbol consistency
deferred") but §8 still says "SOL-only artifact blocked partially". The blocker
is `reject_train_neg_pnl`, not combined_sharpe. Restate: combined_sharpe blocks
the train-strong/val-weak class only; SOL-only class needs NG3.

**Must resolve**: Update §8 wording. Status row "SOL-only artifact blocked:
partially — via train_neg_pnl ONLY; combined_sharpe does NOT contribute".

---

### F4 — `TRAIN_NEG_PNL` lifecycle reason has no canonical taxonomy entry. **MEDIUM**

**Claim (41-05 §4)**: "If the classifier doesn't yet have explicit mappings,
it falls back to the raw key name (which is still emitted in batch metrics)."

**Critique**: A1 `_emit_a1_lifecycle_safe` is called with
`reject_reason="TRAIN_NEG_PNL"` BEFORE `arena_rejection_taxonomy.classify`
adds the canonical name. Downstream observability metric #3 ("A1 reject
distribution top-5") includes an "UNKNOWN_REJECT" RED threshold. Until the
taxonomy is updated, every TRAIN_NEG_PNL reject risks being counted as
UNKNOWN_REJECT in metric #3 → false-RED in CLI exit code. A follow-up order
mention is insufficient — this is a same-PR concurrent edit needed.

**Must resolve**: Either (a) commit the taxonomy update in same PR #43, or
(b) explicitly allowlist `TRAIN_NEG_PNL` and `COMBINED_SHARPE_LOW` raw-keys
in metric #3 allowlist.

---

### F5 — `train_pnl > 0` gate placement is correct, but documented justification is weak. **LOW**

**Claim (41-05 NEW row)**: gate placed "after gate 1 (train trade count),
BEFORE val backtest — saves CPU".

**Critique**: Placement is correct (val backtest is the expensive op). However,
the gate uses `bt.net_pnl` — net of cost — meaning a high-friction-but-
edgey alpha that loses to costs in train but wins in val (legitimate post-cost
shift) is rejected. Given the existing `val_neg_pnl` floor, this is an additive
strictness with low false-negative risk in practice, but the "saves CPU"
justification ignores that we are also increasing training-window selection
pressure. Acceptable but document the tradeoff.

**Must resolve**: Add a note in 41-05 §1 row that train_neg_pnl rejects
post-cost negatives even when pre-cost was positive. No code change.

---

### F6 — Track A BLOCKED is a latent time-bomb, not a clean defer. **HIGH**

**Claim (41-04, 41-06)**: "All currently masked because A1 candidates fail at
upstream COUNTER_INCONSISTENCY/COST_NEGATIVE before reaching these code paths."

**Critique**: This is true TODAY. But the master order's purpose is to PREPARE
for cold-start. Cold-start is precisely the path that bypasses A1's upstream
CONFIG_INCONSISTENCY/COST_NEGATIVE rejects: alpha_zoo_injection feeds
hand-translated formulas straight at the validation contract. The moment a
governance order authorizes `--confirm-write`, the staging insert path
activates and faults on missing schema. Calling Track A "documented BLOCKED"
hides the dependency chain: cold-start → confirm-write → staging insert →
admission_validator → fresh insert. ALL FOUR layers are missing.

**Must resolve**: Add explicit precondition in any future cold-start order:
"Track A migration applied AND verified live before --confirm-write may be
issued". The Alaya rulebook §3 should add a 10th preflight field "Track A
migration applied = YES" for cold-start orders specifically.

---

### F7 — Pytest 1 fail dismissed too quickly. **MEDIUM**

**Claim**: "1 fail is pre-existing test_db trying direct INSERT into
champion_pipeline_fresh — guard catches it correctly, but test design is
broken."

**Critique**: I cannot independently verify the new gate code paths
(reject_train_neg_pnl, reject_combined_sharpe_low) are exercised by pytest.
The 708-pass count is asserted but there is no listed test name or path that
specifically covers the new branches. The order pre-amble (Phase 11) promises
"explicit gate-level tests" but the evidence does not enumerate them.

**Must resolve**: List the test file(s) and test_func names that cover
`reject_train_neg_pnl` and `reject_combined_sharpe_low`. If absent → write
them before declaring Phase 5 PASS.

---

### F8 — Cost model funding gap dismissed as YELLOW. **MEDIUM**

**Claim (42-09 Track J)**: "Funding Data: ✓ LOADED (present but not consumed;
using flat 1.0 bps estimate). YELLOW for arena-gate realism (recommend funding
cost boost + zero-volume bar handling)."

**Critique**: A 1.0 bps flat versus 3-8 bps observed funding is a 3-8× cost
under-estimate. This is precisely the failure mode that produced PR #41 SOL
single-symbol survivors at cost=0.5x. Calling it YELLOW with "recommend"
language is too soft. This is the proximate cause that train_neg_pnl now
masks; any cold-start under the current cost model will reproduce the same
bias. Recommendation: either upgrade flat to 2.0 bps (conservative) BEFORE
cold-start, or block cold-start until dynamic funding lookup lands.

**Must resolve**: Track J finding upgraded to ORANGE/RED for cold-start
specifically. CANARY without cost-model fix has known-PnL-anomaly precedent.

---

### F9 — "Alaya verified" stamp is unattainable today. **LOW**

**Claim (42-08 Rule 3)**: 9-field preflight, including DB schema inventory
matching v0.7.x manifest.

**Critique**: With Track A BLOCKED, no future order can satisfy Rule 3 field
3 (DB schema inventory ≠ v0.7.1 manifest). The rulebook is sound; my note is
that the rulebook + Track A BLOCKED together mean **NO** future order can
carry the stamp until Track A unblocks. The Lead should state this
explicitly so j13 understands the gating.

**Must resolve**: 42-08 should add a paragraph "Until Track A migration is
applied, no future order can pass Rule 3 field 3. The stamp is unattainable.
This is by design."

---

### F10 — Rollback runbook §13 "alpha_zoo unsafe rerun" is correct but undertested. **LOW**

**Claim (42-15 §13)**: "without the safety flags, alpha_zoo falls back to its
previous state, which is unsafe to execute. Do not run the unflagged script
under any circumstance."

**Critique**: Correct in spirit. But because F1 is unfixed, the *current*
flagged script is not actually safer than the unflagged one — the unused
flags create false confidence. Operators reading §13 may believe the *flagged*
state is safe. Until F1 fixes, the runbook should say "the flagged state
provides single-gate safety via --confirm-write; the dry-run and no-db-write
flags are not yet effective".

**Must resolve**: amend 42-15 §13 with the F1 caveat.

---

### F11 — Final status optimism. **MEDIUM**

**Claim (implicit)**: 17 tracks delivered, 1 BLOCKED with documented reason →
near-GREEN.

**Critique**: 4 tracks (T-track itself plus the doc-only design tracks G/N/O/P/Q)
deliver no runtime change; they are paper deliverables. Substantive runtime
change is only in Tracks D (validation gates) and E (cold-start flags). E has
F1+F2 defects. D has F3 architectural overclaim and F4 taxonomy gap. So in
runtime-effect terms, this consolidation is **2 partial wins, 1 blocker, 5
design specs, 9 audits**. That's still meaningful — boundary maps and rulebooks
have value — but it is not "consolidation complete". Status `CONSOLIDATION_DOCUMENTED_TWO_GATES_LANDED_RUNTIME_BLOCKED` is more honest.

**Must resolve**: status string should reflect "documented" not "complete".

---

## Risk classification

| Finding | Severity | Class | Lead must resolve before final status |
|---------|----------|-------|----------------------------------------|
| F1 | HIGH | Code defect | YES — fix or remove dead flags |
| F2 | MEDIUM | Doc/code mismatch | YES — pick one |
| F3 | HIGH | Architectural overclaim | YES — restate §8 |
| F4 | MEDIUM | Observability false-RED risk | YES — taxonomy entry or allowlist |
| F5 | LOW | Doc gap | recommended |
| F6 | HIGH | Latent dependency chain | YES — add precondition to cold-start order |
| F7 | MEDIUM | Test evidence gap | YES — enumerate tests |
| F8 | MEDIUM | Cost model PnL realism | recommended; CANARY blocker |
| F9 | LOW | Rulebook self-consistency | recommended |
| F10 | LOW | Runbook caveat | recommended (after F1) |
| F11 | MEDIUM | Status overclaim | YES — restate |

---

## Approval Conditions (for upgrade APPROVE_WITH_WARNINGS → APPROVE)

1. F1 resolved: `--dry-run` and `--no-db-write` either implemented or removed.
2. F2 resolved: `--inspect-only` default matches documented behavior.
3. F3 resolved: 41-05 §8 wording corrected to credit train_neg_pnl, not combined_sharpe.
4. F4 resolved: taxonomy update in same PR or metric-3 allowlist.
5. F6 resolved: cold-start governance order template carries Track A precondition.
6. F7 resolved: enumerated test files + test_func names for new gates.
7. F11 resolved: final status string demoted to "DOCUMENTED" not "COMPLETE".

If 1–7 done: status `CONSOLIDATION_DOCUMENTED_TWO_GATES_LANDED_RUNTIME_BLOCKED_BY_TRACK_A` is APPROVE.

If only some done: APPROVE_WITH_WARNINGS, list unresolved.

If F1, F3, F6 not done: BLOCK.

---

## Approved Final Status Options

Gemini endorses (in descending preference):

1. `CONSOLIDATION_DOCUMENTED_TWO_GATES_LANDED_RUNTIME_BLOCKED_BY_TRACK_A` — **PREFERRED**
2. `CONSOLIDATION_PARTIAL_RUNTIME_BLOCKED` — acceptable
3. `CONSOLIDATION_COMPLETE_BUT_RUNTIME_BLOCKED_BY_TRACK_A` — **REJECT** (overclaims completeness)
4. Any "READY FOR CANARY" framing — **REJECT** (F1+F8 unresolved)
5. Any "GREEN" framing — **REJECT**

---

## Recommended Next-Order Priority

**P0 — TEAM ORDER 0-9Y-COLD-START-SAFETY-FLAGS-IMPLEMENT**
Resolve F1+F2 and add explicit gate-level pytest cases. ≤ 90 min.

**P0 — TEAM ORDER 0-9Y-VALIDATION-TAXONOMY-CATCHUP**
Add canonical names TRAIN_NEG_PNL, COMBINED_SHARPE_LOW to
arena_rejection_taxonomy.py + metric-3 allowlist. ≤ 30 min.

**P1 — TEAM ORDER 0-9Y-DB-MIGRATION-MULTI-STAGE**
Track A unblock. v0.4 → v0.6 → v0.7.0 → v0.7.1 sequence with explicit
governance review per step. Required before any cold-start --confirm-write.

**P1 — TEAM ORDER 0-9Y-COST-MODEL-FUNDING-CALIBRATION**
F8: upgrade flat 1.0 bps to 2.0 bps OR implement dynamic lookup. Block
cold-start CANARY until merged.

**P2 — TEAM ORDER 0-9Y-CROSS-SYMBOL-CONSISTENCY**
NG3 (deferred per 41-05 §3). Architectural refactor of per-cell loop to
enable ≥2/3-symbols-positive aggregation.

**P3** — Implement Tracks G/O/Q/P specs (rulebook automation, observability
CLI, profiler harness, recovery automation).

---

*Review complete. Lead may proceed with conditional GREEN once approval
conditions 1–7 met. Until then: APPROVE_WITH_WARNINGS, runtime change
blocked.*
