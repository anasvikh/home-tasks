#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "Usage: $0 <db_path> <backup_dir> <retention>" >&2
  exit 1
fi

DB_PATH=$1
BACKUP_DIR=$2
RETENTION=$3
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BASENAME=$(basename "${DB_PATH}")
TARGET="${BACKUP_DIR}/${BASENAME%.*}-${TIMESTAMP}.sqlite3.gz"

mkdir -p "${BACKUP_DIR}"

RAW_COPY=$(mktemp "${BACKUP_DIR}/db.XXXXXX.sqlite3")
trap 'rm -f "${RAW_COPY}"' EXIT

sqlite3 "${DB_PATH}" ".backup '${RAW_COPY}'"
gzip -c "${RAW_COPY}" > "${TARGET}"
rm -f "${RAW_COPY}"
trap - EXIT

if [[ ${RETENTION} -gt 0 && -d "${BACKUP_DIR}" ]]; then
  if compgen -G "${BACKUP_DIR}"/*.sqlite3.gz > /dev/null; then
    ls -1t "${BACKUP_DIR}"/*.sqlite3.gz | tail -n +$((RETENTION + 1)) | xargs -r rm -f
  fi
fi

echo "Backup stored at ${TARGET}"
