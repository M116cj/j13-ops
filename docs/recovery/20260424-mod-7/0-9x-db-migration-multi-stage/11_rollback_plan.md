# 11 — Rollback Plan

## Backup Location
`/home/j13/db-backups/zangetsu-20260427T050506Z/full_before_0_9x_db_migration.dump`

SHA-256: `488ff17cfc8c52794eaef5a55f8f6c67e214bb4002d392648f67dd56d6b9b352`

## Restore Command (Path A — Full Dump Restore)

```bash
docker cp /home/j13/db-backups/zangetsu-20260427T050506Z/full_before_0_9x_db_migration.dump deploy-postgres-1:/tmp/restore.dump
docker exec deploy-postgres-1 psql -U zangetsu -d zangetsu_v5 -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO zangetsu;"
docker exec deploy-postgres-1 pg_restore --no-owner --dbname=postgresql://zangetsu:$ZV5_DB_PASSWORD@localhost/zangetsu_v5 /tmp/restore.dump
```

**WARNING**: This is destructive. It DROPs the public schema (all post-migration objects) and restores from backup.

## Restore Command (Path B — v0.7.1 Rollback Script)

```bash
docker cp /home/j13/j13-ops/zangetsu/migrations/postgres/rollback_v0.7.1.sql deploy-postgres-1:/tmp/rollback.sql
docker exec deploy-postgres-1 psql -U zangetsu -d zangetsu_v5 -f /tmp/rollback.sql
```

This reverses v0.7.1 only. v0.4/v0.6/v0.7.0 stay applied. NOT a full rollback.

## Expected Downtime
- Path A: ~30 seconds
- Path B: ~10 seconds

## Data Loss Risk
- Source DB had 0 rows in champion_pipeline at backup time
- Migration added 0 rows
- Worst-case: 0 row loss

## Decision Tree

```
Is migration causing live A1 crashes?
  ├── NO → don't rollback; investigate test failures separately
  └── YES → 
       ├── Are crashes due to schema mismatch?
       │    ├── YES → Path B (rollback v0.7.1, keep v0.7.0 baseline)
       │    └── NO → diagnose elsewhere
       └── Did data corruption occur?
            └── YES → Path A (full restore from backup)
```

## Authorization
- Path A: requires j13 explicit confirmation (destructive)
- Path B: requires j13 explicit confirmation (reverses governance migration)

Both paths must be authorized via Telegram message OR session-level "授權執行 rollback".

## Conservative Rollback Sequence

1. **STOP affected workers** (currently 0 alive, so no action needed)
2. **Disable A1/A23/A45 cron** (`watchdog.sh` becomes a no-op for arena workers)
3. **Take fresh pg_dump** (state at moment of rollback decision)
4. **Apply rollback** (Path A or B)
5. **Verify schema** (re-run Phase B inventory)
6. **Restart workers** ONLY AFTER explicit authorization

## rollback_commands.sh (NOT executable by default)

A bash script `/tmp/rollback_commands.sh` containing the above commands is committed alongside this evidence. By default, the script is `chmod 644` (NOT executable) to prevent accidental invocation. To run, j13 must explicitly `chmod +x` AND invoke with backup path argument.

## Recommendation

Migration is row-preserving (0 rows before, 0 rows after) and the schema is the v0.7.1 contract that code expects. **Rollback is technically available but operationally unnecessary** unless A1 starts producing schema-mismatch errors after cold-boot recovery.
