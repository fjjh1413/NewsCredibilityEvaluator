<template>
  <div class="page-stack history-page">
    <PageHeader
      eyebrow="个人记录"
      title="历史记录"
      description="查看当前账号提交过的新闻可信度检测记录，按风险等级、关键词和分页快速定位结果。"
    >
      <template #actions>
        <RouterLink class="button button--primary" :to="{ name: 'detect' }">去检测新闻</RouterLink>
      </template>
    </PageHeader>

    <section class="history-filter surface-card surface-card--padded" aria-label="历史记录筛选">
      <div class="history-filter__heading">
        <h2>筛选条件</h2>
        <p>普通用户仅查看本人检测记录，结果评分与风险等级均以后端返回为准。</p>
      </div>

      <el-form class="history-filter__form" label-position="top" @submit.prevent>
        <el-form-item label="关键词搜索">
          <el-input
            v-model.trim="filters.keyword"
            :prefix-icon="Search"
            clearable
            placeholder="搜索新闻标题关键词"
            @keyup.enter="handleSearch"
          />
        </el-form-item>

        <el-form-item label="风险等级">
          <el-select v-model="filters.riskLevel" clearable placeholder="全部风险等级">
            <el-option
              v-for="level in riskOptions"
              :key="level"
              :label="level"
              :value="level"
            />
          </el-select>
        </el-form-item>

        <div class="history-filter__actions">
          <el-button class="history-action history-action--primary" :loading="loading" @click="handleSearch">
            <el-icon><Search /></el-icon>
            查询
          </el-button>
          <el-button class="history-action history-action--secondary" :disabled="loading" @click="handleReset">
            <el-icon><Refresh /></el-icon>
            重置
          </el-button>
        </div>
      </el-form>
    </section>

    <LoadingState v-if="loading && !rows.length" :lines="6" label="历史记录加载中" />

    <section v-else class="history-table-card surface-card" aria-label="检测历史列表">
      <div class="history-table-card__header">
        <div>
          <h2>检测列表</h2>
          <p>共 {{ total }} 条记录</p>
        </div>
        <span class="history-table-card__meta">GET /api/detect/history</span>
      </div>

      <el-alert
        v-if="errorMessage"
        class="history-error"
        type="error"
        :title="errorMessage"
        show-icon
        :closable="false"
      />

      <EmptyState
        v-if="!loading && !rows.length"
        title="暂无检测记录"
        description="提交第一条新闻后，检测结果会保存在这里。"
        action-text="去检测新闻"
        :to="{ name: 'detect' }"
      />

      <template v-else>
        <div v-loading="loading" class="history-table-wrap" element-loading-text="正在刷新记录">
          <el-table
            class="history-table"
            :data="rows"
            row-key="rowKey"
            style="width: 100%"
          >
            <el-table-column prop="title" label="新闻标题" min-width="260" show-overflow-tooltip>
              <template #default="{ row }">
                <button class="history-title" type="button" @click="goDetail(row)">
                  {{ row.title }}
                </button>
              </template>
            </el-table-column>

            <el-table-column label="检测时间" width="170">
              <template #default="{ row }">
                <span class="history-muted">{{ formatDateTime(row.detectedAt) }}</span>
              </template>
            </el-table-column>

            <el-table-column label="可信度评分" width="160">
              <template #default="{ row }">
                <div class="history-score">
                  <span>{{ formatScore(row.finalScore) }}</span>
                  <div class="history-score__track" aria-hidden="true">
                    <i :style="{ width: `${scorePercent(row.finalScore)}%` }" />
                  </div>
                </div>
              </template>
            </el-table-column>

            <el-table-column label="风险等级" width="150" align="center">
              <template #default="{ row }">
                <RiskLevelTag :level="row.riskLevel" :score="row.finalScore" size="small" />
              </template>
            </el-table-column>

            <el-table-column label="是否高风险" width="120" align="center">
              <template #default="{ row }">
                <span
                  v-if="row.isHighRisk !== null"
                  class="history-high"
                  :class="{ 'history-high--danger': row.isHighRisk }"
                >
                  {{ row.isHighRisk ? '是' : '否' }}
                </span>
                <span v-else class="history-muted">--</span>
              </template>
            </el-table-column>

            <el-table-column label="报告状态" width="150" align="center">
              <template #default="{ row }">
                <button
                  v-if="row.reportUrl"
                  class="history-report-link"
                  type="button"
                  :disabled="downloadingReportId === row.reportId"
                  :aria-busy="downloadingReportId === row.reportId"
                  @click="handleDownloadReport(row)"
                >
                  <el-icon>
                    <Loading v-if="downloadingReportId === row.reportId" class="history-report-link__loading" />
                    <Download v-else />
                  </el-icon>
                  {{ downloadingReportId === row.reportId ? '下载中' : '下载报告' }}
                </button>
                <span v-else class="history-muted">暂未生成</span>
              </template>
            </el-table-column>

            <el-table-column label="查看详情" width="130" fixed="right" align="center">
              <template #default="{ row }">
                <el-button
                  class="history-detail-button"
                  :disabled="!row.id"
                  text
                  @click="goDetail(row)"
                >
                  <el-icon><View /></el-icon>
                  详情
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="history-pagination">
          <el-pagination
            v-model:current-page="pagination.page"
            v-model:page-size="pagination.pageSize"
            :page-sizes="[10, 20, 50]"
            :total="total"
            background
            layout="total, sizes, prev, pager, next, jumper"
            @size-change="handleSizeChange"
            @current-change="handleCurrentChange"
          />
        </div>
      </template>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Download, Loading, Refresh, Search, View } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus/es/components/message/index.mjs'
import { getDetectionHistory } from '@/api/detect'
import { downloadReportFile } from '@/api/report'
import EmptyState from '@/components/EmptyState.vue'
import LoadingState from '@/components/LoadingState.vue'
import PageHeader from '@/components/PageHeader.vue'
import RiskLevelTag from '@/components/RiskLevelTag.vue'
import { formatDateTime, formatScore, scoreToPercent as normalizeScorePercent } from '@/utils/format'

const router = useRouter()

const loading = ref(false)
const errorMessage = ref('')
const rawRows = ref([])
const rows = ref([])
const total = ref(0)
const responseUsesLocalList = ref(false)
const downloadingReportId = ref('')

const filters = reactive({
  keyword: '',
  riskLevel: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 10
})

const riskOptions = ['可信新闻', '存疑信息', '疑似谣言', '高风险谣言']

const queryParams = computed(() => ({
  page: pagination.page,
  page_size: pagination.pageSize,
  keyword: filters.keyword || undefined,
  risk_level: filters.riskLevel || undefined
}))

function unwrapApiResponse(response) {
  const body = response?.data ?? response
  const code = body?.code

  if (code !== undefined && ![0, 200].includes(Number(code))) {
    throw new Error(body?.message || '历史记录加载失败')
  }

  if (body?.success === false) {
    throw new Error(body?.message || '历史记录加载失败')
  }

  if (body?.data !== undefined && (body?.code !== undefined || body?.success !== undefined || body?.message !== undefined)) {
    if (Array.isArray(body.data)) {
      return {
        items: body.data,
        total: body.total ?? body.count ?? body.total_count ?? body.totalCount ?? body.data.length
      }
    }

    if (body.data && typeof body.data === 'object') {
      return {
        ...body.data,
        total: body.data.total ?? body.total ?? body.count ?? body.total_count ?? body.totalCount
      }
    }

    return body.data
  }

  return body
}

function pickList(payload) {
  if (Array.isArray(payload)) {
    return {
      items: payload,
      total: payload.length,
      localList: true
    }
  }

  if (!payload || typeof payload !== 'object') {
    return {
      items: [],
      total: 0,
      localList: false
    }
  }

  const directCandidates = [
    payload.items,
    payload.records,
    payload.list,
    payload.rows,
    payload.results,
    payload.histories
  ]

  const items = directCandidates.find(Array.isArray)

  if (items) {
    return {
      items,
      total: Number(payload.total ?? payload.count ?? payload.total_count ?? payload.totalCount ?? items.length),
      localList: false
    }
  }

  if (Array.isArray(payload.data)) {
    return {
      items: payload.data,
      total: Number(payload.total ?? payload.count ?? payload.total_count ?? payload.totalCount ?? payload.data.length),
      localList: false
    }
  }

  if (payload.data && typeof payload.data === 'object') {
    return pickList(payload.data)
  }

  return {
    items: [],
    total: 0,
    localList: false
  }
}

function normalizeBoolean(value) {
  if (value === true || value === 1 || value === '1') {
    return true
  }

  if (value === false || value === 0 || value === '0') {
    return false
  }

  const text = String(value || '').toLowerCase()

  if (['true', 'yes', '是'].includes(text)) {
    return true
  }

  if (['false', 'no', '否'].includes(text)) {
    return false
  }

  return null
}

function resolveHighRisk(item) {
  const explicitValue = item?.is_high_risk ?? item?.isHighRisk ?? item?.high_risk ?? item?.highRisk
  return normalizeBoolean(explicitValue)
}

function normalizeRecord(item, index) {
  const id = item?.detection_id ?? item?.id ?? item?.record_id ?? item?.result_id ?? item?.report_id ?? ''
  const title = item?.input_title ?? item?.news_title ?? item?.title ?? item?.headline ?? '未命名新闻'
  const riskLevel = item?.risk_level ?? item?.riskLevel ?? item?.risk ?? ''
  const reportUrl = item?.report_url ?? item?.reportUrl ?? item?.pdf_url ?? item?.pdfUrl ?? ''
  const reportId = item?.report_id ?? item?.reportId ?? extractReportId(reportUrl)

  return {
    id,
    rowKey: id || `${pagination.page}-${index}`,
    title,
    detectedAt: item?.detected_at ?? item?.detection_time ?? item?.created_at ?? item?.create_time ?? item?.updated_at ?? '',
    finalScore: item?.final_score ?? item?.credibility_score ?? item?.score ?? item?.finalScore ?? null,
    riskLevel,
    isHighRisk: resolveHighRisk(item),
    reportUrl,
    reportId
  }
}

function applyLocalQuery(items) {
  let list = items

  if (filters.keyword) {
    const keyword = filters.keyword.toLowerCase()
    list = list.filter((item) => {
      const searchableText = [
        item.title,
        item.riskLevel
      ].join(' ').toLowerCase()
      return searchableText.includes(keyword)
    })
  }

  if (filters.riskLevel) {
    list = list.filter((item) => String(item.riskLevel || '').includes(filters.riskLevel))
  }

  total.value = list.length

  const start = (pagination.page - 1) * pagination.pageSize
  rows.value = list.slice(start, start + pagination.pageSize)
}

async function fetchHistory() {
  loading.value = true
  errorMessage.value = ''

  try {
    const response = await getDetectionHistory(queryParams.value)
    const payload = unwrapApiResponse(response)
    const listPayload = pickList(payload)
    const normalized = listPayload.items.map(normalizeRecord)

    rawRows.value = normalized
    responseUsesLocalList.value = listPayload.localList

    if (listPayload.localList) {
      applyLocalQuery(normalized)
    } else {
      rows.value = normalized
      total.value = Number.isFinite(listPayload.total) ? listPayload.total : normalized.length
    }
  } catch (error) {
    const message =
      error?.response?.data?.message ||
      error?.response?.data?.detail ||
      error?.message ||
      '历史记录加载失败，请稍后重试'

    errorMessage.value = message
    rows.value = []
    total.value = 0
    ElMessage.error(message)
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pagination.page = 1

  if (responseUsesLocalList.value) {
    applyLocalQuery(rawRows.value)
    return
  }

  fetchHistory()
}

function handleReset() {
  filters.keyword = ''
  filters.riskLevel = ''
  pagination.page = 1

  fetchHistory()
}

function handleSizeChange(size) {
  pagination.pageSize = size
  pagination.page = 1

  if (responseUsesLocalList.value) {
    applyLocalQuery(rawRows.value)
    return
  }

  fetchHistory()
}

function handleCurrentChange(page) {
  pagination.page = page

  if (responseUsesLocalList.value) {
    applyLocalQuery(rawRows.value)
    return
  }

  fetchHistory()
}

function scorePercent(score) {
  const value = normalizeScorePercent(score)

  if (value === null) {
    return 0
  }

  return value
}

function extractReportId(url) {
  const match = String(url || '').match(/\/report\/download\/(\d+)(?:[/?#]|$)/)
  return match?.[1] || ''
}

function getFilenameFromDisposition(disposition) {
  if (!disposition) {
    return ''
  }

  const encodedMatch = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (encodedMatch?.[1]) {
    try {
      return decodeURIComponent(encodedMatch[1])
    } catch {
      return encodedMatch[1]
    }
  }

  const plainMatch = disposition.match(/filename="?([^";]+)"?/i)
  return plainMatch?.[1] || ''
}

function sanitizeFilename(name) {
  return String(name || '')
    .replace(/[\\/:*?"<>|]+/g, '_')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 120)
}

function saveBlob(blob, filename) {
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')

  link.href = objectUrl
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
}

async function getDownloadErrorMessage(error) {
  const data = error?.response?.data

  if (data instanceof Blob) {
    try {
      const text = await data.text()
      const payload = JSON.parse(text)
      return payload?.message || payload?.detail || 'PDF 报告下载失败'
    } catch {
      return 'PDF 报告下载失败'
    }
  }

  return (
    data?.message ||
    data?.detail ||
    error?.message ||
    'PDF 报告下载失败'
  )
}

async function handleDownloadReport(row) {
  if (!row?.reportId) {
    ElMessage.error('报告下载信息不完整，请进入结果页重新生成报告')
    return
  }

  downloadingReportId.value = row.reportId

  try {
    const response = await downloadReportFile(row.reportId)
    const blob = response?.data instanceof Blob
      ? response.data
      : new Blob([response?.data || response], { type: 'application/pdf' })
    const headerFilename = getFilenameFromDisposition(response?.headers?.['content-disposition'])
    const fallbackFilename = `${sanitizeFilename(row.title) || 'news-credibility-report'}-${row.reportId}.pdf`

    saveBlob(blob, headerFilename || fallbackFilename)
    ElMessage.success('PDF 报告下载已开始')
  } catch (error) {
    ElMessage.error(await getDownloadErrorMessage(error))
  } finally {
    downloadingReportId.value = ''
  }
}

function goDetail(row) {
  if (!row?.id) {
    return
  }

  router.push({
    name: 'result',
    params: { id: row.id }
  })
}

onMounted(fetchHistory)
</script>

<style scoped>
.history-page {
  align-items: stretch;
}

.history-filter {
  display: grid;
  gap: var(--space-5);
}

.history-filter__heading {
  display: grid;
  gap: var(--space-2);
}

.history-filter__heading h2,
.history-table-card__header h2 {
  margin: 0;
  color: var(--color-text-strong);
  font-size: 18px;
}

.history-filter__heading p,
.history-table-card__header p {
  margin: 0;
  color: var(--color-text-muted);
  line-height: 1.7;
}

.history-filter__form {
  display: grid;
  grid-template-columns: minmax(260px, 1.2fr) minmax(220px, 0.7fr) auto;
  gap: var(--space-4);
  align-items: end;
}

.history-filter__actions {
  display: flex;
  gap: var(--space-3);
  min-height: 40px;
  padding-bottom: 18px;
}

.history-action {
  min-width: 92px;
  min-height: 40px;
  border-radius: var(--radius-sm);
  font-weight: 700;
}

.history-action--primary {
  color: #ffffff;
  border-color: var(--color-primary);
  background: var(--color-primary);
}

.history-action--primary:hover,
.history-action--primary:focus {
  color: #ffffff;
  border-color: var(--color-primary-strong);
  background: var(--color-primary-strong);
}

.history-action--secondary {
  color: var(--color-primary-strong);
  border-color: var(--color-border);
  background: #ffffff;
}

.history-action--secondary:hover,
.history-action--secondary:focus {
  color: var(--color-primary-strong);
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
}

.history-table-card {
  display: grid;
  gap: var(--space-5);
  padding: var(--space-6);
}

.history-table-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
}

.history-table-card__meta {
  display: inline-flex;
  min-height: 28px;
  align-items: center;
  padding: 0 var(--space-3);
  border: 1px solid var(--color-border-soft);
  border-radius: 999px;
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}

.history-error {
  border-radius: var(--radius-md);
}

.history-table-wrap {
  overflow-x: auto;
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-lg);
}

.history-table {
  min-width: 980px;
}

.history-title {
  display: inline-block;
  width: 100%;
  min-height: 32px;
  padding: 0;
  overflow: hidden;
  border: 0;
  color: var(--color-text-strong);
  background: transparent;
  font-weight: 700;
  line-height: 32px;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
}

.history-title:hover,
.history-title:focus-visible {
  color: var(--color-primary);
}

.history-muted {
  color: var(--color-text-muted);
  font-size: 13px;
}

.history-score {
  display: grid;
  gap: 7px;
  min-width: 110px;
}

.history-score span {
  color: var(--color-text-strong);
  font-size: 15px;
  font-weight: 800;
}

.history-score__track {
  height: 6px;
  overflow: hidden;
  border-radius: 999px;
  background: #e6eef6;
}

.history-score__track i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--color-primary), var(--color-accent));
}

.history-high {
  display: inline-flex;
  min-height: 26px;
  align-items: center;
  padding: 0 10px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  color: var(--color-text-muted);
  background: var(--color-bg-subtle);
  font-size: 12px;
  font-weight: 800;
}

.history-high--danger {
  color: var(--risk-high);
  border-color: rgba(220, 38, 38, 0.35);
  background: var(--risk-high-bg);
}

.history-report-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 30px;
  padding: 0 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-primary-strong);
  background: #ffffff;
  font-size: 13px;
  font-weight: 700;
  transition: color 200ms ease, border-color 200ms ease, background-color 200ms ease;
  cursor: pointer;
}

.history-report-link:hover,
.history-report-link:focus-visible {
  color: var(--color-primary);
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
}

.history-report-link:disabled {
  cursor: wait;
  opacity: 0.72;
}

.history-report-link__loading {
  animation: history-report-spin 900ms linear infinite;
}

@keyframes history-report-spin {
  to {
    transform: rotate(360deg);
  }
}

.history-detail-button {
  min-height: 32px;
  padding: 0 10px;
  border-radius: var(--radius-sm);
  color: var(--color-primary-strong);
  font-weight: 800;
}

.history-detail-button:hover,
.history-detail-button:focus {
  color: var(--color-primary);
  background: var(--color-primary-soft);
}

.history-pagination {
  display: flex;
  justify-content: flex-end;
}

.history-filter :deep(.el-form-item) {
  margin-bottom: 0;
}

.history-filter :deep(.el-form-item__label) {
  color: var(--color-text-strong);
  font-size: 13px;
  font-weight: 800;
}

.history-filter :deep(.el-select) {
  width: 100%;
}

.history-filter :deep(.el-input__wrapper),
.history-filter :deep(.el-select__wrapper) {
  min-height: 40px;
  border-radius: var(--radius-sm);
  box-shadow: 0 0 0 1px var(--color-border) inset;
}

.history-filter :deep(.el-input__wrapper:hover),
.history-filter :deep(.el-select__wrapper:hover) {
  box-shadow: 0 0 0 1px var(--color-primary) inset;
}

.history-filter :deep(.el-input__wrapper.is-focus),
.history-filter :deep(.el-select__wrapper.is-focused) {
  box-shadow: 0 0 0 1px var(--color-primary) inset, var(--shadow-focus);
}

.history-table :deep(.el-table__inner-wrapper::before) {
  display: none;
}

.history-table :deep(.el-table__header th.el-table__cell) {
  background: var(--color-bg-subtle);
  color: var(--color-text-strong);
  font-size: 13px;
  font-weight: 800;
}

.history-table :deep(.el-table__row) {
  height: 58px;
}

.history-table :deep(.el-table__cell) {
  border-bottom-color: var(--color-border-soft);
}

.history-table :deep(.el-table__body tr:hover > td.el-table__cell) {
  background: rgba(224, 242, 254, 0.45);
}

.history-table :deep(.el-table__fixed-right::before) {
  background: var(--color-border-soft);
}

.history-pagination :deep(.el-pagination) {
  --el-pagination-bg-color: #ffffff;
  --el-pagination-button-bg-color: #ffffff;
  --el-pagination-hover-color: var(--color-primary);
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 6px;
}

.history-pagination :deep(.el-pager li.is-active) {
  background: var(--color-primary);
}

@media (max-width: 980px) {
  .history-filter__form {
    grid-template-columns: 1fr 1fr;
  }

  .history-filter__actions {
    grid-column: 1 / -1;
    padding-bottom: 0;
  }
}

@media (max-width: 640px) {
  .history-filter__form {
    grid-template-columns: 1fr;
  }

  .history-filter__actions,
  .history-table-card__header {
    align-items: stretch;
    flex-direction: column;
  }

  .history-action {
    flex: 1;
  }

  .history-table-card {
    padding: var(--space-5);
  }

  .history-pagination {
    justify-content: flex-start;
  }
}
</style>
