// A processed request is not necessarily a supported credibility verdict.
export function getAssessmentState(result = {}) {
  const explicit = String(result.assessment_status || '')
  const arbitration = String(result.arbitration_status || '')
  let status = explicit || 'legacy'
  if (!explicit || explicit === 'legacy') {
    if (['provider_error', 'retry_exhausted', 'invalid_response', 'unavailable'].includes(arbitration)) {
      status = 'degraded'
    } else if (arbitration === 'no_evidence') {
      status = 'insufficient_evidence'
    } else if (arbitration === 'ok' && result.quality_status && result.quality_status !== 'ok') {
      status = 'degraded'
    } else if (arbitration === 'ok' && result.quality_status === 'ok') {
      const coverage = result.evidence_quality?.coverage
      if (coverage === 0) status = 'insufficient_evidence'
      else if (coverage !== null && coverage !== undefined &&
        (typeof coverage !== 'number' || !Number.isFinite(coverage) || coverage < 0 || coverage > 100)) status = 'degraded'
    }
  }
  // Explicit null must never fall back to an old cached score alias.
  const rawScore = Object.hasOwn(result, 'final_score')
    ? result.final_score
    : result.credibility_score ?? result.score ?? result.finalScore
  const numeric = rawScore !== null && rawScore !== undefined && rawScore !== ''
    ? Number(rawScore) : NaN
  const hasVerdict = ['completed', 'legacy'].includes(status) && typeof rawScore !== 'boolean' && Number.isFinite(numeric) && numeric >= 0 && numeric <= 100
  const titles = {
    degraded: '分析服务降级 · 无法判断',
    insufficient_evidence: '有效证据不足 · 无法判断',
    completed: '分析完成',
    legacy: '历史分析结果'
  }
  return {
    status,
    hasVerdict,
    score: hasVerdict ? numeric : null,
    riskLevel: hasVerdict ? (result.risk_level ?? result.riskLevel ?? result.risk ?? '') : '无法判断',
    title: titles[status] || '分析状态不完整 · 无法判断',
    description: result.assessment_reason || (hasVerdict
      ? '结果仅供辅助核查，请结合原始来源确认。'
      : '本次未形成完整的证据判断，不提供综合可信度分数。请补充来源、稍后重试或人工核查。')
  }
}
