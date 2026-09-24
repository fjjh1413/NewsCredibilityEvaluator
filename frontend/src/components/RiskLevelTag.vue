<template>
  <span class="risk-level-tag" :class="[riskClass, sizeClass]">
    <component :is="riskConfig.icon" class="risk-level-tag__icon" aria-hidden="true" />
    <span>{{ displayLabel }}</span>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { CircleCheck, CircleCloseFilled, InfoFilled, WarningFilled } from '@element-plus/icons-vue'
import { getRiskLevelMeta } from '@/contracts/promptOutputContract'

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

const iconByRiskKey = {
  trusted: CircleCheck,
  suspicious: InfoFilled,
  rumor: WarningFilled,
  high: CircleCloseFilled
}

const specialRiskMap = {
  unknown: {
    key: 'unknown',
    label: '未返回风险等级',
    className: 'risk-level-tag--unknown',
    icon: InfoFilled
  },
  abstained: {
    key: 'abstained', label: '无法判断', className: 'risk-level-tag--unknown', icon: InfoFilled
  },
  auxiliary: {
    key: 'auxiliary',
    label: '辅助证据',
    className: 'risk-level-tag--auxiliary',
    icon: InfoFilled
  },
  unrated: {
    key: 'unrated',
    label: '未评级案例',
    className: 'risk-level-tag--unrated',
    icon: InfoFilled
  }
}

function specialKeyFromLevel(level) {
  const value = String(level || '').toLowerCase()

  if (value.includes('无法判断')) return 'abstained'

  if (!value) {
    return 'unknown'
  }

  if (value.includes('辅助证据') || value.includes('auxiliary')) {
    return 'auxiliary'
  }

  if (value.includes('未评级') || value.includes('unrated')) {
    return 'unrated'
  }

  return 'unknown'
}

function contractRiskConfig(level) {
  const meta = getRiskLevelMeta(level)
  if (!meta) {
    return null
  }
  return {
    key: meta.key,
    label: meta.label,
    className: `risk-level-tag--${meta.key}`,
    icon: iconByRiskKey[meta.key] || InfoFilled
  }
}

const riskConfig = computed(
  () => contractRiskConfig(props.level) || specialRiskMap[specialKeyFromLevel(props.level)]
)

const displayLabel = computed(() => {
  const rawLabel = String(props.level || '').trim()

  if (riskConfig.value.key === 'unknown') {
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

.risk-level-tag--auxiliary {
  color: #6b7280;
  background: #f3f4f6;
}

.risk-level-tag--unrated {
  color: #9ca3af;
  background: #f9fafb;
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
