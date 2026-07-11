<template>
  <section class="admin-ai-quality">
    <PageHeader
      eyebrow="管理员后台"
      title="AI 工程质量"
      description="查看离线评估门禁、RAG 召回、契约有效率、退化率和延迟指标，用于证明检测链路可评估、可回归、可上线。"
    >
      <template #actions>
        <button class="button button--secondary" type="button" :disabled="loading" @click="fetchSummary">
          <Refresh aria-hidden="true" />
          <span>刷新</span>
        </button>
      </template>
    </PageHeader>

    <LoadingState v-if="loading && !summary" :lines="6" label="AI 工程质量数据加载中" />

    <EmptyState
      v-else-if="errorMessage && !summary"
      title="AI 工程质量数据加载失败"
      :description="errorMessage"
    >
      <template #actions>
        <button class="button button--secondary button--small" type="button" @click="fetchSummary">
          重新加载
        </button>
      </template>
    </EmptyState>

    <template v-else-if="summary">
      <section class="gate-band" :class="{ 'gate-band--failed': !gatePassed }">
        <div class="gate-band__icon" aria-hidden="true">
          <component :is="gatePassed ? DataAnalysis : WarningFilled" />
        </div>
        <div>
          <span>质量门禁</span>
          <h2>{{ gatePassed ? '通过' : '未通过' }}</h2>
          <p>{{ sourceText }} · {{ generatedAtText }}</p>
        </div>
        <strong class="gate-pill" :class="{ 'gate-pill--failed': !gatePassed }">
          {{ gatePassed ? 'PASS' : 'FAIL' }}
        </strong>
      </section>

      <section class="metric-cards" aria-label="AI 工程核心指标">
        <AdminStatCard
          v-for="card in metricCards"
          :key="card.key"
          :title="card.title"
          :value="card.value"
          :description="card.description"
          :icon="card.icon"
          :tone="card.tone"
          :loading="loading"
        />
      </section>

      <section class="quality-grid">
        <article class="surface-card surface-card--padded quality-panel">
          <header class="quality-panel__header">
            <div>
              <h2>指标明细</h2>
              <p>来自离线评估 runner 的确定性质量门禁结果。</p>
            </div>
          </header>
          <div class="metric-list">
            <div
              v-for="metric in metricRows"
              :key="metric.key"
              class="metric-row"
              :class="{ 'metric-row--failed': failedMetricSet.has(metric.key) }"
            >
              <span>{{ metric.label }}</span>
              <strong>{{ metric.value }}</strong>
              <small>{{ metric.hint }}</small>
            </div>
          </div>
        </article>

        <article class="surface-card surface-card--padded quality-panel">
          <header class="quality-panel__header">
            <div>
              <h2>门禁失败项</h2>
              <p>失败项可直接转化为回归修复任务。</p>
            </div>
          </header>

          <EmptyState
            v-if="!gateFailures.length"
            title="暂无失败项"
            description="当前离线评估门禁全部通过。"
          />
          <div v-else class="failure-list">
            <div v-for="failure in gateFailures" :key="failure.metric" class="failure-row">
              <strong>{{ metricLabel(failure.metric) }}</strong>
              <span>
                {{ formatMetricValue(failure.metric, failure.actual) }}
                {{ failure.direction }}
                {{ formatMetricValue(failure.metric, failure.threshold) }}
              </span>
            </div>
          </div>
        </article>
      </section>

      <section class="surface-card case-table-card">
        <header class="case-table-card__header">
          <div>
            <h2>Case 明细</h2>
            <p>展示最多 100 条离线评估样本，便于定位契约、风险等级、RAG 和延迟问题。</p>
          </div>
        </header>

        <el-table class="case-table" :data="caseRows" row-key="case_id">
          <el-table-column label="Case" min-width="160">
            <template #default="{ row }">
              <strong class="case-id">{{ row.case_id }}</strong>
            </template>
          </el-table-column>
          <el-table-column label="契约" width="100">
            <template #default="{ row }">
              <span class="status-pill" :class="row.contract_valid ? 'status-pill--success' : 'status-pill--danger'">
                {{ row.contract_valid ? '有效' : '异常' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="风险等级" width="110">
            <template #default="{ row }">
              <span class="status-pill" :class="row.risk_level_match === false ? 'status-pill--danger' : 'status-pill--success'">
                {{ row.risk_level_match === false ? '不匹配' : '匹配' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="RAG Recall" width="120">
            <template #default="{ row }">
              <span class="muted-text">{{ formatPercent(row.context_recall_at_k) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="RAG MRR" width="110">
            <template #default="{ row }">
              <span class="muted-text">{{ formatNumber(row.rag_mrr_at_k) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="延迟" width="130">
            <template #default="{ row }">
              <span class="muted-text">{{ formatLatency(row.total_latency_ms) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="契约问题" min-width="220">
            <template #default="{ row }">
              <span class="muted-text">{{ contractErrorText(row.contract_errors) }}</span>
            </template>
          </el-table-column>
          <template #empty>
            <EmptyState title="暂无 Case 明细" description="summary 中未包含 per_case 数据。" />
          </template>
        </el-table>
      </section>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus/es/components/message/index.mjs'
import { Clock, DataAnalysis, Files, Refresh, WarningFilled } from '@element-plus/icons-vue'
import { getAiEngineeringSummary } from '@/api/adminAiEngineering'
import AdminStatCard from '@/components/admin/AdminStatCard.vue'
import EmptyState from '@/components/EmptyState.vue'
import LoadingState from '@/components/LoadingState.vue'
import PageHeader from '@/components/PageHeader.vue'
import { formatDateTime } from '@/utils/format'
import { unwrapStatisticsResponse } from '@/utils/statisticsCharts'

const loading = ref(false)
const errorMessage = ref('')
const summary = ref(null)

const metrics = computed(() => summary.value?.metrics || {})
const gate = computed(() => summary.value?.gate || {})
const gatePassed = computed(() => Boolean(gate.value.passed))
const gateFailures = computed(() => (Array.isArray(gate.value.failures) ? gate.value.failures : []))
const failedMetricSet = computed(() => new Set(gateFailures.value.map((failure) => failure.metric)))
const caseRows = computed(() => (Array.isArray(summary.value?.per_case) ? summary.value.per_case : []))
const sourceText = computed(() => {
  const source = summary.value?.source || {}
  const label = source.type === 'sample_cases' ? '示例样本' : '评估摘要'
  return `${label}: ${source.path || '--'}`
})
const generatedAtText = computed(() => {
  if (!summary.value?.generated_at) {
    return '生成时间待记录'
  }
  return `生成于 ${formatDateTime(summary.value.generated_at)}`
})

const metricDefinitions = [
  { key: 'contract_valid_rate', label: '契约有效率', hint: '输出字段完整、分数范围合法', type: 'percent' },
  { key: 'risk_level_accuracy', label: '风险等级准确率', hint: '预测风险等级匹配期望', type: 'percent' },
  { key: 'score_in_range_rate', label: '分数区间命中率', hint: '可信度分数落在期望区间', type: 'percent' },
  { key: 'context_precision_at_k', label: 'Context Precision@K', hint: '相关证据是否排在前面', type: 'percent' },
  { key: 'context_recall_at_k', label: 'Context Recall@K', hint: 'RAG 是否召回关键证据', type: 'percent' },
  { key: 'rag_hit_rate_at_k', label: 'RAG Hit@K', hint: '至少命中一条相关证据', type: 'percent' },
  { key: 'rag_mrr_at_k', label: 'RAG MRR@K', hint: '第一条相关证据的平均倒数排名', type: 'number' },
  { key: 'degraded_rate', label: '退化率', hint: 'provider error、parse failed、timeout 等', type: 'percent' },
  { key: 'total_latency_ms_p95', label: 'P95 延迟', hint: '总耗时或阶段耗时求和', type: 'latency' }
]

const metricRows = computed(() =>
  metricDefinitions.map((definition) => ({
    ...definition,
    value: formatMetricValue(definition.key, metrics.value[definition.key], definition.type)
  }))
)

const metricCards = computed(() => [
  {
    key: 'gate',
    title: '质量门禁',
    value: gatePassed.value ? 'PASS' : 'FAIL',
    description: gatePassed.value ? '可作为合并前质量证明' : '存在需修复的回归项',
    icon: DataAnalysis,
    tone: gatePassed.value ? 'success' : 'danger'
  },
  {
    key: 'cases',
    title: '评估样本数',
    value: metrics.value.total_cases ?? '--',
    description: '离线质量门禁覆盖的 case 数量',
    icon: Files,
    tone: 'primary'
  },
  {
    key: 'risk',
    title: '风险准确率',
    value: formatPercent(metrics.value.risk_level_accuracy),
    description: '分类结果与期望标签的一致性',
    icon: DataAnalysis,
    tone: toneForRate(metrics.value.risk_level_accuracy)
  },
  {
    key: 'recall',
    title: 'RAG Recall@K',
    value: formatPercent(metrics.value.context_recall_at_k),
    description: '关键证据召回能力',
    icon: DataAnalysis,
    tone: toneForRate(metrics.value.context_recall_at_k)
  },
  {
    key: 'degraded',
    title: '退化率',
    value: formatPercent(metrics.value.degraded_rate),
    description: '失败、降级、超时等异常占比',
    icon: WarningFilled,
    tone: Number(metrics.value.degraded_rate || 0) > 0 ? 'warning' : 'success'
  },
  {
    key: 'latency',
    title: 'P95 延迟',
    value: formatLatency(metrics.value.total_latency_ms_p95),
    description: '离线捕获输出的端到端耗时',
    icon: Clock,
    tone: 'accent'
  }
])

async function fetchSummary() {
  loading.value = true
  errorMessage.value = ''

  try {
    summary.value = unwrapStatisticsResponse(await getAiEngineeringSummary())
  } catch (error) {
    errorMessage.value = getErrorMessage(error)
    ElMessage.error(errorMessage.value)
  } finally {
    loading.value = false
  }
}

function metricLabel(key) {
  return metricDefinitions.find((metric) => metric.key === key)?.label || key
}

function formatMetricValue(key, value, explicitType = '') {
  const type = explicitType || metricDefinitions.find((metric) => metric.key === key)?.type
  if (type === 'percent') {
    return formatPercent(value)
  }
  if (type === 'latency') {
    return formatLatency(value)
  }
  return formatNumber(value)
}

function formatPercent(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) {
    return '--'
  }
  return `${(number * 100).toFixed(1)}%`
}

function formatNumber(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) {
    return '--'
  }
  return Number.isInteger(number) ? String(number) : number.toFixed(3)
}

function formatLatency(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) {
    return '--'
  }
  return `${Math.round(number)} ms`
}

function contractErrorText(errors) {
  return Array.isArray(errors) && errors.length ? errors.join(', ') : '--'
}

function toneForRate(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) {
    return 'muted'
  }
  if (number >= 0.8) {
    return 'success'
  }
  if (number >= 0.6) {
    return 'warning'
  }
  return 'danger'
}

function getErrorMessage(error) {
  return error?.response?.data?.message || error?.response?.data?.detail || error?.message || 'AI 工程质量数据加载失败'
}

onMounted(fetchSummary)
</script>

<style scoped>
.admin-ai-quality {
  display: grid;
  gap: var(--space-6);
}

.admin-ai-quality .button svg {
  width: 16px;
  height: 16px;
}

.gate-band {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: var(--space-4);
  align-items: center;
  padding: var(--space-5);
  border: 1px solid rgba(22, 163, 74, 0.26);
  border-left: 4px solid var(--color-success);
  border-radius: var(--radius-lg);
  background: rgba(220, 252, 231, 0.55);
}

.gate-band--failed {
  border-color: rgba(220, 38, 38, 0.24);
  border-left-color: var(--color-danger);
  background: rgba(254, 226, 226, 0.58);
}

.gate-band__icon {
  display: grid;
  width: 46px;
  height: 46px;
  place-items: center;
  border-radius: var(--radius-md);
  color: var(--color-success);
  background: #ffffff;
}

.gate-band--failed .gate-band__icon {
  color: var(--color-danger);
}

.gate-band__icon svg {
  width: 24px;
  height: 24px;
}

.gate-band span,
.quality-panel__header p,
.case-table-card__header p,
.muted-text {
  color: var(--color-text-muted);
  font-size: 13px;
}

.gate-band h2,
.quality-panel__header h2,
.case-table-card__header h2 {
  margin: 0;
  color: var(--color-text-strong);
}

.gate-band h2 {
  margin-top: var(--space-1);
  font-size: 24px;
}

.gate-band p,
.quality-panel__header p,
.case-table-card__header p {
  margin: var(--space-2) 0 0;
  line-height: 1.6;
}

.gate-pill {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 0 12px;
  border-radius: 999px;
  color: var(--color-success);
  background: #ffffff;
  font-size: 13px;
}

.gate-pill--failed {
  color: var(--color-danger);
}

.metric-cards {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-4);
}

.quality-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(320px, 0.9fr);
  gap: var(--space-6);
}

.quality-panel,
.case-table-card {
  min-width: 0;
}

.quality-panel__header,
.case-table-card__header {
  margin-bottom: var(--space-4);
}

.metric-list,
.failure-list {
  display: grid;
  gap: var(--space-3);
}

.metric-row,
.failure-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--space-2) var(--space-4);
  align-items: center;
  padding: var(--space-3);
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-sm);
  background: var(--color-bg-subtle);
}

.metric-row--failed,
.failure-row {
  border-color: rgba(220, 38, 38, 0.22);
  background: rgba(254, 226, 226, 0.42);
}

.metric-row span,
.failure-row strong {
  color: var(--color-text-strong);
  font-weight: 800;
}

.metric-row strong,
.failure-row span {
  color: var(--color-primary-strong);
  font-weight: 800;
}

.metric-row small {
  grid-column: 1 / -1;
  color: var(--color-text-muted);
}

.case-table-card {
  overflow: hidden;
}

.case-table-card__header {
  padding: var(--space-5) var(--space-5) 0;
}

.case-table :deep(.el-table__header th) {
  color: var(--color-text-strong);
  background: var(--color-bg-subtle);
  font-size: 13px;
  font-weight: 800;
}

.case-id {
  overflow-wrap: anywhere;
  color: var(--color-text-strong);
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

@media (max-width: 1180px) {
  .metric-cards,
  .quality-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .gate-band,
  .metric-cards,
  .quality-grid {
    grid-template-columns: 1fr;
  }

  .gate-pill {
    justify-self: start;
  }
}
</style>
