import request from '@/utils/request'

export function submitNewsDetection(data) {
  return request.post('/detect/news', data, { timeout: 120000 })
}

export function extractNewsPreview(url) {
  return request.post('/detect/extract-preview', { url }, { timeout: 30000 })
}

export function getDetectionDetail(id) {
  return request.get(`/detect/${id}`)
}

export function reEvaluateDetection(id) {
  return request.post(`/detect/${id}/re-evaluate`, undefined, { timeout: 120000 })
}

export function getDetectionHistory(params) {
  return request.get('/detect/history', { params })
}
