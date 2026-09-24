import assert from 'node:assert/strict'
import test from 'node:test'

import { createBackendProxyErrorHandler } from './backendProxy.js'

test('returns a clear 503 response when the local backend is offline', () => {
  const headers = {}
  let statusCode = null
  let body = ''
  const response = {
    headersSent: false,
    writeHead(status, nextHeaders) {
      statusCode = status
      Object.assign(headers, nextHeaders)
      this.headersSent = true
    },
    end(value) {
      body = value
    }
  }

  const handleProxyError = createBackendProxyErrorHandler()
  handleProxyError(new Error('connect ECONNREFUSED'), {}, response)

  assert.equal(statusCode, 503)
  assert.equal(headers['Content-Type'], 'application/json; charset=utf-8')
  assert.deepEqual(JSON.parse(body), {
    code: 503,
    message: '本地后端服务未启动，请先运行 uvicorn app.main:app --reload。',
    data: null
  })
})

test('does not overwrite a response whose headers were already sent', () => {
  let ended = false
  const response = {
    headersSent: true,
    writeHead() {
      throw new Error('writeHead must not be called')
    },
    end() {
      ended = true
    }
  }

  createBackendProxyErrorHandler()(new Error('socket closed'), {}, response)

  assert.equal(ended, false)
})
