# 01 — Backup Report

## Backup Location

`/home/j13/db-backups/zangetsu-20260427T050506Z/`

## Files

| File | Size | Purpose |
| --- | --- | --- |
| `full_before_0_9x_db_migration.dump` | 13794 bytes | pg_dump --format=custom (full DB; restore via `pg_restore`) |
| `schema_before.sql` | 8347 bytes | pg_dump --schema-only (DDL only, plain SQL) |
| `data_before.sql` | 2617 bytes | pg_dump --data-only (data only, plain SQL) |
| `SHA256SUMS.txt` | 267 bytes | SHA-256 hashes of all 3 files above |
| `restore_list.txt` | (54 lines) | pg_restore --list output verifying dump integrity |

## SHA-256 Manifest

```
f687221cecce97f1ce50f2ceea92c5f3cba72f39be962f4094f96f683a0423c1  data_before.sql
488ff17cfc8c52794eaef5a55f8f6c67e214bb4002d392648f67dd56d6b9b352  full_before_0_9x_db_migration.dump
27b9dd701238f52fe74305ad88bb84b24cf4b03cbb6dab8923a8402922c280ad  schema_before.sql
```

## Verification
- `pg_restore --list` succeeded: 43 TOC entries, format=CUSTOM, dump version 1.14-0, source PG 15.17
- All file sizes > 0
- SHA256 manifest exists

## Restore Command (template)

```bash
docker cp /home/j13/db-backups/zangetsu-20260427T050506Z/full_before_0_9x_db_migration.dump deploy-postgres-1:/tmp/restore.dump
docker exec deploy-postgres-1 pg_restore --clean --if-exists --no-owner --dbname=postgresql://zangetsu:$ZV5_DB_PASSWORD@localhost/zangetsu_v5 /tmp/restore.dump
```

→ **Backup PASS.**
