import http from 'k6/http'
import { check, group, sleep } from 'k6'

const BASE_URL = (__ENV.BASE_URL || 'http://127.0.0.1:8000/api').replace(/\/$/, '')
const USERNAME = __ENV.USERNAME || ''
const PASSWORD = __ENV.PASSWORD || ''
const RUN_DETECT = (__ENV.RUN_DETECT || 'false').toLowerCase() === 'true'
const RUN_ADMIN = (__ENV.RUN_ADMIN || 'false').toLowerCase() === 'true'
const ENABLE_WEB_SEARCH = (__ENV.ENABLE_WEB_SEARCH || 'false').toLowerCase() === 'true'

export const options = {
  scenarios: {
    baseline: {
      executor: 'constant-vus',
      vus: Number(__ENV.VUS || 5),
      duration: __ENV.DURATION || '1m'
    }
  },
  thresholds: {
    http_req_failed: ['rate<0.05'],
    http_req_duration: ['p(95)<1000'],
    'http_req_duration{name:health}': ['p(95)<300'],
    'http_req_duration{name:ready}': ['p(95)<500'],
    'http_req_duration{name:detect_history}': ['p(95)<800'],
    'http_req_duration{name:detect_news}': ['p(95)<15000']
  }
}

export function setup() {
  if (!USERNAME || !PASSWORD) {
    return { token: null }
  }

  const loginResponse = http.post(
    `${BASE_URL}/auth/login`,
    JSON.stringify({ username: USERNAME, password: PASSWORD }),
    {
      headers: { 'Content-Type': 'application/json' },
      tags: { name: 'auth_login' }
    }
  )

  check(loginResponse, {
    'login succeeded': (response) => response.status === 200
  })

  const body = safeJson(loginResponse)
  return {
    token: body?.data?.access_token || null
  }
}

export default function (state) {
  const headers = {
    'Content-Type': 'application/json'
  }
  if (state.token) {
    headers.Authorization = `Bearer ${state.token}`
  }

  group('public health', () => {
    const health = http.get(`${BASE_URL}/health`, { tags: { name: 'health' } })
    check(health, {
      'health is ok': (response) => response.status === 200
    })

    const ready = http.get(`${BASE_URL}/ready`, { tags: { name: 'ready' } })
    check(ready, {
      'ready responds': (response) => response.status === 200 || response.status === 503
    })
  })

  if (state.token) {
    group('authenticated reads', () => {
      const me = http.get(`${BASE_URL}/auth/me`, {
        headers,
        tags: { name: 'auth_me' }
      })
      check(me, {
        'current user loaded': (response) => response.status === 200
      })

      const history = http.get(`${BASE_URL}/detect/history?page=1&page_size=10`, {
        headers,
        tags: { name: 'detect_history' }
      })
      check(history, {
        'history loaded': (response) => response.status === 200
      })
    })
  }

  if (RUN_ADMIN && state.token) {
    group('admin statistics', () => {
      const overview = http.get(`${BASE_URL}/admin/statistics/overview`, {
        headers,
        tags: { name: 'admin_statistics_overview' }
      })
      check(overview, {
        'admin overview loaded': (response) => response.status === 200
      })
    })
  }

  if (RUN_DETECT) {
    group('detection write path', () => {
      const response = http.post(
        `${BASE_URL}/detect/news`,
        JSON.stringify({
          title: 'Baseline performance sample news',
          content:
            'This is a synthetic performance baseline article with enough body text to pass validation. It should be used only in staging or local test environments.',
          category: 'baseline',
          source_name: 'k6',
          enable_web_search: ENABLE_WEB_SEARCH
        }),
        {
          headers,
          tags: { name: 'detect_news' },
          timeout: '120s'
        }
      )
      check(response, {
        'detection accepted': (result) =>
          result.status === 200 || result.status === 202 || result.status === 400
      })
    })
  }

  sleep(Number(__ENV.SLEEP_SECONDS || 1))
}

function safeJson(response) {
  try {
    return response.json()
  } catch {
    return null
  }
}
