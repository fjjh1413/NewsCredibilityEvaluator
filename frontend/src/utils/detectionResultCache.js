export const DETECTION_RESULT_CACHE_TTL_MS = 5 * 60 * 1000

export function getDetectionResultCacheKey(id) {
  return `detection_result_${id}`
}

export function createDetectionResultCache(data, timestamp = Date.now()) {
  return {
    timestamp,
    data
  }
}

export function writeDetectionResultCache(id, data, storage = sessionStorage, timestamp = Date.now()) {
  storage.setItem(
    getDetectionResultCacheKey(id),
    JSON.stringify(createDetectionResultCache(data, timestamp))
  )
}

export function readDetectionResultCache(
  id,
  {
    storage = sessionStorage,
    now = Date.now(),
    ttlMs = DETECTION_RESULT_CACHE_TTL_MS,
    unwrap = (value) => value
  } = {}
) {
  const key = getDetectionResultCacheKey(id)
  const raw = storage.getItem(key)

  if (!raw) {
    return null
  }

  try {
    const parsed = JSON.parse(raw)
    const age = now - parsed?.timestamp

    if (
      !Number.isFinite(age) ||
      age < 0 ||
      age > ttlMs ||
      !Object.prototype.hasOwnProperty.call(parsed, 'data')
    ) {
      storage.removeItem(key)
      return null
    }

    return unwrap(parsed.data)
  } catch {
    storage.removeItem(key)
    return null
  }
}
