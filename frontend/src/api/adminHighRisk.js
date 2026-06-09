import request from '@/utils/request'

export function getAdminHighRisk(params) {
  return request.get('/admin/high-risk', { params })
}

export function getAdminHighRiskDetail(id) {
  return request.get(`/admin/high-risk/${id}`)
}

export function updateAdminHighRiskReview(id, data) {
  return request.put(`/admin/high-risk/${id}/review`, data)
}

export function updateAdminHighRiskPublic(id, data) {
  return request.put(`/admin/high-risk/${id}/public`, data)
}

export function updateAdminHighRiskRemark(id, data) {
  return request.put(`/admin/high-risk/${id}/remark`, data)
}
