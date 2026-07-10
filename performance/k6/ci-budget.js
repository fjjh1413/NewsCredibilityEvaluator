import http from 'k6/http'
import { check, sleep } from 'k6'

const BASE_URL = (__ENV.BASE_URL || 'http://127.0.0.1:8000/api').replace(/\/$/, '')

export const options = {
  scenarios: {
    smoke_budget: {
      executor: 'constant-vus',
      vus: Number(__ENV.VUS || 2),
      duration: __ENV.DURATION || '30s'
    }
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<500'],
    'http_req_duration{name:health}': ['p(95)<250'],
    'http_req_duration{name:ready}': ['p(95)<500'],
    'http_req_duration{name:metrics}': ['p(95)<500']
  }
}

export default function () {
  const health = http.get(`${BASE_URL}/health`, { tags: { name: 'health' } })
  check(health, {
    'health is ok': (response) => response.status === 200
  })

  const ready = http.get(`${BASE_URL}/ready`, { tags: { name: 'ready' } })
  check(ready, {
    'ready responds': (response) => response.status === 200 || response.status === 503
  })

  const metrics = http.get(`${BASE_URL}/metrics`, { tags: { name: 'metrics' } })
  check(metrics, {
    'metrics are exposed internally': (response) => response.status === 200
  })

  sleep(Number(__ENV.SLEEP_SECONDS || 1))
}

