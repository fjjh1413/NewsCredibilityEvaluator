<template>
  <section class="admin-statistics">
    <PageHeader
      eyebrow="管理员后台"
      title="数据统计"
      description="从检测、用户与知识库数据中查看平台运行趋势，支持按时间范围筛选。"
    >
      <template #actions>
        <button class="button button--secondary" type="button" :disabled="loading" @click="fetchStatistics">
          <Refresh aria-hidden="true" />
          <span>刷新数据</span>
        </button>
      </template>
    </PageHeader>

    <section class="surface-card surface-card--padded statistics-filter" aria-label="统计时间筛选">
      <label class="filter-field">
        <span>开始日期</span>
        <input v-model="filters.startDate" class="native-input" type="date" :max="filters.endDate || undefined" />
      </label>

      <label class="filter-field">
        <span>结束日期</span>
        <input v-model="filters.endDate" class="native-input" type="date" :min="filters.startDate || undefined" />
      </label>

      <div class="range-presets" aria-label="快捷时间范围">
        <button
          v-for="preset in rangePresets"
          :key="preset.days"
          class="range-preset"
          :class="{ 'range-preset--active': activePreset === preset.days }"
          type="button"
          :disabled="loading"
          @click="applyPreset(preset.days)"
        >
          {{ preset.label }}
        </button>
      </div>

      <div class="filter-actions">
        <button class="button button--primary" type="button" :disabled="loading" @click="handleQuery">
          <Search aria-hidden="true" />
          <span>查询</span>
        </button>
        <button class="button button--secondary" type="button" :disabled="loading" @click="resetRange">
          重置
        </button>
      </div>
    </section>

    <AdminEndpointNotice
      v-if="pendingEndpointLabels.length"
      title="部分统计接口待接入"
      description="页面仅展示后端实际返回的数据，未注册的接口保持空状态。"
      :endpoints="pendingEndpointLabels"
    />

    <section class="statistics-overview" aria-label="统计总览">
      <AdminStatCard
        v-for="card in overviewCards"
        :key="card.key"
        :title="card.title"
        :value="card.value"
        :description="card.description"
        :icon="card.icon"
        :tone="card.tone"
        :loading="card.loading"
      />
    </section>

    <section class="statistics-grid" aria-label="详细统计图表">
      <AdminChartPanel
        title="检测总量趋势"
        description="展示当前时间范围内每日新闻检测数量"
        chart-type="折线图"
        :option="trendOption"
        :loading="endpointStates.trend.loading"
        :error="endpointStates.trend.error"
        :empty-title="emptyTitle('trend')"
        :empty-description="emptyDescription('trend', '检测趋势')"
        :height="320"
        @retry="retryEndpoint('trend')"
      />

      <AdminChartPanel
        title="风险等级分布"
        description="按后端风险等级统计检测记录占比"
        chart-type="环形图"
        :option="riskOption"
        :loading="endpointStates.risk.loading"
        :error="endpointStates.risk.error"
        :empty-title="emptyTitle('risk')"
        :empty-description="emptyDescription('risk', '风险等级分布')"
        :height="320"
        @retry="retryEndpoint('risk')"
      />

      <AdminChartPanel
        title="新闻类别分布"
        description="对比不同新闻类别的检测数量"
        chart-type="柱状图"
        :option="categoryOption"
        :loading="endpointStates.category.loading"
        :error="endpointStates.category.error"
        :empty-title="emptyTitle('category')"
        :empty-description="emptyDescription('category', '新闻类别分布')"
        :height="320"
        @retry="retryEndpoint('category')"
      />

      <AdminChartPanel
        title="高频关键词 Top 10"
        description="统计检测记录中出现频率较高的关键词"
        chart-type="横向柱状图"
        :option="keywordOption"
        :loading="endpointStates.keywords.loading"
        :error="endpointStates.keywords.error"
        :empty-title="emptyTitle('keywords')"
        :empty-description="emptyDescription('keywords', '高频关键词')"
        :height="320"
        @retry="retryEndpoint('keywords')"
      />

      <AdminChartPanel
        title="用户活跃度"
        description="以每日发生检测行为的去重用户数衡量活跃度"
        chart-type="折线图"
        :option="activityOption"
        :loading="endpointStates.activity.loading"
        :error="endpointStates.activity.error"
        :empty-title="emptyTitle('activity')"
        :empty-description="emptyDescription('activity', '用户活跃度')"
        :height="320"
        @retry="retryEndpoint('activity')"
      />

      <AdminChartPanel
        title="知识库向量同步状态"
        :description="knowledgeChartDescription"
        chart-type="环形图"
        :option="knowledgeOption"
        :loading="endpointStates.knowledge.loading"
        :error="endpointStates.knowledge.error"
        :empty-title="emptyTitle('knowledge')"
        :empty-description="emptyDescription('knowledge', '知识库向量同步状态')"
        :height="320"
        @retry="retryEndpoint('knowledge')"
      />
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus/es/components/message/index.mjs'
import {
  Clock,
  DataAnalysis,
  Files,
  Refresh,
  Search,
  UserFilled,
  WarningFilled
} from '@element-plus/icons-vue'
import {
  getCategoryDistribution,
  getDetectionTrend,
  getKeywordStatistics,
  getKnowledgeOverview,
  getRiskDistribution,
  getStatisticsOverview,
  getUserActivity
} from '@/api/adminStatistics'
import AdminChartPanel from '@/components/admin/AdminChartPanel.vue'
import AdminEndpointNotice from '@/components/admin/AdminEndpointNotice.vue'
import AdminStatCard from '@/components/admin/AdminStatCard.vue'
import PageHeader from '@/components/PageHeader.vue'
import {
  createHorizontalBarChartOption,
  createLineChartOption,
  createRiskDonutOption,
  createVectorDonutOption,
  createVerticalBarChartOption,
  findDistributionValue,
  getStatisticsErrorMessage,
  isPendingStatisticsEndpoint,
  normalizeDistribution,
  normalizeNumber,
  normalizeTimeSeries,
  pickMetric,
  unwrapStatisticsResponse
} from '@/utils/statisticsCharts'

const endpointDefinitions = {
  overview: 'GET /api/admin/statistics/overview',
  trend: 'GET /api/admin/statistics/trend',
  risk: 'GET /api/admin/statistics/risk-distribution',
  category: 'GET /api/admin/statistics/category-distribution',
  keywords: 'GET /api/admin/statistics/keywords',
  activity: 'GET /api/admin/statistics/user-activity',
  knowledge: 'GET /api/admin/statistics/knowledge-overview'
}

const rangePresets = [
  { label: '近 7 日', days: 7 },
  { label: '近 30 日', days: 30 },
  { label: '近 90 日', days: 90 }
]

const filters = reactive({ startDate: '', endDate: '' })
const activePreset = ref(30)
const endpointStates = reactive(createEndpointStates())
const overview = ref({})
const trendData = ref([])
const riskDistribution = ref([])
const categoryDistribution = ref([])
const keywordDistribution = ref([])
const userActivity = ref([])
const knowledgeOverview = ref(createEmptyKnowledgeOverview())

const loading = computed(() => Object.values(endpointStates).some((state) => state.loading))
const pendingEndpointLabels = computed(() =>
  Object.entries(endpointDefinitions)
    .filter(([key]) => endpointStates[key].pending)
    .map(([, endpoint]) => endpoint)
)

const vectorFailedCount = computed(() => {
  const failed = findDistributionValue(knowledgeOverview.value.vector_status_distribution, ['failed', 'error', '失败'])

  if (failed !== null) {
    return failed
  }

  return knowledgeOverview.value.total_knowledge === 0 ? 0 : null
})

const overviewCards = computed(() => [
  {
    key: 'today',
    title: '今日检测数',
    value: pickMetric(overview.value, ['today_detections']),
    description: metricDescription('overview', '今日新增检测记录'),
    icon: Clock,
    tone: 'accent',
    loading: endpointStates.overview.loading
  },
  {
    key: 'detections',
    title: '总检测数',
    value: pickMetric(overview.value, ['total_detections']),
    description: metricDescription('overview', '累计新闻可信度评估'),
    icon: DataAnalysis,
    tone: 'primary',
    loading: endpointStates.overview.loading
  },
  {
    key: 'highRisk',
    title: '高风险新闻数',
    value: pickMetric(overview.value, ['total_high_risk']),
    description: metricDescription('overview', '以后端高风险标记为准'),
    icon: WarningFilled,
    tone: 'danger',
    loading: endpointStates.overview.loading
  },
  {
    key: 'knowledge',
    title: '知识库总数',
    value: knowledgeOverview.value.total_knowledge ?? pickMetric(overview.value, ['total_knowledge']),
    description: metricDescription('knowledge', 'MySQL 知识库记录'),
    icon: Files,
    tone: 'warning',
    loading: endpointStates.knowledge.loading
  },
  {
    key: 'users',
    title: '用户总数',
    value: pickMetric(overview.value, ['total_users']),
    description: metricDescription('overview', '平台注册用户'),
    icon: UserFilled,
    tone: 'success',
    loading: endpointStates.overview.loading
  },
  {
    key: 'vectorFailed',
    title: '向量同步失败数',
    value: vectorFailedCount.value,
    description: metricDescription('knowledge', '需要检查或重新向量化'),
    icon: WarningFilled,
    tone: 'danger',
    loading: endpointStates.knowledge.loading
  }
])

const trendOption = computed(() =>
  trendData.value.length
    ? createLineChartOption('检测数量', trendData.value, {
        color: '#0369A1',
        areaColor: 'rgba(14, 165, 233, 0.14)'
      })
    : null
)
const riskOption = computed(() => (riskDistribution.value.length ? createRiskDonutOption(riskDistribution.value) : null))
const categoryOption = computed(() =>
  categoryDistribution.value.length ? createVerticalBarChartOption('新闻数量', categoryDistribution.value) : null
)
const keywordOption = computed(() =>
  keywordDistribution.value.length
    ? createHorizontalBarChartOption('出现次数', keywordDistribution.value, { limit: 10, color: '#0C4A6E' })
    : null
)
const activityOption = computed(() =>
  userActivity.value.length
    ? createLineChartOption('活跃用户数', userActivity.value, {
        color: '#16A34A',
        areaColor: 'rgba(22, 163, 74, 0.12)'
      })
    : null
)
const knowledgeOption = computed(() =>
  knowledgeOverview.value.vector_status_distribution.length
    ? createVectorDonutOption(knowledgeOverview.value.vector_status_distribution)
    : null
)
const knowledgeChartDescription = computed(() => {
  const total = knowledgeOverview.value.total_knowledge
  return total === null
    ? '展示 MySQL 知识库记录与 Chroma 向量同步状态'
    : `MySQL 知识库共 ${total} 条，展示 Chroma 向量同步状态`
})

function createEndpointStates() {
  return Object.keys(endpointDefinitions).reduce((states, key) => {
    states[key] = { loading: false, pending: false, error: '' }
    return states
  }, {})
}

function createEmptyKnowledgeOverview() {
  return {
    total_knowledge: null,
    category_distribution: [],
    truth_label_distribution: [],
    vector_status_distribution: []
  }
}

function formatDateInput(date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function setDateRange(days) {
  const end = new Date()
  const start = new Date()
  start.setDate(end.getDate() - days + 1)
  filters.startDate = formatDateInput(start)
  filters.endDate = formatDateInput(end)
}

function buildQueryParams() {
  return {
    ...(filters.startDate ? { start_date: filters.startDate } : {}),
    ...(filters.endDate ? { end_date: filters.endDate } : {})
  }
}

function applyPreset(days) {
  activePreset.value = days
  setDateRange(days)
  fetchStatistics()
}

function resetRange() {
  activePreset.value = 30
  setDateRange(30)
  fetchStatistics()
}

function handleQuery() {
  if (filters.startDate && filters.endDate && filters.startDate > filters.endDate) {
    ElMessage.warning('开始日期不能晚于结束日期')
    return
  }

  activePreset.value = null
  fetchStatistics()
}

async function loadEndpoint(key) {
  const state = endpointStates[key]
  state.loading = true
  state.pending = false
  state.error = ''

  try {
    const payload = unwrapStatisticsResponse(await requestEndpoint(key))
    assignPayload(key, payload)
  } catch (error) {
    state.pending = isPendingStatisticsEndpoint(error)
    state.error = state.pending ? '' : getStatisticsErrorMessage(error)
    assignPayload(key, null)
  } finally {
    state.loading = false
  }
}

function requestEndpoint(key) {
  const params = buildQueryParams()

  const requestMap = {
    overview: () => getStatisticsOverview(),
    trend: () => getDetectionTrend(params),
    risk: () => getRiskDistribution(params),
    category: () => getCategoryDistribution(params),
    keywords: () => getKeywordStatistics({ ...params, limit: 10 }),
    activity: () => getUserActivity(params),
    knowledge: () => getKnowledgeOverview()
  }

  return requestMap[key]()
}

function assignPayload(key, payload) {
  if (key === 'overview') {
    overview.value = payload && typeof payload === 'object' && !Array.isArray(payload) ? payload : {}
  } else if (key === 'trend') {
    trendData.value = normalizeTimeSeries(payload, ['detection_count', 'detections'])
  } else if (key === 'risk') {
    riskDistribution.value = normalizeDistribution(payload, { nameKeys: ['risk_level'] })
  } else if (key === 'category') {
    categoryDistribution.value = normalizeDistribution(payload, { nameKeys: ['category'] })
  } else if (key === 'keywords') {
    keywordDistribution.value = normalizeDistribution(payload, { nameKeys: ['keyword'] })
  } else if (key === 'activity') {
    userActivity.value = normalizeTimeSeries(payload, ['active_users', 'active_count', 'user_count'])
  } else if (key === 'knowledge') {
    knowledgeOverview.value = normalizeKnowledgeOverview(payload)
  }
}

function normalizeKnowledgeOverview(payload) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return createEmptyKnowledgeOverview()
  }

  return {
    total_knowledge: normalizeNumber(payload.total_knowledge),
    category_distribution: normalizeDistribution(payload.category_distribution, { nameKeys: ['category'] }),
    truth_label_distribution: normalizeDistribution(payload.truth_label_distribution, { nameKeys: ['truth_label'] }),
    vector_status_distribution: normalizeDistribution(payload.vector_status_distribution, {
      nameKeys: ['vector_sync_status', 'status']
    })
  }
}

function fetchStatistics() {
  return Promise.all(Object.keys(endpointDefinitions).map(loadEndpoint))
}

function retryEndpoint(key) {
  loadEndpoint(key)
}

function metricDescription(key, fallback) {
  if (endpointStates[key].pending) return '统计接口待接入'
  if (endpointStates[key].error) return '数据暂不可用'
  return fallback
}

function emptyTitle(key) {
  return endpointStates[key].pending ? '统计接口待接入' : '暂无统计数据'
}

function emptyDescription(key, label) {
  if (endpointStates[key].pending) {
    return `${endpointDefinitions[key]} 当前未注册，${label}图表已保留接入位置。`
  }

  return `${label}接口未返回当前时间范围内的可展示数据。`
}

onMounted(() => {
  setDateRange(30)
  fetchStatistics()
})
</script>

<style scoped>
.admin-statistics {
  display: grid;
  gap: var(--space-6);
}

.admin-statistics :deep(.page-header__actions svg),
.admin-statistics .button svg {
  width: 16px;
  height: 16px;
}

.statistics-filter {
  display: grid;
  grid-template-columns: minmax(180px, 0.65fr) minmax(180px, 0.65fr) minmax(280px, 1.1fr) auto;
  gap: var(--space-4);
  align-items: end;
}

.filter-field {
  display: grid;
  gap: var(--space-2);
  min-width: 0;
}

.filter-field span {
  color: var(--color-text-strong);
  font-size: 13px;
  font-weight: 800;
}

.native-input {
  width: 100%;
  min-height: 40px;
  padding: 0 12px;
  border: 0;
  border-radius: var(--radius-sm);
  color: var(--color-text);
  background: #ffffff;
  box-shadow: 0 0 0 1px var(--color-border) inset;
}

.native-input:focus {
  box-shadow: 0 0 0 1px var(--color-primary) inset, var(--shadow-focus);
}

.range-presets,
.filter-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.range-preset {
  min-height: 40px;
  padding: 0 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
  background: #ffffff;
  cursor: pointer;
  font-weight: 700;
  transition: color 200ms ease, border-color 200ms ease, background-color 200ms ease;
}

.range-preset:hover,
.range-preset--active {
  color: var(--color-primary-strong);
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
}

.range-preset:disabled {
  cursor: not-allowed;
  opacity: 0.62;
}

.statistics-overview {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-4);
}

.statistics-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(340px, 0.85fr);
  gap: var(--space-6);
  align-items: stretch;
}

@media (max-width: 1280px) {
  .statistics-filter,
  .statistics-overview {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 1080px) {
  .statistics-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .statistics-filter,
  .statistics-overview {
    grid-template-columns: 1fr;
  }
}
</style>
