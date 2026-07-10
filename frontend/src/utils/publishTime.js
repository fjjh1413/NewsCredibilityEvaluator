const DATE_ONLY_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/
const DATE_TIME_PATTERN = /^(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2})(?::(\d{2}))?(?:Z|[+-](?:[01]\d|2[0-3]):?[0-5]\d)?$/i

function isValidDateParts(year, month, day, hour = 0, minute = 0, second = 0) {
  const date = new Date(Date.UTC(year, month - 1, day, hour, minute, second))
  return (
    date.getUTCFullYear() === year &&
    date.getUTCMonth() === month - 1 &&
    date.getUTCDate() === day &&
    date.getUTCHours() === hour &&
    date.getUTCMinutes() === minute &&
    date.getUTCSeconds() === second
  )
}

function invalidPublishTime() {
  return {
    valid: false,
    date: '',
    clock: '',
    precision: null,
    originalValue: ''
  }
}

export function parsePublishTime(value, precision) {
  const originalValue = value == null ? '' : String(value).trim()
  if (!originalValue) {
    return {
      valid: true,
      date: '',
      clock: '',
      precision: null,
      originalValue: ''
    }
  }
  if (precision != null && precision !== 'date' && precision !== 'datetime') {
    return invalidPublishTime()
  }

  const dateOnlyMatch = originalValue.match(DATE_ONLY_PATTERN)
  if (dateOnlyMatch) {
    const [, year, month, day] = dateOnlyMatch
    if (
      precision === 'datetime' ||
      !isValidDateParts(Number(year), Number(month), Number(day))
    ) {
      return invalidPublishTime()
    }
    return {
      valid: true,
      date: `${year}-${month}-${day}`,
      clock: '',
      precision: 'date',
      originalValue
    }
  }

  const dateTimeMatch = originalValue.match(DATE_TIME_PATTERN)
  if (dateTimeMatch) {
    const [, year, month, day, hour, minute, second = '0'] = dateTimeMatch
    if (
      precision === 'date' ||
      !isValidDateParts(
        Number(year),
        Number(month),
        Number(day),
        Number(hour),
        Number(minute),
        Number(second)
      )
    ) {
      return invalidPublishTime()
    }
    return {
      valid: true,
      date: `${year}-${month}-${day}`,
      clock: `${hour}:${minute}`,
      precision: 'datetime',
      originalValue
    }
  }

  return invalidPublishTime()
}

export function composePublishTime({ date, clock, originalValue, edited }) {
  if (!edited && originalValue) {
    return originalValue
  }
  if (!date) {
    return ''
  }
  return clock ? `${date}T${clock}` : date
}
