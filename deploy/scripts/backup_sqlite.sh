#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd -P)"
COMPOSE_FILE="${COMPOSE_FILE:-${PROJECT_ROOT}/deploy/docker-compose.yml}"
ENV_FILE="${ENV_FILE:-${PROJECT_ROOT}/.env}"
SERVICE_NAME="${SERVICE_NAME:-cleaning-bot}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required" >&2
  exit 1
fi

BACKUP_DIR="${PROJECT_ROOT}/backups"
mkdir -p "${BACKUP_DIR}"

# Create a consistent SQLite backup inside the container and copy it to the shared volume.
backup_path=$(docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" \
  exec -T "${SERVICE_NAME}" python - <<'PY'
import datetime
import pathlib
import sqlite3
import os

DATABASE = pathlib.Path(os.environ.get("DATABASE_PATH", "/data/db.sqlite3"))
BACKUP_DIR = pathlib.Path("/backups")
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

if not DATABASE.exists():
    raise SystemExit(f"Database not found at {DATABASE}")

stamp = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
destination = BACKUP_DIR / f"assignments-{stamp}.db"
with sqlite3.connect(f"file:{DATABASE}?mode=ro", uri=True) as source, sqlite3.connect(destination) as target:
    source.backup(target)

print(destination)
PY
)
backup_path="${backup_path##*$'\n'}"
echo "Backup created at ${BACKUP_DIR}/$(basename "${backup_path}")"

# Remove old backups beyond retention window
if [[ -n "${RETENTION_DAYS}" ]]; then
  find "${BACKUP_DIR}" -type f -name 'assignments-*.db' -mtime +"${RETENTION_DAYS}" -delete
fi
