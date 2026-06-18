<template>
  <LoadingState v-if="loading" :lines="5" label="证据列表加载中" />

  <EmptyState
    v-else-if="!normalizedItems.length"
    title="暂无证据"
    description="完成新闻检测后，检索到的相似证据会在这里展示。"
  />

  <div v-else class="evidence-list">
    <article v-for="item in normalizedItems" :key="item.key" class="evidence-item">
      <div class="evidence-item__rank">Top {{ item.rank }}</div>

      <div class="evidence-item__main">
        <h3>
          <a v-if="item.url" :href="item.url" target="_blank" rel="noreferrer">{{ item.title }}</a>
          <span v-else>{{ item.title }}</span>
        </h3>
        <p v-if="item.summary">{{ item.summary }}</p>
        <div class="evidence-item__meta">
          <span v-if="item.sourceType" class="evidence-item__source-badge" :class="{ 'evidence-item__source-badge--web': item.sourceType === 'web_search' }">
            {{ item.sourceLabel }}
          </span>
          <span>{{ item.source }}</span>
          <span v-if="item.time">{{ formatDateTime(item.time) }}</span>
        </div>
      </div>
    </article>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import EmptyState from './EmptyState.vue'
import LoadingState from './LoadingState.vue'
import { formatDateTime } from '@/utils/format'

const props = defineProps({
  items: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const normalizedItems = computed(() =>
  props.items.map((item, index) => {
    const sourceType = item.source_type || item.sourceType || ''
    const sourceLabel = item.source_label || item.sourceLabel || (
      sourceType === 'web_search' ? '🌐 网络检索' : '📚 知识库'
    )

    return {
      key: item.knowledge_id || item.id || item.vector_id || `${index}-${item.title || item.news_title || 'evidence'}`,
      rank: item.rank_order || item.rank || index + 1,
      title: item.title || item.news_title || item.input_title || '未命名证据',
      summary: item.summary || item.content_summary || item.abstract || item.content || '',
      source: item.source_name || item.source || item.media || '未知来源',
      url: item.source_url || item.url || item.link || '',
      time: item.publish_time || item.created_at || item.time || '',
      sourceType,
      sourceLabel
    }
  })
)
</script>

<style scoped>
.evidence-list {
  display: grid;
  gap: var(--space-3);
}

.evidence-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: var(--space-4);
  align-items: center;
  min-height: 96px;
  padding: var(--space-4);
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-md);
  background: var(--color-bg-panel);
}

.evidence-item__rank {
  display: inline-grid;
  min-width: 58px;
  min-height: 30px;
  place-items: center;
  border-radius: var(--radius-sm);
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
  font-size: 12px;
  font-weight: 800;
}

.evidence-item__main {
  min-width: 0;
}

.evidence-item__main h3 {
  margin: 0;
  overflow: hidden;
  color: var(--color-text-strong);
  font-size: 15px;
  line-height: 1.45;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.evidence-item__main a {
  color: inherit;
}

.evidence-item__main a:hover {
  color: var(--color-primary);
}

.evidence-item__main p {
  display: -webkit-box;
  margin: 6px 0 0;
  overflow: hidden;
  color: var(--color-text-muted);
  font-size: 13px;
  line-height: 1.6;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.evidence-item__meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-top: 8px;
  color: var(--color-text-muted);
  font-size: 12px;
}

.evidence-item__source-badge {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0 8px;
  border: 1px solid #bae6fd;
  border-radius: 999px;
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}

.evidence-item__source-badge--web {
  color: #92400e;
  border-color: #fde68a;
  background: #fffbeb;
}

@media (max-width: 720px) {
  .evidence-item {
    grid-template-columns: 1fr;
  }

  .evidence-item__main h3 {
    white-space: normal;
  }
}
</style>
