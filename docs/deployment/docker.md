# Docker Deployment

This project provides a production-like Docker Compose stack with MySQL, Redis,
the FastAPI backend, a Celery worker, and the Vue/Nginx frontend.

## 1. Prepare Environment

Copy the example file and replace every placeholder value before starting the
stack:

```powershell
Copy-Item .env.docker.example .env
```

At minimum, set strong values for:

- `SECRET_KEY`
- `MYSQL_ROOT_PASSWORD`
- `MYSQL_PASSWORD`
- `FIRST_SUPERUSER_PASSWORD`

## 2. Build And Start

```powershell
docker compose build backend worker frontend
docker compose up -d mysql redis backend worker frontend
```

The frontend is published at:

```text
http://127.0.0.1:8080
```

## 3. Initialize Database

Run migrations once after the database is healthy:

```powershell
docker compose exec -T backend python -m app.db.migrate
```

Create the initial administrator once:

```powershell
docker compose exec -T backend python -m app.db.init_db
```

## 4. Optional Async Detection

Synchronous detection remains the default. To move heavy detection work out of
the request thread, set this in `.env` and restart `backend` plus `worker`:

```text
ASYNC_DETECTION_ENABLED=true
CELERY_WORKER_CONCURRENCY=2
```

When enabled, `POST /api/detect/news` returns HTTP `202` with a `task_id`.
Clients should poll `GET /api/detect/tasks/{task_id}` until the task reaches
`succeeded` or `failed`.

## 5. Verify

```powershell
curl.exe -fsS http://127.0.0.1:8080/healthz
curl.exe -fsS http://127.0.0.1:8080/api/ready
docker compose ps worker
```

## Production HTTPS And Observability

For a production host with DNS already pointing to the server, set these
additional values in `.env`:

- `DOMAIN`
- `ACME_EMAIL`
- `GRAFANA_ADMIN_PASSWORD`

Then run:

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml build backend worker frontend
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T backend python -m app.db.migrate
```

Caddy publishes HTTPS on ports `80` and `443`, Prometheus scrapes the backend
inside the Docker network, and Grafana is provisioned with the backend overview
dashboard plus Prometheus, Tempo, and Pyroscope datasources.

## Continuous Profiling

The production overlay starts a `pyroscope` service and enables backend/worker
profiling by default:

```text
PYROSCOPE_ENABLED=true
PYROSCOPE_SERVER_ADDRESS=http://pyroscope:4040
PYROSCOPE_APPLICATION_NAME=newscred
PYROSCOPE_SAMPLE_RATE=100
```

Profiles are visible in Grafana through the `Pyroscope` datasource. The backend
reports as `newscred.backend`, and the Celery worker reports as
`newscred.worker`. Keep profiling labels low-cardinality; do not add user IDs,
article titles, source URLs, request IDs, or raw error messages as tags.

## Notes

- `docker-compose.redis.yml` remains available for Redis-only local development.
- The full stack stores MySQL, Redis, Chroma, and report files in Docker volumes.
- Redis DB `0` is used for app cache/rate limiting, while Celery defaults to
  Redis DB `1` through `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND`.
- Heavy-result caches are controlled by `AI_CACHE_*`, `WEB_SEARCH_CACHE_*`,
  `EMBEDDING_CACHE_*`, and `REPORT_GENERATION_CACHE_ENABLED`.
- Chroma is used through the backend process as a local persistent client. Do
  not add a public ChromaDB HTTP service or publish a Chroma port unless a
  security review confirms the installed ChromaDB version is no longer affected
  by `CVE-2026-45829`.
- Production deployments should replace every placeholder in `.env` and manage
  secrets through the target platform's secret manager when available.
- See `docs/deployment/runbook.md` for rollout, monitoring, backup, and rollback
  steps.
