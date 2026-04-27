#!/usr/bin/env bash
# rollback_commands.sh — TEAM ORDER 0-9X-DB-MIGRATION-MULTI-STAGE
# NOT EXECUTABLE BY DEFAULT (chmod 644). Make executable explicitly via:
#   chmod +x rollback_commands.sh
# Run with explicit backup directory argument:
#   ./rollback_commands.sh /home/j13/db-backups/zangetsu-20260427T050506Z

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <backup_dir>"
  echo "Example: $0 /home/j13/db-backups/zangetsu-20260427T050506Z"
  exit 1
fi

BACKUP_DIR="$1"
DUMP_FILE="$BACKUP_DIR/full_before_0_9x_db_migration.dump"

if [ ! -f "$DUMP_FILE" ]; then
  echo "ERROR: backup dump not found at $DUMP_FILE"
  exit 2
fi

echo "WARNING: This will DROP the public schema in zangetsu_v5 and restore from backup."
echo "         Backup dump: $DUMP_FILE"
echo "         SHA-256: $(sha256sum "$DUMP_FILE" | cut -d' ' -f1)"
echo "         Expected: 488ff17cfc8c52794eaef5a55f8f6c67e214bb4002d392648f67dd56d6b9b352"
echo
read -p "Type 'CONFIRM ROLLBACK' to proceed: " confirm
if [ "$confirm" != "CONFIRM ROLLBACK" ]; then
  echo "Aborted."
  exit 3
fi

echo "Step 1: Take pre-rollback snapshot..."
TS=$(date -u +%Y%m%dT%H%M%SZ)
docker exec deploy-postgres-1 pg_dump -U zangetsu -d zangetsu_v5 --format=custom --file=/tmp/pre_rollback_$TS.dump
docker cp deploy-postgres-1:/tmp/pre_rollback_$TS.dump $BACKUP_DIR/pre_rollback_$TS.dump

echo "Step 2: Restore from backup..."
docker cp "$DUMP_FILE" deploy-postgres-1:/tmp/restore.dump
docker exec deploy-postgres-1 psql -U zangetsu -d zangetsu_v5 -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO zangetsu;"
docker exec deploy-postgres-1 pg_restore --no-owner --dbname=postgresql://zangetsu:$ZV5_DB_PASSWORD@localhost/zangetsu_v5 /tmp/restore.dump

echo "Step 3: Verify schema..."
docker exec deploy-postgres-1 psql -U zangetsu -d zangetsu_v5 -c "\dt"

echo "Rollback complete. Workers should remain stopped until explicit authorization to restart."
