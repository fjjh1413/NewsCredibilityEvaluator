import request from '@/utils/request'

export function getAdminOperationPolicies(params = {}) {
  return request.get('/admin/operation-policies', { params })
}
