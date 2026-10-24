#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BACKUP_DIR="${ROOT_DIR}/data/backups"
TIMESTAMP="$(date -u +"%Y%m%d_%H%M%SZ")"

mkdir -p "${BACKUP_DIR}"

DB_BACKUP_FILE="${BACKUP_DIR}/db_${TIMESTAMP}.sql.gz"
METADATA_BACKUP_FILE="${BACKUP_DIR}/metadata_${TIMESTAMP}.json"

echo "=== Local Media Downloader Backup [${TIMESTAMP}] ==="

# 1. Database dump
echo "Dumping PostgreSQL database..."
docker compose -f "${ROOT_DIR}/compose.yaml" exec -T postgres pg_dump -U mediaapp mediaapp | gzip -c > "${DB_BACKUP_FILE}"

if [[ ! -s "${DB_BACKUP_FILE}" ]]; then
  echo "Error: Database backup file is empty." >&2
  exit 1
fi
echo "Database backup created: ${DB_BACKUP_FILE} ($(du -h "${DB_BACKUP_FILE}" | cut -f1))"

# 2. Export Metadata via API or direct psql
echo "Exporting catalog metadata..."
docker compose -f "${ROOT_DIR}/compose.yaml" exec -T postgres psql -U mediaapp -d mediaapp -t -c \
  "SELECT json_agg(t) FROM (SELECT id, relative_path, original_filename_safe, container, size_bytes, sha256, created_at FROM assets WHERE deleted_at IS NULL) t;" \
  > "${METADATA_BACKUP_FILE}"

echo "Metadata backup created: ${METADATA_BACKUP_FILE}"
echo "Backup completed successfully."
