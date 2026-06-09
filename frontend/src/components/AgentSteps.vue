<template>
  <EmptyState
    v-if="!normalizedSteps.length"
    title="暂无分析步骤"
    description="检测流程开始后，AI 分析链路会在这里按步骤展示。"
  />

  <ol v-else class="agent-steps">
    <li
      v-for="(step, index) in normalizedSteps"
      :key="`${step.title}-${index}`"
      class="agent-step"
      :class="`agent-step--${step.status}`"
    >
      <span class="agent-step__index">{{ index + 1 }}</span>
      <span class="agent-step__content">
        <strong>{{ step.title }}</strong>
        <small v-if="step.description">{{ step.description }}</small>
      </span>
    </li>
  </ol>
</template>

<script setup>
import { computed } from 'vue'
import EmptyState from './EmptyState.vue'

const props = defineProps({
  steps: {
    type: Array,
    default: () => []
  }
})

function normalizeStatus(status) {
  const value = String(status || 'done').toLowerCase()

  if (['pending', 'waiting'].includes(value)) {
    return 'pending'
  }

  if (['running', 'processing', 'active'].includes(value)) {
    return 'running'
  }

  if (['error', 'failed', 'fail'].includes(value)) {
    return 'error'
  }

  return 'done'
}

const normalizedSteps = computed(() =>
  props.steps.map((step) => {
    if (typeof step === 'string') {
      return {
        title: step,
        description: '',
        status: 'done'
      }
    }

    return {
      title: step.title || step.name || step.step || step.label || '未命名步骤',
      description: step.description || step.detail || step.message || '',
      status: normalizeStatus(step.status || step.state)
    }
  })
)
</script>

<style scoped>
.agent-steps {
  display: grid;
  gap: var(--space-3);
  margin: 0;
  padding: 0;
  list-style: none;
}

.agent-step {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  gap: var(--space-3);
  align-items: flex-start;
  padding: var(--space-4);
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-md);
  background: var(--color-bg-panel);
}

.agent-step__index {
  display: grid;
  width: 32px;
  height: 32px;
  place-items: center;
  border-radius: var(--radius-sm);
  color: #ffffff;
  background: var(--color-primary);
  font-size: 13px;
  font-weight: 800;
}

.agent-step__content {
  display: grid;
  gap: 4px;
}

.agent-step__content strong {
  color: var(--color-text-strong);
  font-size: 14px;
}

.agent-step__content small {
  color: var(--color-text-muted);
  font-size: 13px;
  line-height: 1.55;
}

.agent-step--pending .agent-step__index {
  color: var(--color-text-muted);
  background: #e6eef6;
}

.agent-step--running .agent-step__index {
  background: var(--color-accent);
}

.agent-step--error .agent-step__index {
  background: var(--color-danger);
}
</style>
