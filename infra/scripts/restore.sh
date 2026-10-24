#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

if [ $# -lt 1 ]; then
  echo "Usage: $0 <path_to_db_backup.sql.gz>"
  echo "Example: $0 data/backups/db_20261024_120000Z.sql.gz"
  exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "${BACKUP_FILE}" ]; then
  echo "Error: Backup file '${BACKUP_FILE}' not found." >&2
  exit 1
fi

echo "=== Restoring database from: ${BACKUP_FILE} ==="

# Stop consumers
echo "Stopping API and Worker services..."
docker compose -f "${ROOT_DIR}/compose.yaml" stop api worker

# Restore database
echo "Restoring PostgreSQL database..."
gunzip -c "${BACKUP_FILE}" | docker compose -f "${ROOT_DIR}/compose.yaml" exec -T postgres psql -U mediaapp -d mediaapp -v ON_ERROR_STOP=1

# Restart consumers
echo "Restarting API and Worker services..."
docker compose -f "${ROOT_DIR}/compose.yaml" start api worker

echo "Database restore completed successfully."
