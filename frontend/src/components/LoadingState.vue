<template>
  <section class="loading-state" :aria-label="label" aria-busy="true" role="status">
    <div v-for="line in lines" :key="line" class="loading-state__line" />
  </section>
</template>

<script setup>
defineProps({
  lines: {
    type: Number,
    default: 4
  },
  label: {
    type: String,
    default: '内容加载中'
  }
})
</script>

<style scoped>
.loading-state {
  display: grid;
  gap: var(--space-3);
  width: 100%;
  padding: var(--space-5);
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-lg);
  background: var(--color-bg-panel);
}

.loading-state__line {
  height: 14px;
  border-radius: 999px;
  background: linear-gradient(90deg, #e6eef6 0%, #f8fafc 45%, #e6eef6 100%);
  background-size: 220% 100%;
  animation: loading-pulse 1.2s ease-in-out infinite;
}

.loading-state__line:nth-child(1) {
  width: 42%;
  height: 18px;
}

.loading-state__line:nth-child(2) {
  width: 88%;
}

.loading-state__line:nth-child(3) {
  width: 76%;
}

.loading-state__line:nth-child(4) {
  width: 64%;
}

@keyframes loading-pulse {
  0% {
    background-position: 100% 0;
  }

  100% {
    background-position: -100% 0;
  }
}
</style>
