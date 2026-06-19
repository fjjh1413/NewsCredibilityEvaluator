import assert from 'node:assert/strict'
import test from 'node:test'

import { getEvidenceQualityState } from './evidenceQualityState.js'

test('returns an available score only when quality evaluation succeeded', () => {
  const state = getEvidenceQualityState({
    arbitration_status: 'ok',
    quality_status: 'ok',
    evidence_quality: { score: 83, coverage: 85, consistency: 80 }
  })

  assert.equal(state.status, 'ok')
  assert.equal(state.score, 83)
  assert.equal(state.canRetry, false)
})

test('distinguishes no evidence from a zero evidence-quality score', () => {
  const state = getEvidenceQualityState({
    arbitration_status: 'no_evidence',
    quality_status: 'no_evidence',
    evidence_quality: null
  })

  assert.equal(state.status, 'no_evidence')
  assert.equal(state.score, null)
  assert.match(state.description, /未检索到/)
  assert.equal(state.canRetry, false)
})

test('explains exhausted arbitration retries and allows recovery', () => {
  const state = getEvidenceQualityState({
    arbitration_status: 'retry_exhausted',
    quality_status: 'unavailable',
    arbitration_attempts: 2,
    evidence_quality: null
  })

  assert.equal(state.status, 'unavailable')
  assert.equal(state.score, null)
  assert.match(state.description, /2 次/)
  assert.equal(state.canRetry, true)
})

test('keeps legacy unavailable records recoverable', () => {
  const state = getEvidenceQualityState({ arbitration_status: 'unavailable' })

  assert.equal(state.status, 'unavailable')
  assert.equal(state.canRetry, true)
})
