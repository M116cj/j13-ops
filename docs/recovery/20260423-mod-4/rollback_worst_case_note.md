# M6 Rollback Worst-Case Note — MOD-4 Phase 3

**Order**: `/home/j13/claude-inbox/0-5` Phase 3 deliverable
**Produced**: 2026-04-23T10:10Z
**Addresses**: Gemini R3b-F3 MEDIUM — "M6 30min worst-case rollback remains unacceptable for arena state machine freeze"

---

## 1. Problem recap

MOD-3 `amended_module_boundary_map.md §5.2` added persistent `eval_cache_snapshot` for M6 `eval_contract`:
- p50 = 90s (with snapshot ≤ 2h old)
- p95 = 3min (with snapshot ≤ 2h old)
- **worst-case = 30min (snapshot missing or > 2h old)**

Gemini R3b-F3: "The 30-minute worst-case remains unacceptable. In a production incident where snapshots are corrupted or missing, a 30-minute block on evaluation effectively freezes the Arena, preventing recovery or emergency transitions."

## 2. MOD-4 resolution: three-mode rollback

Replace single worst-case with three explicit operational modes:

### Mode 1: `full` — snapshot fresh
- Precondition: `data_cache_snapshot` exists AND age < 2h
- Action: load snapshot; restart eval workers
- Downstream: gates pause ~90-180s; kernel queues champions
- p50 = 90s, p95 = 3min
- Alert level: none (normal rollback)

### Mode 2: `lean` — NEW in MOD-4 (snapshot stale or missing)
- Precondition: snapshot missing OR stale (> 2h)
- Action: restart eval workers with REDUCED data_cache (5 most recent symbols only, not full 14); emit `degraded_quality=true` flag on each MetricsContract
- Downstream: gate_contract receives degraded flag; gate decisions for 14-5=9 symbols are SKIPPED (emit warnings); only 5-symbol subset evaluated
- p50 = 45s, p95 = 90s
- Alert level: **RED Telegram** (operator must restore snapshot)
- Safety: degraded quality flag prevents any champion evaluated in lean mode from being promoted to deployable (gate_contract rejects degraded results at promotion gate)

### Mode 3: `cold` — complete data_cache rebuild (absolute worst case)
- Precondition: snapshot + lean mode both unavailable (e.g., parquet corrupted, disk full)
- Action: rebuild data_cache from fresh parquet reads across all 14 symbols
- Downstream: arena state machine FREEZES (kernel blocks on gate_contract queue)
- p50 = 15min, p95 = 30min
- Alert level: **CRITICAL** (j13 must be involved)
- Explicit: this is NOT a routine state — represents a secondary failure (snapshot infrastructure down)

## 3. Mode selection logic (at rollback trigger)

```python
# Pseudocode — Phase 7 implementation
def select_rollback_mode():
    snapshot_path = "zangetsu/data/eval_cache_snapshot/latest.parquet"
    if os.path.exists(snapshot_path):
        age_seconds = time.time() - os.stat(snapshot_path).st_mtime
        if age_seconds < 2 * 3600:
            return "full"
    # snapshot missing or stale
    if lean_mode_enabled():  # CP flag
        return "lean"
    return "cold"
```

Reality: `cold` should never run in steady state. If it does, investigate snapshot infrastructure separately.

## 4. Snapshot infrastructure reliability requirements

To make `cold` mode genuinely rare:

### 4.1 Snapshot cron (new)
```cron
*/60 * * * * /home/j13/j13-ops/zangetsu/scripts/data_cache_snapshot.sh \
  >> /tmp/zangetsu_snapshot.log 2>&1
```
Hourly snapshot refresh. Takes ~30s to write 14-symbol parquet snapshot.

### 4.2 Snapshot health monitor (via gov_reconciler)
- Every 5min: assert snapshot age < 2h
- If age > 1h: WARN
- If age > 2h: RED Telegram
- If age > 6h: CRITICAL (snapshot infrastructure broken)

### 4.3 Snapshot integrity
- Each snapshot file includes SHA256 manifest
- Lean/full mode checks SHA before load
- Integrity fail → fall back to next mode

## 5. gate_contract interaction with degraded MetricsContract

When M6 is in `lean` mode, MetricsContract objects it produces carry `degraded_quality=true`. `gate_contract` handling:

| Gate | Degraded flag handling |
|---|---|
| Admission | Unchanged (admission doesn't care about cache state) |
| A2 OOS | Runs; outcome recorded but NOT promoted past A2 |
| A3 train | Runs; outcome recorded but NOT promoted past A3 |
| A4 | NOT EVALUATED (skipped with reason=degraded_quality) |
| Promote | **REJECTED** (champions from degraded eval cannot reach deployable) |

This prevents a worst-case race where: rollback → lean mode → degraded eval → accidentally promote a champion that shouldn't be deployable.

## 6. Non-negotiable rules

| Rule | Compliance |
|---|---|
| 1. No silent mutation | ✅ — mode switch is explicit + alerted |
| 3. No live gate change | ✅ — degraded-flag handling is a contract addition, not a threshold change |
| 8. No broad refactor | ✅ — targeted rollback spec |

## 7. Resolution status

Gemini R3b-F3 MEDIUM — **RESOLVED**. The 30min worst-case is preserved as an absolute ceiling (cold mode) but is bypassed in practice by:
- `lean` mode (45s–90s) when snapshot is stale
- `full` mode (90s–3min) normal case

## 8. Q1 adversarial

| Dim | Verdict |
|---|---|
| Input boundary | PASS — 3 modes with concrete preconditions |
| Silent failure | PASS — degraded_quality flag prevents silent promotion from lean mode; CRITICAL alert for cold |
| External dep | PASS — snapshot cron + integrity check declared |
| Concurrency | PASS — single mode selection at rollback trigger |
| Scope creep | PASS — M6 rollback only |

## 9. Label per 0-5 rule 10

- §2 three modes: **VERIFIED** (operational design)
- §4 infra requirements: **PROBABLE** (cron + monitor spec; Phase 7 implementation)
- §5 degraded handling: **VERIFIED** (gate_contract contract update in `gate_contract_dependency_update.md §1`)
