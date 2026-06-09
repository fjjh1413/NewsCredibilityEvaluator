<template>
  <section class="admin-reports">
    <PageHeader
      eyebrow="管理员后台"
      title="报告管理"
      description="查看检测报告记录、关联用户、检测结果和 PDF 文件状态。"
    >
      <template #actions>
        <button class="button button--secondary" type="button" :disabled="loading" @click="fetchReports">
          <Refresh aria-hidden="true" />
          <span>刷新</span>
        </button>
      </template>
    </PageHeader>

    <section class="surface-card surface-card--padded report-filter" aria-label="报告筛选">
      <label class="filter-field filter-field--keyword">
        <span>关键词</span>
        <el-input v-model.trim="filters.keyword" clearable placeholder="搜索报告、标题、用户或邮箱" @keyup.enter="handleSearch" />
      </label>

      <label class="filter-field">
        <span>用户 ID</span>
        <el-input v-model.trim="filters.userId" clearable placeholder="用户 ID" @keyup.enter="handleSearch" />
      </label>

      <label class="filter-field">
        <span>检测 ID</span>
        <el-input v-model.trim="filters.detectionId" clearable placeholder="检测记录 ID" @keyup.enter="handleSearch" />
      </label>

      <label class="filter-field">
        <span>报告状态</span>
        <el-select v-model="filters.status" clearable placeholder="全部状态">
          <el-option label="可下载" value="generated" />
          <el-option label="文件缺失" value="missing" />
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
        <button class="button button--primary" type="button" :disabled="loading" @click="handleSearch">
          <Search aria-hidden="true" />
          <span>查询</span>
        </button>
        <button class="button button--secondary" type="button" :disabled="loading" @click="resetFilters">重置</button>
      </div>
    </section>

    <section class="surface-card report-table-card">
      <LoadingState v-if="loading" :lines="6" label="报告记录加载中" />
      <el-table v-else class="report-table" :data="rows" row-key="report_id">
        <el-table-column label="报告 / 检测标题" min-width="260">
          <template #default="{ row }">
            <div class="report-title">
              <strong>{{ row.news_title || row.report_title || '未命名报告' }}</strong>
              <span>报告 #{{ row.report_id }} · 检测 #{{ row.detection_id }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="用户" min-width="140">
          <template #default="{ row }">
            <div class="muted-stack">
              <strong>{{ row.username || '未知用户' }}</strong>
              <span>ID {{ row.user_id || '--' }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="风险等级" width="150">
          <template #default="{ row }">
            <RiskLevelTag :level="row.risk_level" :score="row.final_score" size="small" />
          </template>
        </el-table-column>

        <el-table-column label="可信度" width="100">
          <template #default="{ row }">
            <strong class="score-text">{{ formatScore(row.final_score) }}</strong>
          </template>
        </el-table-column>

        <el-table-column label="PDF 文件" min-width="180">
          <template #default="{ row }">
            <div class="muted-stack">
              <strong>{{ row.file_name || '--' }}</strong>
              <span>{{ formatFileSize(row.file_size) }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <span class="status-pill" :class="statusClass(row.status)">
              {{ statusText(row.status) }}
            </span>
          </template>
        </el-table-column>

        <el-table-column label="生成时间" min-width="160">
          <template #default="{ row }">
            <span class="muted-text">{{ formatDateTime(row.created_at) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <div class="table-actions">
              <button class="text-button" type="button" @click="openDetail(row)">
                <View aria-hidden="true" />
                <span>详情</span>
              </button>
              <button
                class="text-button"
                type="button"
                :disabled="row.status !== 'generated'"
                @click="downloadReport(row)"
              >
                <Download aria-hidden="true" />
                <span>下载</span>
              </button>
            </div>
          </template>
        </el-table-column>

        <template #empty>
          <EmptyState
            :title="errorMessage ? '报告记录加载失败' : filtersActive ? '当前筛选条件下暂无报告' : '暂无报告记录'"
            :description="errorMessage || '用户在检测结果页生成 PDF 报告后，会出现在这里。'"
          >
            <template v-if="errorMessage" #actions>
              <button class="button button--secondary button--small" type="button" @click="fetchReports">重新加载</button>
            </template>
          </EmptyState>
        </template>
      </el-table>

      <div class="report-pagination">
        <span>共 {{ total }} 份报告</span>
        <el-pagination
          background
          layout="sizes, prev, pager, next"
          :current-page="pagination.page"
          :page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </section>

    <el-dialog v-model="detailVisible" title="报告详情" width="min(820px, 94vw)">
      <LoadingState v-if="detailLoading" :lines="5" label="报告详情加载中" />
      <EmptyState v-else-if="!detailData" title="详情加载失败" :description="detailError || '后端未返回报告详情。'" />
      <div v-else class="report-detail">
        <section class="detail-summary">
          <div>
            <span>报告状态</span>
            <strong :class="statusClass(detailData.status)">{{ statusText(detailData.status) }}</strong>
          </div>
          <div>
            <span>可信度评分</span>
            <strong>{{ formatScore(detailData.final_score) }}</strong>
          </div>
          <RiskLevelTag :level="detailData.risk_level" :score="detailData.final_score" size="large" />
        </section>

        <section class="detail-grid">
          <div><span>报告 ID</span><strong>{{ detailData.report_id }}</strong></div>
          <div><span>检测 ID</span><strong>{{ detailData.detection_id }}</strong></div>
          <div><span>用户</span><strong>{{ detailData.username || '未知用户' }} / {{ detailData.user_id || '--' }}</strong></div>
          <div><span>生成时间</span><strong>{{ formatDateTime(detailData.created_at) }}</strong></div>
        </section>

        <section class="detail-block">
          <h3>{{ detailData.news_title || '未命名新闻' }}</h3>
          <p>{{ detailData.news_summary || '暂无摘要' }}</p>
        </section>

        <section class="detail-grid">
          <div><span>文件名</span><strong>{{ detailData.file_name || '--' }}</strong></div>
          <div><span>文件大小</span><strong>{{ formatFileSize(detailData.file_size) }}</strong></div>
          <div><span>相对路径</span><strong>{{ detailData.report_path || '--' }}</strong></div>
          <div><span>下载地址</span><strong>{{ detailData.download_url || '--' }}</strong></div>
        </section>
      </div>
      <template #footer>
        <button class="button button--secondary" type="button" @click="detailVisible = false">关闭</button>
        <button
          class="button button--primary"
          type="button"
          :disabled="!detailData || detailData.status !== 'generated'"
          @click="downloadReport(detailData)"
        >
          下载报告
        </button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus/es/components/message/index.mjs'
import { Download, Refresh, Search, View } from '@element-plus/icons-vue'
import { downloadAdminReport, getAdminReportDetail, getAdminReports } from '@/api/adminReports'
import EmptyState from '@/components/EmptyState.vue'
import LoadingState from '@/components/LoadingState.vue'
import PageHeader from '@/components/PageHeader.vue'
import RiskLevelTag from '@/components/RiskLevelTag.vue'
import { formatDateTime, formatScore } from '@/utils/format'
import { unwrapStatisticsResponse } from '@/utils/statisticsCharts'

const rows = ref([])
const total = ref(0)
const loading = ref(false)
const errorMessage = ref('')
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailData = ref(null)
const detailError = ref('')

const filters = reactive({
  keyword: '',
  userId: '',
  detectionId: '',
  status: '',
  startDate: '',
  endDate: ''
})
const pagination = reactive({ page: 1, pageSize: 20 })

const filtersActive = computed(() => Object.values(filters).some(Boolean))
const queryParams = computed(() => {
  const params = { page: pagination.page, page_size: pagination.pageSize }
  if (filters.keyword) params.keyword = filters.keyword
  if (filters.userId) params.user_id = filters.userId
  if (filters.detectionId) params.detection_id = filters.detectionId
  if (filters.status) params.status = filters.status
  if (filters.startDate) params.start_date = filters.startDate
  if (filters.endDate) params.end_date = filters.endDate
  return params
})

async function fetchReports() {
  loading.value = true
  errorMessage.value = ''
  try {
    const data = unwrapStatisticsResponse(await getAdminReports(queryParams.value))
    rows.value = Array.isArray(data?.items) ? data.items : []
    total.value = Number(data?.total) || 0
  } catch (error) {
    rows.value = []
    total.value = 0
    errorMessage.value = await getErrorMessage(error, '报告记录加载失败，请稍后重试')
    ElMessage.error(errorMessage.value)
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pagination.page = 1
  fetchReports()
}

function resetFilters() {
  Object.assign(filters, {
    keyword: '',
    userId: '',
    detectionId: '',
    status: '',
    startDate: '',
    endDate: ''
  })
  pagination.page = 1
  fetchReports()
}

function handleSizeChange(size) {
  pagination.pageSize = size
  pagination.page = 1
  fetchReports()
}

function handlePageChange(page) {
  pagination.page = page
  fetchReports()
}

async function openDetail(row) {
  detailVisible.value = true
  detailLoading.value = true
  detailData.value = null
  detailError.value = ''
  try {
    detailData.value = unwrapStatisticsResponse(await getAdminReportDetail(row.report_id))
  } catch (error) {
    detailError.value = await getErrorMessage(error, '报告详情加载失败')
    ElMessage.error(detailError.value)
  } finally {
    detailLoading.value = false
  }
}

async function downloadReport(row) {
  if (!row?.report_id || row.status !== 'generated') {
    ElMessage.warning('报告文件不可下载，请确认文件状态')
    return
  }

  try {
    const payload = await downloadAdminReport(row.report_id)
    const blob = payload instanceof Blob ? payload : new Blob([payload], { type: 'application/pdf' })
    const objectUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = objectUrl
    link.download = row.file_name || `news-credibility-report-${row.report_id}.pdf`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(objectUrl)
  } catch (error) {
    ElMessage.error(await getErrorMessage(error, '报告下载失败，请稍后重试'))
  }
}

function statusText(status) {
  return { generated: '可下载', missing: '文件缺失' }[status] || '未知状态'
}

function statusClass(status) {
  return {
    generated: 'status-pill--success',
    missing: 'status-pill--danger'
  }[status] || 'status-pill--muted'
}

function formatFileSize(size) {
  const number = Number(size)
  if (!Number.isFinite(number) || number <= 0) return '--'
  if (number < 1024) return `${number} B`
  if (number < 1024 * 1024) return `${(number / 1024).toFixed(1)} KB`
  return `${(number / 1024 / 1024).toFixed(1)} MB`
}

async function getErrorMessage(error, fallback) {
  const data = error?.response?.data
  if (data instanceof Blob) {
    try {
      const text = await data.text()
      const parsed = JSON.parse(text)
      return parsed?.message || parsed?.detail || fallback
    } catch {
      return fallback
    }
  }
  return data?.message || data?.detail || error?.message || fallback
}

onMounted(fetchReports)
</script>

<style scoped>
.admin-reports,
.report-detail {
  display: grid;
  gap: var(--space-6);
}

.admin-reports .button svg,
.admin-reports .text-button svg {
  width: 16px;
  height: 16px;
}

.report-filter {
  display: grid;
  grid-template-columns: minmax(220px, 1.2fr) repeat(5, minmax(140px, 0.75fr)) auto;
  gap: var(--space-4);
  align-items: end;
}

.filter-field {
  display: grid;
  gap: var(--space-2);
  min-width: 0;
}

.filter-field span,
.detail-summary span,
.detail-grid span {
  color: var(--color-text-muted);
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
  padding: 0 12px;
  border: 1px solid var(--color-border);
  color: var(--color-text);
  background: #ffffff;
}

.filter-actions,
.table-actions,
.report-pagination {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.filter-actions,
.table-actions {
  flex-wrap: wrap;
}

.report-table-card {
  overflow: hidden;
}

.report-table :deep(.el-table__header th) {
  color: var(--color-text-strong);
  background: var(--color-bg-subtle);
  font-size: 13px;
  font-weight: 800;
}

.report-title,
.muted-stack {
  display: grid;
  gap: 4px;
}

.report-title strong,
.muted-stack strong {
  overflow: hidden;
  color: var(--color-text-strong);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.report-title span,
.muted-stack span,
.muted-text,
.report-pagination span {
  color: var(--color-text-muted);
  font-size: 13px;
}

.score-text {
  color: var(--color-primary-strong);
}

.status-pill {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 0 9px;
  border: 1px solid currentColor;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}

.status-pill--success {
  color: var(--color-success);
  background: var(--risk-trusted-bg);
}

.status-pill--danger {
  color: var(--color-danger);
  background: var(--risk-high-bg);
}

.status-pill--muted {
  color: var(--color-text-muted);
  background: var(--color-bg-subtle);
}

.text-button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 30px;
  padding: 0 7px;
  border: 0;
  border-radius: var(--radius-sm);
  color: var(--color-primary-strong);
  background: transparent;
  cursor: pointer;
  font-weight: 800;
}

.text-button:hover {
  background: var(--color-primary-soft);
}

.text-button:disabled {
  cursor: not-allowed;
  opacity: 0.52;
}

.report-pagination {
  justify-content: space-between;
  padding: var(--space-4) var(--space-5);
  border-top: 1px solid var(--color-border-soft);
}

.detail-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-4);
  align-items: center;
  padding: var(--space-5);
  border: 1px solid var(--color-border-soft);
  border-left: 4px solid var(--color-primary);
  border-radius: var(--radius-md);
  background: var(--color-bg-subtle);
}

.detail-summary div,
.detail-grid div {
  display: grid;
  gap: var(--space-2);
}

.detail-summary strong,
.detail-grid strong {
  overflow-wrap: anywhere;
  color: var(--color-text-strong);
}

.detail-block {
  padding: var(--space-5);
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-md);
}

.detail-block h3,
.detail-block p {
  margin: 0;
}

.detail-block h3 {
  color: var(--color-text-strong);
  font-size: 18px;
}

.detail-block p {
  margin-top: var(--space-3);
  color: var(--color-text);
  line-height: 1.8;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
}

.detail-grid div {
  padding: var(--space-4);
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-md);
}

@media (max-width: 1440px) {
  .report-filter {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 860px) {
  .report-filter,
  .detail-summary,
  .detail-grid {
    grid-template-columns: 1fr;
  }

  .report-pagination {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
