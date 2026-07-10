#!/usr/bin/env sh
set -eu

PROJECT_NAME="${COMPOSE_PROJECT_NAME:-news-credibility-evaluator}"
BACKUP_ROOT="${BACKUP_ROOT:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="${BACKUP_ROOT}/${TIMESTAMP}"

compose() {
  # COMPOSE_FILES may be set to "-f docker-compose.yml -f docker-compose.prod.yml".
  # shellcheck disable=SC2086
  docker compose ${COMPOSE_FILES:-} "$@"
}

archive_volume() {
  volume_name="$1"
  output_name="$2"

  docker volume inspect "${volume_name}" >/dev/null
  docker run --rm \
    -v "${volume_name}:/source:ro" \
    -v "${BACKUP_DIR}:/backup" \
    alpine:3.20 \
    sh -c "cd /source && tar -czf /backup/${output_name} ."
}

mkdir -p "${BACKUP_DIR}"

compose exec -T mysql sh -c \
  'MYSQL_PWD="$MYSQL_PASSWORD" mysqldump -u"$MYSQL_USER" --single-transaction --routines --triggers --no-tablespaces "$MYSQL_DATABASE"' \
  > "${BACKUP_DIR}/mysql.sql"

archive_volume "${PROJECT_NAME}_chroma_data" "chroma_data.tgz"
archive_volume "${PROJECT_NAME}_report_data" "report_data.tgz"
archive_volume "${PROJECT_NAME}_redis_data" "redis_data.tgz"

{
  echo "timestamp=${TIMESTAMP}"
  echo "project=${PROJECT_NAME}"
  echo "created_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "contents=mysql.sql,chroma_data.tgz,report_data.tgz,redis_data.tgz"
} > "${BACKUP_DIR}/manifest.txt"

(
  cd "${BACKUP_DIR}"
  sha256sum mysql.sql chroma_data.tgz report_data.tgz redis_data.tgz manifest.txt > SHA256SUMS
)

find "${BACKUP_ROOT}" -mindepth 1 -maxdepth 1 -type d -mtime "+${RETENTION_DAYS}" -print -exec rm -rf {} \;

echo "Backup created at ${BACKUP_DIR}"
