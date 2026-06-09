<template>
  <section class="admin-prompts">
    <PageHeader
      eyebrow="管理员后台"
      title="Prompt 模板管理"
      description="管理新闻可信度分析使用的 Prompt 模板、启停状态和同类型默认模板。"
    >
      <template #actions>
        <button class="button button--secondary" type="button" :disabled="loading" @click="fetchPrompts">
          <Refresh aria-hidden="true" />
          <span>刷新</span>
        </button>
        <button class="button button--primary" type="button" @click="openCreateForm">
          <Plus aria-hidden="true" />
          <span>新增模板</span>
        </button>
      </template>
    </PageHeader>

    <section class="surface-card surface-card--padded admin-prompts__filter" aria-label="Prompt 模板筛选">
      <label class="filter-field filter-field--keyword">
        <span>关键词</span>
        <el-input v-model.trim="filters.keyword" clearable placeholder="模板名称、类型或内容" @keyup.enter="handleSearch" />
      </label>

      <label class="filter-field">
        <span>模板类型</span>
        <el-select v-model="filters.type" clearable filterable allow-create default-first-option placeholder="全部类型">
          <el-option label="news_credibility" value="news_credibility" />
        </el-select>
      </label>

      <label class="filter-field">
        <span>状态</span>
        <el-select v-model="filters.status" clearable placeholder="全部状态">
          <el-option label="已启用" value="enabled" />
          <el-option label="已停用" value="disabled" />
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

    <LoadingState v-if="loading && !rows.length" :lines="6" label="Prompt 模板加载中" />

    <section v-else class="surface-card admin-prompts__table-card">
      <EmptyState
        v-if="!rows.length"
        :title="emptyTitle"
        :description="emptyDescription"
      >
        <template #actions>
          <button class="button button--primary" type="button" @click="openCreateForm">
            <Plus aria-hidden="true" />
            <span>新增模板</span>
          </button>
        </template>
      </EmptyState>

      <template v-else>
        <el-table class="admin-prompts__table" :data="rows" row-key="rowKey" v-loading="loading">
          <el-table-column label="模板名称" min-width="230">
            <template #default="{ row }">
              <div class="prompt-name">
                <strong>{{ row.name }}</strong>
                <span>ID：{{ row.id || '--' }}</span>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="模板类型" min-width="170">
            <template #default="{ row }">
              <code class="type-tag">{{ row.type || '--' }}</code>
            </template>
          </el-table-column>

          <el-table-column label="Prompt 内容" min-width="320">
            <template #default="{ row }">
              <p class="prompt-preview">{{ row.content || '--' }}</p>
            </template>
          </el-table-column>

          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <span class="status-pill" :class="statusClass(row.status)">
                {{ statusText(row.status) }}
              </span>
            </template>
          </el-table-column>

          <el-table-column label="默认模板" width="120">
            <template #default="{ row }">
              <span class="default-pill" :class="{ 'default-pill--active': row.isDefault }">
                {{ row.isDefault ? '默认' : '非默认' }}
              </span>
            </template>
          </el-table-column>

          <el-table-column label="创建人 ID" width="110" align="center">
            <template #default="{ row }">
              <span class="muted-text">{{ row.createdBy || '--' }}</span>
            </template>
          </el-table-column>

          <el-table-column label="更新时间" min-width="160">
            <template #default="{ row }">
              <span class="muted-text">{{ formatDateTime(row.updatedAt) }}</span>
            </template>
          </el-table-column>

          <el-table-column label="操作" width="270" fixed="right">
            <template #default="{ row }">
              <div class="table-actions">
                <button class="text-button" type="button" @click="openEditForm(row)">编辑</button>
                <button
                  class="text-button"
                  type="button"
                  :disabled="actionId === row.id"
                  @click="confirmStatusChange(row)"
                >
                  {{ row.status === 'enabled' ? '停用' : '启用' }}
                </button>
                <button
                  v-if="!row.isDefault"
                  class="text-button"
                  type="button"
                  :disabled="actionId === row.id"
                  @click="confirmSetDefault(row)"
                >
                  设为默认
                </button>
                <button class="text-button text-button--danger" type="button" @click="confirmDelete(row)">删除</button>
              </div>
            </template>
          </el-table-column>
        </el-table>

        <div class="admin-prompts__pagination">
          <span>共 {{ total }} 个模板</span>
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

    <section v-if="formVisible" class="prompt-dialog-overlay" role="dialog" aria-modal="true" aria-labelledby="prompt-dialog-title">
      <div class="prompt-dialog">
        <header class="prompt-dialog__header">
          <div>
            <p>{{ formMode === 'create' ? '新增 Prompt 模板' : '编辑 Prompt 模板' }}</p>
            <h2 id="prompt-dialog-title">{{ formTitle }}</h2>
          </div>
          <button class="icon-button" type="button" aria-label="关闭 Prompt 模板表单" @click="closeForm">
            <Close aria-hidden="true" />
          </button>
        </header>

        <LoadingState v-if="formLoading" :lines="5" label="Prompt 模板详情加载中" />

        <form v-else class="prompt-form" @submit.prevent="submitForm">
          <div class="form-grid">
            <label class="form-field">
              <span>模板名称 <strong>*</strong></span>
              <el-input v-model.trim="form.name" maxlength="100" show-word-limit placeholder="请输入模板名称" />
            </label>

            <label class="form-field">
              <span>模板类型 <strong>*</strong></span>
              <el-select v-model="form.type" filterable allow-create default-first-option placeholder="选择或输入模板类型">
                <el-option label="news_credibility" value="news_credibility" />
              </el-select>
            </label>

            <label class="form-field">
              <span>状态</span>
              <el-select v-model="form.status" placeholder="选择模板状态">
                <el-option label="已启用" value="enabled" />
                <el-option label="已停用" value="disabled" />
              </el-select>
            </label>

            <label class="default-field">
              <input v-model="form.is_default" type="checkbox" />
              <span>保存后设为该类型的默认模板</span>
            </label>

            <div v-if="form.is_default" class="default-impact-notice" role="note">
              <strong>默认模板会直接影响新闻检测主流程</strong>
              <span>保存前请确认模板完整保留新闻标题、正文和检索证据输入。</span>
            </div>

            <label class="form-field form-field--wide">
              <span>Prompt 内容 <strong>*</strong></span>
              <el-input
                v-model="form.content"
                class="prompt-editor"
                type="textarea"
                :rows="20"
                resize="vertical"
                placeholder="请输入 Prompt 模板内容"
              />
            </label>

            <div v-if="isNewsCredibilityPrompt" class="placeholder-guide" aria-live="polite">
              <div class="placeholder-guide__header">
                <strong>新闻检测 Prompt 必需占位符</strong>
                <span>保存、启用和设为默认时，后端会再次强校验。</span>
              </div>
              <ul>
                <li
                  v-for="item in promptPlaceholderChecks"
                  :key="item.key"
                  :class="{ 'placeholder-guide__item--valid': item.valid }"
                >
                  <code>{{ item.placeholder }}</code>
                  <span>{{ item.description }}</span>
                  <strong>{{ item.valid ? '已包含' : '缺失' }}</strong>
                </li>
              </ul>
              <p>检索证据也兼容已有占位符 <code>{evidence_json}</code>。</p>
            </div>
          </div>

          <footer class="prompt-dialog__footer">
            <button class="button button--secondary" type="button" :disabled="submitting" @click="closeForm">
              取消
            </button>
            <button class="button button--primary" type="submit" :disabled="submitting">
              {{ submitting ? '保存中' : '保存模板' }}
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
import { Close, Plus, Refresh, Search } from '@element-plus/icons-vue'
import {
  createAdminPrompt,
  deleteAdminPrompt,
  disableAdminPrompt,
  enableAdminPrompt,
  getAdminPromptDetail,
  getAdminPrompts,
  setDefaultAdminPrompt,
  updateAdminPrompt
} from '@/api/adminPrompts'
import EmptyState from '@/components/EmptyState.vue'
import LoadingState from '@/components/LoadingState.vue'
import PageHeader from '@/components/PageHeader.vue'
import { formatDateTime } from '@/utils/format'

const loading = ref(false)
const rows = ref([])
const total = ref(0)
const errorMessage = ref('')
const interfacePending = ref(false)
const actionId = ref(null)
const formVisible = ref(false)
const formLoading = ref(false)
const formMode = ref('create')
const editingId = ref(null)
const submitting = ref(false)

const NEWS_CREDIBILITY_PROMPT_TYPE = 'news_credibility'
const NEWS_PROMPT_PLACEHOLDERS = [
  {
    key: 'title',
    placeholder: '{title}',
    alternatives: ['{title}'],
    description: '新闻标题'
  },
  {
    key: 'content',
    placeholder: '{content}',
    alternatives: ['{content}'],
    description: '新闻正文'
  },
  {
    key: 'evidence',
    placeholder: '{evidence_list}',
    alternatives: ['{evidence_list}', '{evidence_json}'],
    description: '检索证据'
  }
]

const filters = reactive({
  keyword: '',
  type: '',
  status: ''
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
  if (filters.type) {
    params.type = filters.type
  }
  if (filters.status) {
    params.status = filters.status
  }

  return params
})

const emptyTitle = computed(() => {
  if (interfacePending.value) {
    return 'Prompt 模板接口待接入'
  }
  if (errorMessage.value) {
    return 'Prompt 模板加载失败'
  }
  return '暂无 Prompt 模板'
})

const emptyDescription = computed(() => {
  if (interfacePending.value) {
    return '当前后端尚未注册 /api/admin/prompts 相关接口，页面已保留模板管理入口。'
  }
  return errorMessage.value || '当前筛选条件下没有 Prompt 模板。'
})

const formTitle = computed(() => {
  if (formMode.value === 'create') {
    return '新增模板'
  }
  return form.name || '编辑模板'
})

const isNewsCredibilityPrompt = computed(
  () => form.type.trim() === NEWS_CREDIBILITY_PROMPT_TYPE
)

const promptPlaceholderChecks = computed(() =>
  NEWS_PROMPT_PLACEHOLDERS.map((item) => ({
    ...item,
    valid: item.alternatives.some((placeholder) => form.content.includes(placeholder))
  }))
)

const missingPromptPlaceholders = computed(() =>
  isNewsCredibilityPrompt.value
    ? promptPlaceholderChecks.value.filter((item) => !item.valid)
    : []
)

function createEmptyForm() {
  return {
    name: '',
    type: 'news_credibility',
    content: '',
    status: 'enabled',
    is_default: false
  }
}

function unwrapApiResponse(response) {
  const body = response?.data ?? response
  const code = body?.code

  if (code !== undefined && ![0, 200, 201].includes(Number(code))) {
    throw new Error(body?.message || 'Prompt 模板请求失败')
  }

  if (body?.success === false) {
    throw new Error(body?.message || 'Prompt 模板请求失败')
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
    payload.prompts ??
    payload.data ??
    []

  return {
    items: Array.isArray(items) ? items : [],
    total: Number(payload.total ?? payload.count ?? payload.total_count ?? (Array.isArray(items) ? items.length : 0))
  }
}

function normalizePrompt(item, index = 0) {
  const id = pick(item?.id, item?.prompt_id, item?.promptId)

  return {
    id,
    rowKey: id || `${pagination.page}-${index}`,
    name: pick(item?.name, item?.prompt_name, '未命名模板'),
    type: pick(item?.type, item?.prompt_type, 'news_credibility'),
    content: pick(item?.content, item?.prompt_content, ''),
    isDefault: Boolean(item?.is_default ?? item?.isDefault ?? false),
    status: pick(item?.status, 'disabled'),
    createdBy: pick(item?.created_by, item?.createdBy, ''),
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
    return '登录状态已失效，请重新登录后访问 Prompt 模板管理。'
  }

  if (error?.response?.status === 403) {
    return '当前账号没有访问 Prompt 模板管理接口的权限。'
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

  return error?.response?.data?.message || detail || error?.message || 'Prompt 模板请求失败'
}

function statusText(status) {
  if (status === 'enabled') {
    return '已启用'
  }
  if (status === 'disabled') {
    return '已停用'
  }
  return status || '--'
}

function statusClass(status) {
  return status === 'enabled' ? 'status-pill--success' : 'status-pill--muted'
}

function resetForm(nextValues = createEmptyForm()) {
  Object.assign(form, createEmptyForm(), nextValues)
}

function fillForm(item) {
  resetForm({
    name: item.name || '',
    type: item.type || 'news_credibility',
    content: item.content || '',
    status: item.status || 'enabled',
    is_default: Boolean(item.isDefault)
  })
}

function validateForm() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写模板名称')
    return false
  }
  if (!form.type.trim()) {
    ElMessage.warning('请填写模板类型')
    return false
  }
  if (!form.content.trim()) {
    ElMessage.warning('Prompt 内容不能为空')
    return false
  }
  if (missingPromptPlaceholders.value.length) {
    const missing = missingPromptPlaceholders.value
      .map((item) => `${item.description} ${item.placeholder}`)
      .join('、')
    ElMessage.warning(`新闻检测 Prompt 缺少必要占位符：${missing}`)
    return false
  }
  if (form.status === 'disabled' && form.is_default) {
    ElMessage.warning('停用模板不能设为默认模板')
    return false
  }
  return true
}

function buildFormPayload() {
  return {
    name: form.name.trim(),
    type: form.type.trim(),
    content: form.content.trim(),
    status: form.status,
    is_default: Boolean(form.is_default)
  }
}

async function fetchPrompts() {
  loading.value = true
  errorMessage.value = ''
  interfacePending.value = false

  try {
    const response = await getAdminPrompts(queryParams.value)
    const payload = pickList(unwrapApiResponse(response))
    rows.value = payload.items.map(normalizePrompt)
    total.value = Number.isFinite(payload.total) ? payload.total : rows.value.length
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
  fetchPrompts()
}

function handleReset() {
  filters.keyword = ''
  filters.type = ''
  filters.status = ''
  pagination.page = 1
  fetchPrompts()
}

function handleSizeChange(size) {
  pagination.pageSize = size
  pagination.page = 1
  fetchPrompts()
}

function handleCurrentChange(page) {
  pagination.page = page
  fetchPrompts()
}

function openCreateForm() {
  formMode.value = 'create'
  editingId.value = null
  resetForm()
  formVisible.value = true
}

async function openEditForm(row) {
  if (!row?.id) {
    ElMessage.warning('当前模板缺少 ID，无法编辑')
    return
  }

  formMode.value = 'edit'
  editingId.value = row.id
  fillForm(row)
  formVisible.value = true
  formLoading.value = true

  try {
    const response = await getAdminPromptDetail(row.id)
    fillForm(normalizePrompt(unwrapApiResponse(response)))
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
    if (formMode.value === 'create') {
      await createAdminPrompt(payload)
      ElMessage.success('Prompt 模板已新增')
    } else {
      await updateAdminPrompt(editingId.value, payload)
      ElMessage.success('Prompt 模板已更新')
    }

    formVisible.value = false
    editingId.value = null
    resetForm()
    fetchPrompts()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    submitting.value = false
  }
}

async function confirmStatusChange(row) {
  if (!row?.id) {
    ElMessage.warning('当前模板缺少 ID，无法修改状态')
    return
  }

  const enabling = row.status !== 'enabled'
  const nextStatusText = enabling ? '启用' : '停用'
  const defaultNote = !enabling && row.isDefault ? '停用后，该类型将暂时没有默认模板并使用代码兜底模板。' : ''

  try {
    await ElMessageBox.confirm(
      `确认${nextStatusText}「${row.name}」吗？${defaultNote}`,
      `${nextStatusText} Prompt 模板`,
      {
        confirmButtonText: `确认${nextStatusText}`,
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
  } catch {
    return
  }

  actionId.value = row.id

  try {
    if (enabling) {
      await enableAdminPrompt(row.id)
    } else {
      await disableAdminPrompt(row.id)
    }
    ElMessage.success(`Prompt 模板已${nextStatusText}`)
    fetchPrompts()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    actionId.value = null
  }
}

async function confirmSetDefault(row) {
  if (!row?.id) {
    ElMessage.warning('当前模板缺少 ID，无法设为默认')
    return
  }

  if (row.status !== 'enabled') {
    ElMessage.warning('停用模板不能设为默认模板')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确认将「${row.name}」设为 ${row.type} 类型的默认模板吗？同类型原默认模板将被自动取消。`,
      '设置默认 Prompt 模板',
      {
        confirmButtonText: '确认设为默认',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
  } catch {
    return
  }

  actionId.value = row.id

  try {
    await setDefaultAdminPrompt(row.id)
    ElMessage.success('默认 Prompt 模板已更新')
    fetchPrompts()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    actionId.value = null
  }
}

async function confirmDelete(row) {
  if (!row?.id) {
    ElMessage.warning('当前模板缺少 ID，无法删除')
    return
  }

  if (row.isDefault) {
    ElMessage.warning('默认模板不能直接删除，请先停用或设置同类型的其他默认模板')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确认删除 Prompt 模板「${row.name}」吗？该操作不可撤销。`,
      '删除 Prompt 模板',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
  } catch {
    return
  }

  actionId.value = row.id

  try {
    await deleteAdminPrompt(row.id)
    ElMessage.success('Prompt 模板已删除')
    fetchPrompts()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    actionId.value = null
  }
}

onMounted(fetchPrompts)
</script>

<style scoped>
.admin-prompts {
  display: grid;
  gap: var(--space-6);
}

.admin-prompts :deep(.page-header__actions svg),
.admin-prompts .button svg {
  width: 16px;
  height: 16px;
}

.admin-prompts__filter {
  display: grid;
  grid-template-columns: minmax(280px, 1fr) minmax(210px, 0.65fr) minmax(170px, 0.5fr) auto;
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
.form-field :deep(.el-textarea__inner) {
  min-height: 40px;
  border-radius: var(--radius-sm);
  box-shadow: 0 0 0 1px var(--color-border) inset;
}

.filter-field :deep(.el-input__wrapper.is-focus),
.filter-field :deep(.el-select__wrapper.is-focused),
.form-field :deep(.el-input__wrapper.is-focus),
.form-field :deep(.el-select__wrapper.is-focused),
.form-field :deep(.el-textarea__inner:focus) {
  box-shadow: 0 0 0 1px var(--color-primary) inset, var(--shadow-focus);
}

.filter-actions {
  display: flex;
  gap: var(--space-2);
}

.admin-prompts__table-card {
  overflow: hidden;
}

.admin-prompts__table {
  width: 100%;
}

.admin-prompts__table :deep(.el-table__header th) {
  color: var(--color-text-strong);
  background: var(--color-bg-subtle);
  font-size: 13px;
  font-weight: 800;
}

.admin-prompts__table :deep(.el-table__row:hover > td) {
  background: #f0f9ff;
}

.prompt-name {
  display: grid;
  gap: 5px;
  min-width: 0;
}

.prompt-name strong {
  overflow: hidden;
  color: var(--color-text-strong);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.prompt-name span,
.muted-text {
  color: var(--color-text-muted);
  font-size: 13px;
}

.type-tag {
  display: inline-flex;
  max-width: 100%;
  min-height: 26px;
  align-items: center;
  overflow: hidden;
  padding: 0 8px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
  font-family: Consolas, "SFMono-Regular", monospace;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.prompt-preview {
  display: -webkit-box;
  margin: 0;
  overflow: hidden;
  color: var(--color-text-muted);
  font-size: 13px;
  line-height: 1.55;
  white-space: pre-line;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}

.status-pill,
.default-pill {
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

.status-pill--muted,
.default-pill {
  color: var(--color-text-muted);
  background: var(--color-bg-subtle);
}

.default-pill--active {
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
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

.admin-prompts__pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-5);
  border-top: 1px solid var(--color-border-soft);
}

.admin-prompts__pagination > span {
  color: var(--color-text-muted);
  font-size: 13px;
  font-weight: 700;
}

.prompt-dialog-overlay {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: grid;
  place-items: center;
  padding: var(--space-6);
  background: rgba(15, 23, 42, 0.34);
}

.prompt-dialog {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  width: min(1040px, 100%);
  max-height: min(90vh, 920px);
  overflow: hidden;
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-lg);
  background: var(--color-bg-page);
  box-shadow: 0 22px 64px rgba(15, 23, 42, 0.22);
}

.prompt-dialog__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-5) var(--space-6);
  border-bottom: 1px solid var(--color-border-soft);
  background: rgba(255, 255, 255, 0.96);
}

.prompt-dialog__header p {
  margin: 0 0 var(--space-2);
  color: var(--color-primary);
  font-size: 13px;
  font-weight: 800;
}

.prompt-dialog__header h2 {
  margin: 0;
  color: var(--color-text-strong);
  font-size: 20px;
}

.prompt-form {
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

.default-impact-notice,
.placeholder-guide {
  grid-column: 1 / -1;
}

.default-impact-notice {
  display: grid;
  gap: 4px;
  padding: var(--space-3) var(--space-4);
  border-left: 3px solid var(--color-warning);
  border-radius: var(--radius-sm);
  color: var(--color-text);
  background: var(--risk-suspicious-bg);
  font-size: 13px;
}

.default-impact-notice strong {
  color: var(--color-text-strong);
}

.placeholder-guide {
  display: grid;
  gap: var(--space-3);
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg-subtle);
}

.placeholder-guide__header {
  display: grid;
  gap: 4px;
}

.placeholder-guide__header strong {
  color: var(--color-text-strong);
  font-size: 13px;
}

.placeholder-guide__header span,
.placeholder-guide p {
  margin: 0;
  color: var(--color-text-muted);
  font-size: 12px;
}

.placeholder-guide ul {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.placeholder-guide li {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--color-danger);
  border-radius: var(--radius-sm);
  color: var(--color-danger);
  background: var(--risk-high-bg);
  font-size: 12px;
}

.placeholder-guide__item--valid {
  border-color: var(--color-success);
  color: var(--color-success);
  background: var(--risk-trusted-bg);
}

.placeholder-guide code {
  color: currentColor;
  font-family: Consolas, "SFMono-Regular", monospace;
  font-weight: 800;
}

.placeholder-guide li span {
  overflow: hidden;
  color: var(--color-text);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.placeholder-guide li strong {
  color: currentColor;
  font-size: 12px;
  white-space: nowrap;
}

.default-field {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-height: 40px;
  padding: 0 var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text-strong);
  background: #ffffff;
  cursor: pointer;
  font-size: 13px;
  font-weight: 800;
}

.default-field input {
  width: 17px;
  height: 17px;
  accent-color: var(--color-primary);
}

.prompt-editor :deep(.el-textarea__inner) {
  min-height: 380px !important;
  color: var(--color-text);
  font-family: Consolas, "SFMono-Regular", "Microsoft YaHei", monospace;
  font-size: 13px;
  line-height: 1.65;
}

.prompt-dialog__footer {
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

@media (max-width: 980px) {
  .admin-prompts__filter,
  .form-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .placeholder-guide ul {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .admin-prompts__filter,
  .form-grid {
    grid-template-columns: 1fr;
  }

  .admin-prompts__pagination {
    align-items: flex-start;
    flex-direction: column;
  }
}

@media (max-width: 640px) {
  .filter-actions {
    flex-wrap: wrap;
  }

  .prompt-dialog-overlay {
    padding: var(--space-3);
  }

  .prompt-dialog__header,
  .prompt-form {
    padding-right: var(--space-4);
    padding-left: var(--space-4);
  }

  .prompt-dialog__footer {
    flex-direction: column-reverse;
    margin-right: calc(var(--space-4) * -1);
    margin-left: calc(var(--space-4) * -1);
    padding-right: var(--space-4);
    padding-left: var(--space-4);
  }
}
</style>
