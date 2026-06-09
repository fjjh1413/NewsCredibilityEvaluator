<template>
  <section class="admin-module">
    <PageHeader
      eyebrow="管理员后台"
      title="系统日志"
      description="查看登录、新闻检测和管理员操作等关键审计记录。"
    >
      <template #actions>
        <button class="button button--secondary" type="button" @click="notifyPending">
          <Refresh aria-hidden="true" />
          <span>刷新</span>
        </button>
      </template>
    </PageHeader>

    <AdminEndpointNotice
      title="日志接口待接入"
      description="当前后端 OpenAPI 未注册 GET /api/admin/logs。页面不会生成或展示模拟日志。"
      :endpoints="pendingEndpoints"
    />

    <section class="surface-card surface-card--padded module-filter" aria-label="系统日志筛选">
      <label class="filter-field">
        <span>模块</span>
        <el-select v-model="filters.module" clearable placeholder="全部模块">
          <el-option label="登录认证" value="auth" />
          <el-option label="新闻检测" value="detection" />
          <el-option label="管理员操作" value="admin" />
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

      <div class="filter-actions">
        <button class="button button--primary" type="button" @click="notifyPending">
          <Search aria-hidden="true" />
          <span>查询</span>
        </button>
        <button class="button button--secondary" type="button" @click="resetFilters">重置</button>
      </div>
    </section>

    <section class="surface-card module-table-card">
      <el-table class="module-table" :data="rows" row-key="id">
        <el-table-column label="用户" min-width="150" />
        <el-table-column label="模块" width="130">
          <template #default="{ row }">
            <span class="module-pill">{{ row.module || '--' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="160" />
        <el-table-column label="描述" min-width="300" />
        <el-table-column label="IP" min-width="150" />
        <el-table-column label="时间" min-width="170" />

        <template #empty>
          <EmptyState
            title="日志接口待接入"
            description="GET /api/admin/logs 未注册，暂时无法展示登录、检测或管理员操作日志。"
          />
        </template>
      </el-table>

      <div class="module-pagination">
        <span>共 0 条日志</span>
        <el-pagination background layout="sizes, prev, pager, next" :total="0" :page-size="20" disabled />
      </div>
    </section>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus/es/components/message/index.mjs'
import { Refresh, Search } from '@element-plus/icons-vue'
import EmptyState from '@/components/EmptyState.vue'
import PageHeader from '@/components/PageHeader.vue'
import AdminEndpointNotice from '@/components/admin/AdminEndpointNotice.vue'

const pendingEndpoints = ['GET /api/admin/logs']
const rows = ref([])
const filters = reactive({
  module: '',
  dateFrom: '',
  dateTo: ''
})

function notifyPending() {
  ElMessage.info('日志接口待接入，当前未发送请求')
}

function resetFilters() {
  filters.module = ''
  filters.dateFrom = ''
  filters.dateTo = ''
}
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
  grid-template-columns: minmax(190px, 0.75fr) minmax(220px, 0.9fr) minmax(220px, 0.9fr) auto;
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

@media (max-width: 980px) {
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
