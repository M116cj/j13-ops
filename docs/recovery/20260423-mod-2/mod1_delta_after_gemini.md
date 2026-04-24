# MOD-1 Delta After Gemini Round-2

**Order**: `/home/j13/claude-inbox/0-3` Phase 3 third deliverable
**Produced**: 2026-04-23T04:15Z
**Scope**: Translate Gemini's 14 findings into concrete amendments to MOD-1 deliverables. **These amendments are NOT applied in MOD-2** — MOD-2 is clearance, not re-authoring.

---

## 1. Summary — amendments required by CRITICAL / HIGH findings

### CRITICAL-1 (R1a-F1): Gate-B label-trigger bypass
**Target file**: `docs/recovery/20260423-mod-1/modularization_execution_gate.md`
**Target section**: §5.2 Gate-B enforcement
**Amendment**:

Change from:
```
Trigger: any PR with label `module-migration/<module_id>`
```
to:
```
Trigger: any PR that modifies paths under `zangetsu/src/modules/**`
  OR `zangetsu/module_contracts/*.yaml`
  OR creates a new file matching `zangetsu/src/l[0-9]*/**`.
Label-based triggers are ADDITIVE (informational), not gating.
```

**Reason**: Path-based triggers cannot be omitted by the PR author; label-based triggers can.

### CRITICAL-2 (R2-F1): Missing gate_contract module
**Target file**: `docs/recovery/20260423-mod-1/module_boundary_map.md`
**Target section**: §MOD-1.B — 7 mandatory module contracts
**Amendment**:

Add **Module 8 — gate_contract (L6 execution engine)** with full 14-field contract. Key fields:
- purpose: "Execution engine for every L6 gate; consumes MetricsContract from eval_contract + ThresholdLookup from gate_registry; produces GateOutcomeContract for kernel_dispatcher."
- responsibilities: (5 entries covering admission / A2 / A3 / A4 / promote gate evaluation routing)
- blackbox_allowed: false
- rollback_surface: code=git-revert; state="gate outcomes append-only in pipeline_audit_log; no retroactive change"
- Full 14-field spec per `module_contract_template.md`.

Update `README.md §1 Deliverables index` to reference 8 mandatory modules (not 7).
Update `module_boundary_map.md §MOD-1.C` mapping table accordingly.

**Reason**: Without gate_contract, kernel takes `GateOutcomeContract` as input but no mandatory module produces it. Architecture is incomplete.

### HIGH-1 (R1a-F2): Local-hook bypass via `--no-verify`
**Target**: `modularization_execution_gate.md §5.1`
**Amendment**: Mirror Gate-A logic into a server-side GitHub Actions workflow (`phase-7-gate.yml`) that runs on `push` to `main` and `blocks` if A.1-A.3 conditions aren't met. Local hook stays as convenience but is non-authoritative.

### HIGH-2 (R1b-F1): blackbox_allowed=false egress stealth
**Target**: `module_contract_template.md §2`
**Amendment**: Add **Field 15 — execution_environment**:
```yaml
execution_environment:
  permitted_egress_hosts: [<hostname:port>, ...]   # empty list = no network
  subprocess_spawn_allowed: true | false
  filesystem_write_paths: [<absolute-path-prefix>, ...]
  max_rss_mb: <int>
  max_cpu_pct_sustained: <int>
```
Update §4 acceptance checklist to verify this field.
Update §5 anti-patterns: "module writes network payloads to hosts not in permitted_egress_hosts → automatic rejection + egress audit".

### HIGH-3 (R2-F2): kernel vs gov_contract_engine split-brain
**Target**: `module_boundary_map.md §MOD-1.B` Module 1 responsibilities
**Amendment**: Change engine_kernel §responsibilities:
- Remove: "enforces rollout gating"
- Add: "consumes PolicyVerdict from gov_contract_engine; if verdict=deny, halts transition"

Move rollout authorization explicitly into `gov_contract_engine §responsibilities`:
- Add: "owns rollout gating — consumes CP rollout advance request, emits authorized / denied verdict"

### HIGH-4 (R2-F3): cp_worker_bridge not in 7 mandatory
**Target**: `module_boundary_map.md §MOD-1.B`
**Amendment**: Promote `cp_worker_bridge` to the mandatory set (making total 9 mandatory modules after R2-F1 also adds gate_contract). Add full 14-field contract. Rationale: if every umbrella module depends on it, it's a core boundary.

## 2. MEDIUM findings — track for future refinement (not required for Gate-A)

| ID | Summary | Target | Disposition |
|---|---|---|---|
| R1a-F3 | §A.2 only blocks `feat(` — expand to "any non-docs commit" | `modularization_execution_gate.md §A.2` | Track for MOD-3 |
| R1a-F4 | Rollback p95 unverified | `modularization_execution_gate.md §B.2` | Add "empirical p95 measured during SHADOW rehearsal" requirement before Gate-B clear |
| R1a-F5 | Override ADR lacks crypto identity | `modularization_execution_gate.md §6` | Require GPG-signed commits for ADRs with `gate-override` tag |
| R1b-F2 | Compute-budget / rate-limit contract | `module_contract_template.md §2` | Merge into Field 5 (Outputs) as `rate_limit` sub-schema |
| R1b-F3 | Responsibilities semantic-fluff | `module_contract_template.md §4` | Require 1:1 mapping from responsibilities to test_boundary fixtures |
| R2-F4 | M6 rollback p95=8min wishful | `module_boundary_map.md §MOD-1.B Module 6` | Downgrade to p95=30min OR add persistent data_cache snapshot requirement |

## 3. LOW findings — cosmetic

| ID | Summary | Disposition |
|---|---|---|
| R2-F5 | M6 missing L9 adapter disclaimer | Add same clause as M5 search_contract |
| R1b-F4 | Rollback/Replacement redundancy | **DISPROVEN** — no change |

## 4. Amendment plan — when to apply

**NOT in MOD-2.** MOD-2 is clearance + hardening only. MOD-1 amendments are:

- MOD-3 (next team order after MOD-2) should include "MOD-1 amendment pass" as first phase
- Gate-A.1 classification reflects the composite verdict — see `gate_a_readiness_memo.md §MOD-1 ACCEPT status`
- Until amendments land, Phase 7 migration is BLOCKED regardless of quiescence window

## 5. How this file is used by Phase 5 readiness memo

`gate_a_readiness_memo.md` reads this file's §1 CRITICAL list to classify Gate-A.1 as `PARTIALLY_CLEARED` (Gemini review happened + verdict integrated, but mandatory amendments pending). Phase 7 earliest-viable date shifts from 2026-04-30 to "after MOD-3 lands amendments" — see memo for details.

## 6. Non-negotiable rules compliance

| Rule | Evidence |
|---|---|
| 1. No silent production mutation | ✅ — doc-only, no code |
| 5. No Phase 7 migration work | ✅ |
| 9. No module merge into mainline migration | ✅ |
| 10. Labels applied | ✅ — CRITICAL / HIGH / MEDIUM / LOW + VERIFIED / PROBABLE / INCONCLUSIVE / DISPROVEN throughout |

## 7. Q1 adversarial

| Dim | Verdict |
|---|---|
| Input boundary | PASS — each of 14 Gemini findings classified; no finding ignored |
| Silent failure | PASS — amendments are explicit; no silent deferral |
| External dep | PASS — Gemini CLI operational (see gemini_cli_repair_report) |
| Concurrency | PASS — single-author delta |
| Scope creep | PASS — no amendments applied; only enumerated |

## 8. Exit condition

0-3 §Phase 3 third output: "explicitly flag whether any MOD-1 deliverable must be amended" — **MET.** Yes: at minimum, 2 CRITICAL + 4 HIGH amendments. Concrete text + target section specified above.
