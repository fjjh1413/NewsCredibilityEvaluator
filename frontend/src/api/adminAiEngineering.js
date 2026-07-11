import request from '@/utils/request'

export function getAiEngineeringSummary() {
  return request.get('/admin/ai-engineering/summary')
}
