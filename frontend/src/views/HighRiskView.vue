<template>
  <div class="page-stack high-risk-page">
    <PageHeader
      eyebrow="公开风险态势"
      title="高风险新闻"
      description="查看经过管理员审核并允许公开的高风险新闻摘要、风险关键词与类别分布。"
    >
      <template #actions>
        <RouterLink class="button button--primary" :to="{ name: 'detect' }">检测新闻</RouterLink>
      </template>
    </PageHeader>

    <el-alert
      class="high-risk-intro"
      type="info"
      title="本页面仅展示经管理员审核并公开的高风险新闻记录，供用户了解常见风险类型和识别线索。"
      description="为避免风险内容继续传播，页面只提供摘要，不展示完整正文、管理员备注或内部审核信息。"
      show-icon
      :closable="false"
    />

    <section class="surface-card surface-card--padded high-risk-filter" aria-label="公开高风险新闻筛选">
      <label class="filter-field filter-field--keyword">
        <span>关键词</span>
        <el-input v-model.trim="filters.keyword" clearable placeholder="搜索标题或摘要" @keyup.enter="handleSearch" />
      </label>
      <label class="filter-field">
        <span>新闻类别</span>
        <el-select v-model="filters.category" clearable placeholder="全部类别">
          <el-option v-for="item in categoryStats" :key="item.name" :label="item.name" :value="item.name" />
        </el-select>
      </label>
      <label class="filter-field">
        <span>风险等级</span>
        <el-select v-model="filters.riskLevel" clearable placeholder="全部风险等级">
          <el-option label="高风险谣言" value="高风险谣言" />
          <el-option label="疑似谣言" value="疑似谣言" />
          <el-option label="存疑信息" value="存疑信息" />
        </el-select>
      </label>
      <label class="filter-field">
        <span>开始时间</span>
        <input v-model="filters.startDate" class="native-input" type="datetime-local" />
      </label>
      <label class="filter-field">
        <span>结束时间</span>
        <input v-model="filters.endDate" class="native-input" type="datetime-local" />
      </label>
      <div class="filter-actions">
        <button class="button button--primary" type="button" :disabled="listLoading" @click="handleSearch">
          <Search aria-hidden="true" />
          <span>查询</span>
        </button>
        <button class="button button--secondary" type="button" :disabled="listLoading" @click="handleReset">重置</button>
      </div>
    </section>

    <section class="high-risk-overview" aria-label="公开高风险新闻摘要">
      <article class="surface-card high-risk-metric">
        <span>公开记录</span>
        <strong>{{ total }}</strong>
        <p>符合当前筛选条件</p>
      </article>
      <article class="surface-card high-risk-metric">
        <span>排行榜记录</span>
        <strong>{{ rankingNews.length }}</strong>
        <p>按可信度评分从低到高</p>
      </article>
      <article class="surface-card high-risk-metric">
        <span>风险关键词</span>
        <strong>{{ keywordStats.length }}</strong>
        <p>公开记录 Top 10</p>
      </article>
      <article class="surface-card high-risk-metric">
        <span>涉及类别</span>
        <strong>{{ categoryStats.length }}</strong>
        <p>公开高风险新闻分布</p>
      </article>
    </section>

    <section class="high-risk-grid">
      <article class="surface-card surface-card--padded public-list-panel">
        <header class="panel-header">
          <div>
            <h2>最新公开高风险新闻</h2>
            <p>按审核公开时间倒序，仅展示摘要与识别线索。</p>
          </div>
          <button class="button button--secondary button--small" type="button" :disabled="listLoading" @click="fetchPublicNews">
            <Refresh aria-hidden="true" />
            <span>刷新</span>
          </button>
        </header>

        <LoadingState v-if="listLoading" :lines="6" label="公开高风险新闻加载中" />
        <EmptyState
          v-else-if="listError || !publicNews.length"
          :title="listError ? '高风险新闻加载失败' : filtersActive ? '当前筛选条件下暂无数据' : '暂无公开高风险新闻'"
          :description="listError || '通过审核并设置为公开的高风险记录会展示在这里。'"
        >
          <template v-if="listError" #actions>
            <button class="button button--secondary button--small" type="button" @click="fetchPublicNews">重新加载</button>
          </template>
        </EmptyState>

        <div v-else class="public-news-list">
          <article v-for="item in publicNews" :key="item.id" class="public-news-card">
            <div class="public-news-card__meta">
              <RiskLevelTag :level="item.risk_level" :score="item.final_score" size="small" />
              <span>{{ formatDateTime(item.published_at) }}</span>
            </div>
            <h3>{{ item.title || '未命名新闻' }}</h3>
            <p>{{ item.summary || '暂无摘要' }}</p>
            <div class="public-news-card__facts">
              <span>{{ item.category || '未分类' }}</span>
              <span>可信度评分 {{ formatScore(item.final_score) }}</span>
            </div>
            <div v-if="item.keywords?.length" class="keyword-list" aria-label="风险关键词">
              <span v-for="keyword in item.keywords.slice(0, 6)" :key="keyword">{{ keyword }}</span>
            </div>
          </article>
        </div>

        <div v-if="total > pagination.pageSize" class="public-pagination">
          <span>共 {{ total }} 条公开记录</span>
          <el-pagination
            background
            layout="prev, pager, next"
            :current-page="pagination.page"
            :page-size="pagination.pageSize"
            :total="total"
            @current-change="handlePageChange"
          />
        </div>
      </article>

      <article class="surface-card surface-card--padded ranking-panel">
        <header class="panel-header">
          <div>
            <h2>高风险新闻排行榜</h2>
            <p>评分越低代表可信度越低，同分时优先展示较新的记录。</p>
          </div>
        </header>
        <LoadingState v-if="insightLoading" :lines="5" label="排行榜加载中" />
        <EmptyState
          v-else-if="rankingError || !rankingNews.length"
          :title="rankingError ? '排行榜加载失败' : '暂无排行榜数据'"
          :description="rankingError || '暂无已审核公开的高风险新闻。'"
        />
        <ol v-else class="risk-ranking">
          <li v-for="(item, index) in rankingNews" :key="item.id">
            <span class="risk-ranking__index">{{ index + 1 }}</span>
            <div>
              <h3>{{ item.title || '未命名新闻' }}</h3>
              <p>{{ item.category || '未分类' }} · {{ formatDateTime(item.published_at) }}</p>
            </div>
            <strong>{{ formatScore(item.final_score) }}</strong>
          </li>
        </ol>
      </article>
    </section>

    <section class="high-risk-chart-grid">
      <AdminChartPanel
        title="高频风险关键词"
        description="公开高风险新闻中出现频率较高的识别线索。"
        chart-type="Top 10"
        :option="keywordChartOption"
        :loading="insightLoading"
        :error="keywordError"
        empty-description="暂无公开高风险新闻关键词统计。"
        @retry="fetchInsights"
      />
      <AdminChartPanel
        title="高风险类别分布"
        description="公开高风险新闻所属类别及数量。"
        chart-type="类别分布"
        :option="categoryChartOption"
        :loading="insightLoading"
        :error="categoryError"
        empty-description="暂无公开高风险新闻类别统计。"
        @retry="fetchInsights"
      />
    </section>

    <section class="high-risk-disclaimer">
      页面内容仅用于辅助识别与风险提示，不能替代人工事实核查、官方通报或权威媒体结论。
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Refresh, Search } from '@element-plus/icons-vue'
import {
  getHighRiskCategoryDistribution,
  getHighRiskKeywords,
  getHighRiskRanking,
  getPublicHighRiskNews
} from '@/api/highRisk'
import EmptyState from '@/components/EmptyState.vue'
import LoadingState from '@/components/LoadingState.vue'
import PageHeader from '@/components/PageHeader.vue'
import RiskLevelTag from '@/components/RiskLevelTag.vue'
import AdminChartPanel from '@/components/admin/AdminChartPanel.vue'
import { formatDateTime, formatScore } from '@/utils/format'
import {
  createHorizontalBarChartOption,
  createVerticalBarChartOption,
  getStatisticsErrorMessage,
  normalizeDistribution,
  unwrapStatisticsResponse
} from '@/utils/statisticsCharts'

const publicNews = ref([])
const rankingNews = ref([])
const keywordStats = ref([])
const categoryStats = ref([])
const total = ref(0)
const listLoading = ref(false)
const insightLoading = ref(false)
const listError = ref('')
const rankingError = ref('')
const keywordError = ref('')
const categoryError = ref('')

const filters = reactive({
  keyword: '',
  category: '',
  riskLevel: '',
  startDate: '',
  endDate: ''
})
const pagination = reactive({ page: 1, pageSize: 6 })

const filtersActive = computed(() => Object.values(filters).some(Boolean))
const queryParams = computed(() => {
  const params = { page: pagination.page, page_size: pagination.pageSize }
  if (filters.keyword) params.keyword = filters.keyword
  if (filters.category) params.category = filters.category
  if (filters.riskLevel) params.risk_level = filters.riskLevel
  if (filters.startDate) params.start_date = filters.startDate
  if (filters.endDate) params.end_date = filters.endDate
  return params
})
const keywordChartOption = computed(() =>
  keywordStats.value.length ? createHorizontalBarChartOption('出现次数', keywordStats.value, { limit: 10 }) : null
)
const categoryChartOption = computed(() =>
  categoryStats.value.length ? createVerticalBarChartOption('公开记录数', categoryStats.value) : null
)

async function fetchPublicNews() {
  listLoading.value = true
  listError.value = ''
  try {
    const data = unwrapStatisticsResponse(await getPublicHighRiskNews(queryParams.value))
    publicNews.value = Array.isArray(data?.items) ? data.items : []
    total.value = Number(data?.total) || 0
  } catch (error) {
    publicNews.value = []
    total.value = 0
    listError.value = getStatisticsErrorMessage(error)
  } finally {
    listLoading.value = false
  }
}

async function fetchInsights() {
  insightLoading.value = true
  rankingError.value = ''
  keywordError.value = ''
  categoryError.value = ''
  const results = await Promise.allSettled([
    getHighRiskRanking({ limit: 10 }),
    getHighRiskKeywords({ limit: 10 }),
    getHighRiskCategoryDistribution()
  ])

  if (results[0].status === 'fulfilled') {
    const data = unwrapStatisticsResponse(results[0].value)
    rankingNews.value = Array.isArray(data?.items) ? data.items : []
  } else {
    rankingNews.value = []
    rankingError.value = getStatisticsErrorMessage(results[0].reason)
  }

  if (results[1].status === 'fulfilled') {
    keywordStats.value = normalizeDistribution(unwrapStatisticsResponse(results[1].value), {
      nameKeys: ['keyword']
    })
  } else {
    keywordStats.value = []
    keywordError.value = getStatisticsErrorMessage(results[1].reason)
  }

  if (results[2].status === 'fulfilled') {
    categoryStats.value = normalizeDistribution(unwrapStatisticsResponse(results[2].value), {
      nameKeys: ['category']
    })
  } else {
    categoryStats.value = []
    categoryError.value = getStatisticsErrorMessage(results[2].reason)
  }
  insightLoading.value = false
}

function handleSearch() {
  pagination.page = 1
  fetchPublicNews()
}

function handleReset() {
  Object.assign(filters, { keyword: '', category: '', riskLevel: '', startDate: '', endDate: '' })
  pagination.page = 1
  fetchPublicNews()
}

function handlePageChange(page) {
  pagination.page = page
  fetchPublicNews()
}

onMounted(() => {
  fetchPublicNews()
  fetchInsights()
})
</script>

<style scoped>
.high-risk-page,
.public-list-panel,
.ranking-panel {
  align-items: stretch;
}

.high-risk-intro {
  border-radius: var(--radius-lg);
}

.high-risk-filter {
  display: grid;
  grid-template-columns: minmax(220px, 1.25fr) repeat(4, minmax(150px, 0.8fr)) auto;
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

.filter-field :deep(.el-input__wrapper),
.filter-field :deep(.el-select__wrapper),
.native-input {
  min-height: 40px;
  border-radius: var(--radius-sm);
}

.native-input {
  width: 100%;
  padding: 0 var(--space-3);
  border: 1px solid var(--color-border);
  color: var(--color-text);
  background: #fff;
}

.filter-actions,
.public-news-card__meta,
.public-news-card__facts,
.public-pagination {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.filter-actions {
  min-width: 132px;
}

.filter-actions .button {
  white-space: nowrap;
}

.high-risk-overview {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-4);
}

.high-risk-metric {
  display: grid;
  gap: var(--space-2);
  padding: var(--space-5);
}

.high-risk-metric span,
.high-risk-metric p,
.panel-header p,
.public-news-card__meta span,
.public-news-card__facts,
.risk-ranking p,
.public-pagination span {
  color: var(--color-text-muted);
  font-size: 13px;
}

.high-risk-metric strong {
  color: var(--color-primary-strong);
  font-size: 32px;
}

.high-risk-metric p,
.panel-header p,
.public-news-card p,
.risk-ranking p {
  margin: 0;
}

.high-risk-grid,
.high-risk-chart-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(340px, 0.85fr);
  gap: var(--space-6);
  align-items: start;
}

.public-list-panel,
.ranking-panel {
  display: grid;
  gap: var(--space-5);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  gap: var(--space-4);
}

.panel-header h2 {
  margin: 0;
  color: var(--color-text-strong);
  font-size: 18px;
}

.panel-header p {
  margin-top: var(--space-2);
  line-height: 1.6;
}

.public-news-list,
.risk-ranking {
  display: grid;
  gap: var(--space-4);
}

.public-news-card {
  display: grid;
  gap: var(--space-3);
  padding: var(--space-5);
  border: 1px solid var(--color-border-soft);
  border-left: 4px solid var(--risk-high);
  border-radius: var(--radius-md);
  background: var(--color-bg-subtle);
}

.public-news-card__meta,
.public-news-card__facts,
.public-pagination {
  justify-content: space-between;
  flex-wrap: wrap;
}

.public-news-card h3,
.risk-ranking h3 {
  margin: 0;
  color: var(--color-text-strong);
  font-size: 16px;
  line-height: 1.5;
}

.public-news-card p {
  color: var(--color-text);
  line-height: 1.75;
}

.keyword-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.keyword-list span {
  padding: 5px 9px;
  border: 1px solid rgba(3, 105, 161, 0.16);
  border-radius: 999px;
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
  font-size: 12px;
  font-weight: 800;
}

.risk-ranking {
  margin: 0;
  padding: 0;
  list-style: none;
}

.risk-ranking li {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) 54px;
  gap: var(--space-3);
  align-items: center;
  padding: var(--space-4);
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-md);
  background: var(--color-bg-subtle);
}

.risk-ranking__index {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: var(--radius-sm);
  color: #fff;
  background: var(--color-primary-strong);
  font-weight: 800;
}

.risk-ranking strong {
  color: var(--risk-high);
  font-size: 20px;
  text-align: right;
}

.public-pagination {
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-border-soft);
}

.high-risk-disclaimer {
  padding: var(--space-5);
  border: 1px solid rgba(217, 119, 6, 0.24);
  border-radius: var(--radius-lg);
  color: var(--color-text);
  background: #fffbeb;
  line-height: 1.8;
}

@media (max-width: 1280px) {
  .high-risk-filter {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 980px) {
  .high-risk-overview {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .high-risk-grid,
  .high-risk-chart-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 680px) {
  .high-risk-filter,
  .high-risk-overview {
    grid-template-columns: 1fr;
  }

  .filter-actions,
  .public-pagination {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
