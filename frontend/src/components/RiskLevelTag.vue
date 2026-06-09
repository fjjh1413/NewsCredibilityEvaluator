<template>
  <span class="risk-level-tag" :class="[riskClass, sizeClass]">
    <component :is="riskConfig.icon" class="risk-level-tag__icon" aria-hidden="true" />
    <span>{{ displayLabel }}</span>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { CircleCheck, CircleCloseFilled, InfoFilled, WarningFilled } from '@element-plus/icons-vue'

const props = defineProps({
  level: {
    type: String,
    default: ''
  },
  score: {
    type: [Number, String],
    default: null
  },
  size: {
    type: String,
    default: 'default',
    validator: (value) => ['small', 'default', 'large'].includes(value)
  }
})

const riskMap = {
  unknown: {
    label: '未返回风险等级',
    className: 'risk-level-tag--unknown',
    icon: InfoFilled
  },
  trusted: {
    label: '可信新闻',
    className: 'risk-level-tag--trusted',
    icon: CircleCheck
  },
  suspicious: {
    label: '存疑信息',
    className: 'risk-level-tag--suspicious',
    icon: InfoFilled
  },
  rumor: {
    label: '疑似谣言',
    className: 'risk-level-tag--rumor',
    icon: WarningFilled
  },
  high: {
    label: '高风险谣言',
    className: 'risk-level-tag--high',
    icon: CircleCloseFilled
  }
}

function keyFromLevel(level) {
  const value = String(level || '').toLowerCase()
  const normalized = value.replace(/[\s-]+/g, '_')

  if (!value) {
    return 'unknown'
  }

  if (
    value.includes('高风险') ||
    normalized === 'high' ||
    normalized === 'high_risk' ||
    normalized === 'high_risk_rumor' ||
    normalized.startsWith('high_risk_')
  ) {
    return 'high'
  }

  if (value.includes('可信') || value.includes('trusted') || value.includes('credible')) {
    return 'trusted'
  }

  if (value.includes('存疑') || value.includes('suspicious') || value.includes('uncertain')) {
    return 'suspicious'
  }

  if (
    value.includes('疑似') ||
    normalized === 'suspected_rumor' ||
    normalized.includes('suspected_rumor') ||
    normalized === 'rumor' ||
    normalized === 'rumour' ||
    normalized.endsWith('_rumor') ||
    normalized.endsWith('_rumour')
  ) {
    return 'rumor'
  }

  return 'unknown'
}

const riskKey = computed(() => keyFromLevel(props.level))
const riskConfig = computed(() => riskMap[riskKey.value])

const displayLabel = computed(() => {
  const rawLabel = String(props.level || '').trim()

  if (riskKey.value === 'unknown') {
    return riskConfig.value.label
  }

  return /[\u4e00-\u9fff]/.test(rawLabel) ? rawLabel : riskConfig.value.label
})
const riskClass = computed(() => riskConfig.value.className)
const sizeClass = computed(() => `risk-level-tag--${props.size}`)
</script>

<style scoped>
.risk-level-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
  border: 1px solid currentColor;
  border-radius: 999px;
  font-weight: 700;
  line-height: 1;
  white-space: nowrap;
}

.risk-level-tag__icon {
  width: 14px;
  height: 14px;
  flex: 0 0 auto;
}

.risk-level-tag--small {
  min-height: 24px;
  padding: 0 9px;
  font-size: 12px;
}

.risk-level-tag--default {
  min-height: 28px;
  padding: 0 11px;
  font-size: 13px;
}

.risk-level-tag--large {
  min-height: 34px;
  padding: 0 14px;
  font-size: 15px;
}

.risk-level-tag--trusted {
  color: var(--risk-trusted);
  background: var(--risk-trusted-bg);
}

.risk-level-tag--unknown {
  color: var(--color-text-muted);
  background: var(--color-bg-subtle);
}

.risk-level-tag--suspicious {
  color: var(--risk-suspicious);
  background: var(--risk-suspicious-bg);
}

.risk-level-tag--rumor {
  color: var(--risk-rumor);
  background: var(--risk-rumor-bg);
}

.risk-level-tag--high {
  color: var(--risk-high);
  background: var(--risk-high-bg);
}
</style>
