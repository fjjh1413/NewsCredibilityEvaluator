import request from '@/utils/request'

export function getAdminKnowledge(params) {
  return request.get('/admin/knowledge', { params })
}

export function getAdminKnowledgeDetail(id) {
  return request.get(`/admin/knowledge/${id}`)
}

export function createAdminKnowledge(data) {
  return request.post('/admin/knowledge', data)
}

export function updateAdminKnowledge(id, data) {
  return request.put(`/admin/knowledge/${id}`, data)
}

export function deleteAdminKnowledge(id) {
  return request.delete(`/admin/knowledge/${id}`)
}

export function vectorizeAdminKnowledge(id) {
  return request.post(`/admin/knowledge/${id}/vectorize`)
}

export function rebuildAdminKnowledgeIndex() {
  return request.post('/admin/knowledge/rebuild-index')
}
