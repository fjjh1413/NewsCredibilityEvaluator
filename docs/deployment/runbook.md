# Production Runbook

This runbook is the operator checklist for the Docker production deployment.

## Preflight

- DNS `A`/`AAAA` records point `DOMAIN` to the deployment host.
- Ports `80` and `443` are open to the internet.
- `.env` is present on the host and contains non-placeholder values for all
  required secrets.
- `BACKEND_CORS_ORIGINS` is set by `docker-compose.prod.yml` to
  `https://$DOMAIN`.
- A recent backup exists and a restore has been tested in staging.
- ChromaDB is not exposed as a public HTTP service. The production stack should
  use the backend's embedded `chromadb.PersistentClient` with the
  `chroma_data:/data/chroma` volume only.
- If async detection is enabled, `worker` must be running and Redis must be
  healthy. Use `ASYNC_DETECTION_ENABLED=false` to fall back to synchronous
  detection during an incident.
- If continuous profiling is enabled, `pyroscope` must be running and Grafana
  should show the `Pyroscope` datasource.

## Deploy

Manual GitHub Actions deployment requires these `production` environment
secrets:

- `PRODUCTION_SSH_HOST`
- `PRODUCTION_SSH_USER`
- `PRODUCTION_SSH_KEY`
- `PRODUCTION_APP_DIR`

The deployment host must already contain a git checkout of this repository and
its production `.env` file.

Configure `FEISHU_WEBHOOK_URL` in the production `.env` file. Treat the webhook
as a secret; do not commit the real URL to git.

```sh
docker compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.prod.yml build backend worker frontend
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T backend python -m app.db.migrate
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T backend python -m app.db.init_db
```

## Smoke Test

```sh
curl -fsS https://$DOMAIN/healthz
curl -fsS https://$DOMAIN/api/ready
curl -I https://$DOMAIN/
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps worker
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps pyroscope
```

Confirm:

- `Strict-Transport-Security` is present.
- `/api/ready` returns status `ok`.
- `/api/metrics` is not exposed through the public frontend proxy.

## Monitoring

Prometheus scrapes `backend:8000/api/metrics` on the internal Docker network.
Grafana provisions a `Backend Overview` dashboard with request rate, 5xx ratio,
and p95 latency. Alertmanager sends notifications to the internal
`feishu-alerts` bridge, which converts Alertmanager payloads to Feishu custom
bot text messages.

First hour after deployment:

- Watch backend 5xx ratio.
- Watch backend p95 latency.
- Watch `detection_tasks_total` by status and
  `detection_task_duration_seconds` p95 if async detection is enabled.
- Watch `cache_events_total` for low hit rate or repeated Redis errors.
- Open Grafana Profiles and compare `newscred.backend` versus
  `newscred.worker` CPU hot paths when p95 latency or task duration regresses.
- Check logs by `request_id` for any failed smoke test.
- Manually run the critical detection flow.

## Alerts

### BackendUnavailable

Meaning: Prometheus cannot scrape the backend metrics endpoint.

First checks:

```sh
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=100 backend
curl -fsS http://127.0.0.1:8080/api/ready
```

Escalate if the backend container is restarting or `/api/ready` is degraded.

### BackendHighErrorRate

Meaning: backend 5xx responses exceeded 1% for 5 minutes.

First checks:

```sh
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=200 backend
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T backend python -m app.db.migrate
```

Look for database connectivity errors, missing secrets, failed external API
calls, and repeated request IDs.

### BackendHighLatencyP95

Meaning: p95 request duration exceeded 2 seconds for 10 minutes.

First checks:

```sh
docker compose -f docker-compose.yml -f docker-compose.prod.yml stats --no-stream
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=100 mysql
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=100 backend
```

Check slow external AI/search calls, MySQL pressure, and host CPU/memory.

### DetectionWorkerUnavailable

Meaning: async detection is enabled but tasks stay queued or fail quickly.

First checks:

```sh
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps worker redis
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=200 worker
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T backend python -m app.db.migrate
```

If the worker cannot be restored quickly, set `ASYNC_DETECTION_ENABLED=false`
and restart backend to return to synchronous detection.

### CacheDegraded

Meaning: Redis cache errors increase or hit rate drops unexpectedly.

First checks:

```sh
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=100 redis
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=100 backend
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=100 worker
```

Temporarily disable affected caches with `AI_CACHE_ENABLED=false`,
`WEB_SEARCH_CACHE_ENABLED=false`, `EMBEDDING_CACHE_ENABLED=false`, or
`REPORT_GENERATION_CACHE_ENABLED=false`.

### ProfilingUnavailable

Meaning: profiles are missing in Grafana while `PYROSCOPE_ENABLED=true`.

First checks:

```sh
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps pyroscope backend worker
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=100 pyroscope
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=100 backend
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=100 worker
```

If profiling causes startup risk during an incident, set
`PYROSCOPE_ENABLED=false` and restart backend plus worker. If profiling is meant
to be mandatory for a load-test window, set `PYROSCOPE_REQUIRED=true` so missing
SDK/configuration fails fast.

## CI Performance Budgets

Every PR runs two performance gates:

- Lighthouse CI against the built frontend in `frontend/lighthouserc.cjs`.
- k6 API smoke budget in `performance/k6/ci-budget.js`.

When either gate fails, inspect the uploaded `lighthouseci` or
`k6-performance-budget` artifact before raising budgets. Budget increases must
include a short explanation and a follow-up optimization issue.

## Backup

```sh
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml" \
BACKUP_ROOT=/srv/newscred/backups \
RETENTION_DAYS=14 \
sh scripts/backup/backup_docker_stack.sh
```

Copy the resulting directory off-host. See
`docs/deployment/backup-restore.md` for restore instructions.

## Rollback

Rollback triggers:

- Backend 5xx rate is more than 2x baseline for 5 minutes.
- p95 latency is more than 50% above baseline for 10 minutes.
- Authentication, detection, or admin workflows are broken.
- A security vulnerability is discovered in the release.

Rollback steps:

```sh
git checkout <previous-release-tag-or-commit>
docker compose -f docker-compose.yml -f docker-compose.prod.yml build backend worker frontend
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d backend worker frontend
curl -fsS https://$DOMAIN/api/ready
```

If the release included a database migration that must be reverted, restore from
the latest verified backup in staging first, then production.
