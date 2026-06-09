<template>
  <header class="page-header">
    <div class="page-header__content">
      <p v-if="eyebrow" class="page-header__eyebrow">{{ eyebrow }}</p>
      <h1>{{ title }}</h1>
      <p v-if="description">{{ description }}</p>
    </div>
    <div v-if="$slots.actions" class="page-header__actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<script setup>
defineProps({
  eyebrow: {
    type: String,
    default: ''
  },
  title: {
    type: String,
    required: true
  },
  description: {
    type: String,
    default: ''
  }
})
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-5);
  padding: var(--space-6);
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.94);
  box-shadow: var(--shadow-card);
}

.page-header__content {
  display: grid;
  gap: var(--space-2);
}

.page-header__eyebrow {
  margin: 0;
  color: var(--color-primary);
  font-size: 13px;
  font-weight: 800;
}

.page-header h1 {
  margin: 0;
  color: var(--color-text-strong);
  font-size: 28px;
  line-height: 1.2;
}

.page-header p:not(.page-header__eyebrow) {
  max-width: 720px;
  margin: 0;
  color: var(--color-text-muted);
  line-height: 1.7;
}

.page-header__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--space-3);
}

@media (max-width: 720px) {
  .page-header {
    align-items: stretch;
    flex-direction: column;
  }

  .page-header__actions {
    justify-content: flex-start;
  }
}
</style>

