const palette = {
  primary: '#0369A1',
  accent: '#0EA5E9',
  success: '#16A34A',
  warning: '#D97706',
  orange: '#F97316',
  danger: '#DC2626',
  muted: '#64748B',
  text: '#1E293B',
  border: '#D8E3EE',
  borderSoft: '#E6EEF6'
}

const baseTextStyle = {
  color: palette.muted,
  fontSize: 12
}

const baseTooltip = {
  backgroundColor: 'rgba(255, 255, 255, 0.98)',
  borderColor: palette.border,
  borderWidth: 1,
  textStyle: {
    color: palette.text,
    fontSize: 13
  }
}

export function unwrapStatisticsResponse(response) {
  const body = response?.data ?? response
  const code = body?.code

  if (code !== undefined && ![0, 200].includes(Number(code))) {
    throw new Error(body?.message || '统计数据加载失败')
  }

  if (body?.success === false) {
    throw new Error(body?.message || '统计数据加载失败')
  }

  if (
    body?.data !== undefined &&
    (body?.code !== undefined || body?.success !== undefined || body?.message !== undefined)
  ) {
    return body.data
  }

  return body
}

export function normalizeNumber(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

export function pickMetric(source, keys) {
  for (const key of keys) {
    if (source?.[key] !== undefined && source[key] !== null && source[key] !== '') {
      return normalizeNumber(source[key])
    }
  }

  return null
}

export function normalizeDistribution(payload, options = {}) {
  const { arrayKeys = [], nameKeys = [] } = options

  if (Array.isArray(payload)) {
    return payload
      .map((item, index) => normalizeDistributionItem(item, index, nameKeys))
      .filter((item) => item.name && item.value !== null)
  }

  if (payload && typeof payload === 'object') {
    const arrayPayload = pickFirstArray(payload, ['items', 'list', 'records', 'rows', ...arrayKeys])

    if (arrayPayload) {
      return normalizeDistribution(arrayPayload, options)
    }

    return Object.entries(payload)
      .map(([name, value]) => ({ name, value: normalizeNumber(value) }))
      .filter((item) => item.name && item.value !== null)
  }

  return []
}

export function normalizeTimeSeries(payload, valueKeys = []) {
  if (Array.isArray(payload?.dates)) {
    const values =
      pickFirstArray(payload, [...valueKeys, 'counts', 'values', 'totals', 'active_users', 'user_counts']) || []

    return payload.dates
      .map((date, index) => ({
        date: String(date),
        value: normalizeNumber(values[index])
      }))
      .filter((item) => item.date && item.value !== null)
  }

  if (Array.isArray(payload)) {
    return payload
      .map((item, index) => {
        if (Array.isArray(item)) {
          return {
            date: String(item[0] ?? `第 ${index + 1} 日`),
            value: normalizeNumber(item[1])
          }
        }

        return {
          date: String(item?.date ?? item?.day ?? item?.name ?? item?.label ?? `第 ${index + 1} 日`),
          value: normalizeNumber(
            valueKeys.map((key) => item?.[key]).find((value) => value !== undefined) ??
              item?.count ??
              item?.value ??
              item?.total
          )
        }
      })
      .filter((item) => item.date && item.value !== null)
  }

  return []
}

export function getStatisticsErrorMessage(error) {
  if (error?.response?.status === 401) {
    return '登录状态已失效，请重新登录'
  }

  if (error?.response?.status === 403) {
    return '当前账号没有统计接口访问权限'
  }

  const backendMessage = error?.response?.data?.message || error?.response?.data?.detail

  if (backendMessage) {
    return backendMessage
  }

  if (error?.message && !/^(Network Error|Request failed with status code)/.test(error.message)) {
    return error.message
  }

  return '数据加载失败，请稍后重试'
}

export function isPendingStatisticsEndpoint(error) {
  return [404, 405, 501].includes(error?.response?.status)
}

export function findDistributionValue(data, names) {
  const normalizedNames = names.map((name) => String(name).toLowerCase())
  const matches = data.filter((item) => {
    const value = String(item.name || '').toLowerCase()
    return normalizedNames.some((name) => value.includes(name))
  })

  if (!data.length) {
    return null
  }

  return matches.reduce((total, item) => total + item.value, 0)
}

export function createLineChartOption(name, data, options = {}) {
  const color = options.color || palette.primary
  const areaColor = options.areaColor || 'rgba(14, 165, 233, 0.14)'

  return {
    color: [color],
    grid: { top: 26, right: 20, bottom: 42, left: 48 },
    tooltip: {
      ...baseTooltip,
      trigger: 'axis',
      axisPointer: { type: 'line', lineStyle: { color: palette.border } }
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: data.map((item) => item.date),
      axisLabel: {
        ...baseTextStyle,
        hideOverlap: true
      },
      axisTick: { show: false },
      axisLine: { lineStyle: { color: palette.border } }
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: baseTextStyle,
      axisLine: { show: false },
      splitLine: { lineStyle: { color: palette.borderSoft } }
    },
    series: [
      {
        name,
        type: 'line',
        smooth: 0.28,
        showSymbol: data.length <= 14,
        symbolSize: 7,
        lineStyle: { width: 3 },
        itemStyle: { borderWidth: 2, borderColor: '#FFFFFF' },
        areaStyle: { color: areaColor },
        data: data.map((item) => item.value)
      }
    ]
  }
}

export function createRiskDonutOption(data) {
  const decoratedData = data.map((item) => ({
    ...item,
    name: riskLabel(item.name),
    itemStyle: { color: riskColor(item.name) }
  }))

  return createDonutChartOption('风险等级', decoratedData)
}

export function createVectorDonutOption(data) {
  const decoratedData = data.map((item) => ({
    ...item,
    name: vectorStatusLabel(item.name),
    itemStyle: { color: vectorStatusColor(item.name) }
  }))

  return createDonutChartOption('向量同步状态', decoratedData)
}

export function createVerticalBarChartOption(name, data) {
  const sortedData = [...data].sort((left, right) => right.value - left.value).slice(0, 12)

  return {
    color: [palette.accent],
    grid: { top: 24, right: 18, bottom: 62, left: 48 },
    tooltip: {
      ...baseTooltip,
      trigger: 'axis',
      axisPointer: { type: 'shadow' }
    },
    xAxis: {
      type: 'category',
      data: sortedData.map((item) => item.name),
      axisLabel: {
        ...baseTextStyle,
        interval: 0,
        formatter: (value) => wrapAxisLabel(value, 5)
      },
      axisTick: { show: false },
      axisLine: { lineStyle: { color: palette.border } }
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: baseTextStyle,
      axisLine: { show: false },
      splitLine: { lineStyle: { color: palette.borderSoft } }
    },
    series: [
      {
        name,
        type: 'bar',
        barMaxWidth: 34,
        itemStyle: { borderRadius: [6, 6, 0, 0] },
        data: sortedData.map((item) => item.value)
      }
    ]
  }
}

export function createHorizontalBarChartOption(name, data, options = {}) {
  const sortedData = [...data].sort((left, right) => right.value - left.value).slice(0, options.limit || 10)

  return {
    color: [options.color || palette.primary],
    grid: { top: 16, right: 42, bottom: 26, left: 104 },
    tooltip: {
      ...baseTooltip,
      trigger: 'axis',
      axisPointer: { type: 'shadow' }
    },
    xAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: baseTextStyle,
      axisLine: { show: false },
      splitLine: { lineStyle: { color: palette.borderSoft } }
    },
    yAxis: {
      type: 'category',
      inverse: true,
      data: sortedData.map((item) => item.name),
      axisLabel: {
        ...baseTextStyle,
        width: 88,
        overflow: 'truncate'
      },
      axisTick: { show: false },
      axisLine: { lineStyle: { color: palette.border } }
    },
    series: [
      {
        name,
        type: 'bar',
        barMaxWidth: 20,
        label: {
          show: true,
          position: 'right',
          color: palette.text
        },
        itemStyle: { borderRadius: [0, 6, 6, 0] },
        data: sortedData.map((item) => item.value)
      }
    ]
  }
}

function createDonutChartOption(name, data) {
  return {
    tooltip: {
      ...baseTooltip,
      trigger: 'item',
      formatter: '{b}<br/>{a}：{c}（{d}%）'
    },
    legend: {
      bottom: 0,
      itemWidth: 10,
      itemHeight: 10,
      textStyle: baseTextStyle
    },
    series: [
      {
        name,
        type: 'pie',
        radius: ['45%', '68%'],
        center: ['50%', '42%'],
        avoidLabelOverlap: true,
        label: {
          show: false,
          color: palette.text,
          formatter: '{b}\n{c}'
        },
        labelLine: {
          show: false,
          lineStyle: { color: palette.border }
        },
        emphasis: {
          label: {
            show: true,
            color: palette.text,
            fontSize: 13,
            fontWeight: 700,
            formatter: '{b}\n{c}'
          }
        },
        data
      }
    ]
  }
}

function normalizeDistributionItem(item, index, nameKeys) {
  if (Array.isArray(item)) {
    return {
      name: String(item[0] ?? `统计项 ${index + 1}`),
      value: normalizeNumber(item[1])
    }
  }

  if (typeof item === 'string') {
    return { name: item, value: 1 }
  }

  const fallbackKeys = ['name', 'label', 'keyword', 'status', 'risk_level', 'category', 'vector_sync_status']
  const name = [...nameKeys, ...fallbackKeys]
    .map((key) => item?.[key])
    .find((value) => value !== undefined && value !== null && value !== '')

  return {
    name: String(name ?? `统计项 ${index + 1}`),
    value: normalizeNumber(item?.value ?? item?.count ?? item?.total ?? item?.num)
  }
}

function pickFirstArray(source, keys) {
  if (!source || typeof source !== 'object') {
    return null
  }

  for (const key of keys) {
    if (Array.isArray(source[key])) {
      return source[key]
    }
  }

  return null
}

function wrapAxisLabel(value, length) {
  const text = String(value)
  const lines = []

  for (let index = 0; index < text.length; index += length) {
    lines.push(text.slice(index, index + length))
  }

  return lines.slice(0, 2).join('\n')
}

function riskLabel(name) {
  const value = String(name || '').toLowerCase()

  if (value.includes('high') || value.includes('高风险')) return '高风险'
  if (value.includes('rumor') || value.includes('谣言')) return '疑似谣言'
  if (value.includes('medium') || value.includes('suspicious') || value.includes('存疑')) return '存疑'
  if (value.includes('low') || value.includes('trusted') || value.includes('可信')) return '可信'
  return String(name)
}

function riskColor(name) {
  const value = String(name || '').toLowerCase()

  if (value.includes('high') || value.includes('高风险')) return palette.danger
  if (value.includes('rumor') || value.includes('谣言')) return palette.orange
  if (value.includes('medium') || value.includes('suspicious') || value.includes('存疑')) return palette.warning
  if (value.includes('low') || value.includes('trusted') || value.includes('可信')) return palette.success
  return palette.accent
}

function vectorStatusLabel(name) {
  const value = String(name || '').toLowerCase()

  if (value.includes('synced') || value.includes('success') || value.includes('已同步')) return '已同步'
  if (value.includes('failed') || value.includes('error') || value.includes('失败')) return '同步失败'
  if (value.includes('pending') || value.includes('待同步')) return '待同步'
  return String(name)
}

function vectorStatusColor(name) {
  const value = String(name || '').toLowerCase()

  if (value.includes('synced') || value.includes('success') || value.includes('已同步')) return palette.success
  if (value.includes('failed') || value.includes('error') || value.includes('失败')) return palette.danger
  if (value.includes('pending') || value.includes('待同步')) return palette.warning
  return palette.muted
}
