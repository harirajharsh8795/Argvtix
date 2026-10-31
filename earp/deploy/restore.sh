#!/usr/bin/env bash
# ==============================================================================
# Proofline Production Database Restore Script
# Verifies SHA256 integrity checksum, drops active connections, and restores DB
# ==============================================================================
set -euo pipefail

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <path_to_backup_sql_gz>"
    exit 1
fi

BACKUP_FILE="$1"
CHECKSUM_FILE="${BACKUP_FILE}.sha256"

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "[FAIL] Backup file not found: ${BACKUP_FILE}"
    exit 1
fi

# Verify SHA256 checksum if available
if [ -f "${CHECKSUM_FILE}" ]; then
    echo "[INFO] Verifying SHA256 checksum..."
    sha256sum -c "${CHECKSUM_FILE}" || {
        echo "[CRITICAL] Checksum verification failed! Backup may be corrupted."
        exit 1
    }
    echo "[PASS] Checksum verified."
fi

TARGET_DB="${TARGET_DB:-proofline}"
echo "[INFO] Restoring database to '${TARGET_DB}'..."

# Drop existing connections and restore
PGPASSWORD="${POSTGRES_PASSWORD:-proofline_secure_pass_2026}" \
psql -h "${POSTGRES_HOST:-localhost}" \
     -p "${POSTGRES_PORT:-5432}" \
     -U "${POSTGRES_USER:-proofline}" \
     -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${TARGET_DB}' AND pid <> pg_backend_pid();"

gunzip -c "${BACKUP_FILE}" | \
PGPASSWORD="${POSTGRES_PASSWORD:-proofline_secure_pass_2026}" \
psql -h "${POSTGRES_HOST:-localhost}" \
     -p "${POSTGRES_PORT:-5432}" \
     -U "${POSTGRES_USER:-proofline}" \
     -d "${TARGET_DB}"

echo "[PASS] Database restore completed successfully."
