import request from '@/utils/request'

export function getStatisticsOverview(params) {
  return request.get('/admin/statistics/overview', { params })
}

export function getRiskDistribution(params) {
  return request.get('/admin/statistics/risk-distribution', { params })
}

export function getDetectionTrend(params) {
  return request.get('/admin/statistics/trend', { params })
}

export function getCategoryDistribution(params) {
  return request.get('/admin/statistics/category-distribution', { params })
}

export function getUserActivity(params) {
  return request.get('/admin/statistics/user-activity', { params })
}

export function getKeywordStatistics(params) {
  return request.get('/admin/statistics/keywords', { params })
}

export function getKnowledgeOverview(params) {
  return request.get('/admin/statistics/knowledge-overview', { params })
}

export function getKnowledgeVectorStatus(params) {
  return request.get('/admin/statistics/knowledge-vector-status', { params })
}
