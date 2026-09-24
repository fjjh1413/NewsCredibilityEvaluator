import assert from 'node:assert/strict'
import test from 'node:test'
import { getAssessmentState } from './assessmentState.js'

test('completed zero score is a valid verdict', () => {
  const state = getAssessmentState({ assessment_status: 'completed', final_score: 0, risk_level: '高风险谣言' })
  assert.equal(state.score, 0)
  assert.equal(state.hasVerdict, true)
})

test('degraded high diagnostic values cannot become a verdict', () => {
  const state = getAssessmentState({ assessment_status: 'degraded', final_score: 99, rule_score: 100, risk_level: '可信新闻' })
  assert.equal(state.score, null)
  assert.equal(state.riskLevel, '无法判断')
})

test('explicit null cannot fall back to cached score aliases', () => {
  assert.equal(getAssessmentState({ assessment_status: 'insufficient_evidence', final_score: null, score: 99 }).score, null)
})

test('legacy failed/no-evidence cached results are conservatively interpreted', () => {
  for (const arbitration_status of ['provider_error', 'retry_exhausted', 'no_evidence']) {
    assert.equal(getAssessmentState({ arbitration_status, final_score: 100 }).hasVerdict, false)
  }
})

test('missing and non-finite scores are never displayed as zero', () => {
  for (const final_score of [null, undefined, '', Infinity, 'NaN', true, -1, 101]) {
    assert.equal(getAssessmentState({ final_score }).hasVerdict, false)
  }
})

test('legacy quality failure and zero coverage cannot display cached high scores', () => {
  for (const evidence_quality of [{ coverage: 0 }, { coverage: '90' }, { coverage: 101 }]) {
    assert.equal(getAssessmentState({ arbitration_status: 'ok', quality_status: 'ok', evidence_quality, final_score: 99 }).hasVerdict, false)
  }
  assert.equal(getAssessmentState({ arbitration_status: 'ok', quality_status: 'unavailable', final_score: 99 }).hasVerdict, false)
})
