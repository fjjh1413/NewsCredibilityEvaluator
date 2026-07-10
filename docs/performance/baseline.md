# Performance Baseline

This baseline makes latency visible before optimization work starts.

## Signals

- API p95/p99: Prometheus metric `http_request_duration_seconds`.
- DB query latency: Prometheus metric `db_query_duration_seconds`.
- Detection stages: OpenTelemetry spans named `detection.*`.
- Async task throughput: Prometheus metric `detection_tasks_total`.
- Async task latency: Prometheus metric `detection_task_duration_seconds`.
- Cache behavior: Prometheus metric `cache_events_total`.
- Continuous profiling: Grafana Pyroscope applications `newscred.backend` and
  `newscred.worker`.
- Frontend bundle size: `frontend/dist/bundle-stats.html` and `bundle-stats.json`.
- Load-test latency: k6 `http_req_duration` grouped by request tag `name`.

## Traces

Tracing is disabled by default in local Docker and enabled by default in the
production compose overlay.

Local opt-in:

```powershell
$env:OTEL_TRACING_ENABLED="true"
$env:OTEL_TRACE_SAMPLE_RATIO="1.0"
docker compose --env-file .env.docker.example -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Production:

```powershell
docker compose --env-file .env -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Open Grafana and use the `Tempo` datasource to search traces. Start from a slow
HTTP request, then expand child spans such as `detection.rag_search`,
`detection.web_search`, `detection.llm_analysis`, `detection.rule_score`, and
`detection.db_save`.

Recommended initial sampling:

- `OTEL_TRACE_SAMPLE_RATIO=1.0` in local and short staging tests.
- `OTEL_TRACE_SAMPLE_RATIO=0.10` in production until real traffic volume is known.

## Continuous Profiling

Production compose starts Pyroscope and enables the Python SDK for both the API
process and Celery worker. Use Grafana Profiles to answer:

- Is CPU time in request handling, Celery worker execution, PDF generation, or
  external-client serialization?
- Did a change move CPU from API submission to the worker as intended?
- Are repeated detections spending time in cached paths or recomputing
  embedding/search/LLM/report work?

Local opt-in through Docker:

```powershell
$env:PYROSCOPE_ENABLED="true"
$env:PYROSCOPE_SERVER_ADDRESS="http://pyroscope:4040"
docker compose --env-file .env.docker.example -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Use only low-cardinality tags such as `role`, `env`, `version`, and static
operation names. Never add user IDs, request IDs, source URLs, article titles,
or raw error messages as profile labels.

## Frontend Bundle Analysis

```powershell
cd frontend
npm run build:analyze
```

Outputs:

- `frontend/dist/bundle-stats.html` for interactive inspection.
- `frontend/dist/bundle-stats.json` for machine-readable size tracking.

Start by checking the `echarts`, `element-plus`, and route chunks. The first
optimization target is any chart/admin chunk loaded before it is needed.

## k6 Baseline

Health-only baseline:

```powershell
Get-Content -Raw .\performance\k6\baseline.js | docker run --rm -i --network news-credibility-evaluator_default `
  -e BASE_URL=http://backend:8000/api `
  grafana/k6:2.1.0 run -
```

Authenticated read baseline:

```powershell
Get-Content -Raw .\performance\k6\baseline.js | docker run --rm -i --network news-credibility-evaluator_default `
  -e BASE_URL=http://backend:8000/api `
  -e USERNAME=admin `
  -e PASSWORD=replace_with_admin_password `
  -e VUS=10 `
  -e DURATION=3m `
  grafana/k6:2.1.0 run -
```

Detection write-path baseline for staging only:

```powershell
Get-Content -Raw .\performance\k6\baseline.js | docker run --rm -i --network news-credibility-evaluator_default `
  -e BASE_URL=http://backend:8000/api `
  -e USERNAME=admin `
  -e PASSWORD=replace_with_admin_password `
  -e RUN_DETECT=true `
  -e ENABLE_WEB_SEARCH=false `
  -e VUS=3 `
  -e DURATION=1m `
  grafana/k6:2.1.0 run -
```

Keep `ENABLE_WEB_SEARCH=false` for routine baselines to avoid measuring external
provider variance and cost. Run a separate external-dependency test when needed.

CI smoke budget:

```powershell
Get-Content -Raw .\performance\k6\ci-budget.js | docker run --rm -i --network news-credibility-evaluator_default `
  -e BASE_URL=http://backend:8000/api `
  -e VUS=2 `
  -e DURATION=30s `
  grafana/k6:2.1.0 run -
```

Frontend budget:

```powershell
cd frontend
npm run build
npm run lhci
```

## First Review Queries

Prometheus examples:

```promql
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, route, method))
histogram_quantile(0.95, sum(rate(db_query_duration_seconds_bucket[5m])) by (le, operation, status))
histogram_quantile(0.95, sum(rate(detection_task_duration_seconds_bucket[5m])) by (le, status))
sum(rate(http_requests_total{status_class=~"5xx"}[5m])) by (route, method)
sum(rate(detection_tasks_total[5m])) by (status)
sum(rate(cache_events_total[5m])) by (namespace, outcome)
```

Use these numbers to choose the first real optimization target. Do not tune
worker counts, cache TTLs, or SQL indexes until the baseline identifies the
specific bottleneck.

## Third-Phase Optimization Checks

When `ASYNC_DETECTION_ENABLED=true`, compare `POST /api/detect/news` p95 before
and after the switch. The submit request should become mostly database/queue
time, while full detection duration moves to `detection_task_duration_seconds`.

Cache checks:

- `llm_chat`: repeated same prompt should move from `miss/set` to `hit`.
- `web_search`: empty results are not cached; persistent `miss` with Bocha
  errors usually means the upstream search provider is unhealthy.
- `embedding`: batch jobs should show a rising hit rate after repeated vector
  sync or similar-content retrieval.
- report generation: repeated report requests for the same detection should
  avoid PDF conversion while both generated files still exist.
