<template>
  <section class="admin-page">
    <PageHeader :eyebrow="eyebrow" :title="title" :description="description" />

    <section class="surface-card surface-card--padded admin-page__panel" aria-live="polite">
      <div class="admin-page__panel-header">
        <div class="admin-page__mark" aria-hidden="true">
          <component :is="icon" />
        </div>
        <div class="admin-page__copy">
          <h2>{{ panelTitle }}</h2>
          <p>{{ panelDescription }}</p>
        </div>
        <span class="admin-page__status">基础页面</span>
      </div>
    </section>
  </section>
</template>

<script setup>
import { Document } from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'

defineProps({
  eyebrow: {
    type: String,
    default: '管理员后台'
  },
  title: {
    type: String,
    required: true
  },
  description: {
    type: String,
    default: ''
  },
  panelTitle: {
    type: String,
    default: '页面结构已就绪'
  },
  panelDescription: {
    type: String,
    default: '本阶段仅完成后台布局与路由接入，业务数据和操作接口将在后续任务中按模块接入。'
  },
  icon: {
    type: [Object, Function],
    default: () => Document
  }
})
</script>

<style scoped>
.admin-page {
  display: grid;
  gap: var(--space-6);
}

.admin-page__panel {
  min-height: 220px;
}

.admin-page__panel-header {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: var(--space-4);
  align-items: center;
}

.admin-page__mark {
  display: grid;
  width: 48px;
  height: 48px;
  place-items: center;
  border: 1px solid rgba(3, 105, 161, 0.14);
  border-radius: var(--radius-md);
  color: var(--color-primary);
  background: var(--color-primary-soft);
}

.admin-page__mark svg {
  width: 24px;
  height: 24px;
}

.admin-page__copy {
  display: grid;
  gap: var(--space-2);
  min-width: 0;
}

.admin-page__copy h2 {
  margin: 0;
  color: var(--color-text-strong);
  font-size: 18px;
  line-height: 1.35;
}

.admin-page__copy p {
  max-width: 720px;
  margin: 0;
  color: var(--color-text-muted);
  line-height: 1.7;
}

.admin-page__status {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border: 1px solid rgba(3, 105, 161, 0.18);
  border-radius: 999px;
  color: var(--color-primary-strong);
  background: rgba(224, 242, 254, 0.76);
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}

@media (max-width: 720px) {
  .admin-page__panel-header {
    grid-template-columns: 1fr;
  }

  .admin-page__status {
    justify-self: start;
  }
}
</style>
