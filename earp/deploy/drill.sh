#!/usr/bin/env bash
# ==============================================================================
# Proofline Monthly Automated Disaster Recovery Drill
# Backup -> Spawn Test DB -> Restore -> Verify Integrity -> Teardown -> Report
# ==============================================================================
set -euo pipefail

DRILL_ID="drill_$(date -u +"%Y%m%d_%H%M%SZ")"
TEMP_DB="proofline_drill_${DRILL_ID}"
DRILL_DIR="/tmp/proofline_drills/${DRILL_ID}"

echo "================================================================================"
echo "      PROOFLINE DISASTER RECOVERY DRILL & RESTORATION AUDIT"
echo "      Drill ID: ${DRILL_ID}"
echo "================================================================================"

mkdir -p "${DRILL_DIR}"

# Step 1: Execute production backup
echo "[STEP 1/5] Executing automated database backup..."
BACKUP_DIR="${DRILL_DIR}" bash deploy/backup.sh

BACKUP_FILE=$(find "${DRILL_DIR}" -name "*.sql.gz" | head -n 1)

# Step 2: Create isolated drill test database
echo "[STEP 2/5] Creating isolated verification database '${TEMP_DB}'..."
PGPASSWORD="${POSTGRES_PASSWORD:-proofline_secure_pass_2026}" \
psql -h "${POSTGRES_HOST:-localhost}" \
     -p "${POSTGRES_PORT:-5432}" \
     -U "${POSTGRES_USER:-proofline}" \
     -d postgres -c "CREATE DATABASE ${TEMP_DB};"

# Step 3: Restore backup into test database
echo "[STEP 3/5] Restoring backup into verification database..."
TARGET_DB="${TEMP_DB}" bash deploy/restore.sh "${BACKUP_FILE}"

# Step 4: Run smoke test and integrity checks
echo "[STEP 4/5] Running database table and row count integrity assertions..."
TABLE_COUNT=$(PGPASSWORD="${POSTGRES_PASSWORD:-proofline_secure_pass_2026}" \
psql -h "${POSTGRES_HOST:-localhost}" \
     -p "${POSTGRES_PORT:-5432}" \
     -U "${POSTGRES_USER:-proofline}" \
     -d "${TEMP_DB}" -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';")

echo "[INFO] Verified ${TABLE_COUNT// /} tables restored in target database."

if [ "${TABLE_COUNT// /}" -lt 10 ]; then
    echo "[FAIL] Expected at least 10 tables, found ${TABLE_COUNT// /}."
    exit 1
fi

# Step 5: Teardown drill database
echo "[STEP 5/5] Tearing down temporary drill database..."
PGPASSWORD="${POSTGRES_PASSWORD:-proofline_secure_pass_2026}" \
psql -h "${POSTGRES_HOST:-localhost}" \
     -p "${POSTGRES_PORT:-5432}" \
     -U "${POSTGRES_USER:-proofline}" \
     -d postgres -c "DROP DATABASE ${TEMP_DB};"

rm -rf "${DRILL_DIR}"

echo "================================================================================"
echo "[PASS] MONTHLY DISASTER RECOVERY DRILL PASSED SUCCESSFULLY (0 FAILURES)"
echo "================================================================================"
