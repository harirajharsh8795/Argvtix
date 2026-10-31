#!/usr/bin/env bash
# ==============================================================================
# Proofline Production Database Backup Script
# Creates a compressed, timestamped pg_dump with SHA256 checksum verification
# ==============================================================================
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/proofline}"
TIMESTAMP="$(date -u +"%Y%m%d_%H%M%SZ")"
BACKUP_FILE="${BACKUP_DIR}/proofline_db_${TIMESTAMP}.sql.gz"
CHECKSUM_FILE="${BACKUP_FILE}.sha256"

mkdir -p "${BACKUP_DIR}"

echo "[INFO] Starting database backup at ${TIMESTAMP}..."

# Execute pg_dump with compression
PGPASSWORD="${POSTGRES_PASSWORD:-proofline_secure_pass_2026}" \
pg_dump -h "${POSTGRES_HOST:-localhost}" \
        -p "${POSTGRES_PORT:-5432}" \
        -U "${POSTGRES_USER:-proofline}" \
        -d "${POSTGRES_DB:-proofline}" \
        --format=plain \
        --no-owner \
        --clean \
        --if-exists | gzip -9 > "${BACKUP_FILE}"

# Generate SHA256 checksum
sha256sum "${BACKUP_FILE}" > "${CHECKSUM_FILE}"

echo "[PASS] Backup successfully created:"
echo "       Archive:  ${BACKUP_FILE}"
echo "       Checksum: $(cat "${CHECKSUM_FILE}")"
