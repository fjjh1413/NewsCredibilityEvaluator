import request from '@/utils/request'

export function getAdminUsers(params) {
  return request.get('/admin/users', { params })
}

export function getAdminUserDetail(id) {
  return request.get(`/admin/users/${id}`)
}

export function enableAdminUser(id) {
  return request.post(`/admin/users/${id}/enable`)
}

export function disableAdminUser(id) {
  return request.post(`/admin/users/${id}/disable`)
}

export function getAdminUserDetections(id, params) {
  return request.get(`/admin/users/${id}/detections`, { params })
}
