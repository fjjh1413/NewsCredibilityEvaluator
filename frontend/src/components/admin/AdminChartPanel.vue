<template>
  <article class="admin-chart-panel surface-card surface-card--padded">
    <header class="admin-chart-panel__header">
      <div>
        <h2>{{ title }}</h2>
        <p v-if="description">{{ description }}</p>
      </div>
      <span v-if="chartType" class="admin-chart-panel__tag">{{ chartType }}</span>
    </header>

    <div class="admin-chart-panel__body" :style="{ '--chart-height': `${height}px` }">
      <LoadingState v-if="loading" :lines="5" :label="`${title}加载中`" />

      <EmptyState
        v-else-if="error || !hasOption"
        :title="error ? '数据加载失败' : emptyTitle"
        :description="error || emptyDescription"
        :class="{ 'admin-chart-panel__empty--error': error }"
        role="status"
      >
        <template v-if="error" #actions>
          <button class="button button--secondary button--small" type="button" @click="$emit('retry')">
            <Refresh aria-hidden="true" />
            <span>重新加载</span>
          </button>
        </template>
      </EmptyState>

      <div
        v-else
        ref="chartRef"
        class="admin-chart-panel__chart"
        role="img"
        :aria-label="`${title}图表`"
      />
    </div>
  </article>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { Refresh } from '@element-plus/icons-vue'
import EmptyState from '@/components/EmptyState.vue'
import LoadingState from '@/components/LoadingState.vue'

echarts.use([BarChart, LineChart, PieChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

const props = defineProps({
  title: {
    type: String,
    required: true
  },
  description: {
    type: String,
    default: ''
  },
  chartType: {
    type: String,
    default: ''
  },
  option: {
    type: Object,
    default: null
  },
  loading: {
    type: Boolean,
    default: false
  },
  error: {
    type: String,
    default: ''
  },
  emptyTitle: {
    type: String,
    default: '暂无统计数据'
  },
  emptyDescription: {
    type: String,
    default: '当前时间范围内没有可展示的数据。'
  },
  height: {
    type: Number,
    default: 310
  }
})

defineEmits(['retry'])

const chartRef = ref(null)
const hasOption = computed(
  () => Boolean(props.option && Array.isArray(props.option.series) && props.option.series.length)
)

let chart = null
let resizeObserver = null

async function syncChart() {
  await nextTick()

  if (props.loading || props.error || !hasOption.value || !chartRef.value) {
    disposeChart()
    return
  }

  if (!chart || chart.getDom() !== chartRef.value) {
    disposeChart()
    chart = echarts.init(chartRef.value)
  }

  chart.setOption(props.option, true)
  observeChartSize()
}

function observeChartSize() {
  resizeObserver?.disconnect()

  if (!chartRef.value || typeof ResizeObserver === 'undefined') {
    return
  }

  resizeObserver = new ResizeObserver(() => chart?.resize())
  resizeObserver.observe(chartRef.value)
}

function resizeChart() {
  chart?.resize()
}

function disposeChart() {
  resizeObserver?.disconnect()
  resizeObserver = null
  chart?.dispose()
  chart = null
}

watch(
  () => [props.option, props.loading, props.error],
  syncChart,
  { deep: true }
)

onMounted(() => {
  syncChart()
  window.addEventListener('resize', resizeChart)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeChart)
  disposeChart()
})
</script>

<style scoped>
.admin-chart-panel {
  display: grid;
  gap: var(--space-5);
  min-width: 0;
  align-content: start;
}

.admin-chart-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
}

.admin-chart-panel__header h2,
.admin-chart-panel__header p {
  margin: 0;
}

.admin-chart-panel__header h2 {
  color: var(--color-text-strong);
  font-size: 18px;
  line-height: 1.35;
}

.admin-chart-panel__header p {
  margin-top: var(--space-2);
  color: var(--color-text-muted);
  font-size: 13px;
  line-height: 1.6;
}

.admin-chart-panel__tag {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  flex: 0 0 auto;
  border: 1px solid rgba(3, 105, 161, 0.16);
  border-radius: 999px;
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}

.admin-chart-panel__body,
.admin-chart-panel__chart,
.admin-chart-panel__body :deep(.empty-state),
.admin-chart-panel__body :deep(.loading-state) {
  width: 100%;
  min-height: var(--chart-height);
}

.admin-chart-panel__body {
  display: grid;
  align-items: stretch;
  min-width: 0;
}

.admin-chart-panel__chart {
  min-width: 0;
}

.admin-chart-panel__body :deep(.loading-state) {
  align-content: center;
}

.admin-chart-panel__body :deep(.admin-chart-panel__empty--error) {
  border-color: rgba(220, 38, 38, 0.25);
  background: rgba(254, 242, 242, 0.72);
}

.admin-chart-panel__body :deep(.button svg) {
  width: 16px;
  height: 16px;
}

@media (max-width: 640px) {
  .admin-chart-panel {
    gap: var(--space-4);
  }

  .admin-chart-panel__header {
    flex-direction: column;
  }

  .admin-chart-panel__body,
  .admin-chart-panel__chart,
  .admin-chart-panel__body :deep(.empty-state),
  .admin-chart-panel__body :deep(.loading-state) {
    min-height: min(var(--chart-height), 270px);
  }
}
</style>
