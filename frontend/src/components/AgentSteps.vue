<template>
  <EmptyState
    v-if="!normalizedSteps.length"
    title="暂无分析步骤"
    description="检测流程开始后，AI 分析链路会在这里按步骤展示。"
  />

  <ol v-else class="agent-steps" aria-label="证据调查 Agent 执行轨迹">
    <li
      v-for="(step, index) in normalizedSteps"
      :key="step.id || `${step.title}-${index}`"
      class="agent-step"
      :class="`agent-step--${step.status}`"
    >
      <span class="agent-step__index" aria-hidden="true">{{ index + 1 }}</span>
      <span class="agent-step__content">
        <span class="agent-step__heading">
          <strong>{{ step.title }}</strong>
          <span class="agent-step__status">{{ statusLabel(step.status) }}</span>
          <span v-if="step.latencyMs != null" class="agent-step__latency">
            {{ formatLatency(step.latencyMs) }}
          </span>
        </span>
        <span v-if="step.tool" class="agent-step__tool">工具 · {{ step.tool }}</span>
        <small v-if="step.description">{{ step.description }}</small>
        <small v-if="step.decision" class="agent-step__decision">
          <span>决策依据</span>{{ step.decision }}
        </small>
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
  const value = String(status || 'completed').toLowerCase()

  if (['pending', 'waiting'].includes(value)) {
    return 'pending'
  }

  if (['running', 'processing', 'active'].includes(value)) {
    return 'running'
  }

  if (['error', 'failed', 'fail'].includes(value)) {
    return 'failed'
  }

  if (['skipped', 'disabled', 'not_needed'].includes(value)) return 'skipped'
  if (['degraded', 'fallback', 'partial', 'retry_exhausted'].includes(value)) return 'degraded'

  return 'completed'
}

function statusLabel(status) {
  return {
    completed: '已完成',
    skipped: '已跳过',
    degraded: '已降级',
    failed: '失败',
    pending: '等待中',
    running: '执行中'
  }[normalizeStatus(status)]
}

function formatLatency(value) {
  const latency = Number(value)
  if (!Number.isFinite(latency)) return ''
  return latency >= 1000 ? `${(latency / 1000).toFixed(2)} s` : `${latency.toFixed(1)} ms`
}

const normalizedSteps = computed(() =>
  props.steps.map((step) => {
    if (typeof step === 'string') {
      return {
        title: step,
        description: '',
        status: 'completed',
        decision: '',
        tool: '',
        latencyMs: null
      }
    }

    return {
      title: step.title || step.name || step.step || step.label || '未命名步骤',
      description: step.description || step.detail || step.message || '',
      status: normalizeStatus(step.status || step.state),
      decision: step.decision || '',
      tool: step.tool || '',
      latencyMs: step.latencyMs ?? step.latency_ms ?? null
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

.agent-step__heading {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  align-items: center;
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

.agent-step__status,
.agent-step__latency,
.agent-step__tool {
  width: fit-content;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 700;
}

.agent-step__status,
.agent-step__latency {
  padding: 2px 7px;
  color: var(--color-text-muted);
  background: var(--color-bg-subtle);
}

.agent-step__tool {
  padding: 3px 8px;
  color: var(--color-primary);
  border: 1px solid var(--color-border-soft);
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
}

.agent-step__decision {
  padding-top: var(--space-2);
  border-top: 1px dashed var(--color-border-soft);
}

.agent-step__decision span {
  margin-right: var(--space-2);
  color: var(--color-text-strong);
  font-weight: 700;
}

.agent-step--pending .agent-step__index {
  color: var(--color-text-muted);
  background: #e6eef6;
}

.agent-step--running .agent-step__index {
  background: var(--color-accent);
}

.agent-step--failed .agent-step__index {
  background: var(--color-danger);
}

.agent-step--skipped .agent-step__index {
  color: var(--color-text-muted);
  background: #dbe5ec;
}

.agent-step--degraded .agent-step__index {
  background: var(--color-warning);
}

@media (max-width: 640px) {
  .agent-step {
    grid-template-columns: 28px minmax(0, 1fr);
    padding: var(--space-3);
  }

  .agent-step__index {
    width: 28px;
    height: 28px;
  }
}
</style>
