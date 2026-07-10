# Backup And Restore

The Docker deployment stores durable data in MySQL plus Docker volumes for
Chroma vectors and generated reports. Redis is treated as cache by default, but
its volume is archived so a restore can preserve any future persisted state.

## Backup

Run from the repository root on the deployment host:

```sh
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml" \
BACKUP_ROOT=/srv/newscred/backups \
RETENTION_DAYS=14 \
sh scripts/backup/backup_docker_stack.sh
```

The backup directory contains:

- `mysql.sql`
- `chroma_data.tgz`
- `report_data.tgz`
- `redis_data.tgz`
- `manifest.txt`
- `SHA256SUMS`

Store a second copy outside the host, such as object storage or an encrypted
backup vault. Local disk alone is not a disaster recovery plan.

## Restore

Restores are destructive. Use a staging host first whenever possible.

```sh
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml" \
RESTORE_CONFIRM=yes \
sh scripts/backup/restore_docker_stack.sh /srv/newscred/backups/20260706T120000Z
```

After restore, verify:

```sh
curl -fsS https://$DOMAIN/api/ready
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

## Recovery Objectives

- Target RPO: 24 hours until scheduled off-host backups are configured.
- Target RTO: 60 minutes for a Docker host restore with images already built.
- Test restore at least monthly and after schema-changing releases.
