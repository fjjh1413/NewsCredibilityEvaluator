<template>
  <article class="score-card" :class="toneClass">
    <div class="score-card__header">
      <span class="score-card__title">{{ title }}</span>
      <slot name="extra" />
    </div>
    <div class="score-card__value">
      {{ formattedScore }}
      <span v-if="showUnit && formattedScore !== '--'" class="score-card__unit">分</span>
    </div>
    <p v-if="subtitle" class="score-card__subtitle">{{ subtitle }}</p>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { formatScore } from '@/utils/format'

const props = defineProps({
  title: {
    type: String,
    required: true
  },
  score: {
    type: [Number, String],
    default: null
  },
  subtitle: {
    type: String,
    default: ''
  },
  tone: {
    type: String,
    default: 'primary',
    validator: (value) => ['primary', 'success', 'warning', 'danger', 'neutral'].includes(value)
  },
  showUnit: {
    type: Boolean,
    default: true
  }
})

const formattedScore = computed(() => formatScore(props.score))
const toneClass = computed(() => `score-card--${props.tone}`)
</script>

<style scoped>
.score-card {
  display: grid;
  gap: var(--space-3);
  min-height: 132px;
  padding: var(--space-5);
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-lg);
  background: var(--color-bg-panel);
  box-shadow: var(--shadow-card);
}

.score-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.score-card__title {
  color: var(--color-text-muted);
  font-size: 13px;
  font-weight: 700;
}

.score-card__value {
  color: var(--score-color, var(--color-primary-strong));
  font-size: 34px;
  font-weight: 800;
  line-height: 1;
}

.score-card__unit {
  margin-left: 3px;
  font-size: 14px;
  font-weight: 700;
}

.score-card__subtitle {
  margin: 0;
  color: var(--color-text-muted);
  font-size: 13px;
  line-height: 1.6;
}

.score-card--primary {
  --score-color: var(--color-primary);
}

.score-card--success {
  --score-color: var(--color-success);
}

.score-card--warning {
  --score-color: var(--color-warning);
}

.score-card--danger {
  --score-color: var(--color-danger);
}

.score-card--neutral {
  --score-color: var(--color-text-strong);
}
</style>
