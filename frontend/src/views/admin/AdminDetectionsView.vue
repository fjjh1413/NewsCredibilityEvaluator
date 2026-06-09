<template>
  <section class="admin-detections">
    <PageHeader
      eyebrow="管理员后台"
      title="检测记录管理"
      description="查看全站新闻可信度检测记录，支持按风险等级、关键词、时间范围和用户 ID 检索。"
    >
      <template #actions>
        <button class="button button--secondary" type="button" :disabled="loading" @click="fetchRecords">
          <Refresh aria-hidden="true" />
          <span>刷新</span>
        </button>
      </template>
    </PageHeader>

    <section class="surface-card surface-card--padded admin-detections__filter" aria-label="检测记录筛选">
      <label class="filter-field">
        <span>关键词</span>
        <el-input v-model.trim="filters.keyword" clearable placeholder="标题、正文、关键词或理由" @keyup.enter="handleSearch" />
      </label>

      <label class="filter-field">
        <span>风险等级</span>
        <el-select v-model="filters.riskLevel" clearable placeholder="全部风险等级">
          <el-option label="可信新闻" value="可信新闻" />
          <el-option label="存疑信息" value="存疑信息" />
          <el-option label="疑似谣言" value="疑似谣言" />
          <el-option label="高风险谣言" value="高风险谣言" />
        </el-select>
      </label>

      <label class="filter-field">
        <span>开始时间</span>
        <input v-model="filters.dateFrom" class="native-input" type="datetime-local" />
      </label>

      <label class="filter-field">
        <span>结束时间</span>
        <input v-model="filters.dateTo" class="native-input" type="datetime-local" />
      </label>

      <label class="filter-field filter-field--user">
        <span>用户 ID</span>
        <input v-model.trim="filters.userId" class="native-input" inputmode="numeric" placeholder="可选" />
      </label>

      <div class="filter-actions">
        <button class="button button--primary" type="button" :disabled="loading" @click="handleSearch">
          <Search aria-hidden="true" />
          <span>查询</span>
        </button>
        <button class="button button--secondary" type="button" :disabled="loading" @click="handleReset">
          重置
        </button>
      </div>
    </section>

    <LoadingState v-if="loading && !rows.length" :lines="6" label="检测记录加载中" />

    <section v-else class="surface-card admin-detections__table-card">
      <EmptyState
        v-if="!rows.length"
        :title="interfacePending ? '检测记录接口待接入' : errorMessage ? '检测记录加载失败' : '暂无检测记录'"
        :description="
          interfacePending
            ? '当前后端尚未注册 /api/admin/detections，页面已保留筛选、表格与管理操作接入位置。'
            : errorMessage || '当前筛选条件下没有检测记录。'
        "
      />

      <template v-else>
        <el-table
          class="admin-detections__table"
          :data="rows"
          row-key="rowKey"
          v-loading="loading"
        >
          <el-table-column label="检测标题" min-width="260">
            <template #default="{ row }">
              <div class="record-title">
                <strong>{{ row.title }}</strong>
                <span>ID：{{ row.id || '--' }}</span>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="用户" min-width="110">
            <template #default="{ row }">
              <span class="muted-text">{{ row.userLabel }}</span>
            </template>
          </el-table-column>

          <el-table-column label="final_score" width="120" align="center">
            <template #default="{ row }">
              <strong class="score-text">{{ formatScore(row.finalScore) }}</strong>
            </template>
          </el-table-column>

          <el-table-column label="risk_level" width="150">
            <template #default="{ row }">
              <RiskLevelTag :level="row.riskLevel" :score="row.finalScore" size="small" />
            </template>
          </el-table-column>

          <el-table-column label="is_high_risk" width="130" align="center">
            <template #default="{ row }">
              <span class="status-pill" :class="highRiskClass(row.isHighRisk)">
                {{ highRiskText(row.isHighRisk) }}
              </span>
            </template>
          </el-table-column>

          <el-table-column label="检测时间" min-width="160">
            <template #default="{ row }">
              <span class="muted-text">{{ formatDateTime(row.detectedAt) }}</span>
            </template>
          </el-table-column>

          <el-table-column label="报告状态" width="130">
            <template #default="{ row }">
              <span class="status-pill" :class="reportStatusClass(row.reportStatus)">
                {{ reportStatusText(row.reportStatus) }}
              </span>
            </template>
          </el-table-column>

          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <div class="table-actions">
                <button class="text-button" type="button" @click="openDetail(row)">详情</button>
                <button class="text-button text-button--danger" type="button" @click="confirmDelete(row)">删除</button>
              </div>
            </template>
          </el-table-column>
        </el-table>

        <div class="admin-detections__pagination">
          <span>共 {{ total }} 条</span>
          <el-pagination
            background
            layout="sizes, prev, pager, next"
            :current-page="pagination.page"
            :page-size="pagination.pageSize"
            :page-sizes="[10, 20, 50, 100]"
            :total="total"
            @size-change="handleSizeChange"
            @current-change="handleCurrentChange"
          />
        </div>
      </template>
    </section>

    <section v-if="detailVisible" class="detail-overlay" role="dialog" aria-modal="true" aria-labelledby="admin-detail-title">
      <div class="detail-dialog">
        <header class="detail-dialog__header">
          <div>
            <p>检测详情</p>
            <h2 id="admin-detail-title">{{ detailTitle }}</h2>
          </div>
          <button class="icon-button" type="button" aria-label="关闭详情" @click="closeDetail">
            <Close aria-hidden="true" />
          </button>
        </header>

        <LoadingState v-if="detailLoading" :lines="6" label="检测详情加载中" />

        <EmptyState
          v-else-if="!detailData"
          title="详情加载失败"
          :description="detailError || '后端未返回检测详情。'"
        />

        <div v-else class="detail-content">
          <section class="detail-summary surface-card">
            <div>
              <span>综合评分</span>
              <strong>{{ formatScore(detailFinalScore) }}</strong>
            </div>
            <RiskLevelTag :level="detailRiskLevel" :score="detailFinalScore" size="large" />
            <p>{{ detailJudgement }}</p>
          </section>

          <section class="detail-meta-grid">
            <div>
              <span>用户</span>
              <strong>{{ detailUserLabel }}</strong>
            </div>
            <div>
              <span>is_high_risk</span>
              <strong>{{ highRiskText(detailHighRisk) }}</strong>
            </div>
            <div>
              <span>检测时间</span>
              <strong>{{ formatDateTime(detailTime) }}</strong>
            </div>
            <div>
              <span>报告状态</span>
              <strong>{{ reportStatusText(resolveReportStatus(detailData)) }}</strong>
            </div>
          </section>

          <section class="detail-score-grid">
            <ScoreCard title="证据相关度" :score="detailEvidenceScore" subtitle="后端返回 evidence_score" tone="primary" />
            <ScoreCard title="大模型判断" :score="detailLlmScore" subtitle="后端返回 llm_score" tone="neutral" />
            <ScoreCard title="来源/规则评分" :score="detailRuleScore" subtitle="后端返回 rule_score" :tone="detailRuleTone" />
          </section>

          <section class="detail-two-column">
            <ResultSection title="判断理由" description="来自检测详情接口的 reason 字段。">
              <p class="detail-text">{{ detailReason }}</p>
            </ResultSection>

            <ResultSection title="辟谣建议" tone="info" description="来自检测详情接口的 suggestion 字段。">
              <p class="detail-text">{{ detailSuggestion }}</p>
            </ResultSection>
          </section>

          <section class="detail-two-column">
            <ResultSection title="风险点" description="以后端返回 risk_points 为准。">
              <EmptyState v-if="!detailRiskPoints.length" title="暂无风险点" description="后端未返回明确风险点。" />
              <ul v-else class="risk-point-list">
                <li v-for="(point, index) in detailRiskPoints" :key="`${point}-${index}`">
                  <span>{{ index + 1 }}</span>
                  <p>{{ point }}</p>
                </li>
              </ul>
            </ResultSection>

            <ResultSection title="关键词" description="来自 keywords 字段。">
              <EmptyState v-if="!detailKeywords.length" title="暂无关键词" description="后端未返回关键词。" />
              <div v-else class="keyword-list">
                <span v-for="keyword in detailKeywords" :key="keyword">{{ keyword }}</span>
              </div>
            </ResultSection>
          </section>

          <ResultSection title="检索证据" description="复用用户端 EvidenceList 展示 evidence_matches。">
            <EvidenceList :items="detailEvidenceList" />
          </ResultSection>

          <ResultSection title="AI 分析过程" description="复用用户端 AgentSteps 展示分析链路。">
            <AgentSteps :steps="detailAgentSteps" />
          </ResultSection>
        </div>
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus/es/components/message/index.mjs'
import { ElMessageBox } from 'element-plus/es/components/message-box/index.mjs'
import { Close, Refresh, Search } from '@element-plus/icons-vue'
import {
  deleteAdminDetection,
  getAdminDetectionDetail,
  getAdminDetections
} from '@/api/adminDetections'
import AgentSteps from '@/components/AgentSteps.vue'
import EmptyState from '@/components/EmptyState.vue'
import EvidenceList from '@/components/EvidenceList.vue'
import LoadingState from '@/components/LoadingState.vue'
import PageHeader from '@/components/PageHeader.vue'
import ResultSection from '@/components/ResultSection.vue'
import RiskLevelTag from '@/components/RiskLevelTag.vue'
import ScoreCard from '@/components/ScoreCard.vue'
import { formatDateTime, formatScore } from '@/utils/format'

const loading = ref(false)
const rows = ref([])
const total = ref(0)
const errorMessage = ref('')
const interfacePending = ref(false)
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailError = ref('')
const detailData = ref(null)

const filters = reactive({
  keyword: '',
  riskLevel: '',
  dateFrom: '',
  dateTo: '',
  userId: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 20
})

const queryParams = computed(() => {
  const params = {
    page: pagination.page,
    page_size: pagination.pageSize
  }

  if (filters.keyword) {
    params.keyword = filters.keyword
  }

  if (filters.riskLevel) {
    params.risk_level = filters.riskLevel
  }

  if (filters.dateFrom) {
    params.date_from = filters.dateFrom
  }

  if (filters.dateTo) {
    params.date_to = filters.dateTo
  }

  const userId = Number(filters.userId)
  if (Number.isInteger(userId) && userId > 0) {
    params.user_id = userId
  }

  return params
})

const detailTitle = computed(() =>
  pick(detailData.value?.input_title, detailData.value?.news_title, detailData.value?.title, '未命名检测记录')
)
const detailFinalScore = computed(() => pick(detailData.value?.final_score, detailData.value?.credibility_score, detailData.value?.score))
const detailEvidenceScore = computed(() => pick(detailData.value?.evidence_score, detailData.value?.retrieval_score))
const detailLlmScore = computed(() => pick(detailData.value?.llm_score, detailData.value?.model_score))
const detailRuleScore = computed(() => pick(detailData.value?.rule_score, detailData.value?.source_score))
const detailRiskLevel = computed(() => pick(detailData.value?.risk_level, detailData.value?.riskLevel))
const detailHighRisk = computed(() => resolveHighRisk(detailData.value || {}))
const detailTime = computed(() =>
  pick(detailData.value?.created_at, detailData.value?.detected_at, detailData.value?.detection_time, detailData.value?.create_time)
)
const detailUserLabel = computed(() => formatUserLabel(detailData.value || {}))
const detailJudgement = computed(() =>
  pick(detailData.value?.judgement_result, detailData.value?.judgment_result, detailData.value?.conclusion, '暂无判断结论')
)
const detailReason = computed(() => pick(detailData.value?.reason, detailData.value?.analysis_reason, '后端未返回判断理由。'))
const detailSuggestion = computed(() => pick(detailData.value?.suggestion, detailData.value?.advice, '后端未返回辟谣建议。'))
const detailRiskPoints = computed(() => getArray(detailData.value?.risk_points ?? detailData.value?.riskPoints))
const detailKeywords = computed(() => getArray(detailData.value?.keywords ?? detailData.value?.keyword_list))
const detailEvidenceList = computed(() =>
  getArray(detailData.value?.evidence_matches ?? detailData.value?.evidence_list ?? detailData.value?.evidenceList)
)
const detailAgentSteps = computed(() =>
  getArray(detailData.value?.agent_steps ?? detailData.value?.agentSteps ?? detailData.value?.analysis_steps)
)
const detailRuleTone = computed(() => {
  const level = String(detailRiskLevel.value || '')

  if (level.includes('高风险')) {
    return 'danger'
  }

  if (level.includes('疑似') || level.includes('存疑')) {
    return 'warning'
  }

  return 'primary'
})

function unwrapApiResponse(response) {
  const body = response?.data ?? response
  const code = body?.code

  if (code !== undefined && ![0, 200, 201].includes(Number(code))) {
    throw new Error(body?.message || '检测记录请求失败')
  }

  if (body?.success === false) {
    throw new Error(body?.message || '检测记录请求失败')
  }

  if (
    body?.data !== undefined &&
    (body?.code !== undefined || body?.success !== undefined || body?.message !== undefined)
  ) {
    return body.data
  }

  return body
}

function pick(...values) {
  return values.find((value) => value !== undefined && value !== null && value !== '') ?? ''
}

function pickList(payload) {
  if (Array.isArray(payload)) {
    return {
      items: payload,
      total: payload.length
    }
  }

  if (!payload || typeof payload !== 'object') {
    return {
      items: [],
      total: 0
    }
  }

  const items =
    payload.items ??
    payload.records ??
    payload.rows ??
    payload.list ??
    payload.data ??
    []

  return {
    items: Array.isArray(items) ? items : [],
    total: Number(payload.total ?? payload.count ?? payload.total_count ?? (Array.isArray(items) ? items.length : 0))
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

function resolveReportStatus(item) {
  const reportValue = item?.report_url ?? item?.reportUrl ?? item?.pdf_url ?? item?.pdfUrl
  const hasReportField = ['report_url', 'reportUrl', 'pdf_url', 'pdfUrl'].some((key) =>
    Object.prototype.hasOwnProperty.call(item || {}, key)
  )

  if (reportValue) {
    return 'generated'
  }

  return hasReportField ? 'missing' : 'unknown'
}

function formatUserLabel(item) {
  const username = item?.username ?? item?.user_name ?? item?.userName
  const userId = item?.user_id ?? item?.userId

  if (username && userId) {
    return `${username} (#${userId})`
  }

  if (username) {
    return username
  }

  if (userId !== undefined && userId !== null && userId !== '') {
    return `用户 #${userId}`
  }

  return '未绑定用户'
}

function normalizeRecord(item, index) {
  const id = item?.id ?? item?.detection_id ?? item?.record_id ?? item?.result_id ?? ''

  return {
    id,
    rowKey: id || `${pagination.page}-${index}`,
    title: pick(item?.input_title, item?.news_title, item?.title, item?.headline, '未命名新闻'),
    userLabel: formatUserLabel(item),
    finalScore: pick(item?.final_score, item?.credibility_score, item?.score, item?.finalScore, null),
    riskLevel: pick(item?.risk_level, item?.riskLevel, item?.risk, ''),
    isHighRisk: resolveHighRisk(item),
    detectedAt: pick(item?.created_at, item?.detected_at, item?.detection_time, item?.create_time, item?.updated_at),
    reportStatus: resolveReportStatus(item),
    raw: item
  }
}

function getArray(value) {
  if (Array.isArray(value)) {
    return value.filter(Boolean)
  }

  if (Array.isArray(value?.items)) {
    return value.items.filter(Boolean)
  }

  if (Array.isArray(value?.records)) {
    return value.records.filter(Boolean)
  }

  if (Array.isArray(value?.list)) {
    return value.list.filter(Boolean)
  }

  if (typeof value === 'string') {
    const text = value.trim()

    if (!text) {
      return []
    }

    try {
      const parsed = JSON.parse(text)
      if (Array.isArray(parsed)) {
        return parsed.filter(Boolean)
      }
    } catch {
      // Fall through to delimiter parsing.
    }

    return text
      .split(/[\n,，;；]/)
      .map((item) => item.trim())
      .filter(Boolean)
  }

  return []
}

function highRiskText(value) {
  if (value === true) {
    return '是'
  }

  if (value === false) {
    return '否'
  }

  return '未标记'
}

function highRiskClass(value) {
  if (value === true) {
    return 'status-pill--danger'
  }

  if (value === false) {
    return 'status-pill--success'
  }

  return 'status-pill--muted'
}

function reportStatusText(status) {
  if (status === 'generated') {
    return '已生成'
  }

  if (status === 'missing') {
    return '未生成'
  }

  return '接口未返回'
}

function reportStatusClass(status) {
  if (status === 'generated') {
    return 'status-pill--success'
  }

  if (status === 'missing') {
    return 'status-pill--warning'
  }

  return 'status-pill--muted'
}

function getErrorMessage(error) {
  return (
    error?.response?.data?.message ||
    error?.response?.data?.detail ||
    error?.message ||
    '检测记录请求失败'
  )
}

function isPendingInterfaceError(error) {
  return [404, 405, 501].includes(error?.response?.status)
}

async function fetchRecords() {
  loading.value = true
  errorMessage.value = ''
  interfacePending.value = false

  try {
    const response = await getAdminDetections(queryParams.value)
    const payload = unwrapApiResponse(response)
    const listPayload = pickList(payload)

    rows.value = listPayload.items.map(normalizeRecord)
    total.value = Number.isFinite(listPayload.total) ? listPayload.total : rows.value.length
  } catch (error) {
    interfacePending.value = isPendingInterfaceError(error)
    errorMessage.value = interfacePending.value ? '' : getErrorMessage(error)
    rows.value = []
    total.value = 0

    if (!interfacePending.value) {
      ElMessage.error(errorMessage.value)
    }
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pagination.page = 1
  fetchRecords()
}

function handleReset() {
  filters.keyword = ''
  filters.riskLevel = ''
  filters.dateFrom = ''
  filters.dateTo = ''
  filters.userId = ''
  pagination.page = 1
  fetchRecords()
}

function handleSizeChange(size) {
  pagination.pageSize = size
  pagination.page = 1
  fetchRecords()
}

function handleCurrentChange(page) {
  pagination.page = page
  fetchRecords()
}

async function openDetail(row) {
  if (!row?.id) {
    ElMessage.warning('当前记录缺少 ID，无法查看详情')
    return
  }

  detailVisible.value = true
  detailLoading.value = true
  detailError.value = ''
  detailData.value = null

  try {
    const response = await getAdminDetectionDetail(row.id)
    detailData.value = unwrapApiResponse(response)
  } catch (error) {
    detailError.value = getErrorMessage(error)
    ElMessage.error(detailError.value)
  } finally {
    detailLoading.value = false
  }
}

function closeDetail() {
  detailVisible.value = false
  detailData.value = null
  detailError.value = ''
}

async function confirmDelete(row) {
  if (!row?.id) {
    ElMessage.warning('当前记录缺少 ID，无法删除')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确认删除检测记录「${row.title}」吗？删除后不可恢复。`,
      '删除检测记录',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
  } catch {
    return
  }

  try {
    await deleteAdminDetection(row.id)
    ElMessage.success('检测记录已删除')
    if (rows.value.length === 1 && pagination.page > 1) {
      pagination.page -= 1
    }
    fetchRecords()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

onMounted(fetchRecords)
</script>

<style scoped>
.admin-detections {
  display: grid;
  gap: var(--space-6);
}

.admin-detections :deep(.page-header__actions svg),
.admin-detections .button svg {
  width: 16px;
  height: 16px;
}

.admin-detections__filter {
  display: grid;
  grid-template-columns: minmax(220px, 1.25fr) minmax(180px, 0.85fr) repeat(2, minmax(190px, 0.9fr)) minmax(120px, 0.6fr) auto;
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

.filter-field :deep(.el-input__wrapper),
.filter-field :deep(.el-select__wrapper) {
  box-shadow: 0 0 0 1px var(--color-border) inset;
}

.filter-field :deep(.el-input__wrapper.is-focus),
.filter-field :deep(.el-select__wrapper.is-focused) {
  box-shadow: 0 0 0 1px var(--color-primary) inset, var(--shadow-focus);
}

.native-input {
  width: 100%;
  border: 1px solid var(--color-border);
  padding: 0 var(--space-3);
  color: var(--color-text);
  background: #ffffff;
}

.native-input:focus {
  border-color: var(--color-primary);
}

.filter-actions {
  display: flex;
  gap: var(--space-2);
}

.admin-detections__table-card {
  overflow: hidden;
}

.admin-detections__table {
  width: 100%;
}

.admin-detections__table :deep(.el-table__header th) {
  color: var(--color-text-strong);
  background: var(--color-bg-subtle);
  font-size: 13px;
  font-weight: 800;
}

.admin-detections__table :deep(.el-table__row:hover > td) {
  background: #f0f9ff;
}

.record-title {
  display: grid;
  gap: 5px;
  min-width: 0;
}

.record-title strong {
  overflow: hidden;
  color: var(--color-text-strong);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.record-title span,
.muted-text {
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

.status-pill--warning {
  color: var(--color-warning);
  background: var(--risk-suspicious-bg);
}

.status-pill--muted {
  color: var(--color-text-muted);
  background: var(--color-bg-subtle);
}

.table-actions {
  display: flex;
  gap: var(--space-2);
}

.text-button {
  min-height: 30px;
  border: 0;
  border-radius: var(--radius-sm);
  color: var(--color-primary-strong);
  background: transparent;
  cursor: pointer;
  font-weight: 800;
  transition: color 200ms ease, background-color 200ms ease;
}

.text-button:hover {
  color: var(--color-primary);
  background: var(--color-primary-soft);
}

.text-button--danger {
  color: var(--color-danger);
}

.text-button--danger:hover {
  color: var(--color-danger);
  background: var(--risk-high-bg);
}

.admin-detections__pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-5);
  border-top: 1px solid var(--color-border-soft);
}

.admin-detections__pagination > span {
  color: var(--color-text-muted);
  font-size: 13px;
  font-weight: 700;
}

.detail-overlay {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: grid;
  place-items: center;
  padding: var(--space-6);
  background: rgba(15, 23, 42, 0.34);
}

.detail-dialog {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: var(--space-5);
  width: min(1120px, 100%);
  max-height: min(88vh, 920px);
  overflow: hidden;
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-lg);
  background: var(--color-bg-page);
  box-shadow: 0 22px 64px rgba(15, 23, 42, 0.22);
}

.detail-dialog__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-5) var(--space-6);
  border-bottom: 1px solid var(--color-border-soft);
  background: rgba(255, 255, 255, 0.96);
}

.detail-dialog__header p {
  margin: 0 0 var(--space-2);
  color: var(--color-primary);
  font-size: 13px;
  font-weight: 800;
}

.detail-dialog__header h2 {
  margin: 0;
  color: var(--color-text-strong);
  font-size: 20px;
  line-height: 1.4;
}

.detail-content {
  display: grid;
  gap: var(--space-5);
  min-height: 0;
  overflow-y: auto;
  padding: 0 var(--space-6) var(--space-6);
}

.detail-summary {
  display: grid;
  grid-template-columns: auto auto minmax(0, 1fr);
  gap: var(--space-5);
  align-items: center;
  padding: var(--space-5);
  border-left: 4px solid var(--color-primary);
}

.detail-summary div {
  display: grid;
  gap: var(--space-2);
}

.detail-summary span,
.detail-meta-grid span {
  color: var(--color-text-muted);
  font-size: 13px;
  font-weight: 800;
}

.detail-summary strong {
  color: var(--color-primary-strong);
  font-size: 36px;
  line-height: 1;
}

.detail-summary p {
  margin: 0;
  color: var(--color-text);
  line-height: 1.7;
}

.detail-meta-grid,
.detail-score-grid,
.detail-two-column {
  display: grid;
  gap: var(--space-4);
}

.detail-meta-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.detail-meta-grid div {
  display: grid;
  gap: var(--space-2);
  padding: var(--space-4);
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.96);
}

.detail-meta-grid strong {
  overflow: hidden;
  color: var(--color-text-strong);
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-score-grid,
.detail-two-column {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.detail-score-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.detail-text {
  margin: 0;
  color: var(--color-text);
  line-height: 1.8;
}

.risk-point-list {
  display: grid;
  gap: var(--space-3);
  margin: 0;
  padding: 0;
  list-style: none;
}

.risk-point-list li {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr);
  gap: var(--space-3);
  align-items: start;
  padding: var(--space-3);
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-md);
  background: var(--color-bg-panel);
}

.risk-point-list span {
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  border-radius: var(--radius-sm);
  color: #ffffff;
  background: var(--color-warning);
  font-size: 12px;
  font-weight: 800;
}

.risk-point-list p {
  margin: 0;
  color: var(--color-text);
  line-height: 1.7;
}

.keyword-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.keyword-list span {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border: 1px solid rgba(3, 105, 161, 0.16);
  border-radius: 999px;
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
  font-size: 13px;
  font-weight: 800;
}

@media (max-width: 1500px) {
  .admin-detections__filter {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .filter-actions {
    align-self: stretch;
  }
}

@media (max-width: 900px) {
  .admin-detections__filter {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .detail-summary,
  .detail-meta-grid,
  .detail-score-grid,
  .detail-two-column {
    grid-template-columns: 1fr;
  }

  .admin-detections__pagination {
    align-items: flex-start;
    flex-direction: column;
  }
}

@media (max-width: 640px) {
  .admin-detections__filter {
    grid-template-columns: 1fr;
  }

  .filter-actions {
    flex-wrap: wrap;
  }

  .detail-overlay {
    padding: var(--space-3);
  }

  .detail-dialog__header,
  .detail-content {
    padding-right: var(--space-4);
    padding-left: var(--space-4);
  }
}
</style>
