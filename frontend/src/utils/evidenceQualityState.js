function finiteScore(value) {
  const score = Number(value)
  return Number.isFinite(score) && score >= 0 && score <= 100 ? score : null
}

export function getEvidenceQualityState(result = {}) {
  const arbitrationStatus = String(result?.arbitration_status || '').trim()
  const rawQualityStatus = String(result?.quality_status || '').trim()
  const quality = result?.evidence_quality || result?.evidenceQuality || null
  const score = finiteScore(quality?.score)
  const attempts = Math.max(0, Number(result?.arbitration_attempts) || 0)

  if (
    (rawQualityStatus === 'ok' || (!rawQualityStatus && arbitrationStatus === 'ok')) &&
    score !== null
  ) {
    return {
      status: 'ok',
      score,
      title: '证据质量评估完成',
      description: '基于已完成仲裁的有效证据计算覆盖度与一致性。',
      cardSubtitle: 'LLM 对有效证据覆盖度与一致性的评价',
      canRetry: false
    }
  }

  if (rawQualityStatus === 'no_evidence' || arbitrationStatus === 'no_evidence') {
    return {
      status: 'no_evidence',
      score: null,
      title: '暂无可评估证据',
      description: '本次未检索到可供仲裁的候选证据，因此证据质量不计为 0 分。',
      cardSubtitle: '未检索到可供质量评估的证据',
      canRetry: false
    }
  }

  const description = arbitrationStatus === 'provider_error'
    ? '大模型服务调用失败，证据质量本次未参与综合评分，可重新评估。'
    : arbitrationStatus === 'retry_exhausted'
      ? `模型连续 ${attempts || 2} 次未返回符合契约的证据仲裁结果，证据质量本次未参与综合评分。`
      : '该记录未完成证据仲裁，证据质量本次未参与综合评分，可使用当前契约重新评估。'

  return {
    status: 'unavailable',
    score: null,
    title: '证据质量评估未完成',
    description,
    cardSubtitle: '评估未完成，未作为 0 分处理',
    canRetry: true
  }
}
