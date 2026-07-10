#!/usr/bin/env sh
set -eu

if [ "${1:-}" = "" ]; then
  echo "Usage: RESTORE_CONFIRM=yes $0 <backup-directory>" >&2
  exit 2
fi

if [ "${RESTORE_CONFIRM:-}" != "yes" ]; then
  echo "Refusing to restore without RESTORE_CONFIRM=yes." >&2
  exit 2
fi

PROJECT_NAME="${COMPOSE_PROJECT_NAME:-news-credibility-evaluator}"
BACKUP_DIR="$1"

compose() {
  # COMPOSE_FILES may be set to "-f docker-compose.yml -f docker-compose.prod.yml".
  # shellcheck disable=SC2086
  docker compose ${COMPOSE_FILES:-} "$@"
}

restore_volume() {
  volume_name="$1"
  archive_name="$2"

  test -f "${BACKUP_DIR}/${archive_name}"
  docker volume inspect "${volume_name}" >/dev/null
  docker run --rm \
    -v "${volume_name}:/target" \
    -v "${BACKUP_DIR}:/backup:ro" \
    alpine:3.20 \
    sh -c "find /target -mindepth 1 -maxdepth 1 -exec rm -rf {} + && tar -xzf /backup/${archive_name} -C /target"
}

test -f "${BACKUP_DIR}/mysql.sql"
test -f "${BACKUP_DIR}/SHA256SUMS"

(
  cd "${BACKUP_DIR}"
  sha256sum -c SHA256SUMS
)

compose up -d mysql redis

compose exec -T mysql sh -c 'MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE"' \
  < "${BACKUP_DIR}/mysql.sql"

restore_volume "${PROJECT_NAME}_chroma_data" "chroma_data.tgz"
restore_volume "${PROJECT_NAME}_report_data" "report_data.tgz"
restore_volume "${PROJECT_NAME}_redis_data" "redis_data.tgz"

compose restart backend frontend

echo "Restore completed from ${BACKUP_DIR}"
