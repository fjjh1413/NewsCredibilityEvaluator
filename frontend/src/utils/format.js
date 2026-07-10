export function isValidScore(score) {
  if (score === null || score === undefined || score === '') {
    return false
  }

  if (typeof score === 'string' && score.trim() === '') {
    return false
  }

  const value = Number(score)
  return Number.isFinite(value)
}

export function scoreToPercent(score) {
  if (!isValidScore(score)) {
    return null
  }

  const value = Number(score)
  const percent = value <= 1 ? value * 100 : value
  return Math.max(0, Math.min(100, percent))
}

export function formatScore(score) {
  if (!isValidScore(score)) {
    return '--'
  }

  const value = Number(score)
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

export function formatPercent(value) {
  const percent = scoreToPercent(value)

  if (percent === null) {
    return '--'
  }

  return `${Math.round(percent)}%`
}

export function formatDateTime(value) {
  if (!value) {
    return '--'
  }

  const dateOnlyMatch = String(value).match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (dateOnlyMatch) {
    return `${dateOnlyMatch[1]}/${dateOnlyMatch[2]}/${dateOnlyMatch[3]}`
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return String(value)
  }

  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(date)
}
