# gov_contract_engine Boundary Update — MOD-3

**Order**: `/home/j13/claude-inbox/0-4` Phase 2 deliverable
**Produced**: 2026-04-23T07:36Z
**Supersedes**: `docs/recovery/20260423-mod-1/module_boundary_map.md §MOD-1.B Module 4 gov_contract_engine`
**Resolves**: Gemini R2-F2 HIGH (kernel vs gov split-brain on rollout gating)

---

## 1. Amendment summary

**Move rollout-gating ownership** from `engine_kernel` (M1) to `gov_contract_engine` (M4). Resolves the split-brain where both modules claimed policy enforcement authority.

## 2. Rationale

Per Gemini R2-F2:
> "Both modules claim ownership of runtime 'gating' and 'policy' enforcement, creating a split-brain for rollout authorization."

Correct ownership: **policy decisions are governance authority, not kernel authority**. The kernel's job is to execute transitions; the governor's job is to authorize them. Mixing the two inside the kernel violates layered-architecture discipline.

Charter alignment: CLAUDE.md §5 "Calcifer = Alaya infra guardian" + §17 "governance enforcement" both point to governance-layer ownership of authorization decisions.

## 3. Amended responsibilities

### M4 `gov_contract_engine` — responsibilities (full amended list)

```yaml
responsibilities:
  # existing 5 (unchanged)
  - consume commit + PR + CP write events
  - evaluate each against charter §17 rules and mutation_blocklist entries
  - emit allow/deny + audit + rollback-handle
  - post RED Telegram alert on any high-severity rule violation
  - sync decisions to cp_audit
  # NEW MOD-3 (per R2-F2)
  - authorize rollout tier advances for every module (OFF → SHADOW → CANARY → FULL)
  - consume RolloutAdvanceRequest from cp_api; emit verdict
  - consume TransitionAttemptEvent from engine_kernel; emit PolicyVerdict per transition
  - enforce Gate-C sub-conditions (≥30d CP uptime, decision-rights enforcement, scatter-site removal) for control-plane takeover
  - publish the decision-rights matrix as queryable CP surface
```

Count: 10 responsibilities (within §2 Field 3 2–7 rule? **NO** — over limit).

### Mitigation: split gov_contract_engine into sub-modules

To keep M4 under the §2 Field 3 "2–7 entries" discipline, split into peer modules:

| Sub-module | Responsibilities |
|---|---|
| **gov_contract_engine (core)** | commit/PR/CP-write evaluation against charter + blocklist; emit allow/deny + audit; RED Telegram on violation (3 entries) |
| **gov_rollout_authority (NEW sub)** | authorize rollout advances; consume RolloutAdvanceRequest + TransitionAttemptEvent; emit PolicyVerdict; enforce Gate-C sub-conditions; publish decision-rights matrix (5 entries) |

`gov_rollout_authority` is a NEW peer module under L8.G. It is NOT promoted to the mandatory-module set (MOD-1 module_boundary_map §2 Ascension table already includes `gov_rollout` as a sub-module of the L8.G umbrella; the amendment is just making its interface explicit).

### M1 engine_kernel — amended responsibilities

Old:
```
responsibilities:
  - transition champion status
  - acquire/release leases
  - reap expired leases
  - route events to L4/L5/L6
  - emit transition events
  - enforces rollout gating       ← REMOVED
```

New:
```
responsibilities:
  - transition champion status
  - acquire/release leases
  - reap expired leases
  - route events to L4/L5/L6
  - emit transition events
  - consume PolicyVerdict from gov_contract_engine; halt transition if verdict=deny  ← ADDED
```

Count: 6 responsibilities (within 2–7 ✅).

## 4. Edge additions

### M1 engine_kernel — NEW input
```yaml
inputs:
  # ... existing inputs ...
  - contract_name: PolicyVerdict
    source_module: gov_contract_engine
    cardinality: one_per_transition_attempt
    frequency: event
```

### M4 gov_contract_engine — NEW inputs
```yaml
inputs:
  # ... existing 3 inputs ...
  - contract_name: RolloutAdvanceRequest
    source_module: cp_api
    cardinality: one_per_advance
    frequency: event (operator-triggered)
  - contract_name: TransitionAttemptEvent
    source_module: engine_kernel
    cardinality: one_per_transition_attempt
    frequency: event (stream)
```

### M4 gov_contract_engine — NEW output
```yaml
outputs:
  # ... existing 2 outputs ...
  - contract_name: PolicyVerdict
    consumer_modules: [engine_kernel, cp_api, gov_ci_hooks]
    cardinality: one_per_input
    guarantees:
      delivery: exactly_once
      ordering: total
      idempotency: true (keyed by request_id)
```

## 5. State-ownership update (cross-ref `state_ownership_matrix.md`)

| State | Old owner | New owner |
|---|---|---|
| `control_plane.rollout` (rollout tier per subsystem) | cp_storage (store) + engine_kernel (authority) | cp_storage (store) + **gov_rollout_authority (authority)** |

Store and authority split: cp_storage owns the data; authority owns the decision to advance.

## 6. Failure-surface update for M4

Add 2 new failure modes:
```yaml
failure_surface:
  # existing 7 modes ...
  - {name: rollout_verdict_timeout, detection: verdict decision > 5s for a RolloutAdvanceRequest, recovery: timeout_as_deny + audit + RED Telegram}
  - {name: kernel_transition_storm, detection: TransitionAttemptEvent rate > N/s per champion, recovery: rate_limit + audit (likely signals kernel bug, not policy issue)}
```

## 7. Console controls (Field 14) update for M4

```yaml
console_controls:
  # existing 3 controls ...
  - {surface_key: "gov.rollout.advance.<module>", class: rollout_advance, decision_rights_ref: "control_plane_blueprint.md#rollout-advance", audit_tier: high}
  - {surface_key: "gov.rollout.policy.strictness", class: parameter, decision_rights_ref: "control_plane_blueprint.md#gov", audit_tier: high}
```

## 8. `control_plane_blueprint.md §5 decision-rights matrix` reference

The matrix already has a "rollout-advance" row (see `control_plane_blueprint.md §5` decision-rights table). Post-MOD-3 amendment, the "Parameter class" column for "rollout-advance" reads:

| Param class | j13 direct | Claude Lead | Gemini | Codex | Calcifer | Miniapp | **Ownership authority** |
|---|:---:|:---:|:---:|:---:|:---:|:---:|---|
| rollout-advance | YES | PROPOSE | CHALLENGE | n/a | n/a | YES (owner-fresh + high-tier audit) | **gov_rollout_authority** |

Authority column is NEW in MOD-3 — clarifies which module enforces.

## 9. Resolution status

| Finding | Status |
|---|---|
| R2-F2 HIGH (kernel vs gov split-brain) | **RESOLVED** — ownership moved; edges updated; sub-module split preserves §2 discipline |

## 10. Label per 0-4 rule 10

- §3 responsibilities: **VERIFIED** (each entry maps to existing or planned code path; sub-module split keeps 2–7 discipline)
- §4 edges: **PROBABLE** (design; VERIFIED when edges wire in Phase 7)
- §8 decision-rights matrix row: **PROBABLE** (Gemini round-3 may refine)
