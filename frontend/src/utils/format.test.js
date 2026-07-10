import assert from 'node:assert/strict'
import test from 'node:test'

import { formatDateTime } from './format.js'

test('formats a date-only value without displaying a fabricated midnight time', () => {
  assert.equal(formatDateTime('2026-06-19'), '2026/06/19')
})

