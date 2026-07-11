<template>
  <section class="admin-operation-policies">
    <PageHeader
      eyebrow="管理员后台"
      title="操作策略"
      description="查看后台高风险操作的当前强制控制、审计字段和下一阶段治理措施。"
    >
      <template #actions>
        <div class="toolbar-actions">
          <el-select
            v-model="riskLevel"
            class="risk-select"
            clearable
            placeholder="风险等级"
            @change="fetchPolicies"
            @clear="fetchPolicies"
          >
            <el-option label="Critical" value="critical" />
            <el-option label="High" value="high" />
            <el-option label="Medium" value="medium" />
          </el-select>
          <button class="button button--secondary" type="button" :disabled="loading" @click="fetchPolicies">
            <Refresh aria-hidden="true" />
            <span>刷新</span>
          </button>
        </div>
      </template>
    </PageHeader>

    <LoadingState v-if="loading && !policies.length" :lines="6" label="操作策略加载中" />

    <EmptyState
      v-else-if="errorMessage && !policies.length"
      title="操作策略加载失败"
      :description="errorMessage"
    >
      <template #actions>
        <button class="button button--secondary button--small" type="button" @click="fetchPolicies">
          重新加载
        </button>
      </template>
    </EmptyState>

    <template v-else>
      <section class="policy-summary" aria-label="操作策略概览">
        <article v-for="item in summaryCards" :key="item.key" class="summary-card">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </article>
      </section>

      <section class="surface-card policy-table-card">
        <el-table class="policy-table" :data="policies" row-key="operation_key">
          <el-table-column label="操作" min-width="220">
            <template #default="{ row }">
              <div class="operation-cell">
                <strong>{{ row.title }}</strong>
                <span>{{ row.operation_key }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="风险" width="120">
            <template #default="{ row }">
              <span class="risk-pill" :class="`risk-pill--${row.risk_level}`">
                {{ riskLabel(row.risk_level) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="目标对象" width="140">
            <template #default="{ row }">
              <code class="code-text">{{ row.target_type }}</code>
            </template>
          </el-table-column>
          <el-table-column label="当前强制项" min-width="240">
            <template #default="{ row }">
              <div class="chip-list">
                <span v-for="control in row.current_enforcement" :key="control" class="chip">
                  {{ control }}
                </span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="审计字段" min-width="220">
            <template #default="{ row }">
              <div class="audit-fields">
                <code v-for="field in row.audit_fields" :key="field">{{ field }}</code>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="下一步控制" min-width="260">
            <template #default="{ row }">
              <ul class="control-list">
                <li v-for="control in row.next_controls" :key="control">{{ control }}</li>
              </ul>
            </template>
          </el-table-column>
          <template #empty>
            <EmptyState title="暂无操作策略" description="当前筛选条件下没有匹配的治理策略。" />
          </template>
        </el-table>
      </section>

      <section class="policy-notes">
        <article class="surface-card surface-card--padded">
          <h2>执行边界</h2>
          <p>当前版本以管理员权限、二次确认、结构化审计和服务端保护为主；双人复核、会话重认证和软删除留存进入下一阶段。</p>
        </article>
        <article class="surface-card surface-card--padded">
          <h2>简历表达</h2>
          <p>该页面把“能操作”提升为“可治理”：高风险动作有风险分级、审计字段、回滚提示和演进路线，可作为 AI 应用工程化能力的展示面。</p>
        </article>
      </section>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus/es/components/message/index.mjs'
import { Refresh } from '@element-plus/icons-vue'
import { getAdminOperationPolicies } from '@/api/adminOperationPolicies'
import EmptyState from '@/components/EmptyState.vue'
import LoadingState from '@/components/LoadingState.vue'
import PageHeader from '@/components/PageHeader.vue'
import { unwrapApiResponse } from '@/utils/response'

const loading = ref(false)
const errorMessage = ref('')
const riskLevel = ref('')
const policies = ref([])

const summaryCards = computed(() => {
  const counts = policies.value.reduce(
    (acc, policy) => {
      acc.total += 1
      acc[policy.risk_level] = (acc[policy.risk_level] || 0) + 1
      if (policy.requires_dual_approval) {
        acc.dual += 1
      }
      return acc
    },
    { total: 0, critical: 0, high: 0, medium: 0, dual: 0 }
  )

  return [
    { key: 'total', label: '策略总数', value: counts.total },
    { key: 'critical', label: 'Critical', value: counts.critical },
    { key: 'high', label: 'High', value: counts.high },
    { key: 'dual', label: '建议双人复核', value: counts.dual }
  ]
})

async function fetchPolicies() {
  loading.value = true
  errorMessage.value = ''

  try {
    const params = riskLevel.value ? { risk_level: riskLevel.value } : {}
    const data = unwrapApiResponse(await getAdminOperationPolicies(params))
    policies.value = Array.isArray(data?.items) ? data.items : []
  } catch (error) {
    errorMessage.value = getErrorMessage(error)
    ElMessage.error(errorMessage.value)
  } finally {
    loading.value = false
  }
}

function riskLabel(level) {
  const labels = {
    critical: 'Critical',
    high: 'High',
    medium: 'Medium'
  }
  return labels[level] || level || '--'
}

function getErrorMessage(error) {
  return error?.response?.data?.message || error?.response?.data?.detail || error?.message || '操作策略加载失败'
}

onMounted(fetchPolicies)
</script>

<style scoped>
.admin-operation-policies {
  display: grid;
  gap: var(--space-6);
}

.toolbar-actions {
  display: inline-flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.toolbar-actions .button svg {
  width: 16px;
  height: 16px;
}

.risk-select {
  width: 150px;
}

.policy-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-4);
}

.summary-card {
  display: grid;
  gap: var(--space-2);
  padding: var(--space-4);
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-md);
  background: #ffffff;
}

.summary-card span {
  color: var(--color-text-muted);
  font-size: 13px;
  font-weight: 700;
}

.summary-card strong {
  color: var(--color-text-strong);
  font-size: 28px;
  line-height: 1.1;
}

.policy-table-card {
  overflow: hidden;
}

.policy-table :deep(.el-table__header th) {
  color: var(--color-text-strong);
  background: var(--color-bg-subtle);
  font-size: 13px;
  font-weight: 800;
}

.operation-cell {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.operation-cell strong {
  color: var(--color-text-strong);
}

.operation-cell span {
  overflow-wrap: anywhere;
  color: var(--color-text-muted);
  font-size: 12px;
}

.risk-pill {
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

.risk-pill--critical {
  color: var(--color-danger);
  background: var(--risk-high-bg);
}

.risk-pill--high {
  color: var(--risk-suspicious);
  background: var(--risk-suspicious-bg);
}

.risk-pill--medium {
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
}

.code-text,
.audit-fields code {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 7px;
  border-radius: var(--radius-xs);
  color: var(--color-text-strong);
  background: var(--color-bg-subtle);
  font-size: 12px;
}

.chip-list,
.audit-fields {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chip {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 8px;
  border-radius: 999px;
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
  font-size: 12px;
  font-weight: 800;
}

.control-list {
  display: grid;
  gap: 4px;
  margin: 0;
  padding-left: 18px;
  color: var(--color-text);
  font-size: 13px;
}

.policy-notes {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
}

.policy-notes h2 {
  margin: 0;
  color: var(--color-text-strong);
  font-size: 18px;
}

.policy-notes p {
  margin: var(--space-2) 0 0;
  color: var(--color-text-muted);
  line-height: 1.7;
}

@media (max-width: 1080px) {
  .policy-summary,
  .policy-notes {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .policy-summary,
  .policy-notes {
    grid-template-columns: 1fr;
  }

  .risk-select {
    width: 100%;
  }
}
</style>
