import assert from 'node:assert/strict'
import test from 'node:test'

import { composePublishTime, parsePublishTime } from './publishTime.js'

test('parses a date-only publication value without inventing a time', () => {
  assert.deepEqual(parsePublishTime('2026-06-19', 'date'), {
    valid: true,
    date: '2026-06-19',
    clock: '',
    precision: 'date',
    originalValue: '2026-06-19'
  })
})

test('parses a publication datetime without applying a timezone conversion', () => {
  assert.deepEqual(parsePublishTime('2026-06-19T14:30:54+08:00', 'datetime'), {
    valid: true,
    date: '2026-06-19',
    clock: '14:30',
    precision: 'datetime',
    originalValue: '2026-06-19T14:30:54+08:00'
  })
})

test('infers precision for responses from an older backend', () => {
  assert.equal(parsePublishTime('2026-06-19', null).precision, 'date')
  assert.equal(parsePublishTime('2026-06-19 14:30', null).precision, 'datetime')
})

test('rejects a precision that contradicts the publication value', () => {
  assert.equal(parsePublishTime('2026-06-19', 'datetime').valid, false)
  assert.equal(parsePublishTime('2026-06-19T14:30', 'date').valid, false)
  assert.equal(parsePublishTime('2026-06-19T14:30', 'unknown').valid, false)
})

test('preserves seconds and timezone when the extracted value was not edited', () => {
  assert.equal(
    composePublishTime({
      date: '2026-06-19',
      clock: '14:30',
      originalValue: '2026-06-19T14:30:54+08:00',
      edited: false
    }),
    '2026-06-19T14:30:54+08:00'
  )
})

test('composes edited publication values at the precision entered by the user', () => {
  assert.equal(
    composePublishTime({ date: '2026-06-19', clock: '', originalValue: '', edited: true }),
    '2026-06-19'
  )
  assert.equal(
    composePublishTime({ date: '2026-06-19', clock: '14:31', originalValue: '', edited: true }),
    '2026-06-19T14:31'
  )
  assert.equal(composePublishTime({ date: '', clock: '', originalValue: '', edited: true }), '')
})
