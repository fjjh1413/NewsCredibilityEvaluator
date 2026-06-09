<template>
  <section class="endpoint-notice" aria-live="polite">
    <div class="endpoint-notice__icon" aria-hidden="true">
      <WarningFilled />
    </div>
    <div class="endpoint-notice__content">
      <h2>{{ title }}</h2>
      <p>{{ description }}</p>
      <ul>
        <li v-for="endpoint in endpoints" :key="endpoint">
          <code>{{ endpoint }}</code>
          <span>待后端接入</span>
        </li>
      </ul>
    </div>
  </section>
</template>

<script setup>
import { WarningFilled } from '@element-plus/icons-vue'

defineProps({
  title: {
    type: String,
    required: true
  },
  description: {
    type: String,
    required: true
  },
  endpoints: {
    type: Array,
    default: () => []
  }
})
</script>

<style scoped>
.endpoint-notice {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: var(--space-4);
  padding: var(--space-5);
  border: 1px solid rgba(217, 119, 6, 0.28);
  border-radius: var(--radius-lg);
  background: rgba(254, 243, 199, 0.48);
}

.endpoint-notice__icon {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  border-radius: var(--radius-md);
  color: var(--color-warning);
  background: var(--risk-suspicious-bg);
}

.endpoint-notice__icon svg {
  width: 21px;
  height: 21px;
}

.endpoint-notice__content {
  display: grid;
  gap: var(--space-3);
  min-width: 0;
}

.endpoint-notice h2,
.endpoint-notice p {
  margin: 0;
}

.endpoint-notice h2 {
  color: var(--color-text-strong);
  font-size: 17px;
}

.endpoint-notice p {
  color: var(--color-text-muted);
  line-height: 1.7;
}

.endpoint-notice ul {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  min-width: 0;
  margin: 0;
  padding: 0;
  list-style: none;
}

.endpoint-notice li {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  max-width: 100%;
  min-width: 0;
  min-height: 30px;
  padding: 4px 8px;
  border: 1px solid rgba(217, 119, 6, 0.2);
  border-radius: var(--radius-sm);
  color: var(--color-text);
  background: rgba(255, 255, 255, 0.76);
  font-size: 12px;
}

.endpoint-notice code {
  overflow: hidden;
  min-width: 0;
  color: var(--color-primary-strong);
  font-family: Consolas, "SFMono-Regular", monospace;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.endpoint-notice li span {
  flex: 0 0 auto;
  color: var(--color-warning);
  font-weight: 800;
}

@media (max-width: 640px) {
  .endpoint-notice {
    grid-template-columns: 1fr;
  }

  .endpoint-notice li {
    width: 100%;
  }
}
</style>
