<template>
  <section class="empty-state" aria-live="polite">
    <div class="empty-state__icon" aria-hidden="true">
      <Document />
    </div>
    <div class="empty-state__body">
      <h2>{{ title }}</h2>
      <p v-if="description">{{ description }}</p>
    </div>
    <div v-if="$slots.actions || (actionText && to)" class="empty-state__actions">
      <slot name="actions">
        <RouterLink class="button button--primary" :to="to">{{ actionText }}</RouterLink>
      </slot>
    </div>
  </section>
</template>

<script setup>
import { Document } from '@element-plus/icons-vue'

defineProps({
  title: {
    type: String,
    default: '暂无内容'
  },
  description: {
    type: String,
    default: ''
  },
  actionText: {
    type: String,
    default: ''
  },
  to: {
    type: [String, Object],
    default: null
  }
})
</script>

<style scoped>
.empty-state {
  display: grid;
  justify-items: center;
  gap: var(--space-4);
  min-height: 240px;
  padding: var(--space-8);
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-lg);
  background: rgba(248, 250, 252, 0.8);
  text-align: center;
}

.empty-state__icon {
  display: grid;
  width: 48px;
  height: 48px;
  place-items: center;
  border-radius: var(--radius-md);
  color: var(--color-primary);
  background: var(--color-primary-soft);
}

.empty-state__icon svg {
  width: 24px;
  height: 24px;
}

.empty-state__body {
  display: grid;
  gap: var(--space-2);
}

.empty-state h2 {
  margin: 0;
  color: var(--color-text-strong);
  font-size: 18px;
}

.empty-state p {
  max-width: 520px;
  margin: 0;
  color: var(--color-text-muted);
  line-height: 1.7;
}

.empty-state__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: var(--space-3);
}
</style>

