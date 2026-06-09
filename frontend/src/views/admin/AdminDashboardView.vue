<template>
  <section class="admin-dashboard">
    <PageHeader
      eyebrow="管理员后台"
      title="后台首页"
      description="集中查看平台检测量、风险分布、用户规模与知识库运行概况。"
    >
      <template #actions>
        <RouterLink class="button button--secondary" :to="{ name: 'adminStatistics' }">
          <DataAnalysis aria-hidden="true" />
          <span>完整数据统计</span>
        </RouterLink>
        <button class="button button--secondary" type="button" :disabled="loading" @click="fetchDashboard">
          <Refresh aria-hidden="true" />
          <span>刷新</span>
        </button>
      </template>
    </PageHeader>

    <AdminEndpointNotice
      v-if="pendingEndpointLabels.length"
      title="部分统计接口待接入"
      description="后台首页仅展示后端真实返回的核心指标，未注册接口保持空状态。"
      :endpoints="pendingEndpointLabels"
    />

    <section class="dashboard-stats" aria-label="后台核心统计">
      <AdminStatCard
        v-for="card in statCards"
        :key="card.key"
        :title="card.title"
        :value="card.value"
        :description="card.description"
        :icon="card.icon"
        :tone="card.tone"
        :loading="endpointStates.overview.loading"
      />
    </section>

    <section class="dashboard-chart-grid" aria-label="后台核心图表">
      <AdminChartPanel
        title="近 7 日检测趋势"
        description="快速观察每日新闻检测数量变化"
        chart-type="折线图"
        :option="trendOption"
        :loading="endpointStates.trend.loading"
        :error="endpointStates.trend.error"
        :empty-title="emptyTitle('trend')"
        :empty-description="emptyDescription('trend', '近 7 日检测趋势')"
        :height="300"
        @retry="retryEndpoint('trend')"
      />

      <AdminChartPanel
        title="风险等级分布"
        description="查看当前检测记录的风险层级占比"
        chart-type="环形图"
        :option="riskOption"
        :loading="endpointStates.risk.loading"
        :error="endpointStates.risk.error"
        :empty-title="emptyTitle('risk')"
        :empty-description="emptyDescription('risk', '风险等级分布')"
        :height="300"
        @retry="retryEndpoint('risk')"
      />
    </section>

    <section class="dashboard-latest" aria-labelledby="dashboard-latest-title">
      <header class="dashboard-section-heading">
        <div>
          <h2 id="dashboard-latest-title">最近高风险新闻</h2>
          <p>展示最近进入管理员审核队列的高风险检测记录</p>
        </div>
        <RouterLink class="text-link" :to="{ name: 'adminHighRisk' }">进入高风险管理</RouterLink>
      </header>
      <LoadingState v-if="recentHighRiskLoading" :lines="4" label="最近高风险记录加载中" />
      <EmptyState
        v-else-if="recentHighRiskError || !recentHighRiskRows.length"
        :title="recentHighRiskError ? '最近高风险记录加载失败' : '暂无高风险检测记录'"
        :description="recentHighRiskError || '高风险检测记录会自动进入管理员审核队列。'"
      />
      <div v-else class="dashboard-risk-list">
        <article v-for="item in recentHighRiskRows" :key="item.id">
          <div>
            <strong>{{ item.input_title || '未命名新闻' }}</strong>
            <span>{{ item.category || '未分类' }} · {{ formatDateTime(item.created_at) }}</span>
          </div>
          <RiskLevelTag :level="item.risk_level" :score="item.final_score" size="small" />
          <span class="dashboard-review-status">{{ reviewStatusText(item.review_status) }}</span>
        </article>
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { DataAnalysis, Files, Refresh, UserFilled, WarningFilled } from '@element-plus/icons-vue'
import {
  getDetectionTrend,
  getRiskDistribution,
  getStatisticsOverview
} from '@/api/adminStatistics'
import { getAdminHighRisk } from '@/api/adminHighRisk'
import AdminChartPanel from '@/components/admin/AdminChartPanel.vue'
import AdminEndpointNotice from '@/components/admin/AdminEndpointNotice.vue'
import AdminStatCard from '@/components/admin/AdminStatCard.vue'
import EmptyState from '@/components/EmptyState.vue'
import LoadingState from '@/components/LoadingState.vue'
import PageHeader from '@/components/PageHeader.vue'
import RiskLevelTag from '@/components/RiskLevelTag.vue'
import { formatDateTime } from '@/utils/format'
import {
  createLineChartOption,
  createRiskDonutOption,
  getStatisticsErrorMessage,
  isPendingStatisticsEndpoint,
  normalizeDistribution,
  normalizeTimeSeries,
  pickMetric,
  unwrapStatisticsResponse
} from '@/utils/statisticsCharts'

const endpointDefinitions = {
  overview: 'GET /api/admin/statistics/overview',
  trend: 'GET /api/admin/statistics/trend',
  risk: 'GET /api/admin/statistics/risk-distribution'
}

const endpointStates = reactive(createEndpointStates())
const overview = ref({})
const trendData = ref([])
const riskDistribution = ref([])
const recentHighRiskRows = ref([])
const recentHighRiskLoading = ref(false)
const recentHighRiskError = ref('')

const loading = computed(() => Object.values(endpointStates).some((state) => state.loading))
const pendingEndpointLabels = computed(() =>
  Object.entries(endpointDefinitions)
    .filter(([key]) => endpointStates[key].pending)
    .map(([, endpoint]) => endpoint)
)

const statCards = computed(() => [
  {
    key: 'totalDetections',
    title: '总检测数',
    value: pickMetric(overview.value, ['total_detections']),
    description: metricDescription('累计新闻可信度评估'),
    icon: DataAnalysis,
    tone: 'primary'
  },
  {
    key: 'totalHighRisk',
    title: '高风险新闻数',
    value: pickMetric(overview.value, ['total_high_risk']),
    description: metricDescription('以后端高风险标记为准'),
    icon: WarningFilled,
    tone: 'danger'
  },
  {
    key: 'totalKnowledge',
    title: '知识库数量',
    value: pickMetric(overview.value, ['total_knowledge']),
    description: metricDescription('MySQL 知识库记录'),
    icon: Files,
    tone: 'warning'
  },
  {
    key: 'totalUsers',
    title: '用户总数',
    value: pickMetric(overview.value, ['total_users']),
    description: metricDescription('平台注册用户'),
    icon: UserFilled,
    tone: 'success'
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

function createEndpointStates() {
  return Object.keys(endpointDefinitions).reduce((states, key) => {
    states[key] = { loading: false, pending: false, error: '' }
    return states
  }, {})
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
  const requestMap = {
    overview: () => getStatisticsOverview(),
    trend: () => getDetectionTrend({ days: 7 }),
    risk: () => getRiskDistribution()
  }

  return requestMap[key]()
}

function assignPayload(key, payload) {
  if (key === 'overview') {
    overview.value = payload && typeof payload === 'object' && !Array.isArray(payload) ? payload : {}
  } else if (key === 'trend') {
    trendData.value = normalizeTimeSeries(payload, ['detection_count', 'detections']).slice(-7)
  } else if (key === 'risk') {
    riskDistribution.value = normalizeDistribution(payload, { nameKeys: ['risk_level'] })
  }
}

function fetchDashboard() {
  return Promise.all([
    ...Object.keys(endpointDefinitions).map(loadEndpoint),
    loadRecentHighRisk()
  ])
}

function retryEndpoint(key) {
  loadEndpoint(key)
}

function metricDescription(fallback) {
  if (endpointStates.overview.pending) return '统计接口待接入'
  if (endpointStates.overview.error) return '数据暂不可用'
  return fallback
}

function emptyTitle(key) {
  return endpointStates[key].pending ? '统计接口待接入' : '暂无统计数据'
}

function emptyDescription(key, label) {
  if (endpointStates[key].pending) {
    return `${endpointDefinitions[key]} 当前未注册，${label}图表已保留接入位置。`
  }

  return `${label}接口暂未返回可展示数据。`
}

async function loadRecentHighRisk() {
  recentHighRiskLoading.value = true
  recentHighRiskError.value = ''
  try {
    const payload = unwrapStatisticsResponse(await getAdminHighRisk({ page: 1, page_size: 5 }))
    recentHighRiskRows.value = Array.isArray(payload?.items) ? payload.items : []
  } catch (error) {
    recentHighRiskRows.value = []
    recentHighRiskError.value = getStatisticsErrorMessage(error)
  } finally {
    recentHighRiskLoading.value = false
  }
}

function reviewStatusText(status) {
  return {
    pending: '待审核',
    approved: '审核通过',
    rejected: '审核驳回'
  }[status] || '未知状态'
}

onMounted(fetchDashboard)
</script>

<style scoped>
.admin-dashboard {
  display: grid;
  gap: var(--space-6);
}

.admin-dashboard :deep(.page-header__actions svg),
.admin-dashboard .button svg {
  width: 16px;
  height: 16px;
}

.dashboard-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-4);
}

.dashboard-chart-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(340px, 0.85fr);
  gap: var(--space-6);
  align-items: stretch;
}

.dashboard-latest {
  display: grid;
  gap: var(--space-4);
}

.dashboard-section-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-4);
}

.dashboard-section-heading h2,
.dashboard-section-heading p {
  margin: 0;
}

.dashboard-section-heading h2 {
  color: var(--color-text-strong);
  font-size: 18px;
}

.dashboard-section-heading p {
  margin-top: var(--space-2);
  color: var(--color-text-muted);
  font-size: 13px;
}

.dashboard-risk-list {
  display: grid;
  gap: var(--space-3);
}

.dashboard-risk-list article {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto 88px;
  gap: var(--space-4);
  align-items: center;
  padding: var(--space-4);
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-md);
  background: var(--color-bg-subtle);
}

.dashboard-risk-list article div {
  display: grid;
  gap: 5px;
  min-width: 0;
}

.dashboard-risk-list strong {
  overflow: hidden;
  color: var(--color-text-strong);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dashboard-risk-list span {
  color: var(--color-text-muted);
  font-size: 13px;
}

.dashboard-review-status {
  font-weight: 800;
  text-align: right;
}

@media (max-width: 1280px) {
  .dashboard-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 1080px) {
  .dashboard-chart-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .dashboard-stats {
    grid-template-columns: 1fr;
  }

  .dashboard-section-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .dashboard-risk-list article {
    grid-template-columns: 1fr;
  }

  .dashboard-review-status {
    text-align: left;
  }
}
</style>
