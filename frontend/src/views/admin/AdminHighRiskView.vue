<template>
  <section class="admin-high-risk">
    <PageHeader
      eyebrow="管理员后台"
      title="高风险新闻管理"
      description="审核高风险检测记录，维护公开状态与内部备注。只有审核通过且设置公开的记录会出现在用户端。"
    >
      <template #actions>
        <button class="button button--secondary" type="button" :disabled="loading" @click="fetchRecords">
          <Refresh aria-hidden="true" />
          <span>刷新</span>
        </button>
      </template>
    </PageHeader>

    <el-alert
      type="info"
      title="公开规则"
      description="审核通过不等于自动公开；待审核与已驳回记录无法公开，驳回会强制撤下已公开内容。"
      show-icon
      :closable="false"
    />

    <section class="surface-card surface-card--padded filter-panel" aria-label="高风险记录筛选">
      <label class="filter-field filter-field--keyword">
        <span>标题关键词</span>
        <el-input v-model.trim="filters.keyword" clearable placeholder="搜索新闻标题" @keyup.enter="handleSearch" />
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
        <span>新闻类别</span>
        <el-input v-model.trim="filters.category" clearable placeholder="全部类别" />
      </label>
      <label class="filter-field">
        <span>审核状态</span>
        <el-select v-model="filters.reviewStatus" clearable placeholder="全部状态">
          <el-option label="待审核" value="pending" />
          <el-option label="审核通过" value="approved" />
          <el-option label="审核驳回" value="rejected" />
        </el-select>
      </label>
      <label class="filter-field">
        <span>公开状态</span>
        <el-select v-model="filters.isPublic" clearable placeholder="全部状态">
          <el-option label="已公开" :value="true" />
          <el-option label="未公开" :value="false" />
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
        <button class="button button--secondary" type="button" :disabled="loading" @click="handleReset">重置</button>
      </div>
    </section>

    <LoadingState v-if="loading && !rows.length" :lines="6" label="高风险检测记录加载中" />

    <section v-else class="surface-card table-card">
      <EmptyState
        v-if="!rows.length"
        :title="errorMessage ? '数据加载失败' : filtersActive ? '当前筛选条件下暂无数据' : '暂无高风险检测记录'"
        :description="errorMessage || '高风险检测记录会自动进入待审核列表。'"
      >
        <template v-if="errorMessage" #actions>
          <button class="button button--secondary button--small" type="button" @click="fetchRecords">重新加载</button>
        </template>
      </EmptyState>

      <template v-else>
        <el-table class="high-risk-table" :data="rows" row-key="id" v-loading="loading">
          <el-table-column label="检测记录" min-width="260">
            <template #default="{ row }">
              <div class="record-title">
                <strong>{{ row.input_title || '未命名新闻' }}</strong>
                <span>ID：{{ row.id }} · 用户：{{ row.user_id ? `#${row.user_id}` : '未绑定' }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="category" label="类别" width="110">
            <template #default="{ row }">{{ row.category || '未分类' }}</template>
          </el-table-column>
          <el-table-column label="评分" width="90" align="center">
            <template #default="{ row }"><strong class="score-text">{{ formatScore(row.final_score) }}</strong></template>
          </el-table-column>
          <el-table-column label="风险等级" width="150">
            <template #default="{ row }">
              <RiskLevelTag :level="row.risk_level" :score="row.final_score" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="审核状态" width="120">
            <template #default="{ row }">
              <span class="status-pill" :class="reviewStatusClass(row.review_status)">{{ reviewStatusText(row.review_status) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="公开状态" width="110">
            <template #default="{ row }">
              <span class="status-pill" :class="row.is_public ? 'status-pill--success' : 'status-pill--muted'">
                {{ row.is_public ? '已公开' : '未公开' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="管理员备注" min-width="180">
            <template #default="{ row }"><span class="remark-text">{{ row.admin_remark || '暂无备注' }}</span></template>
          </el-table-column>
          <el-table-column label="创建时间" min-width="160">
            <template #default="{ row }"><span class="muted-text">{{ formatDateTime(row.created_at) }}</span></template>
          </el-table-column>
          <el-table-column label="操作" width="260" fixed="right">
            <template #default="{ row }">
              <div class="table-actions">
                <button class="text-button" type="button" @click="openDetail(row)">详情</button>
                <button class="text-button" type="button" @click="openReview(row)">审核</button>
                <button class="text-button" type="button" @click="togglePublic(row)">
                  {{ row.is_public ? '取消公开' : '设为公开' }}
                </button>
                <button class="text-button" type="button" @click="openRemark(row)">备注</button>
              </div>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination">
          <span>共 {{ total }} 条高风险记录</span>
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
      </template>
    </section>

    <el-dialog v-model="reviewVisible" title="审核高风险记录" width="min(560px, 92vw)">
      <div class="dialog-summary">{{ reviewForm.title }}</div>
      <el-form label-position="top">
        <el-form-item label="审核状态">
          <el-select v-model="reviewForm.review_status">
            <el-option label="待审核" value="pending" />
            <el-option label="审核通过" value="approved" />
            <el-option label="审核驳回" value="rejected" />
          </el-select>
        </el-form-item>
        <el-form-item label="管理员备注">
          <el-input v-model="reviewForm.admin_remark" type="textarea" :rows="5" maxlength="2000" show-word-limit placeholder="说明审核依据或处理意见" />
        </el-form-item>
      </el-form>
      <template #footer>
        <button class="button button--secondary" type="button" @click="reviewVisible = false">取消</button>
        <button class="button button--primary" type="button" :disabled="actionLoading" @click="submitReview">确认审核</button>
      </template>
    </el-dialog>

    <el-dialog v-model="remarkVisible" title="编辑管理员备注" width="min(560px, 92vw)">
      <div class="dialog-summary">{{ remarkForm.title }}</div>
      <el-input v-model="remarkForm.admin_remark" type="textarea" :rows="6" maxlength="2000" show-word-limit placeholder="备注仅管理员可见" />
      <template #footer>
        <button class="button button--secondary" type="button" @click="remarkVisible = false">取消</button>
        <button class="button button--primary" type="button" :disabled="actionLoading" @click="submitRemark">保存备注</button>
      </template>
    </el-dialog>

    <el-dialog v-model="detailVisible" title="高风险检测详情" width="min(1040px, 94vw)" class="detail-dialog">
      <LoadingState v-if="detailLoading" :lines="6" label="高风险详情加载中" />
      <EmptyState v-else-if="!detailData" title="详情加载失败" :description="detailError || '后端未返回详情数据。'" />
      <div v-else class="detail-content">
        <section class="detail-summary">
          <div>
            <span>可信度评分</span>
            <strong>{{ formatScore(detailData.final_score) }}</strong>
          </div>
          <RiskLevelTag :level="detailData.risk_level" :score="detailData.final_score" size="large" />
          <p>{{ detailData.judgement_result || '暂无判断结论' }}</p>
        </section>
        <section class="detail-meta">
          <div><span>审核状态</span><strong>{{ reviewStatusText(detailData.review_status) }}</strong></div>
          <div><span>公开状态</span><strong>{{ detailData.is_public ? '已公开' : '未公开' }}</strong></div>
          <div><span>审核时间</span><strong>{{ formatDateTime(detailData.reviewed_at) }}</strong></div>
          <div><span>审核人 ID</span><strong>{{ detailData.reviewed_by || '--' }}</strong></div>
        </section>
        <ResultSection title="新闻正文" description="完整正文仅在管理员端展示。">
          <p class="detail-text">{{ detailData.input_content || '暂无正文' }}</p>
        </ResultSection>
        <section class="detail-grid">
          <ResultSection title="模型分析理由">
            <p class="detail-text">{{ detailData.reason || '暂无分析理由' }}</p>
          </ResultSection>
          <ResultSection title="辟谣建议" tone="info">
            <p class="detail-text">{{ detailData.suggestion || '暂无建议' }}</p>
          </ResultSection>
        </section>
        <section class="detail-grid">
          <ResultSection title="风险点">
            <ul v-if="detailData.risk_points?.length" class="risk-points">
              <li v-for="point in detailData.risk_points" :key="point">{{ point }}</li>
            </ul>
            <EmptyState v-else title="暂无风险点" description="后端未返回明确风险点。" />
          </ResultSection>
          <ResultSection title="关键词">
            <div v-if="detailData.keywords?.length" class="keyword-list">
              <span v-for="keyword in detailData.keywords" :key="keyword">{{ keyword }}</span>
            </div>
            <EmptyState v-else title="暂无关键词" description="后端未返回关键词。" />
          </ResultSection>
        </section>
        <ResultSection title="检索证据">
          <EvidenceList :items="detailData.evidence_matches || []" />
        </ResultSection>
        <ResultSection title="管理员备注">
          <p class="detail-text">{{ detailData.admin_remark || '暂无管理员备注' }}</p>
        </ResultSection>
      </div>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus/es/components/message/index.mjs'
import { ElMessageBox } from 'element-plus/es/components/message-box/index.mjs'
import { Refresh, Search } from '@element-plus/icons-vue'
import {
  getAdminHighRisk,
  getAdminHighRiskDetail,
  updateAdminHighRiskPublic,
  updateAdminHighRiskRemark,
  updateAdminHighRiskReview
} from '@/api/adminHighRisk'
import EmptyState from '@/components/EmptyState.vue'
import EvidenceList from '@/components/EvidenceList.vue'
import LoadingState from '@/components/LoadingState.vue'
import PageHeader from '@/components/PageHeader.vue'
import ResultSection from '@/components/ResultSection.vue'
import RiskLevelTag from '@/components/RiskLevelTag.vue'
import { formatDateTime, formatScore } from '@/utils/format'
import { getStatisticsErrorMessage, unwrapStatisticsResponse } from '@/utils/statisticsCharts'

const rows = ref([])
const total = ref(0)
const loading = ref(false)
const actionLoading = ref(false)
const errorMessage = ref('')
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailData = ref(null)
const detailError = ref('')
const reviewVisible = ref(false)
const remarkVisible = ref(false)

const filters = reactive({
  keyword: '',
  riskLevel: '',
  category: '',
  reviewStatus: '',
  isPublic: '',
  startDate: '',
  endDate: ''
})
const pagination = reactive({ page: 1, pageSize: 20 })
const reviewForm = reactive({ id: null, title: '', review_status: 'pending', admin_remark: '' })
const remarkForm = reactive({ id: null, title: '', admin_remark: '' })

const filtersActive = computed(() => Object.values(filters).some((value) => value !== '' && value !== null))
const queryParams = computed(() => {
  const params = { page: pagination.page, page_size: pagination.pageSize }
  if (filters.keyword) params.keyword = filters.keyword
  if (filters.riskLevel) params.risk_level = filters.riskLevel
  if (filters.category) params.category = filters.category
  if (filters.reviewStatus) params.review_status = filters.reviewStatus
  if (typeof filters.isPublic === 'boolean') params.is_public = filters.isPublic
  if (filters.startDate) params.start_date = filters.startDate
  if (filters.endDate) params.end_date = filters.endDate
  return params
})

async function fetchRecords() {
  loading.value = true
  errorMessage.value = ''
  try {
    const data = unwrapStatisticsResponse(await getAdminHighRisk(queryParams.value))
    rows.value = Array.isArray(data?.items) ? data.items : []
    total.value = Number(data?.total) || 0
  } catch (error) {
    rows.value = []
    total.value = 0
    errorMessage.value = getStatisticsErrorMessage(error)
    ElMessage.error(errorMessage.value)
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pagination.page = 1
  fetchRecords()
}

function handleReset() {
  Object.assign(filters, {
    keyword: '',
    riskLevel: '',
    category: '',
    reviewStatus: '',
    isPublic: '',
    startDate: '',
    endDate: ''
  })
  pagination.page = 1
  fetchRecords()
}

function handleSizeChange(size) {
  pagination.pageSize = size
  pagination.page = 1
  fetchRecords()
}

function handlePageChange(page) {
  pagination.page = page
  fetchRecords()
}

async function openDetail(row) {
  detailVisible.value = true
  detailLoading.value = true
  detailData.value = null
  detailError.value = ''
  try {
    detailData.value = unwrapStatisticsResponse(await getAdminHighRiskDetail(row.id))
  } catch (error) {
    detailError.value = getStatisticsErrorMessage(error)
    ElMessage.error(detailError.value)
  } finally {
    detailLoading.value = false
  }
}

function openReview(row) {
  Object.assign(reviewForm, {
    id: row.id,
    title: row.input_title || '未命名新闻',
    review_status: row.review_status || 'pending',
    admin_remark: row.admin_remark || ''
  })
  reviewVisible.value = true
}

async function submitReview() {
  const statusText = reviewStatusText(reviewForm.review_status)
  try {
    await ElMessageBox.confirm(
      `确认将「${reviewForm.title}」设置为“${statusText}”吗？驳回或重置为待审核会立即取消公开。`,
      '确认审核结果',
      { confirmButtonText: '确认', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }

  actionLoading.value = true
  try {
    await updateAdminHighRiskReview(reviewForm.id, {
      review_status: reviewForm.review_status,
      admin_remark: reviewForm.admin_remark || null
    })
    reviewVisible.value = false
    ElMessage.success('审核状态已更新')
    fetchRecords()
  } catch (error) {
    ElMessage.error(getStatisticsErrorMessage(error))
  } finally {
    actionLoading.value = false
  }
}

async function togglePublic(row) {
  if (!row.is_public && row.review_status !== 'approved') {
    ElMessage.warning('请先审核通过后再公开展示')
    return
  }
  const nextValue = !row.is_public
  try {
    await ElMessageBox.confirm(
      nextValue
        ? `确认公开展示「${row.input_title}」的摘要吗？`
        : `确认取消公开「${row.input_title}」吗？`,
      nextValue ? '设置公开展示' : '取消公开展示',
      { confirmButtonText: '确认', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }

  try {
    await updateAdminHighRiskPublic(row.id, { is_public: nextValue })
    ElMessage.success(nextValue ? '已公开展示' : '已取消公开')
    fetchRecords()
  } catch (error) {
    ElMessage.error(getStatisticsErrorMessage(error))
  }
}

function openRemark(row) {
  Object.assign(remarkForm, {
    id: row.id,
    title: row.input_title || '未命名新闻',
    admin_remark: row.admin_remark || ''
  })
  remarkVisible.value = true
}

async function submitRemark() {
  actionLoading.value = true
  try {
    await updateAdminHighRiskRemark(remarkForm.id, {
      admin_remark: remarkForm.admin_remark || null
    })
    remarkVisible.value = false
    ElMessage.success('管理员备注已保存')
    fetchRecords()
  } catch (error) {
    ElMessage.error(getStatisticsErrorMessage(error))
  } finally {
    actionLoading.value = false
  }
}

function reviewStatusText(status) {
  return { pending: '待审核', approved: '审核通过', rejected: '审核驳回' }[status] || '未知状态'
}

function reviewStatusClass(status) {
  return {
    pending: 'status-pill--warning',
    approved: 'status-pill--success',
    rejected: 'status-pill--danger'
  }[status] || 'status-pill--muted'
}

onMounted(fetchRecords)
</script>

<style scoped>
.admin-high-risk,
.detail-content {
  display: grid;
  gap: var(--space-6);
}

.admin-high-risk .button svg {
  width: 16px;
  height: 16px;
}

.filter-panel {
  display: grid;
  grid-template-columns: minmax(210px, 1.2fr) repeat(4, minmax(145px, 0.75fr)) repeat(2, minmax(180px, 0.9fr)) auto;
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
.detail-meta span {
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
  padding: 0 var(--space-3);
  border: 1px solid var(--color-border);
  color: var(--color-text);
  background: #fff;
}

.filter-actions,
.table-actions,
.pagination {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.table-card {
  overflow: hidden;
}

.high-risk-table :deep(.el-table__header th) {
  color: var(--color-text-strong);
  background: var(--color-bg-subtle);
  font-size: 13px;
  font-weight: 800;
}

.record-title {
  display: grid;
  gap: 5px;
}

.record-title strong {
  overflow: hidden;
  color: var(--color-text-strong);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.record-title span,
.muted-text,
.remark-text,
.pagination span {
  color: var(--color-text-muted);
  font-size: 13px;
}

.remark-text {
  display: -webkit-box;
  overflow: hidden;
  line-height: 1.5;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
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

.status-pill--warning {
  color: var(--color-warning);
  background: var(--risk-suspicious-bg);
}

.status-pill--danger {
  color: var(--color-danger);
  background: var(--risk-high-bg);
}

.status-pill--muted {
  color: var(--color-text-muted);
  background: var(--color-bg-subtle);
}

.table-actions {
  flex-wrap: wrap;
}

.text-button {
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

.pagination {
  justify-content: space-between;
  padding: var(--space-4) var(--space-5);
  border-top: 1px solid var(--color-border-soft);
}

.dialog-summary {
  margin-bottom: var(--space-5);
  padding: var(--space-3) var(--space-4);
  border-left: 3px solid var(--color-primary);
  color: var(--color-text-strong);
  background: var(--color-bg-subtle);
  font-weight: 800;
}

.detail-summary {
  display: grid;
  grid-template-columns: auto auto minmax(0, 1fr);
  gap: var(--space-5);
  align-items: center;
  padding: var(--space-5);
  border: 1px solid var(--color-border-soft);
  border-left: 4px solid var(--risk-high);
  border-radius: var(--radius-md);
  background: var(--color-bg-subtle);
}

.detail-summary div {
  display: grid;
  gap: var(--space-2);
}

.detail-summary strong {
  color: var(--risk-high);
  font-size: 34px;
}

.detail-summary p,
.detail-text {
  margin: 0;
  color: var(--color-text);
  line-height: 1.8;
  white-space: pre-wrap;
}

.detail-meta,
.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
}

.detail-meta {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.detail-meta div {
  display: grid;
  gap: var(--space-2);
  padding: var(--space-4);
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-md);
}

.detail-meta strong {
  color: var(--color-text-strong);
  font-size: 14px;
}

.risk-points {
  display: grid;
  gap: var(--space-2);
  margin: 0;
  padding-left: var(--space-5);
  color: var(--color-text);
  line-height: 1.7;
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

.admin-high-risk :deep(.detail-dialog .el-dialog__body) {
  max-height: 72vh;
  overflow-y: auto;
}

@media (max-width: 1500px) {
  .filter-panel {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

@media (max-width: 980px) {
  .filter-panel {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .detail-summary,
  .detail-meta,
  .detail-grid {
    grid-template-columns: 1fr;
  }

  .pagination {
    align-items: flex-start;
    flex-direction: column;
  }
}

@media (max-width: 640px) {
  .filter-panel {
    grid-template-columns: 1fr;
  }
}
</style>
