<template>
  <section class="admin-knowledge">
    <PageHeader
      eyebrow="管理员后台"
      title="知识库管理"
      description="维护 RAG 检索使用的新闻知识库数据，查看 MySQL 与向量索引同步状态，并通过后端接口触发向量化。"
    >
      <template #actions>
        <button class="button button--secondary" type="button" :disabled="loading || rebuilding" @click="fetchKnowledge">
          <Refresh aria-hidden="true" />
          <span>刷新</span>
        </button>
        <button class="button button--secondary" type="button" :disabled="loading || rebuilding" @click="confirmRebuildIndex">
          <Connection aria-hidden="true" />
          <span>全量重建</span>
        </button>
        <button class="button button--primary" type="button" @click="openCreateForm">
          <Plus aria-hidden="true" />
          <span>新增知识</span>
        </button>
      </template>
    </PageHeader>

    <section class="surface-card surface-card--padded admin-knowledge__filter" aria-label="知识库筛选">
      <label class="filter-field filter-field--keyword">
        <span>关键词</span>
        <el-input v-model.trim="filters.keyword" clearable placeholder="标题、正文、摘要或关键词" @keyup.enter="handleSearch" />
      </label>

      <label class="filter-field">
        <span>类别</span>
        <el-input v-model.trim="filters.category" clearable placeholder="如 社会、科技" @keyup.enter="handleSearch" />
      </label>

      <label class="filter-field">
        <span>真实性标签</span>
        <el-select v-model="filters.truthLabel" clearable filterable allow-create default-first-option placeholder="全部标签">
          <el-option label="可信" value="可信" />
          <el-option label="不实" value="不实" />
          <el-option label="存疑" value="存疑" />
          <el-option label="辟谣" value="辟谣" />
        </el-select>
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
        <span>向量状态</span>
        <el-select v-model="filters.vectorStatus" clearable placeholder="全部状态">
          <el-option label="synced" value="synced" />
          <el-option label="pending" value="pending" />
          <el-option label="failed" value="failed" />
        </el-select>
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

    <LoadingState v-if="loading && !rows.length" :lines="6" label="知识库数据加载中" />

    <section v-else class="surface-card admin-knowledge__table-card">
      <EmptyState
        v-if="!displayRows.length"
        :title="emptyTitle"
        :description="emptyDescription"
      >
        <template #actions>
          <button class="button button--primary" type="button" @click="openCreateForm">
            <Plus aria-hidden="true" />
            <span>新增知识</span>
          </button>
        </template>
      </EmptyState>

      <template v-else>
        <el-table class="admin-knowledge__table" :data="displayRows" row-key="rowKey" v-loading="loading">
          <el-table-column label="新闻标题" min-width="280">
            <template #default="{ row }">
              <div class="knowledge-title">
                <strong>{{ row.title }}</strong>
                <span>ID：{{ row.id || '--' }}</span>
                <p v-if="row.summary">{{ row.summary }}</p>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="类别" width="110">
            <template #default="{ row }">
              <span class="muted-text">{{ row.category || '--' }}</span>
            </template>
          </el-table-column>

          <el-table-column label="真实性标签" width="120">
            <template #default="{ row }">
              <span class="status-pill status-pill--primary">{{ row.truthLabel || '--' }}</span>
            </template>
          </el-table-column>

          <el-table-column label="来源" min-width="170">
            <template #default="{ row }">
              <div class="source-cell">
                <strong>{{ row.sourceName || '--' }}</strong>
                <a v-if="row.sourceUrl" :href="row.sourceUrl" target="_blank" rel="noreferrer">查看原文</a>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="风险等级" width="150">
            <template #default="{ row }">
              <RiskLevelTag :level="row.riskLevel" size="small" />
            </template>
          </el-table-column>

          <el-table-column label="向量同步状态" width="160">
            <template #default="{ row }">
              <div class="vector-cell">
                <span class="vector-pill" :class="vectorStatusClass(row.vectorStatus)">
                  {{ vectorStatusText(row.vectorStatus) }}
                </span>
                <button
                  v-if="row.vectorStatus === 'failed'"
                  class="mini-link mini-link--danger"
                  type="button"
                  @click="showVectorError(row)"
                >
                  错误详情
                </button>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="向量错误信息" min-width="180">
            <template #default="{ row }">
              <span class="error-snippet" :title="row.vectorError || ''">{{ row.vectorError || '--' }}</span>
            </template>
          </el-table-column>

          <el-table-column label="更新时间" min-width="160">
            <template #default="{ row }">
              <span class="muted-text">{{ formatDateTime(row.updatedAt) }}</span>
            </template>
          </el-table-column>

          <el-table-column label="操作" width="230" fixed="right">
            <template #default="{ row }">
              <div class="table-actions">
                <button class="text-button" type="button" @click="openEditForm(row)">编辑</button>
                <button
                  class="text-button"
                  type="button"
                  :disabled="vectorizingId === row.id"
                  @click="confirmVectorize(row)"
                >
                  {{ vectorizingId === row.id ? '向量化中' : '重新向量化' }}
                </button>
                <button class="text-button text-button--danger" type="button" @click="confirmDelete(row)">删除</button>
              </div>
            </template>
          </el-table-column>
        </el-table>

        <div class="admin-knowledge__pagination">
          <span v-if="filters.vectorStatus">当前页匹配 {{ displayRows.length }} 条 / 共 {{ total }} 条</span>
          <span v-else>共 {{ total }} 条知识</span>
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

    <section v-if="formVisible" class="knowledge-dialog-overlay" role="dialog" aria-modal="true" aria-labelledby="knowledge-dialog-title">
      <div class="knowledge-dialog">
        <header class="knowledge-dialog__header">
          <div>
            <p>{{ formMode === 'create' ? '新增知识库数据' : '编辑知识库数据' }}</p>
            <h2 id="knowledge-dialog-title">{{ formTitle }}</h2>
          </div>
          <button class="icon-button" type="button" aria-label="关闭知识库表单" @click="closeForm">
            <Close aria-hidden="true" />
          </button>
        </header>

        <LoadingState v-if="formLoading" :lines="5" label="知识库详情加载中" />

        <form v-else class="knowledge-form" @submit.prevent="submitForm">
          <div class="form-grid">
            <label class="form-field form-field--wide">
              <span>新闻标题 <strong>*</strong></span>
              <el-input v-model.trim="form.title" maxlength="255" show-word-limit placeholder="请输入新闻标题" />
            </label>

            <label class="form-field">
              <span>类别</span>
              <el-input v-model.trim="form.category" maxlength="50" placeholder="如 社会、科技" />
            </label>

            <label class="form-field">
              <span>真实性标签 <strong>*</strong></span>
              <el-select v-model="form.truth_label" filterable allow-create default-first-option placeholder="选择或输入标签">
                <el-option label="可信" value="可信" />
                <el-option label="不实" value="不实" />
                <el-option label="存疑" value="存疑" />
                <el-option label="辟谣" value="辟谣" />
              </el-select>
            </label>

            <label class="form-field">
              <span>来源名称</span>
              <el-input v-model.trim="form.source_name" maxlength="100" placeholder="如 官方媒体" />
            </label>

            <label class="form-field">
              <span>来源链接</span>
              <el-input v-model.trim="form.source_url" maxlength="500" placeholder="https://example.com/news" />
            </label>

            <label class="form-field">
              <span>发布时间</span>
              <input v-model="form.publish_time" class="native-input" type="datetime-local" />
            </label>

            <label class="form-field">
              <span>风险等级</span>
              <el-select v-model="form.risk_level" clearable placeholder="选择风险等级">
                <el-option label="可信新闻" value="可信新闻" />
                <el-option label="存疑信息" value="存疑信息" />
                <el-option label="疑似谣言" value="疑似谣言" />
                <el-option label="高风险谣言" value="高风险谣言" />
              </el-select>
            </label>

            <label class="form-field form-field--wide">
              <span>关键词</span>
              <el-input v-model.trim="form.keywords" maxlength="500" show-word-limit placeholder="多个关键词可用逗号分隔" />
            </label>

            <label class="form-field form-field--wide">
              <span>摘要</span>
              <el-input v-model="form.summary" type="textarea" :rows="3" placeholder="请输入新闻摘要" />
            </label>

            <label class="form-field form-field--wide">
              <span>新闻正文 <strong>*</strong></span>
              <el-input v-model="form.content" type="textarea" :rows="8" placeholder="请输入新闻正文或事实核查材料正文" />
            </label>

            <label class="form-field form-field--wide">
              <span>辟谣说明</span>
              <el-input v-model="form.debunking_explanation" type="textarea" :rows="4" placeholder="请输入辟谣说明、事实核查结论或佐证说明" />
            </label>

            <label class="form-field form-field--wide">
              <span>管理员备注</span>
              <el-input v-model="form.admin_note" type="textarea" :rows="3" placeholder="仅管理员可见的维护备注" />
            </label>
          </div>

          <footer class="knowledge-dialog__footer">
            <button class="button button--secondary" type="button" :disabled="submitting" @click="closeForm">
              取消
            </button>
            <button class="button button--primary" type="submit" :disabled="submitting">
              {{ submitting ? '保存中' : '保存' }}
            </button>
          </footer>
        </form>
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus/es/components/message/index.mjs'
import { ElMessageBox } from 'element-plus/es/components/message-box/index.mjs'
import { Close, Connection, Plus, Refresh, Search } from '@element-plus/icons-vue'
import {
  createAdminKnowledge,
  deleteAdminKnowledge,
  getAdminKnowledge,
  getAdminKnowledgeDetail,
  rebuildAdminKnowledgeIndex,
  updateAdminKnowledge,
  vectorizeAdminKnowledge
} from '@/api/adminKnowledge'
import EmptyState from '@/components/EmptyState.vue'
import LoadingState from '@/components/LoadingState.vue'
import PageHeader from '@/components/PageHeader.vue'
import RiskLevelTag from '@/components/RiskLevelTag.vue'
import { formatDateTime } from '@/utils/format'

const loading = ref(false)
const rows = ref([])
const total = ref(0)
const errorMessage = ref('')
const interfacePending = ref(false)
const vectorizingId = ref(null)
const rebuilding = ref(false)
const formVisible = ref(false)
const formMode = ref('create')
const formLoading = ref(false)
const submitting = ref(false)
const editingId = ref(null)

const filters = reactive({
  keyword: '',
  category: '',
  truthLabel: '',
  riskLevel: '',
  vectorStatus: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 20
})

const form = reactive(createEmptyForm())

const queryParams = computed(() => {
  const params = {
    page: pagination.page,
    page_size: pagination.pageSize
  }

  if (filters.keyword) {
    params.keyword = filters.keyword
  }

  if (filters.category) {
    params.category = filters.category
  }

  if (filters.truthLabel) {
    params.truth_label = filters.truthLabel
  }

  if (filters.riskLevel) {
    params.risk_level = filters.riskLevel
  }

  if (filters.vectorStatus) {
    params.vector_sync_status = filters.vectorStatus
  }

  return params
})

const displayRows = computed(() => {
  if (!filters.vectorStatus) {
    return rows.value
  }

  return rows.value.filter((row) => row.vectorStatus === filters.vectorStatus)
})

const emptyTitle = computed(() => {
  if (interfacePending.value) {
    return '知识库管理接口待接入'
  }

  if (errorMessage.value) {
    return '知识库数据加载失败'
  }

  return '暂无知识库数据'
})

const emptyDescription = computed(() => {
  if (interfacePending.value) {
    return '当前后端尚未注册 /api/admin/knowledge 相关接口，页面已保留知识库管理表格与操作入口。'
  }

  if (errorMessage.value) {
    return errorMessage.value
  }

  if (filters.vectorStatus) {
    return '当前页没有匹配该向量同步状态的知识库数据。'
  }

  return '当前筛选条件下没有知识库数据。'
})

const formTitle = computed(() => {
  if (formMode.value === 'create') {
    return '新增知识库数据'
  }

  return form.title || '编辑知识库数据'
})

function createEmptyForm() {
  return {
    title: '',
    content: '',
    category: '',
    truth_label: '',
    source_name: '',
    source_url: '',
    publish_time: '',
    summary: '',
    keywords: '',
    debunking_explanation: '',
    risk_level: '',
    admin_note: ''
  }
}

function unwrapApiResponse(response) {
  const body = response?.data ?? response
  const code = body?.code

  if (code !== undefined && ![0, 200, 201].includes(Number(code))) {
    throw new Error(body?.message || '知识库请求失败')
  }

  if (body?.success === false) {
    throw new Error(body?.message || '知识库请求失败')
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
    payload.knowledge ??
    payload.data ??
    []

  return {
    items: Array.isArray(items) ? items : [],
    total: Number(payload.total ?? payload.count ?? payload.total_count ?? (Array.isArray(items) ? items.length : 0))
  }
}

function normalizeKnowledge(item, index = 0) {
  const id = pick(item?.id, item?.knowledge_id, item?.knowledgeId)

  return {
    id,
    rowKey: id || `${pagination.page}-${index}`,
    title: pick(item?.title, item?.news_title, '未命名知识'),
    content: pick(item?.content, item?.news_content, ''),
    category: pick(item?.category, ''),
    truthLabel: pick(item?.truth_label, item?.truthLabel, ''),
    sourceName: pick(item?.source_name, item?.sourceName, ''),
    sourceUrl: pick(item?.source_url, item?.sourceUrl, ''),
    publishTime: pick(item?.publish_time, item?.publishTime, ''),
    summary: pick(item?.summary, ''),
    keywords: pick(item?.keywords, ''),
    debunkingExplanation: pick(item?.debunking_explanation, item?.debunkingExplanation, ''),
    riskLevel: pick(item?.risk_level, item?.riskLevel, ''),
    adminNote: pick(item?.admin_note, item?.adminNote, ''),
    vectorId: pick(item?.vector_id, item?.vectorId, ''),
    vectorStatus: pick(item?.vector_sync_status, item?.vectorSyncStatus, 'pending'),
    vectorError: pick(item?.vector_sync_error, item?.vectorSyncError, ''),
    createdAt: pick(item?.created_at, item?.createdAt, ''),
    updatedAt: pick(item?.updated_at, item?.updatedAt, ''),
    raw: item
  }
}

function isPendingInterfaceError(error) {
  return [404, 405, 501].includes(error?.response?.status)
}

function getErrorMessage(error) {
  if (error?.response?.status === 401) {
    return '登录状态已失效，请重新登录后访问知识库管理。'
  }

  if (error?.response?.status === 403) {
    return '当前账号没有访问知识库管理接口的权限。'
  }

  const detail = error?.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => item?.msg || item?.message || JSON.stringify(item))
      .filter(Boolean)
      .join('；')
  }

  if (detail && typeof detail === 'object') {
    return detail.message || JSON.stringify(detail)
  }

  return error?.response?.data?.message || detail || error?.message || '知识库请求失败'
}

function vectorStatusText(status) {
  if (status === 'synced') {
    return 'synced'
  }

  if (status === 'failed') {
    return 'failed'
  }

  if (status === 'pending') {
    return 'pending'
  }

  return status || '--'
}

function vectorStatusClass(status) {
  if (status === 'synced') {
    return 'vector-pill--success'
  }

  if (status === 'failed') {
    return 'vector-pill--danger'
  }

  return 'vector-pill--pending'
}

function resetForm(nextValues = createEmptyForm()) {
  Object.assign(form, createEmptyForm(), nextValues)
}

function fillFormFromKnowledge(item) {
  resetForm({
    title: item.title || '',
    content: item.content || '',
    category: item.category || '',
    truth_label: item.truthLabel || '',
    source_name: item.sourceName || '',
    source_url: item.sourceUrl || '',
    publish_time: toDateTimeLocal(item.publishTime),
    summary: item.summary || '',
    keywords: item.keywords || '',
    debunking_explanation: item.debunkingExplanation || '',
    risk_level: item.riskLevel || '',
    admin_note: item.adminNote || ''
  })
}

function toDateTimeLocal(value) {
  if (!value) {
    return ''
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return String(value).slice(0, 16)
  }

  const offsetDate = new Date(date.getTime() - date.getTimezoneOffset() * 60000)
  return offsetDate.toISOString().slice(0, 16)
}

function cleanNullableText(value) {
  if (value === null || value === undefined) {
    return null
  }

  const text = String(value).trim()
  return text ? text : null
}

function buildFormPayload() {
  return {
    title: form.title.trim(),
    content: form.content.trim(),
    category: cleanNullableText(form.category),
    truth_label: form.truth_label.trim(),
    source_name: cleanNullableText(form.source_name),
    source_url: cleanNullableText(form.source_url),
    publish_time: form.publish_time || null,
    summary: cleanNullableText(form.summary),
    keywords: cleanNullableText(form.keywords),
    debunking_explanation: cleanNullableText(form.debunking_explanation),
    risk_level: cleanNullableText(form.risk_level),
    admin_note: cleanNullableText(form.admin_note)
  }
}

function validateForm() {
  if (!form.title.trim()) {
    ElMessage.warning('请填写新闻标题')
    return false
  }

  if (!form.truth_label.trim()) {
    ElMessage.warning('请填写真实性标签')
    return false
  }

  if (!form.content.trim()) {
    ElMessage.warning('请填写新闻正文')
    return false
  }

  return true
}

function updateRow(updatedItem) {
  const normalized = normalizeKnowledge(updatedItem)
  const index = rows.value.findIndex((item) => item.id === normalized.id)
  if (index >= 0) {
    rows.value.splice(index, 1, normalized)
  }
  return normalized
}

async function fetchKnowledge() {
  loading.value = true
  errorMessage.value = ''
  interfacePending.value = false

  try {
    const response = await getAdminKnowledge(queryParams.value)
    const payload = unwrapApiResponse(response)
    const listPayload = pickList(payload)

    rows.value = listPayload.items.map(normalizeKnowledge)
    total.value = Number.isFinite(listPayload.total) ? listPayload.total : rows.value.length
  } catch (error) {
    rows.value = []
    total.value = 0
    interfacePending.value = isPendingInterfaceError(error)
    errorMessage.value = interfacePending.value ? '' : getErrorMessage(error)

    if (!interfacePending.value) {
      ElMessage.error(errorMessage.value)
    }
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pagination.page = 1
  fetchKnowledge()
}

function handleReset() {
  filters.keyword = ''
  filters.category = ''
  filters.truthLabel = ''
  filters.riskLevel = ''
  filters.vectorStatus = ''
  pagination.page = 1
  fetchKnowledge()
}

function handleSizeChange(size) {
  pagination.pageSize = size
  pagination.page = 1
  fetchKnowledge()
}

function handleCurrentChange(page) {
  pagination.page = page
  fetchKnowledge()
}

function openCreateForm() {
  formMode.value = 'create'
  editingId.value = null
  resetForm()
  formVisible.value = true
}

async function openEditForm(row) {
  if (!row?.id) {
    ElMessage.warning('当前知识库数据缺少 ID，无法编辑')
    return
  }

  formMode.value = 'edit'
  editingId.value = row.id
  fillFormFromKnowledge(row)
  formVisible.value = true
  formLoading.value = true

  try {
    const response = await getAdminKnowledgeDetail(row.id)
    fillFormFromKnowledge(normalizeKnowledge(unwrapApiResponse(response)))
  } catch (error) {
    ElMessage.warning(getErrorMessage(error))
  } finally {
    formLoading.value = false
  }
}

function closeForm() {
  if (submitting.value || formLoading.value) {
    return
  }

  formVisible.value = false
  editingId.value = null
  resetForm()
}

async function submitForm() {
  if (!validateForm()) {
    return
  }

  submitting.value = true

  try {
    const payload = buildFormPayload()
    const response =
      formMode.value === 'create'
        ? await createAdminKnowledge(payload)
        : await updateAdminKnowledge(editingId.value, payload)

    const saved = normalizeKnowledge(unwrapApiResponse(response))
    const message = formMode.value === 'create' ? '知识库数据已新增' : '知识库数据已更新'

    if (saved.vectorStatus === 'failed') {
      ElMessage.warning(`${message}，但向量化失败，请查看错误详情`)
    } else {
      ElMessage.success(message)
    }

    formVisible.value = false
    editingId.value = null
    resetForm()
    fetchKnowledge()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    submitting.value = false
  }
}

async function confirmDelete(row) {
  if (!row?.id) {
    ElMessage.warning('当前知识库数据缺少 ID，无法删除')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确认删除「${row.title}」吗？删除会通过后端同步处理 MySQL 与 Chroma。`,
      '删除知识库数据',
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
    await deleteAdminKnowledge(row.id)
    ElMessage.success('知识库数据已删除')
    fetchKnowledge()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

async function confirmVectorize(row) {
  if (!row?.id) {
    ElMessage.warning('当前知识库数据缺少 ID，无法向量化')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确认重新向量化「${row.title}」吗？该操作会调用后端写入向量索引。`,
      '重新向量化',
      {
        confirmButtonText: '确认向量化',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
  } catch {
    return
  }

  vectorizingId.value = row.id

  try {
    const response = await vectorizeAdminKnowledge(row.id)
    const updated = updateRow(unwrapApiResponse(response))

    if (updated.vectorStatus === 'failed') {
      ElMessage.warning('向量化失败，请查看错误详情')
      showVectorError(updated)
    } else {
      ElMessage.success('向量化已完成')
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    vectorizingId.value = null
  }
}

async function confirmRebuildIndex() {
  try {
    await ElMessageBox.confirm(
      '确认全量重建知识库向量索引吗？该操作会调用后端重建 Chroma 索引，耗时取决于知识库规模。',
      '全量重建索引',
      {
        confirmButtonText: '确认重建',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
  } catch {
    return
  }

  rebuilding.value = true

  try {
    const response = await rebuildAdminKnowledgeIndex()
    const data = unwrapApiResponse(response)
    const summary = `总数 ${data?.total ?? 0}，成功 ${data?.success ?? 0}，失败 ${data?.failed ?? 0}`

    if (Number(data?.failed || 0) > 0) {
      ElMessage.warning(`索引重建完成但存在失败：${summary}`)
      await ElMessageBox.alert(
        `失败 ID：${Array.isArray(data?.failed_ids) && data.failed_ids.length ? data.failed_ids.join(', ') : '--'}`,
        '索引重建失败详情',
        { confirmButtonText: '知道了' }
      )
    } else {
      ElMessage.success(`索引重建完成：${summary}`)
    }

    fetchKnowledge()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    rebuilding.value = false
  }
}

function showVectorError(row) {
  ElMessageBox.alert(
    row?.vectorError || '后端未返回具体向量化错误信息。',
    `向量错误：${row?.title || '知识库数据'}`,
    {
      confirmButtonText: '知道了',
      type: 'error'
    }
  )
}

onMounted(fetchKnowledge)
</script>

<style scoped>
.admin-knowledge {
  display: grid;
  gap: var(--space-6);
}

.admin-knowledge :deep(.page-header__actions svg),
.admin-knowledge .button svg {
  width: 16px;
  height: 16px;
}

.admin-knowledge__filter {
  display: grid;
  grid-template-columns: minmax(240px, 1.2fr) minmax(150px, 0.7fr) minmax(150px, 0.7fr) minmax(170px, 0.75fr) minmax(150px, 0.7fr) auto;
  gap: var(--space-4);
  align-items: end;
}

.filter-field,
.form-field {
  display: grid;
  gap: var(--space-2);
  min-width: 0;
}

.filter-field span,
.form-field span {
  color: var(--color-text-strong);
  font-size: 13px;
  font-weight: 800;
}

.form-field strong {
  color: var(--color-danger);
}

.filter-field :deep(.el-input__wrapper),
.filter-field :deep(.el-select__wrapper),
.form-field :deep(.el-input__wrapper),
.form-field :deep(.el-select__wrapper),
.form-field :deep(.el-textarea__inner),
.native-input {
  min-height: 40px;
  border-radius: var(--radius-sm);
  box-shadow: 0 0 0 1px var(--color-border) inset;
}

.filter-field :deep(.el-input__wrapper.is-focus),
.filter-field :deep(.el-select__wrapper.is-focused),
.form-field :deep(.el-input__wrapper.is-focus),
.form-field :deep(.el-select__wrapper.is-focused),
.form-field :deep(.el-textarea__inner:focus),
.native-input:focus {
  box-shadow: 0 0 0 1px var(--color-primary) inset, var(--shadow-focus);
}

.native-input {
  width: 100%;
  padding: 0 12px;
  border: 0;
  color: var(--color-text);
  background: #ffffff;
}

.filter-actions {
  display: flex;
  gap: var(--space-2);
}

.admin-knowledge__table-card {
  overflow: hidden;
}

.admin-knowledge__table {
  width: 100%;
}

.admin-knowledge__table :deep(.el-table__header th) {
  color: var(--color-text-strong);
  background: var(--color-bg-subtle);
  font-size: 13px;
  font-weight: 800;
}

.admin-knowledge__table :deep(.el-table__row:hover > td) {
  background: #f0f9ff;
}

.knowledge-title {
  display: grid;
  gap: 5px;
  min-width: 0;
}

.knowledge-title strong {
  overflow: hidden;
  color: var(--color-text-strong);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.knowledge-title span,
.knowledge-title p,
.muted-text {
  color: var(--color-text-muted);
  font-size: 13px;
}

.knowledge-title p {
  display: -webkit-box;
  margin: 0;
  overflow: hidden;
  line-height: 1.5;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.source-cell {
  display: grid;
  gap: 5px;
}

.source-cell strong {
  overflow: hidden;
  color: var(--color-text-strong);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-cell a,
.mini-link {
  width: fit-content;
  border: 0;
  color: var(--color-primary-strong);
  background: transparent;
  cursor: pointer;
  font-size: 13px;
  font-weight: 800;
}

.source-cell a:hover,
.mini-link:hover {
  color: var(--color-primary);
}

.mini-link--danger {
  color: var(--color-danger);
}

.status-pill,
.vector-pill {
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

.status-pill--primary {
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
}

.vector-cell {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  align-items: center;
}

.vector-pill--success {
  color: var(--color-success);
  background: var(--risk-trusted-bg);
}

.vector-pill--pending {
  color: var(--color-warning);
  background: var(--risk-suspicious-bg);
}

.vector-pill--danger {
  color: var(--color-danger);
  background: var(--risk-high-bg);
}

.error-snippet {
  display: block;
  overflow: hidden;
  color: var(--color-text-muted);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.table-actions {
  display: flex;
  flex-wrap: wrap;
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

.text-button:disabled {
  cursor: not-allowed;
  opacity: 0.56;
}

.text-button--danger {
  color: var(--color-danger);
}

.text-button--danger:hover {
  color: var(--color-danger);
  background: var(--risk-high-bg);
}

.admin-knowledge__pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-5);
  border-top: 1px solid var(--color-border-soft);
}

.admin-knowledge__pagination > span {
  color: var(--color-text-muted);
  font-size: 13px;
  font-weight: 700;
}

.knowledge-dialog-overlay {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: grid;
  place-items: center;
  padding: var(--space-6);
  background: rgba(15, 23, 42, 0.34);
}

.knowledge-dialog {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  width: min(1040px, 100%);
  max-height: min(90vh, 900px);
  overflow: hidden;
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-lg);
  background: var(--color-bg-page);
  box-shadow: 0 22px 64px rgba(15, 23, 42, 0.22);
}

.knowledge-dialog__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-5) var(--space-6);
  border-bottom: 1px solid var(--color-border-soft);
  background: rgba(255, 255, 255, 0.96);
}

.knowledge-dialog__header p {
  margin: 0 0 var(--space-2);
  color: var(--color-primary);
  font-size: 13px;
  font-weight: 800;
}

.knowledge-dialog__header h2 {
  margin: 0;
  color: var(--color-text-strong);
  font-size: 20px;
}

.knowledge-form {
  display: grid;
  min-height: 0;
  overflow-y: auto;
  padding: var(--space-6);
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-5);
}

.form-field--wide {
  grid-column: 1 / -1;
}

.knowledge-dialog__footer {
  position: sticky;
  bottom: 0;
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
  margin: var(--space-6) calc(var(--space-6) * -1) calc(var(--space-6) * -1);
  padding: var(--space-4) var(--space-6);
  border-top: 1px solid var(--color-border-soft);
  background: rgba(255, 255, 255, 0.98);
}

@media (max-width: 1500px) {
  .admin-knowledge__filter {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 820px) {
  .admin-knowledge__filter,
  .form-grid {
    grid-template-columns: 1fr;
  }

  .admin-knowledge__pagination {
    align-items: flex-start;
    flex-direction: column;
  }
}

@media (max-width: 640px) {
  .filter-actions {
    flex-wrap: wrap;
  }

  .knowledge-dialog-overlay {
    padding: var(--space-3);
  }

  .knowledge-dialog__header,
  .knowledge-form {
    padding-right: var(--space-4);
    padding-left: var(--space-4);
  }

  .knowledge-dialog__footer {
    flex-direction: column-reverse;
    margin-right: calc(var(--space-4) * -1);
    margin-left: calc(var(--space-4) * -1);
    padding-right: var(--space-4);
    padding-left: var(--space-4);
  }
}
</style>
