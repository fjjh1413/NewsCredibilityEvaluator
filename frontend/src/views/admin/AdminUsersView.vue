<template>
  <section class="admin-users">
    <PageHeader
      eyebrow="管理员后台"
      title="用户管理"
      description="查看平台账号、角色和启用状态，并安全执行账号启用与禁用。"
    >
      <template #actions>
        <button class="button button--secondary" type="button" :disabled="loading" @click="fetchUsers">
          <Refresh aria-hidden="true" />
          <span>刷新</span>
        </button>
      </template>
    </PageHeader>

    <section class="surface-card surface-card--padded admin-users__filter" aria-label="用户筛选">
      <label class="filter-field filter-field--keyword">
        <span>用户名或邮箱</span>
        <el-input v-model.trim="filters.keyword" clearable placeholder="输入用户名或邮箱" @keyup.enter="handleSearch" />
      </label>

      <label class="filter-field">
        <span>角色</span>
        <el-select v-model="filters.role" clearable placeholder="全部角色">
          <el-option label="管理员" value="admin" />
          <el-option label="普通用户" value="user" />
        </el-select>
      </label>

      <label class="filter-field">
        <span>状态</span>
        <el-select v-model="filters.status" clearable placeholder="全部状态">
          <el-option label="启用" value="active" />
          <el-option label="禁用" value="disabled" />
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

    <LoadingState v-if="loading && !rows.length" :lines="6" label="用户列表加载中" />

    <section v-else class="surface-card admin-users__table-card">
      <EmptyState
        v-if="!rows.length"
        :title="emptyTitle"
        :description="emptyDescription"
      />

      <template v-else>
        <el-table class="admin-users__table" :data="rows" row-key="rowKey" v-loading="loading">
          <el-table-column label="用户名" min-width="180">
            <template #default="{ row }">
              <div class="user-identity">
                <strong>{{ row.username }}</strong>
                <span>ID：{{ row.id || '--' }}</span>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="邮箱" min-width="220">
            <template #default="{ row }">
              <span class="muted-text">{{ row.email || '--' }}</span>
            </template>
          </el-table-column>

          <el-table-column label="角色" width="120">
            <template #default="{ row }">
              <span class="status-pill" :class="roleClass(row.role)">
                {{ roleText(row.role) }}
              </span>
            </template>
          </el-table-column>

          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <span class="status-pill" :class="statusClass(row.status)">
                {{ statusText(row.status) }}
              </span>
            </template>
          </el-table-column>

          <el-table-column label="注册时间" min-width="160">
            <template #default="{ row }">
              <span class="muted-text">{{ formatDateTime(row.createdAt) }}</span>
            </template>
          </el-table-column>

          <el-table-column label="最近登录" min-width="160">
            <template #default="{ row }">
              <span class="muted-text">{{ formatDateTime(row.lastLoginAt) }}</span>
            </template>
          </el-table-column>

          <el-table-column label="检测次数" width="110" align="center">
            <template #default="{ row }">
              <strong class="count-text">{{ formatCount(row.detectionCount) }}</strong>
            </template>
          </el-table-column>

          <el-table-column label="操作" width="320" fixed="right">
            <template #default="{ row }">
              <div class="table-actions">
                <button class="text-button" type="button" @click="openUserPanel(row)">详情</button>
                <button class="text-button" type="button" @click="openUserDetections(row)">检测记录</button>
                <button
                  class="text-button"
                  :class="{ 'text-button--danger': row.status === 'active' }"
                  type="button"
                  :disabled="statusUpdatingId === row.id"
                  @click="confirmStatusChange(row)"
                >
                  {{ row.status === 'active' ? '禁用' : '启用' }}
                </button>
                <button
                  class="text-button"
                  :class="{ 'text-button--danger': row.role !== 'admin' }"
                  type="button"
                  :disabled="roleUpdatingId === row.id"
                  @click="confirmRoleChange(row)"
                >
                  {{ row.role === 'admin' ? '改为普通用户' : '设为管理员' }}
                </button>
              </div>
            </template>
          </el-table-column>
        </el-table>

        <div class="admin-users__pagination">
          <span>共 {{ total }} 个用户</span>
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

    <section v-if="panelVisible" class="user-panel-overlay" role="dialog" aria-modal="true" aria-labelledby="user-panel-title">
      <div class="user-panel">
        <header class="user-panel__header">
          <div>
            <p>用户详情</p>
            <h2 id="user-panel-title">{{ panelTitle }}</h2>
          </div>
          <button class="icon-button" type="button" aria-label="关闭用户详情" @click="closePanel">
            <Close aria-hidden="true" />
          </button>
        </header>

        <LoadingState v-if="detailLoading" :lines="5" label="用户详情加载中" />

        <div v-else class="user-panel__content">
          <EmptyState
            v-if="detailError && !selectedUser"
            title="用户详情接口待接入"
            :description="detailError"
          />

          <template v-else-if="selectedUser">
            <section class="user-profile surface-card">
              <div class="user-profile__mark" aria-hidden="true">
                <UserFilled />
              </div>
              <div>
                <span>{{ roleText(selectedUser.role) }}</span>
                <h3>{{ selectedUser.username }}</h3>
                <p>{{ selectedUser.email || '未填写邮箱' }}</p>
              </div>
              <span class="status-pill" :class="statusClass(selectedUser.status)">
                {{ statusText(selectedUser.status) }}
              </span>
            </section>

            <section class="user-meta-grid">
              <div>
                <span>用户 ID</span>
                <strong>{{ selectedUser.id || '--' }}</strong>
              </div>
              <div>
                <span>注册时间</span>
                <strong>{{ formatDateTime(selectedUser.createdAt) }}</strong>
              </div>
              <div>
                <span>最近登录</span>
                <strong>{{ formatDateTime(selectedUser.lastLoginAt) }}</strong>
              </div>
              <div>
                <span>检测次数</span>
                <strong>{{ formatCount(selectedUser.detectionCount) }}</strong>
              </div>
            </section>
          </template>

          <section class="surface-card surface-card--padded user-detections">
            <div class="user-detections__header">
              <div>
                <h3>该用户检测记录</h3>
                <p>数据来源：GET /api/admin/users/{id}/detections</p>
              </div>
              <button
                class="button button--secondary button--small"
                type="button"
                :disabled="detectionsLoading || !selectedUser?.id"
                @click="loadUserDetections(selectedUser)"
              >
                刷新记录
              </button>
            </div>

            <LoadingState v-if="detectionsLoading" :lines="4" label="用户检测记录加载中" />
            <EmptyState
              v-else-if="!userDetections.length"
              :title="detectionsPending ? '用户检测记录接口待接入' : '暂无用户检测记录'"
              :description="detectionsError || '当前用户暂无可展示检测记录。'"
            />
            <div v-else class="detection-list">
              <article v-for="record in userDetections" :key="record.rowKey" class="detection-card">
                <div>
                  <h4>{{ record.title }}</h4>
                  <p>{{ formatDateTime(record.createdAt) }}</p>
                </div>
                <RiskLevelTag :level="record.riskLevel" :score="record.finalScore" size="small" />
              </article>
            </div>
          </section>
        </div>
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus/es/components/message/index.mjs'
import { ElMessageBox } from 'element-plus/es/components/message-box/index.mjs'
import { Close, Refresh, Search, UserFilled } from '@element-plus/icons-vue'
import {
  disableAdminUser,
  enableAdminUser,
  getAdminUserDetail,
  getAdminUserDetections,
  getAdminUsers,
  updateAdminUserRole
} from '@/api/adminUsers'
import EmptyState from '@/components/EmptyState.vue'
import LoadingState from '@/components/LoadingState.vue'
import PageHeader from '@/components/PageHeader.vue'
import RiskLevelTag from '@/components/RiskLevelTag.vue'
import { useUserStore } from '@/stores/user'
import { formatDateTime } from '@/utils/format'

const userStore = useUserStore()
const loading = ref(false)
const rows = ref([])
const total = ref(0)
const errorMessage = ref('')
const interfacePending = ref(false)
const statusUpdatingId = ref(null)
const roleUpdatingId = ref(null)
const panelVisible = ref(false)
const detailLoading = ref(false)
const detailError = ref('')
const selectedUser = ref(null)
const detectionsLoading = ref(false)
const detectionsPending = ref(false)
const detectionsError = ref('')
const userDetections = ref([])

const filters = reactive({
  keyword: '',
  role: '',
  status: ''
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

  if (filters.role) {
    params.role = filters.role
  }

  if (filters.status) {
    params.status = filters.status
  }

  return params
})

const currentAdminId = computed(() => {
  const user = userStore.user || {}
  const id = user.id ?? user.user_id ?? user.userId
  const numberId = Number(id)
  return Number.isInteger(numberId) ? numberId : null
})

const emptyTitle = computed(() => {
  if (interfacePending.value) {
    return '用户管理接口待接入'
  }

  if (errorMessage.value) {
    return '用户列表加载失败'
  }

  return '暂无用户数据'
})

const emptyDescription = computed(() => {
  if (interfacePending.value) {
    return '当前后端尚未注册 /api/admin/users 相关接口，页面已保留用户管理表格与操作入口。'
  }

  return errorMessage.value || '当前筛选条件下没有用户。'
})

const panelTitle = computed(() => selectedUser.value?.username || '用户详情')

function unwrapApiResponse(response) {
  const body = response?.data ?? response
  const code = body?.code

  if (code !== undefined && ![0, 200, 201].includes(Number(code))) {
    throw new Error(body?.message || '用户管理请求失败')
  }

  if (body?.success === false) {
    throw new Error(body?.message || '用户管理请求失败')
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
    payload.users ??
    payload.data ??
    []

  return {
    items: Array.isArray(items) ? items : [],
    total: Number(payload.total ?? payload.count ?? payload.total_count ?? (Array.isArray(items) ? items.length : 0))
  }
}

function normalizeUser(item, index) {
  const id = pick(item?.id, item?.user_id, item?.userId)

  return {
    id,
    rowKey: id || `${pagination.page}-${index}`,
    username: pick(item?.username, item?.name, item?.account, '未命名用户'),
    email: pick(item?.email, item?.mail, ''),
    role: pick(item?.role, item?.user_role, item?.userRole, ''),
    status: pick(item?.status, item?.account_status, item?.accountStatus, ''),
    createdAt: pick(item?.created_at, item?.create_time, item?.registered_at, item?.createdAt),
    lastLoginAt: pick(item?.last_login_at, item?.lastLoginAt, item?.last_login_time, item?.lastLoginTime),
    detectionCount: pick(item?.detection_count, item?.detectionCount, item?.detections_count, item?.total_detections, null),
    raw: item
  }
}

function normalizeDetection(item, index) {
  const id = pick(item?.id, item?.detection_id, item?.record_id)

  return {
    id,
    rowKey: id || `${index}-${pick(item?.input_title, item?.title, 'record')}`,
    title: pick(item?.input_title, item?.news_title, item?.title, '未命名检测记录'),
    finalScore: pick(item?.final_score, item?.credibility_score, item?.score, null),
    riskLevel: pick(item?.risk_level, item?.riskLevel, ''),
    createdAt: pick(item?.created_at, item?.detected_at, item?.detection_time, item?.create_time)
  }
}

function isPendingInterfaceError(error) {
  return [404, 405, 501].includes(error?.response?.status)
}

function getErrorMessage(error) {
  if (error?.response?.status === 401) {
    return '登录状态已失效，请重新登录后访问用户管理。'
  }

  if (error?.response?.status === 403) {
    return '当前账号没有访问用户管理接口的权限。'
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

  return error?.response?.data?.message || detail || error?.message || '用户管理请求失败'
}

function roleText(role) {
  if (role === 'admin') {
    return '管理员'
  }

  if (role === 'user') {
    return '普通用户'
  }

  return role || '--'
}

function roleClass(role) {
  if (role === 'admin') {
    return 'status-pill--primary'
  }

  if (role === 'user') {
    return 'status-pill--muted'
  }

  return 'status-pill--muted'
}

function statusText(status) {
  if (status === 'active') {
    return '启用'
  }

  if (status === 'disabled') {
    return '禁用'
  }

  return status || '--'
}

function statusClass(status) {
  if (status === 'active') {
    return 'status-pill--success'
  }

  if (status === 'disabled') {
    return 'status-pill--danger'
  }

  return 'status-pill--muted'
}

function formatCount(value) {
  if (value === null || value === undefined || value === '') {
    return '--'
  }

  const numberValue = Number(value)
  return Number.isFinite(numberValue) ? new Intl.NumberFormat('zh-CN').format(numberValue) : String(value)
}

async function fetchUsers() {
  loading.value = true
  errorMessage.value = ''
  interfacePending.value = false

  try {
    const response = await getAdminUsers(queryParams.value)
    const payload = unwrapApiResponse(response)
    const listPayload = pickList(payload)

    rows.value = listPayload.items.map(normalizeUser)
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
  fetchUsers()
}

function handleReset() {
  filters.keyword = ''
  filters.role = ''
  filters.status = ''
  pagination.page = 1
  fetchUsers()
}

function handleSizeChange(size) {
  pagination.pageSize = size
  pagination.page = 1
  fetchUsers()
}

function handleCurrentChange(page) {
  pagination.page = page
  fetchUsers()
}

async function openUserPanel(row) {
  panelVisible.value = true
  selectedUser.value = row
  detailError.value = ''
  userDetections.value = []
  detectionsError.value = ''
  detectionsPending.value = false

  await loadUserDetail(row)
  await loadUserDetections(selectedUser.value || row)
}

async function openUserDetections(row) {
  panelVisible.value = true
  selectedUser.value = row
  detailError.value = ''
  userDetections.value = []
  await loadUserDetections(row)
}

async function loadUserDetail(row) {
  if (!row?.id) {
    return
  }

  detailLoading.value = true

  try {
    const response = await getAdminUserDetail(row.id)
    selectedUser.value = normalizeUser(unwrapApiResponse(response), 0)
  } catch (error) {
    detailError.value = isPendingInterfaceError(error) ? 'GET /api/admin/users/{id} 尚未实现，当前展示列表中的用户快照。' : getErrorMessage(error)
    selectedUser.value = row
  } finally {
    detailLoading.value = false
  }
}

async function loadUserDetections(user) {
  if (!user?.id) {
    detectionsError.value = '当前用户缺少 ID，无法查询检测记录。'
    userDetections.value = []
    return
  }

  detectionsLoading.value = true
  detectionsError.value = ''
  detectionsPending.value = false

  try {
    const response = await getAdminUserDetections(user.id, { page: 1, page_size: 5 })
    const payload = pickList(unwrapApiResponse(response))
    userDetections.value = payload.items.map(normalizeDetection)
  } catch (error) {
    userDetections.value = []
    detectionsPending.value = isPendingInterfaceError(error)
    detectionsError.value = detectionsPending.value ? 'GET /api/admin/users/{id}/detections 尚未实现。' : getErrorMessage(error)
  } finally {
    detectionsLoading.value = false
  }
}

function closePanel() {
  panelVisible.value = false
  selectedUser.value = null
  detailError.value = ''
  detectionsError.value = ''
  detectionsPending.value = false
  userDetections.value = []
}

function isSelfUser(row) {
  const rowId = Number(row?.id)
  return currentAdminId.value !== null && Number.isInteger(rowId) && rowId === currentAdminId.value
}

async function confirmStatusChange(row) {
  if (!row?.id) {
    ElMessage.warning('当前用户缺少 ID，无法修改状态')
    return
  }

  const nextStatus = row.status === 'active' ? 'disabled' : 'active'

  if (nextStatus === 'disabled' && isSelfUser(row)) {
    ElMessage.warning('不能在前端禁用当前登录的管理员账号')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确认将用户「${row.username}」状态修改为「${statusText(nextStatus)}」吗？`,
      '修改用户状态',
      {
        confirmButtonText: '确认修改',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
  } catch {
    return
  }

  statusUpdatingId.value = row.id

  try {
    if (nextStatus === 'active') {
      await enableAdminUser(row.id)
    } else {
      await disableAdminUser(row.id)
    }
    ElMessage.success('用户状态已更新')
    fetchUsers()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    statusUpdatingId.value = null
  }
}

async function confirmRoleChange(row) {
  if (!row?.id) {
    ElMessage.warning('当前用户缺少 ID，无法修改角色')
    return
  }

  const nextRole = row.role === 'admin' ? 'user' : 'admin'

  if (nextRole === 'user' && isSelfUser(row)) {
    ElMessage.warning('不能在前端降低当前登录管理员的角色')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确认将用户「${row.username}」角色修改为「${roleText(nextRole)}」吗？`,
      '修改用户角色',
      {
        confirmButtonText: '确认修改',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
  } catch {
    return
  }

  roleUpdatingId.value = row.id

  try {
    await updateAdminUserRole(row.id, nextRole)
    ElMessage.success('用户角色已更新')

    if (String(selectedUser.value?.id) === String(row.id)) {
      selectedUser.value = { ...selectedUser.value, role: nextRole }
    }

    await fetchUsers()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    roleUpdatingId.value = null
  }
}

onMounted(fetchUsers)
</script>

<style scoped>
.admin-users {
  display: grid;
  gap: var(--space-6);
}

.admin-users :deep(.page-header__actions svg),
.admin-users .button svg {
  width: 16px;
  height: 16px;
}

.admin-users__filter {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) minmax(180px, 0.55fr) minmax(180px, 0.55fr) auto;
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
.filter-field :deep(.el-select__wrapper) {
  min-height: 40px;
  border-radius: var(--radius-sm);
  box-shadow: 0 0 0 1px var(--color-border) inset;
}

.filter-field :deep(.el-input__wrapper.is-focus),
.filter-field :deep(.el-select__wrapper.is-focused) {
  box-shadow: 0 0 0 1px var(--color-primary) inset, var(--shadow-focus);
}

.filter-actions {
  display: flex;
  gap: var(--space-2);
}

.admin-users__table-card {
  overflow: hidden;
}

.admin-users__table {
  width: 100%;
}

.admin-users__table :deep(.el-table__header th) {
  color: var(--color-text-strong);
  background: var(--color-bg-subtle);
  font-size: 13px;
  font-weight: 800;
}

.admin-users__table :deep(.el-table__row:hover > td) {
  background: #f0f9ff;
}

.user-identity {
  display: grid;
  gap: 5px;
  min-width: 0;
}

.user-identity strong {
  overflow: hidden;
  color: var(--color-text-strong);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-identity span,
.muted-text {
  color: var(--color-text-muted);
  font-size: 13px;
}

.count-text {
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

.status-pill--primary {
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
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

.admin-users__pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-5);
  border-top: 1px solid var(--color-border-soft);
}

.admin-users__pagination > span {
  color: var(--color-text-muted);
  font-size: 13px;
  font-weight: 700;
}

.user-panel-overlay {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: grid;
  place-items: center;
  padding: var(--space-6);
  background: rgba(15, 23, 42, 0.34);
}

.user-panel {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: var(--space-5);
  width: min(980px, 100%);
  max-height: min(88vh, 860px);
  overflow: hidden;
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-lg);
  background: var(--color-bg-page);
  box-shadow: 0 22px 64px rgba(15, 23, 42, 0.22);
}

.user-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-5) var(--space-6);
  border-bottom: 1px solid var(--color-border-soft);
  background: rgba(255, 255, 255, 0.96);
}

.user-panel__header p {
  margin: 0 0 var(--space-2);
  color: var(--color-primary);
  font-size: 13px;
  font-weight: 800;
}

.user-panel__header h2 {
  margin: 0;
  color: var(--color-text-strong);
  font-size: 20px;
}

.user-panel__content {
  display: grid;
  gap: var(--space-5);
  min-height: 0;
  overflow-y: auto;
  padding: 0 var(--space-6) var(--space-6);
}

.user-profile {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: var(--space-4);
  align-items: center;
  padding: var(--space-5);
}

.user-profile__mark {
  display: grid;
  width: 48px;
  height: 48px;
  place-items: center;
  border-radius: var(--radius-md);
  color: var(--color-primary);
  background: var(--color-primary-soft);
}

.user-profile__mark svg {
  width: 24px;
  height: 24px;
}

.user-profile span:not(.status-pill),
.user-meta-grid span {
  color: var(--color-text-muted);
  font-size: 13px;
  font-weight: 800;
}

.user-profile h3 {
  margin: var(--space-1) 0;
  color: var(--color-text-strong);
  font-size: 20px;
}

.user-profile p {
  margin: 0;
  color: var(--color-text-muted);
}

.user-meta-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-4);
}

.user-meta-grid div {
  display: grid;
  gap: var(--space-2);
  padding: var(--space-4);
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.96);
}

.user-meta-grid strong {
  overflow: hidden;
  color: var(--color-text-strong);
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-detections {
  display: grid;
  gap: var(--space-4);
}

.user-detections__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
}

.user-detections__header h3 {
  margin: 0;
  color: var(--color-text-strong);
  font-size: 18px;
}

.user-detections__header p {
  margin: var(--space-2) 0 0;
  color: var(--color-text-muted);
  font-size: 13px;
}

.detection-list {
  display: grid;
  gap: var(--space-3);
}

.detection-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--space-3);
  align-items: center;
  padding: var(--space-4);
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-md);
  background: var(--color-bg-subtle);
}

.detection-card h4 {
  margin: 0;
  overflow: hidden;
  color: var(--color-text-strong);
  font-size: 15px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detection-card p {
  margin: var(--space-2) 0 0;
  color: var(--color-text-muted);
  font-size: 13px;
}

@media (max-width: 1020px) {
  .admin-users__filter {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 820px) {
  .admin-users__pagination,
  .user-detections__header {
    align-items: flex-start;
    flex-direction: column;
  }

  .user-profile,
  .user-meta-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .admin-users__filter {
    grid-template-columns: 1fr;
  }

  .filter-actions {
    flex-wrap: wrap;
  }

  .user-panel-overlay {
    padding: var(--space-3);
  }

  .user-panel__header,
  .user-panel__content {
    padding-right: var(--space-4);
    padding-left: var(--space-4);
  }

  .detection-card {
    grid-template-columns: 1fr;
  }
}
</style>
