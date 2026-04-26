# 11 — Decision Branch

## 1. Phase Classifications Aggregated

| Phase | Question | Verdict |
| --- | --- | --- |
| Phase 1 | Runtime alive? | A1=ACTIVE, A23=ALIVE_IDLE, A45=ALIVE_IDLE, engine.jsonl=WRITING, feedback=CLEAN |
| Phase 2 | A13 feedback healthy? | PASS (12 successful runs since PR #34, 0 errors) |
| Phase 3 | DB lifecycle? | **DB_FLOW_STALLED + DB_FLOW_DEGRADED** (89/89 ARENA2_REJECTED, no fresh activity for 5d 19h, 0 rows since A1 alive) |
| Phase 4 | A1 producing usable candidates? | **A1_CYCLING_NO_OUTPUT** (workers actively cycling, 0 staging rows in 2h 12m) |
| Phase 5 | A23 intake visibility? | **A23_WAITING_NO_CANDIDATES** (correctly idle: no eligible rows exist for A23 to consume) |
| Phase 6 | A45 readiness? | **A45_READY_IDLE** (correctly idle; not the blocker) |
| Phase 7 | Telemetry? | **TELEMETRY_MISSING** (file does not exist, 0 lines) |

## 2. Apply the Decision Tree (order §22)

| Case | Condition | Match? |
| --- | --- | --- |
| A | TELEMETRY_READY → CANARY observation | NO |
| B | TELEMETRY_STARTED_INSUFFICIENT | NO |
| C | TELEMETRY_MISSING + DB_FLOW_ACTIVE → BLOCKED_TELEMETRY_EMISSION | NO (DB flow is NOT ACTIVE) |
| D | TELEMETRY_MISSING + DB_FLOW_COLD | partial — DB has historical rows, so not pure cold |
| **E** | **A1_CYCLING_NO_OUTPUT → BLOCKED_A1_OUTPUT_NOT_MATERIALIZING** | **YES — exact match** |
| F | A23_INTAKE_MISMATCH | NO (intake matches; the rows just aren't eligible) |
| G | A23_WAITING_NO_CANDIDATES (only) | partial — true at A23 level, but the **upstream root cause** is Case E |
| H | safety violation | NO |
| I | telemetry malformed | NO |

## 3. Selected Case

**CASE E** is the most precise diagnosis. The chain of dependence is:

```
A1 cycles for 2h 12m  →  zero new rows in champion_pipeline_staging
                        ↓
                       admission_validator() never invoked
                        ↓
                       champion_pipeline_fresh frozen at 89 ARENA2_REJECTED rows from Apr 21-22
                        ↓
                       no rows match A23 intake query
                        ↓
                       A23 stays idle — correctly
                        ↓
                       A23 never reaches 20-iteration window boundary
                        ↓
                       arena_batch_metrics.jsonl never emitted
                        ↓
                       0-9S-CANARY-OBSERVE-LIVE cannot proceed
```

The downstream symptoms (A23_WAITING_NO_CANDIDATES, TELEMETRY_MISSING) are **consequences** of the upstream root cause (A1_CYCLING_NO_OUTPUT). Reporting Case E identifies the actual repair target.

## 4. Final Status Mapping (order §23 acceptance)

→ **BLOCKED_A1_OUTPUT_NOT_MATERIALIZING** (option 5).

## 5. Phase 8 Verdict

PASS-with-blocked-flag. Decision branch resolved cleanly to Case E. No CANARY can be issued because TELEMETRY_MISSING and zero live batches exist. Issuing any CANARY verdict would violate order §22 ("Do not declare CANARY without live batches") and §27 ("AC19: If no live batches exist, no fake CANARY verdict is issued").
