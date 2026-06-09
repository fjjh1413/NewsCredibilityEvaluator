<template>
  <section class="result-section" :class="toneClass">
    <header class="result-section__header">
      <div>
        <h2>{{ title }}</h2>
        <p v-if="description">{{ description }}</p>
      </div>
      <div v-if="$slots.actions" class="result-section__actions">
        <slot name="actions" />
      </div>
    </header>
    <div class="result-section__body">
      <slot />
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  title: {
    type: String,
    required: true
  },
  description: {
    type: String,
    default: ''
  },
  tone: {
    type: String,
    default: 'default',
    validator: (value) => ['default', 'info', 'warning', 'danger'].includes(value)
  }
})

const toneClass = computed(() => `result-section--${props.tone}`)
</script>

<style scoped>
.result-section {
  display: grid;
  gap: var(--space-5);
  padding: var(--space-6);
  border: 1px solid var(--section-border, var(--color-border-soft));
  border-radius: var(--radius-lg);
  background: var(--section-bg, var(--color-bg-panel));
  box-shadow: var(--shadow-card);
}

.result-section__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
}

.result-section h2 {
  margin: 0;
  color: var(--color-text-strong);
  font-size: 18px;
}

.result-section p {
  margin: 8px 0 0;
  color: var(--color-text-muted);
  line-height: 1.7;
}

.result-section__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--space-3);
}

.result-section__body {
  min-width: 0;
}

.result-section--info {
  --section-bg: #f0f9ff;
  --section-border: #bae6fd;
}

.result-section--warning {
  --section-bg: #fffbeb;
  --section-border: #fde68a;
}

.result-section--danger {
  --section-bg: #fff1f2;
  --section-border: #fecdd3;
}

@media (max-width: 720px) {
  .result-section__header {
    flex-direction: column;
  }

  .result-section__actions {
    justify-content: flex-start;
  }
}
</style>

