import request from '@/utils/request'

export function getAdminDetections(params) {
  return request.get('/admin/detections', { params })
}

export function getAdminDetectionDetail(id) {
  return request.get(`/admin/detections/${id}`)
}

export function deleteAdminDetection(id) {
  return request.delete(`/admin/detections/${id}`)
}
