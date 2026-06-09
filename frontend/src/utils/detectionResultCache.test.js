import assert from 'node:assert/strict'
import test from 'node:test'
import {
  DETECTION_RESULT_CACHE_TTL_MS,
  readDetectionResultCache,
  writeDetectionResultCache
} from './detectionResultCache.js'

function createStorage(initialValues = {}) {
  const values = new Map(Object.entries(initialValues))

  return {
    getItem(key) {
      return values.has(key) ? values.get(key) : null
    },
    setItem(key, value) {
      values.set(key, String(value))
    },
    removeItem(key) {
      values.delete(key)
    },
    hasItem(key) {
      return values.has(key)
    }
  }
}

test('reads cached result when timestamp is within five minutes', () => {
  const storage = createStorage()
  const result = { detection_id: 12, final_score: 88 }

  writeDetectionResultCache(12, result, storage, 1000)

  assert.deepEqual(
    readDetectionResultCache(12, {
      storage,
      now: 1000 + DETECTION_RESULT_CACHE_TTL_MS - 1
    }),
    result
  )
})

test('expires cached result older than five minutes', () => {
  const key = 'detection_result_12'
  const storage = createStorage({
    [key]: JSON.stringify({
      timestamp: 1000,
      data: { detection_id: 12, final_score: 72 }
    })
  })

  assert.equal(
    readDetectionResultCache(12, {
      storage,
      now: 1000 + DETECTION_RESULT_CACHE_TTL_MS + 1
    }),
    null
  )
  assert.equal(storage.hasItem(key), false)
})

test('ignores invalid cached JSON', () => {
  const key = 'detection_result_12'
  const storage = createStorage({ [key]: '{bad json' })

  assert.equal(readDetectionResultCache(12, { storage, now: 1000 }), null)
  assert.equal(storage.hasItem(key), false)
})
