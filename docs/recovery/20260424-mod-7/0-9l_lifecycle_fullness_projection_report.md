# 0-9L — Lifecycle Fullness Projection Report

Per TEAM ORDER 0-9L-PLUS §16.3.

## 1. P7-PR2 PARTIAL baseline

From 0-9K (merge commit `fe1b0a60`):

| Metric | Value |
|---|---:|
| Lifecycles reconstructed | 1,678 |
| FULL | 0 |
| **PARTIAL** | **1,678 (100 %)** |
| UNAVAILABLE | 0 |
| deployable_count | 6 |
| Overall confidence | PARTIAL |

## 2. Missing fields before P7-PR3

| Field | Occurrences | Root cause |
|---|---:|---|
| `arena_1_entry` | 1,678 / 1,678 | A1 per-candidate events not emitted in runtime |
| `arena_1_exit` | 1,678 / 1,678 | same |
| `reject_reason_or_governance_blocker` | 169 | STALLED_AT_A2 candidates (pipeline interrupted between A2 and A3) |
| `arena_2_entry` | 48 | candidates seen at A3 only (legacy log format ambiguity) |
| `arena_2_exit` | 48 | same |

## 3. Which missing fields P7-PR3 solves

P7-PR3's **A1 trace-native emission** directly closes the two largest gaps:

| Field | Pre-P7-PR3 | Post-P7-PR3 (on NEW logs) |
|---|---|---|
| `arena_1_entry` | missing 1,678 / 1,678 | filled from `A1_ENTRY` events |
| `arena_1_exit` | missing 1,678 / 1,678 | filled from `A1_EXIT_PASS` / `A1_EXIT_REJECT` events |

## 4. Which fields remain unresolved after P7-PR3

| Field | Status | Reason |
|---|---|---|
| `arena_2_entry` / `arena_2_exit` | **still missing for some candidates** | A2 emission is still legacy format. Close via future P7-PR4. |
| `reject_reason_or_governance_blocker` for STALLED_AT_A2 | **still missing** | Structural — these candidates were interrupted by pipeline shutdown and have no terminal rejection event. A future `A2_SHUTDOWN_INTERRUPT` event type could close this. |
| Identity unification across A1↔A2 | **open** | A1 uses `alpha_hash`, A2/A3 use post-admission `id=<N>`. Future order could add join via `admission_validator` recording both. |

## 5. Historical FULL / PARTIAL / UNAVAILABLE result (Layer A)

Reconstruction of the existing 2026-04-16 → 2026-04-23 engine.jsonl:

| Metric | Value |
|---|---:|
| Lifecycles | **1,678** |
| FULL | 0 |
| **PARTIAL** | **1,678** |
| UNAVAILABLE | 0 |
| deployable_count | 6 |

**Unchanged from P7-PR2 — as expected.** Historical logs do not contain the newly added A1 trace-native events, so no lifecycle can become FULL retroactively. This is honest and documented.

## 6. Synthetic FULL / PARTIAL / UNAVAILABLE result (Layer B)

Running `reconstruct_lifecycles_from_trace_events()` against a synthetic fixture with the full A1 → A2 → A3 trace-native event sequence for candidate `DPL-X`:

| Event stream | Provenance quality |
|---|---|
| A1_ENTRY + A1_EXIT_PASS + A1_HANDOFF + A2_ENTRY + A2_EXIT_PASS + A3_ENTRY + A3_EXIT_COMPLETE (with A0=PASS inferred) | **FULL** |
| A2-only events (no A1 trace) | PARTIAL |
| Empty identity (no candidate_id / alpha_id / formula_hash) | UNAVAILABLE |

**FULL provenance path is PROVEN on trace-native fixtures.** (Validated by `test_full_synthetic_a1_a2_a3_deployable_path_produces_full_provenance`.)

## 7. Expected future FULL rate once runtime emits A1 events

Under the new runtime (post-P7-PR3 merge + Arena unfreeze), for EVERY candidate:

- A1_ENTRY fires at the top of alpha evaluation → `arena_1_entry` populated.
- A1_EXIT_PASS or A1_EXIT_REJECT fires → `arena_1_exit` populated.
- A1_HANDOFF_TO_A2 fires for champions → bridges A1 → A2.

If A2/A3 emissions remain legacy (P7-PR3 scope does not extend A2/A3), lifecycles will be:

| Scenario | Expected provenance |
|---|---|
| Candidate rejected at A1 (trace-native only) | **FULL** (A1 entry/exit populated; no A2/A3 expected) |
| Candidate passed A1 + goes to A2 legacy path | **PARTIAL** (A1 trace FULL; A2/A3 still legacy → entry/exit timestamps still missing there) |
| Candidate deployable | **PARTIAL** until P7-PR4 adds A2/A3 trace emission |

**Post-P7-PR3 expected FULL rate**: 100 % of A1-reject lifecycles + 0 % of A2-or-later lifecycles = depends on mix. For the 2026-04-16 → 2026-04-23 profile (227 A1 rejects out of 1,678 = 13.5 %), projected FULL rate = **~13.5 %**, with the remainder PARTIAL but with A1 entry/exit closed.

**Post-P7-PR4 (if extended to A2)**: projected FULL rate approaches 100 % for rejected lifecycles; deployable candidates require P7-PR5 (A3) for full FULL.

## 8. Why historical logs cannot become FULL retroactively

**Fundamental reason**: A1 events were never emitted. No amount of post-hoc parsing can recover data that was never written.

The historical reconstruction already infers A1 PASS (a candidate reaching A2 must have passed A1), but cannot synthesize **timestamps**. Timestamps are observational data — they require the event to have fired at the moment in time.

Unless a retroactive timestamp is fabricated (explicitly forbidden by §8.3 "Do not fabricate missing lifecycle fields"), historical logs remain PARTIAL forever. This is honest and correct.

## 9. Next trace-native stage recommendations

Recommended order of future orders:

1. **TEAM ORDER 0-9M** — Phase 7 Controlled-Diff Acceptance Rules Upgrade (close the arena_pipeline_sha tripwire gap for authorized changes).
2. **TEAM ORDER 0-9N (or similar)** — A2 trace-native emission in `arena23_orchestrator.py` (closes arena_2_entry/exit for future candidates).
3. **TEAM ORDER 0-9O (or similar)** — A3 trace-native emission in `arena23_orchestrator.py` (closes arena_3_entry/exit; makes deployable candidates FULL).
4. **TEAM ORDER 0-9P (or similar)** — A4 / A5 trace-native emission if applicable.
5. **TEAM ORDER 0-9Q (or similar)** — Identity unification: admission_validator emits a `CANDIDATE_ADMITTED` event with both `alpha_hash` and `staging_id` for A1↔A2 lifecycle join.

Each order follows the same pattern as P7-PR3:
- ~70 LOC additive to the respective runtime file.
- Exception-safe emission wrapper.
- Behavior-invariance tests.
- Minimal 3-5 emission call sites per stage.
- Expected controlled-diff status: FORBIDDEN on the touched `_sha` field until 0-9M lands, then EXPLAINED afterwards.
