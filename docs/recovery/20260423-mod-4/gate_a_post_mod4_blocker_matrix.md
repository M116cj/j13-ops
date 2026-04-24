# Gate-A Post-MOD-4 Blocker Matrix

**Order**: `/home/j13/claude-inbox/0-5` Phase 6 secondary deliverable
**Produced**: 2026-04-23T11:00Z

---

## 1. Header summary

| Question | Answer |
|---|---|
| Current classification (MOD-4 framework) | **CLEARED_PENDING_QUIESCENCE** |
| 0-6 reclassification forecast (post-commit) | **STILL_PARTIALLY_BLOCKED** |
| Total actionable blockers (MOD-5 queue) | **6** (1 HIGH + 3 MEDIUM + 2 LOW) |
| Time-gated (old framework) | 1 (A.2 quiescence, 2026-04-30) |
| Condition-gated (0-6 framework) | 2 (Condition 4 Adversarial Closure; Condition 5 Controlled-Diff) |

## 2. Blocker matrix (MOD-5 queue)

| ID | Severity | Origin | Blocker | MOD-5 remediation | Phase |
|---|---|---|---|---|---|
| R4b-F1 | **HIGH** | Gemini r4b round-4 | `enforce_admins=false` nullifies signature enforcement for j13 PAT; "Security Theater" for primary automated actor | Transition to `enforce_admins=true` before Phase 7 entry; require PR-based + human GPG-signed merges for MOD-5+ | MOD-5 Phase 1 |
| R4a-F1 | MEDIUM | Gemini r4a | L3 `data_provider` excluded from mandatory set | PROMOTE to M10 with full 15-field contract OR ship `data_provider_mock` for isolation tests | MOD-5 Phase 2 |
| R4b-F2 | MEDIUM | Gemini r4b | M9 `cache_lookup` 10000/s is "soft metric only" — no hard cap on consumer loops | Upgrade to hard cap (20000/s) with circuit-breaker backpressure | MOD-5 Phase 2 |
| R4b-F3 | MEDIUM | Gemini r4b | M9 thundering-herd mitigation (jitter + single_flight) is "design intent", not mandatory | Move to "mandatory functional requirement" in M9 contract; add test_thundering_herd.py golden fixture | MOD-5 Phase 2 |
| R4a-F2 | LOW | Gemini r4a | Transitive-egress rule creates audit blindspot for automated verification | Build-time `aggregate_egress.py` tool producing effective-egress manifest | MOD-5 Phase 3 |
| R4c-F1 | LOW | Gemini r4c | `required_signatures` lacks BYPASS_WARNING log in Gate-B CI output | Add workflow step emitting `::warning::BYPASS_WARNING` + PR comment on unsigned commits | MOD-5 Phase 3 |

All 6 blockers have pre-authored amendment text in `gemini_round4_delta.md §2–§7`.

## 3. Carried-over blockers (still tracked from prior rounds)

| ID | Severity | Status |
|---|---|---|
| R3a-F6 | MEDIUM | PARTIAL — Track A (spec) done; Track B (static) MOD-5; Track C (runtime) Phase 7 |
| R1a-F3 | MEDIUM | DEFERRED — re-evaluation scheduled at 2026-04-30 quiescence expiry |

Neither is a Gate-A blocker per round-4 (both AGREE_RESOLVED by r4c with honest disposition labels).

## 4. 0-6 Condition Groups — Gate-A evaluation

Per 0-6 §C + §D:

| Condition Group | State | Evidence |
|---|---|---|
| 1. Runtime Freeze Proof | **VERIFIED** | arena=0, engine.jsonl static, Calcifer RED held, no respawn detected |
| 2. Governance Live Proof | **PARTIAL** | 7 rules LIVE (G1/G3/G6/G11/G12/G17/G18); admin-bypass gap R4b-F1 HIGH disclosed |
| 3. Corpus Consistency Proof | **VERIFIED** | r4c COHERENT; `mod4_corpus_consistency_patch.md §2` pair-wise |
| 4. Adversarial Closure Proof | **PARTIAL** | 1 HIGH (R4b-F1) + 3 MEDIUM + 2 LOW open; composite ACCEPT_WITH_AMENDMENTS |
| 5. Controlled-Diff Proof | **INCONCLUSIVE** | pre/post snapshots for Phase A/B exist; MOD-4 diff snapshot not yet formalized (0-6 governance patch addresses) |
| 6. Rollback Readiness Proof | **VERIFIED** | rollback specs in every MOD-3/MOD-4 module contract; three-mode M6 rollback documented |

**0-6 classification**: `STILL_PARTIALLY_BLOCKED` (Conditions 2 + 4 + 5 not fully met).

## 5. Severity roll-up

| Severity | MOD-4 open count |
|---|---|
| CRITICAL | 0 |
| HIGH | 1 (R4b-F1) |
| MEDIUM | 4 (R4a-F1, R4b-F2, R4b-F3, R3a-F6 PARTIAL) |
| LOW | 2 (R4a-F2, R4c-F1) |
| DEFERRED (tracked) | 1 (R1a-F3 quiescence loophole) |

## 6. MOD-5 dependency order

```
MOD-5 Phase 1 (required to exit STILL_PARTIALLY_BLOCKED):
  1. R4b-F1 enforce_admins=true transition + PR flow (HIGH)
     → closes Condition 2 gap

MOD-5 Phase 2 (recommended before Phase 7 kickoff):
  2. R4a-F1 data_provider decision
  3. R4b-F2 cache_lookup hard cap
  4. R4b-F3 thundering-herd mandate
     → closes Condition 4 (Adversarial Closure) after Gemini round-5

MOD-5 Phase 3 (polish):
  5. R4a-F2 egress aggregation tool
  6. R4c-F1 BYPASS_WARNING CI log
     → refinements; not gate-blocking

MOD-5 Phase 4: Gemini round-5 re-review
MOD-5 Phase 5: 0-6-framework Gate-A reassessment
  Target: CLEARED (no CRITICAL/HIGH) or CLEARED_PENDING_CONDITIONS (if new medium remains)

Phase 7 entry requires: Gate-A = CLEARED under 0-6 framework
```

## 7. Comparison: MOD-3 → MOD-4 Gate-A state

| Framework | MOD-3 exit | MOD-4 exit |
|---|---|---|
| MOD-1 A.1/A.2/A.3 classification | BLOCKED_BY_NEW_FINDINGS | CLEARED_PENDING_QUIESCENCE |
| 0-6 Condition Groups | N/A (0-6 not yet issued) | STILL_PARTIALLY_BLOCKED |

Net: MOD-4 progressed the architecture; Gate-A moved from BLOCKED → PARTIALLY_BLOCKED. Not yet CLEARED — MOD-5 resolves remaining R4b-F1 HIGH.

## 8. Non-negotiable rules

| Rule | Compliance |
|---|---|
| 10. Labels | ✅ (VERIFIED / PARTIAL / INCONCLUSIVE / DISPROVEN used) |

## 9. Q1 adversarial

| Dim | Verdict |
|---|---|
| Input boundary | PASS — 6 MOD-5 blockers + 2 carryovers + 6 Condition Groups |
| Silent failure | PASS — R4b-F1 HIGH openly carried; no cosmetic closure |
| External dep | PASS — round-4 Gemini evidence cited |
| Concurrency | PASS — single-author matrix |
| Scope creep | PASS — matrix only |

## 10. Label per 0-5 rule 10

- §2 MOD-5 queue: **VERIFIED** (each row cites specific Gemini finding)
- §4 0-6 conditions: **VERIFIED** (per 0-6 §C enumeration)
- §6 MOD-5 dependency order: **PROBABLE** (recommended order; j13 decides MOD-5 scope)
