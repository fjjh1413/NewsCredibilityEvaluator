import request from '@/utils/request'

export function getPublicHighRiskNews(params) {
  return request.get('/high-risk/public', { params })
}

export function getHighRiskRanking(params) {
  return request.get('/high-risk/ranking', { params })
}

export function getHighRiskKeywords(params) {
  return request.get('/high-risk/keywords', { params })
}

export function getHighRiskCategoryDistribution(params) {
  return request.get('/high-risk/category-distribution', { params })
}
