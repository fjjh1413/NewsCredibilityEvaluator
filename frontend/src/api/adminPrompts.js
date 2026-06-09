import request from '@/utils/request'

export function getAdminPrompts(params) {
  return request.get('/admin/prompts', { params })
}

export function getAdminPromptDetail(id) {
  return request.get(`/admin/prompts/${id}`)
}

export function createAdminPrompt(data) {
  return request.post('/admin/prompts', data)
}

export function updateAdminPrompt(id, data) {
  return request.put(`/admin/prompts/${id}`, data)
}

export function deleteAdminPrompt(id) {
  return request.delete(`/admin/prompts/${id}`)
}

export function enableAdminPrompt(id) {
  return request.post(`/admin/prompts/${id}/enable`)
}

export function disableAdminPrompt(id) {
  return request.post(`/admin/prompts/${id}/disable`)
}

export function setDefaultAdminPrompt(id) {
  return request.post(`/admin/prompts/${id}/set-default`)
}
