# 02 — DB Snapshot

**Order:** TEAM ORDER 0-9Y-FINAL-0-MASTER-STATE-LOCK
**Phase:** 0 / sub-doc 02
**Captured (UTC):** 2026-04-28T02:55Z

## DB connection

`docker exec deploy-postgres-1 psql -U zangetsu -d zangetsu` (no host-level psql; container shell via Docker, per Alaya conventions). DB connection live; `now()` matches the wall clock.

## v0.7.1 schema — live counts

| Table / VIEW | Count | Note |
|---|---|---|
| `champion_pipeline` (VIEW over fresh) | **89** | unchanged since 0-9X-DB-MIGRATION |
| `champion_pipeline_staging` | **184** | unchanged |
| `champion_pipeline_fresh` | **89** | unchanged |
| `champion_pipeline_rejected` | **0** | (V10 lane records reject events; 0 since v0.7.1 went live) |
| `engine_telemetry` | **0** | (deprecated per 0-9Y-B2; canonical telemetry is engine.jsonl) |

`zangetsu_status` VIEW (carry-forward):
- `deployable_count = 0` (per 0-9X-PIPELINE-DEPLOYABLE-FLOW-DIAGNOSIS)
- `last_live_at_age_h ≈ 165 hours` (~6.9 days; the last admission was 2026-04-21T04:34Z, currently aged stale per §17.3 watch)
- Calcifer deploy_block.json present (NULL-safe writer from PR #57 confirmed live)

## v0.7.1 contract — required objects all present

Per `0-9Y-A/00_state_lock.md`: 8/8 v0.7.1 objects visible. No regression at FINAL-0 entry. The schema migration from PR #44 is intact.

## DB conservation

`champion_pipeline_staging - champion_pipeline_fresh - champion_pipeline_rejected = 184 - 89 - 0 = 95`. The 95-row gap is consistent with previously-rejected pre-staging entries that never advanced to fresh. Schema-level invariants hold.

## Conclusion

DB v0.7.1 is **healthy, stable, and read-consistent**. The carry-forward fact `deployable_count = 0` is the strategic blocker that this master order is designed to address. No DB-level pathology observed.
