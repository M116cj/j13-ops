# Remaining Findings Resolution Table — MOD-5 Phase 3

**Order**: `/home/j13/claude-inbox/0-7` Phase 3 primary deliverable
**Produced**: 2026-04-24T00:52Z
**Scope**: Pull remaining open MEDIUM + LOW findings from `gemini_round4_delta.md §1`; resolve / downgrade / defer each with explicit boundary. NO finding in vague state.

---

## 1. Findings inventory (from MOD-4 round-4)

| ID | Severity | Original source | MOD-4 carried status |
|---|---|---|---|
| R4a-F1 | MEDIUM | round-4 r4a | L3 data_provider excluded from mandatory set |
| R4b-F2 | MEDIUM | round-4 r4b | M9 cache_lookup soft-metric-only |
| R4b-F3 | MEDIUM | round-4 r4b | M9 thundering-herd spec-only |
| R4a-F2 | LOW | round-4 r4a | Transitive-egress audit blindspot |
| R4c-F1 | LOW | round-4 r4c | CI BYPASS_WARNING missing |

Plus carried from earlier rounds:
| ID | Severity | Status |
|---|---|---|
| R3a-F6 | MEDIUM | PARTIAL (Field 15 runtime) |
| R1a-F3 | MEDIUM | DEFERRED (quiescence loophole — MOOT post-0-6 since quiescence clock removed) |

## 2. MOD-5 disposition per finding

### R4a-F1 MEDIUM — L3 data_provider not mandatory

**Disposition**: **DEFERRED with explicit boundary**

Boundary:
- data_provider is an L3 sub-module with a declared layer home in `modular_target_architecture_amendment.md §2`
- Unlike R2-F3 / R3b-F1 which had NO layer home, data_provider is architecturally accounted for
- Gemini r4a itself noted "mirror of R3b-F1 debt" BUT distinguished "home layer" exists
- Full mandatory-set promotion to M10 is Phase 7 implementation scope (Phase 7 naturally addresses L3 when data flows through mandatory modules)

Deferral explicit boundary:
- Phase 7 data_provider MUST have full 15-field contract before data-consuming modules (M5 search_contract, M6 eval_contract) ship
- Alternative: Phase 7 ships `data_provider_mock` for isolation testing; mock contract same 15 fields
- Gate-B.B.1 at Phase 7 enforces EITHER full L3 contract OR mock contract

**Why DEFERRED not RESOLVED**: promoting to mandatory in MOD-5 is premature — data_provider design details depend on Phase 7 data-flow decisions (which sources are used, which are deprecated).

**Why not downgraded to LOW**: still MEDIUM because Phase 7 must address; ignoring it now risks Phase 7 entry gap.

**Closing action**: Phase 7 kickoff Team Order must explicitly select either "full contract" or "mock" path.

### R4b-F2 MEDIUM — M9 cache_lookup decorative

**Disposition**: **RESOLVED**

Resolution: `gemini_round4_delta.md §4` provided amendment text; MOD-5 formally adopts:

```yaml
cache_lookup:
  max_events_per_second: 20000     # was 10000
  burst_size: 100000               # was 50000
  backpressure_policy: circuit_breaker (open for 1s if sustained breach)
  enforcement: hard_client_side    # was soft_metric_only
```

This spec is now authoritative (supersedes MOD-4 `amended_cp_worker_bridge_contract.md §1 outputs.rate_limit.cache_lookup`). Documented in `medium_findings_patchset.md §1`.

**Why RESOLVED**: hard cap + circuit breaker is a mechanical control, not honor-system. Consumer loops cannot exceed 20k/s without being circuit-broken.

### R4b-F3 MEDIUM — M9 thundering-herd spec-only

**Disposition**: **RESOLVED**

Resolution: `gemini_round4_delta.md §5` text formally adopted. MOD-5 `medium_findings_patchset.md §2` promotes single-flight + jitter from "design intent" to:

```
MANDATORY functional requirement for M9 Phase 7 acceptance:
- single-flight coalesce: per-key pending request deduplication
- jitter: random 0-500ms delay before post-invalidation refetch
Gate-B.B.1 validates both declared + tested via
zangetsu/tests/l1/cp_worker_bridge/test_thundering_herd.py
```

**Why RESOLVED**: mandatory requirement + test gate is mechanical, not aspirational.

### R4a-F2 LOW — Transitive-egress audit blindspot

**Disposition**: **DEFERRED with explicit boundary**

Boundary:
- Runtime enforcement of Field 15 egress (seccomp / iptables) is Phase 7 scope (per `field15_runtime_enforcement_update.md §2 Track C`)
- Build-time `aggregate_egress.py` for effective-egress manifest is MOD-5 logical scope but Phase 7 implementation
- Concrete spec already exists in `gemini_round4_delta.md §6`

Deferral explicit boundary:
- Phase 7 ships `scripts/aggregate_egress.py`
- Output: per-module effective-egress manifest
- Used by Phase 7 runtime policy generator (seccomp / iptables)

**Why DEFERRED not RESOLVED**: build-time tool depends on module YAML existence + Phase 7 CI infrastructure not yet deployed.

**Severity justification**: LOW — not a gate blocker; affects only audit visibility, not correctness.

### R4c-F1 LOW — CI BYPASS_WARNING missing

**Disposition**: **DEFERRED with explicit boundary**

Boundary:
- Gate-B CI workflow (`.github/workflows/module-migration-gate.yml`) is spec-only; not yet deployed
- BYPASS_WARNING step per `gemini_round4_delta.md §7` is pre-authored
- When workflow YAML commits (Phase 7 kickoff), BYPASS_WARNING is required

Deferral explicit boundary:
- Phase 7 workflow YAML MUST include the BYPASS_WARNING step before merge
- Gate-A server-side workflow also includes same step

**Why DEFERRED not RESOLVED**: the workflow file doesn't exist yet to add the step to. Deferral is temporal ordering, not ambiguity.

### R3a-F6 MEDIUM (carried) — Field 15 runtime enforcement

**Disposition**: **PARTIAL — unchanged from MOD-4**

Status unchanged:
- Track A (spec-time at Gate-B.B.1): SPEC READY (validates Field 15 YAML)
- Track B (static source analysis): MOD-5 scope? — **NOT chosen for MOD-5 implementation**; scheduled for Phase 7-adjacent security-hardening sprint
- Track C (runtime seccomp/iptables): Phase 7 scope

MOD-5 does NOT advance beyond MOD-4 disposition. Honest PARTIAL state preserved.

**Why PARTIAL not DEFERRED**: Track A IS active; Tracks B+C are next-phase. "PARTIAL" is correct because enforcement exists (A) but not universal (B+C).

**Boundary**: Phase 7 entry requires Track B static analysis deployed + Track C plan selected.

### R1a-F3 MEDIUM (carried) — Quiescence loophole

**Disposition**: **MOOT (0-6 supersedes)**

The quiescence loophole was specifically about the 7-day date-based clock allowing fix/refactor commits without reset. Post-0-6, the quiescence clock is REMOVED entirely. Finding is moot.

Remediation trace:
- MOD-3: DEFERRED with re-eval trigger at 2026-04-30
- MOD-4: DEFERRED maintained
- **0-6: REMOVED entire mechanism** (see `time_lock_removal_patch.md §2`)
- MOD-5: finding is MOOT (no clock to exploit)

**Why MOOT not RESOLVED**: resolution would imply the rule still exists + is now watertight. The rule itself is gone.

## 3. Summary tally

| Finding | Severity | MOD-5 disposition |
|---|---|---|
| R4a-F1 | MEDIUM | DEFERRED with explicit boundary |
| R4b-F2 | MEDIUM | **RESOLVED** |
| R4b-F3 | MEDIUM | **RESOLVED** |
| R4a-F2 | LOW | DEFERRED with explicit boundary |
| R4c-F1 | LOW | DEFERRED with explicit boundary |
| R3a-F6 | MEDIUM | PARTIAL (unchanged from MOD-4) |
| R1a-F3 | MEDIUM | MOOT (0-6 supersedes) |

Count:
- RESOLVED: 2
- DEFERRED with boundary: 3
- PARTIAL unchanged: 1
- MOOT: 1
- VAGUE: 0 ✅

## 4. Blocker matrix update

R4b-F2 + R4b-F3 RESOLVED → removed from MOD-5 post-commit blocker matrix.
Other findings remain with boundary-clarified status.

See `blocker_matrix_delta_mod5.md` for full updated matrix.

## 5. Non-negotiable rules compliance

| Rule | Evidence |
|---|---|
| 8. No broad refactor | ✅ — only MOD-4-queued findings addressed |
| 10. Labels | ✅ — every row has explicit disposition |

## 6. Q1 adversarial

| Dim | Verdict |
|---|---|
| Input boundary | PASS — all 7 findings (5 MOD-4 + 2 carried) listed |
| Silent failure | PASS — no VAGUE entries |
| External dep | PASS — Gemini round-5 will check these dispositions |
| Concurrency | PASS — triage only |
| Scope creep | PASS — triage limited to MOD-4 queue |

## 7. Label per 0-7 rule 10

- §2 per-finding dispositions: **VERIFIED** (each cites boundary or resolution mechanism)
- §3 tally: **VERIFIED**
- §6 Q1: **VERIFIED**
