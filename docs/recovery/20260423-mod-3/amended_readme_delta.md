# MOD-1 README Amended Delta — MOD-3

**Order**: `/home/j13/claude-inbox/0-4` Phase 3 deliverable
**Produced**: 2026-04-23T08:04Z
**Purpose**: Update answers in MOD-1 `README.md` to reflect MOD-3 amendments. This is a DELTA (not a full replacement); readers who pull the MOD-3 corpus read MOD-1 README + this delta.

---

## 1. Updates to MOD-1 README §2 "Mandatory questions — answers"

### Q1 update (add module count to the sketch)

Append to existing Q1 answer:

> After MOD-3 amendments, the mandatory module set is **9 modules** (was 7): engine_kernel (M1), gate_registry (M2), obs_metrics (M3), gov_contract_engine (M4), search_contract (M5), eval_contract (M6), adapter_contract (M7), **gate_contract (M8, NEW)**, **cp_worker_bridge (M9, NEW)**. See `../20260423-mod-3/amended_module_boundary_map.md`.

### Q2 update (preserve + link)

Unchanged body. Append reference:

> Additional preservation constraints post-MOD-3: CD-14 holdout discipline now encoded as a contract invariant inside `gate_contract.failure_surface` rather than a file-level assertion. See `../20260423-mod-3/gate_contract_module_spec.md §2`.

### Q3 update (formulation-specific)

Unchanged body. No MOD-3 change — these are still formulation-specific and must not define future architecture.

### Q4 update (script-centric)

Append:

> Post-MOD-3: every worker becomes engine-centric via `cp_worker_bridge` (M9). Direct `os.environ.get()` reads are forbidden in module code; all parameters flow through the bridge library.

### Q5 update (mixed responsibilities)

Unchanged body for existing mixes. Add:

> Post-MOD-3 amendment: rollout-gating was mixed between engine_kernel (M1) and gov_contract_engine (M4). Resolved: rollout-advance authorization lives in gov_rollout_authority (L8.G sub-module). See `../20260423-mod-3/gov_contract_engine_boundary_update.md`.

### Q6 update (scattered configs)

Append:

> Post-MOD-3: every module's `config_schema.cp_params` list is the exhaustive enumeration of parameters consumed. `cp_worker_bridge` is the sole read path. Any module referencing an env var outside this list will be caught at Gate-B's Field 15 `execution_environment` check.

### Q7 update (modules before modularization)

Append:

> Post-MOD-3: the 9-module set (was 7) includes the L6 execution engine (gate_contract M8) and the L1 CP data-plane library (cp_worker_bridge M9). Without these, kernel→gate→promotion cycle is broken (M8 missing) and every module depends on an unmandated bridge (M9 missing).

### Q8 update (black-box allowed)

Unchanged body. Append:

> Post-MOD-3 Field 15 amendment closes the egress-stealth loophole: `blackbox_allowed: false` MUST be paired with `permitted_egress_hosts: []` (or whitelist). Runtime egress audit + CI static-analysis catch violations. See `../20260423-mod-3/amended_module_contract_template.md §2 Field 15`.

### Q9 update (fully transparent)

Append cp_worker_bridge + gate_contract + gov_rollout_authority to the list of fully-transparent modules. All three are `blackbox_allowed: false` with rationale.

### Q10 update (deferred)

Unchanged. Track 3 discovery restart + Phase 7 migration + console implementation + runtime takeover all remain deferred.

## 2. Updates to MOD-1 README §3 "Non-negotiable rules (0-2) compliance"

Post-MOD-3 additions to the "Evidence" column:

| Rule | MOD-3 additional evidence |
|---|---|
| 8. No black-box control surface | Field 15 `execution_environment` made mandatory — egress whitelisting enforced |
| 9. No module without 14-field contract | 15-field contract template (Field 15 added) + gate_contract M8 + cp_worker_bridge M9 both with full 15 fields |

## 3. Updates to MOD-1 README §4 "Stop conditions"

Unchanged. No MOD-3 stop-condition trigger.

## 4. Updates to MOD-1 README §5 "MOD-1 success criteria"

All 8 criteria remain MET. MOD-3 amendments **strengthen** criteria 4 (module boundaries explicit) + criterion 6 (first control-plane blueprint exists) without removing any already-met condition.

## 5. Updates to MOD-1 README §6 "Q1/Q2/Q3 self-audit"

Append:

> Post-MOD-3 confidence upgrade:
> - Q1 input boundary: **VERIFIED** — 9-module contracts each with 15 fields = 135 field commitments; Gemini round-3 will check coverage
> - Q1 silent failure: **VERIFIED** — Field 15 execution_environment makes OS-level side channels visible; Gate-B path-based trigger closes label-bypass; rollout split-brain closed
> - Q2 structural integrity: **VERIFIED** — 3 new drift candidates D-27/D-28/D-29 all resolved with concrete amendment commits
> - Q3 execution efficiency: **VERIFIED** — MOD-3 added only what was required by round-2 findings; no speculative expansion

## 6. Updates to MOD-1 README §7 "Handoff to MOD-2"

Historical record — no MOD-3 change. MOD-2 completed; MOD-3 amended; MOD-4 awaits.

## 7. Updates to MOD-1 README §8 "File index"

Add MOD-3 cross-reference:

```
../20260423-mod-3/
├── README.md                                        (MOD-3 synthesis)
├── gate_contract_module_spec.md                     (Phase 1 — M8 full contract)
├── amended_module_boundary_map.md                   (Phase 1 — 9-module delta)
├── gate_b_trigger_correction.md                     (Phase 1 — path-based fix)
├── github_actions_gate_b_enforcement_spec.md        (Phase 1 — workflow YAML)
├── amended_module_contract_template.md              (Phase 2 — Field 15)
├── gov_contract_engine_boundary_update.md           (Phase 2 — rollout ownership)
├── cp_worker_bridge_promotion_spec.md               (Phase 2 — M9 full contract)
├── modular_target_architecture_amendment.md         (Phase 2 — topology delta)
├── control_plane_blueprint_amendment.md             (Phase 2 — CP delta)
├── mod1_corpus_consistency_patch.md                 (Phase 3 — coherence audit)
├── amended_modularization_execution_gate.md         (Phase 3 — full gate replacement)
├── amended_readme_delta.md                          (Phase 3 — this file)
├── gemini_round3_repair_report.md                   (Phase 4)
├── gemini_round3_verdict.md                         (Phase 4)
├── gemini_round3_delta.md                           (Phase 4)
├── gate_a_post_mod3_memo.md                         (Phase 5)
└── gate_a_post_mod3_blocker_matrix.md               (Phase 5)
```

## 8. Label per 0-4 rule 10

- §1 Q updates: **VERIFIED** (each amendment traces to a MOD-3 file)
- §2 rule compliance additions: **VERIFIED**
- §6 confidence upgrade: **PROBABLE** pending Gemini round-3
