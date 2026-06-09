<template>
  <article class="admin-stat-card" :class="toneClass">
    <div class="admin-stat-card__icon" aria-hidden="true">
      <component :is="icon" />
    </div>
    <div class="admin-stat-card__body">
      <span>{{ title }}</span>
      <strong v-if="!loading">{{ displayValue }}</strong>
      <div v-else class="admin-stat-card__skeleton" aria-hidden="true" />
      <p>{{ description }}</p>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { DataAnalysis } from '@element-plus/icons-vue'

const props = defineProps({
  title: {
    type: String,
    required: true
  },
  value: {
    type: [Number, String],
    default: null
  },
  description: {
    type: String,
    default: ''
  },
  icon: {
    type: [Object, Function],
    default: () => DataAnalysis
  },
  tone: {
    type: String,
    default: 'primary',
    validator: (value) => ['primary', 'accent', 'success', 'warning', 'danger', 'muted'].includes(value)
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const displayValue = computed(() => {
  if (props.value === null || props.value === undefined || props.value === '') {
    return '待接入'
  }

  if (typeof props.value === 'number') {
    return new Intl.NumberFormat('zh-CN').format(props.value)
  }

  return props.value
})

const toneClass = computed(() => `admin-stat-card--${props.tone}`)
</script>

<style scoped>
.admin-stat-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: var(--space-4);
  min-height: 132px;
  padding: var(--space-5);
  border: 1px solid var(--color-border-soft);
  border-top: 3px solid var(--color-primary);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.96);
  box-shadow: var(--shadow-card);
}

.admin-stat-card__icon {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  border-radius: var(--radius-md);
  color: var(--color-primary);
  background: var(--color-primary-soft);
}

.admin-stat-card__icon svg {
  width: 21px;
  height: 21px;
}

.admin-stat-card__body {
  display: grid;
  gap: var(--space-2);
  min-width: 0;
}

.admin-stat-card__body span {
  color: var(--color-text-muted);
  font-size: 13px;
  font-weight: 800;
}

.admin-stat-card__body strong {
  color: var(--color-text-strong);
  font-size: 30px;
  line-height: 1;
}

.admin-stat-card__body p {
  margin: 0;
  color: var(--color-text-muted);
  font-size: 13px;
  line-height: 1.6;
}

.admin-stat-card__skeleton {
  width: 96px;
  height: 30px;
  border-radius: var(--radius-sm);
  background: linear-gradient(90deg, #e6eef6 0%, #f8fafc 45%, #e6eef6 100%);
  background-size: 220% 100%;
  animation: stat-loading-pulse 1.2s ease-in-out infinite;
}

.admin-stat-card--accent {
  border-top-color: var(--color-accent);
}

.admin-stat-card--success {
  border-top-color: var(--color-success);
}

.admin-stat-card--warning {
  border-top-color: var(--color-warning);
}

.admin-stat-card--danger {
  border-top-color: var(--color-danger);
}

.admin-stat-card--muted {
  border-top-color: var(--color-text-muted);
}

.admin-stat-card--accent .admin-stat-card__icon {
  color: var(--color-accent);
}

.admin-stat-card--success .admin-stat-card__icon {
  color: var(--color-success);
  background: var(--risk-trusted-bg);
}

.admin-stat-card--warning .admin-stat-card__icon {
  color: var(--color-warning);
  background: var(--risk-suspicious-bg);
}

.admin-stat-card--danger .admin-stat-card__icon {
  color: var(--color-danger);
  background: var(--risk-high-bg);
}

.admin-stat-card--muted .admin-stat-card__icon {
  color: var(--color-text-muted);
  background: var(--color-bg-subtle);
}

@keyframes stat-loading-pulse {
  0% {
    background-position: 100% 0;
  }

  100% {
    background-position: -100% 0;
  }
}

@media (max-width: 520px) {
  .admin-stat-card {
    grid-template-columns: 1fr;
  }
}
</style>
