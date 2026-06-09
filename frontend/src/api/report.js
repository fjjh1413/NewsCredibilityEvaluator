import request from '@/utils/request'

export function generateReport(detectionId) {
  return request.post(`/report/generate/${detectionId}`, null, {
    timeout: 60000
  })
}

export function downloadReport(reportId) {
  return request.get(`/report/download/${reportId}`, {
    responseType: 'blob',
    timeout: 60000
  })
}

export function downloadReportFile(reportId) {
  return request.get(`/report/download/${reportId}`, {
    responseType: 'blob',
    timeout: 60000,
    rawResponse: true
  })
}
