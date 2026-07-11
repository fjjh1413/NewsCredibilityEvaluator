import request from '@/utils/request'

export function getAdminReports(params) {
  return request.get('/admin/reports', { params })
}

export function getAdminReportDetail(reportId) {
  return request.get(`/admin/reports/${reportId}`)
}

export function downloadAdminReport(reportId) {
  return request.get(`/admin/reports/${reportId}/download`, {
    responseType: 'blob',
    timeout: 60000
  })
}

export function deleteAdminReport(reportId) {
  return request.delete(`/admin/reports/${reportId}`)
}
