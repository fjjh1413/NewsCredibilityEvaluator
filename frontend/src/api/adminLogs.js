import request from '@/utils/request'

export function getAdminLogs(params) {
  return request.get('/admin/logs', { params })
}
