import request from '@/utils/request'

export function submitNewsDetection(data) {
  return request.post('/detect/news', data, { timeout: 120000 })
}

export function getDetectionDetail(id) {
  return request.get(`/detect/${id}`)
}

export function getDetectionHistory(params) {
  return request.get('/detect/history', { params })
}
