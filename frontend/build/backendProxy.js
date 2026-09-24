const BACKEND_OFFLINE_RESPONSE = {
  code: 503,
  message: '本地后端服务未启动，请先运行 uvicorn app.main:app --reload。',
  data: null
}

export function createBackendProxyErrorHandler() {
  return (_error, _request, response) => {
    if (response.headersSent) return

    response.writeHead(503, {
      'Content-Type': 'application/json; charset=utf-8'
    })
    response.end(JSON.stringify(BACKEND_OFFLINE_RESPONSE))
  }
}

export function configureBackendProxy(proxy) {
  proxy.on('error', createBackendProxyErrorHandler())
}
