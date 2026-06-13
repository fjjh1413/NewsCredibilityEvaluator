<template>
  <section class="admin-module">
    <PageHeader
      eyebrow="管理员后台"
      title="系统日志"
      description="查看登录、新闻检测和管理员操作等关键审计记录。"
    >
      <template #actions>
        <button class="button button--secondary" type="button" :disabled="loading" @click="fetchLogs">
          <Refresh aria-hidden="true" />
          <span>刷新</span>
        </button>
      </template>
    </PageHeader>

    <section class="surface-card surface-card--padded module-filter" aria-label="系统日志筛选">
      <label class="filter-field filter-field--keyword">
        <span>关键词</span>
        <el-input v-model.trim="filters.keyword" clearable placeholder="用户名、描述或 IP" @keyup.enter="handleSearch" />
      </label>

      <label class="filter-field">
        <span>模块</span>
        <el-select v-model="filters.module" clearable placeholder="全部模块">
          <el-option label="登录认证" value="auth" />
          <el-option label="新闻检测" value="detection" />
          <el-option label="管理员操作" value="admin" />
          <el-option label="知识库" value="knowledge" />
          <el-option label="Prompt" value="prompt" />
          <el-option label="高风险审核" value="high_risk" />
        </el-select>
      </label>

      <label class="filter-field">
        <span>操作</span>
        <el-input v-model.trim="filters.action" clearable placeholder="login / create / review" @keyup.enter="handleSearch" />
      </label>

      <label class="filter-field">
        <span>开始时间</span>
        <input v-model="filters.dateFrom" class="native-input" type="datetime-local" />
      </label>

      <label class="filter-field">
        <span>结束时间</span>
        <input v-model="filters.dateTo" class="native-input" type="datetime-local" />
      </label>

      <div class="filter-actions">
        <button class="button button--primary" type="button" :disabled="loading" @click="handleSearch">
          <Search aria-hidden="true" />
          <span>查询</span>
        </button>
        <button class="button button--secondary" type="button" :disabled="loading" @click="resetFilters">重置</button>
      </div>
    </section>

    <LoadingState v-if="loading && !rows.length" :lines="6" label="系统日志加载中" />

    <section v-else class="surface-card module-table-card">
      <el-table class="module-table" :data="rows" row-key="rowKey" v-loading="loading">
        <el-table-column label="用户" min-width="150">
          <template #default="{ row }">
            <div class="log-user">
              <strong>{{ row.username || '匿名/系统' }}</strong>
              <span v-if="row.userId">ID：{{ row.userId }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="模块" width="140">
          <template #default="{ row }">
            <span class="module-pill">{{ moduleText(row.module) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" min-width="160">
          <template #default="{ row }">
            <span class="strong-text">{{ row.action || '--' }}</span>
          </template>
        </el-table-column>

        <el-table-column label="描述" min-width="320">
          <template #default="{ row }">
            <span class="muted-text">{{ row.description || '--' }}</span>
          </template>
        </el-table-column>

        <el-table-column label="IP" min-width="150">
          <template #default="{ row }">
            <span class="muted-text">{{ row.ipAddress || '--' }}</span>
          </template>
        </el-table-column>

        <el-table-column label="时间" min-width="180">
          <template #default="{ row }">
            <span class="muted-text">{{ formatDateTime(row.createdAt) }}</span>
          </template>
        </el-table-column>

        <template #empty>
          <EmptyState :title="emptyTitle" :description="emptyDescription" />
        </template>
      </el-table>

      <div class="module-pagination">
        <span>共 {{ total }} 条日志</span>
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
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus/es/components/message/index.mjs'
import { Refresh, Search } from '@element-plus/icons-vue'
import { getAdminLogs } from '@/api/adminLogs'
import EmptyState from '@/components/EmptyState.vue'
import LoadingState from '@/components/LoadingState.vue'
import PageHeader from '@/components/PageHeader.vue'

const rows = ref([])
const total = ref(0)
const loading = ref(false)
const errorMessage = ref('')
const interfacePending = ref(false)

const filters = reactive({
  keyword: '',
  module: '',
  action: '',
  dateFrom: '',
  dateTo: ''
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

  if (filters.module) {
    params.module = filters.module
  }

  if (filters.action) {
    params.action = filters.action
  }

  if (filters.dateFrom) {
    params.date_from = filters.dateFrom
  }

  if (filters.dateTo) {
    params.date_to = filters.dateTo
  }

  return params
})

const emptyTitle = computed(() => {
  if (interfacePending.value) {
    return '日志接口待接入'
  }

  if (errorMessage.value) {
    return '系统日志加载失败'
  }

  return '暂无系统日志'
})

const emptyDescription = computed(() => {
  if (interfacePending.value) {
    return 'GET /api/admin/logs 尚未注册，暂时无法展示审计记录。'
  }

  return errorMessage.value || '当前筛选条件下没有日志记录。'
})

function unwrapApiResponse(response) {
  const body = response?.data ?? response
  const code = body?.code

  if (code !== undefined && ![0, 200, 201].includes(Number(code))) {
    throw new Error(body?.message || '系统日志请求失败')
  }

  if (body?.success === false) {
    throw new Error(body?.message || '系统日志请求失败')
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
    payload.logs ??
    payload.data ??
    []

  return {
    items: Array.isArray(items) ? items : [],
    total: Number(payload.total ?? payload.count ?? payload.total_count ?? (Array.isArray(items) ? items.length : 0))
  }
}

function normalizeLog(item, index) {
  const id = pick(item?.id, item?.log_id, item?.logId)

  return {
    id,
    rowKey: id || `${pagination.page}-${index}`,
    userId: pick(item?.user_id, item?.userId),
    username: pick(item?.username, item?.user_name, item?.userName),
    module: pick(item?.module, item?.module_name, item?.moduleName),
    action: pick(item?.action, item?.operation, item?.event),
    description: pick(item?.description, item?.detail, item?.message),
    ipAddress: pick(item?.ip_address, item?.ipAddress, item?.ip),
    createdAt: pick(item?.created_at, item?.createdAt, item?.time, item?.created_time)
  }
}

function isPendingInterfaceError(error) {
  return [404, 405, 501].includes(error?.response?.status)
}

function getErrorMessage(error) {
  if (error?.response?.status === 401) {
    return '登录状态已失效，请重新登录后访问系统日志。'
  }

  if (error?.response?.status === 403) {
    return '当前账号没有访问系统日志接口的权限。'
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

  return error?.response?.data?.message || detail || error?.message || '系统日志请求失败'
}

function moduleText(module) {
  const mapping = {
    auth: '登录认证',
    detection: '新闻检测',
    admin: '管理员操作',
    knowledge: '知识库',
    prompt: 'Prompt',
    high_risk: '高风险审核'
  }
  return mapping[module] || module || '--'
}

function formatDateTime(value) {
  if (!value) {
    return '--'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return String(value)
  }

  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(date)
}

async function fetchLogs() {
  loading.value = true
  errorMessage.value = ''
  interfacePending.value = false

  try {
    const response = await getAdminLogs(queryParams.value)
    const payload = pickList(unwrapApiResponse(response))

    rows.value = payload.items.map(normalizeLog)
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
  fetchLogs()
}

function resetFilters() {
  filters.keyword = ''
  filters.module = ''
  filters.action = ''
  filters.dateFrom = ''
  filters.dateTo = ''
  pagination.page = 1
  fetchLogs()
}

function handleSizeChange(size) {
  pagination.pageSize = size
  pagination.page = 1
  fetchLogs()
}

function handleCurrentChange(page) {
  pagination.page = page
  fetchLogs()
}

onMounted(fetchLogs)
</script>

<style scoped>
.admin-module {
  display: grid;
  gap: var(--space-6);
}

.admin-module :deep(.page-header__actions svg),
.admin-module .button svg {
  width: 16px;
  height: 16px;
}

.module-filter {
  display: grid;
  grid-template-columns: minmax(220px, 1.1fr) minmax(170px, 0.8fr) minmax(190px, 0.9fr) minmax(220px, 0.9fr) minmax(220px, 0.9fr) auto;
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
  box-shadow: 0 0 0 1px var(--color-border) inset;
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
  flex-wrap: wrap;
  gap: var(--space-2);
}

.module-table-card {
  overflow: hidden;
}

.module-table :deep(.el-table__header th) {
  color: var(--color-text-strong);
  background: var(--color-bg-subtle);
  font-size: 13px;
  font-weight: 800;
}

.module-table :deep(.el-table__empty-block) {
  min-height: 300px;
}

.log-user {
  display: grid;
  gap: 2px;
}

.log-user strong,
.strong-text {
  color: var(--color-text-strong);
  font-weight: 800;
}

.log-user span,
.muted-text {
  color: var(--color-text-muted);
  font-size: 13px;
}

.module-pill {
  display: inline-flex;
  min-height: 26px;
  align-items: center;
  padding: 0 9px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
  font-size: 12px;
  font-weight: 800;
}

.module-pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-5);
  border-top: 1px solid var(--color-border-soft);
}

.module-pagination span {
  color: var(--color-text-muted);
  font-size: 13px;
  font-weight: 700;
}

@media (max-width: 1280px) {
  .module-filter {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 860px) {
  .module-filter {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .module-filter {
    grid-template-columns: 1fr;
  }

  .module-pagination {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
