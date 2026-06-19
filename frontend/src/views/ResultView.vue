<template>
  <div class="page-stack result-page">
    <LoadingState v-if="loading" :lines="6" label="检测结果加载中" />

    <template v-else-if="resultData">
      <PageHeader
        eyebrow="检测结果"
        :title="newsTitle"
        :description="resultTimeDescription"
      >
        <template #actions>
          <button
            v-if="hasGeneratedReport"
            class="button button--primary report-action-button"
            type="button"
            :disabled="reportBusy"
            :aria-busy="reportDownloading"
            @click="handleDownloadReport"
          >
            <el-icon><Loading v-if="reportDownloading" class="report-action-icon--loading" /><Download v-else /></el-icon>
            {{ reportDownloading ? '报告下载中' : '下载 PDF 报告' }}
          </button>
          <button
            v-if="hasGeneratedReport"
            class="button button--secondary report-action-button"
            type="button"
            :disabled="reportBusy"
            :aria-busy="reportGenerating"
            @click="handleGenerateReport"
          >
            <el-icon><Loading v-if="reportGenerating" class="report-action-icon--loading" /><RefreshRight v-else /></el-icon>
            {{ reportGenerating ? '重新生成中' : '重新生成' }}
          </button>
          <button
            v-else
            class="button button--primary report-action-button"
            type="button"
            :disabled="reportBusy"
            :aria-busy="reportGenerating"
            @click="handleGenerateReport"
          >
            <el-icon><Loading v-if="reportGenerating" class="report-action-icon--loading" /><DocumentAdd v-else /></el-icon>
            {{ reportGenerating ? '报告生成中' : '生成 PDF 报告' }}
          </button>
          <RouterLink class="button button--secondary" :to="{ name: 'detect' }">再次检测</RouterLink>
        </template>
      </PageHeader>

      <el-alert
        v-if="reportError"
        class="report-error-alert"
        :title="reportError"
        type="error"
        show-icon
        :closable="false"
        role="alert"
      />

      <section class="result-hero surface-card" :class="riskHeroClass">
        <div class="result-hero__main">
          <p class="result-hero__eyebrow">综合可信度评分</p>
          <div class="result-score">
            <strong>{{ formattedFinalScore }}</strong>
            <span v-if="formattedFinalScore !== '--'">分</span>
          </div>
          <RiskLevelTag :level="riskLevel" :score="finalScore" size="large" />
          <p v-if="normalizedRiskKey === 'high'" class="result-risk-warning">
            当前结果显示高风险，请勿转发未经证实的信息，并优先核查官方通报或权威媒体来源。
          </p>
          <p class="result-judgement">{{ judgementResult }}</p>
        </div>

        <div class="result-hero__side">
          <div
            class="score-ring"
            :class="{ 'score-ring--empty': !hasFinalScore }"
            :style="{ '--score-percent': scorePercent }"
            aria-label="综合评分可视化"
          >
            <div>
              <strong>{{ formattedFinalScore }}</strong>
              <span>{{ hasFinalScore ? '/ 100' : '未知' }}</span>
            </div>
          </div>
          <p>{{ riskHint }}</p>
        </div>
      </section>

      <section class="score-grid" aria-label="三项评分">
        <ScoreCard title="证据质量" :score="eqScore" :subtitle="qualityState.cardSubtitle" :show-unit="eqScore !== null" tone="primary" />
        <ScoreCard title="大模型判断" :score="llmScore" subtitle="基于 DeepSeek 分析结果" tone="neutral" />
        <ScoreCard title="来源/规则评分" :score="ruleScore" subtitle="基于风险规则和来源特征" :tone="ruleTone" />
      </section>

      <section
        v-if="qualityState.status !== 'ok'"
        class="quality-status surface-card"
        :class="`quality-status--${qualityState.status}`"
        role="status"
      >
        <div>
          <strong>{{ qualityState.title }}</strong>
          <p>{{ qualityState.description }}</p>
        </div>
        <button
          v-if="qualityState.canRetry"
          class="button button--primary"
          type="button"
          :disabled="qualityReevaluating"
          :aria-busy="qualityReevaluating"
          @click="handleQualityReevaluation"
        >
          <el-icon v-if="qualityReevaluating"><Loading class="report-action-icon--loading" /></el-icon>
          {{ qualityReevaluating ? '重新评估中…' : '重新评估证据质量' }}
        </button>
      </section>

      <ResultSection
        v-if="evidenceQuality"
        title="证据质量评估"
        description="LLM 对有效证据覆盖度（能否覆盖新闻核心主张）和一致性（证据间是否互相印证）的详细评价。"
      >
        <div class="eq-panel">
          <div class="eq-row">
            <span class="eq-label">覆盖度</span>
            <div class="eq-bar"><i :style="{ width: (eqCoverage ?? 0) + '%' }" /></div>
            <strong>{{ eqCoverage ?? '--' }} 分</strong>
          </div>
          <div class="eq-row">
            <span class="eq-label">一致性</span>
            <div class="eq-bar"><i :style="{ width: (eqConsistency ?? 0) + '%' }" /></div>
            <strong>{{ eqConsistency ?? '--' }} 分</strong>
          </div>
          <p v-if="eqAssessment" class="eq-assessment">{{ eqAssessment }}</p>
        </div>
      </ResultSection>

      <section class="result-two-column">
        <ResultSection title="判断理由" description="系统结合证据检索、模型分析和规则评分生成。">
          <p class="result-text">{{ reasonText }}</p>
        </ResultSection>

        <ResultSection title="辟谣建议" tone="info" description="用于辅助下一步核查和传播判断。">
          <p class="result-text">{{ suggestionText }}</p>
        </ResultSection>
      </section>

      <section class="result-two-column">
        <ResultSection title="风险点" description="需要重点关注的可信度风险。">
          <EmptyState
            v-if="!riskPoints.length"
            title="暂无风险点"
            description="后端未返回明确风险点。"
          />
          <ul v-else class="risk-point-list">
            <li v-for="(point, index) in riskPoints" :key="`${point}-${index}`">
              <span>{{ index + 1 }}</span>
              <p>{{ point }}</p>
            </li>
          </ul>
        </ResultSection>

        <ResultSection title="关键词" description="模型或规则提取的核心关注词。">
          <EmptyState
            v-if="!keywords.length"
            title="暂无关键词"
            description="后端未返回关键词。"
          />
          <div v-else class="keyword-list">
            <span v-for="keyword in keywords" :key="keyword">{{ keyword }}</span>
          </div>
        </ResultSection>
      </section>

      <ResultSection title="有效证据" :description="evidenceDescription">
        <div
          v-if="arbitrationUnavailable"
          class="web-search-notice"
        >
          ⚠️ 本次检测的<strong>证据仲裁暂不可用</strong>，以下证据尚未经过 LLM 相关性排序，请结合判断理由和风险点评级综合评估。
        </div>
        <div
          v-if="webSearchTriggered"
          class="web-search-notice"
        >
          🌐 本次检测启用了<strong>联网搜索</strong>，从网络检索到
          <strong>{{ webSearchSources }}</strong> 条补充证据（标记为橙色"网络检索"标签）。
        </div>
        <EvidenceList :items="evidenceList" />
      </ResultSection>

      <ResultSection
        v-if="excludedEvidence.length"
        title="排除证据"
        description="以下候选证据经 LLM 判定与本次新闻核心事实无关，未参与评分和排序。"
      >
        <div class="excluded-evidence-list">
          <article v-for="item in excludedEvidence" :key="item.candidate_id || item.title" class="excluded-evidence-item">
            <div class="excluded-evidence-item__main">
              <h4>{{ item.title || '未命名证据' }}</h4>
              <p v-if="item.rejection_reason" class="excluded-evidence-item__reason">
                排除原因：{{ item.rejection_reason }}
              </p>
              <div class="evidence-item__meta">
                <span v-if="item.source_type" class="evidence-item__source-badge" :class="{ 'evidence-item__source-badge--web': item.source_type === 'web_search' }">
                  {{ item.source_label || (item.source_type === 'web_search' ? '🌐 网络检索' : '📚 知识库') }}
                </span>
                <span>{{ item.source_name || '未知来源' }}</span>
              </div>
            </div>
          </article>
        </div>
      </ResultSection>

      <ResultSection title="相似新闻" :description="similarNewsDescription">
        <div v-if="similarNewsIsFallback" class="web-search-notice">
          ⚠️ 证据仲裁暂不可用，以下为检索阶段召回的候选相似新闻，尚未经过 LLM 风险评级。
        </div>
        <EmptyState
          v-if="!similarNews.length"
          title="暂无相似新闻"
          description="后端未返回相似新闻。"
        />
        <div v-else class="similar-news-list">
          <article v-for="(item, index) in similarNews" :key="item.candidate_id || item.title || index" class="similar-news-item">
            <div>
              <h3>{{ item.title || '未命名新闻' }}</h3>
              <p v-if="item.arbitration_reason">{{ item.arbitration_reason }}</p>
              <div class="similar-news-item__meta">
                <span v-if="item.source_name">{{ item.source_name }}</span>
                <span v-if="item.publish_time">{{ formatDateTime(item.publish_time) }}</span>
                <span v-if="item.relevance_score != null">相关性 {{ item.relevance_score }}</span>
                <span v-if="item.quality_score != null">质量 {{ item.quality_score }}</span>
              </div>
            </div>
            <RiskLevelTag
              :level="similarNewsRiskLevel(item)"
              :score="item.final_score ?? item.score"
            />
          </article>
        </div>
      </ResultSection>

      <ResultSection title="AI 分析过程" description="展示轻量 Agent 工具链的关键步骤。">
        <AgentSteps :steps="agentSteps" />
      </ResultSection>

      <section class="result-disclaimer">
        <strong>免责声明</strong>
        <p>{{ disclaimerText }}</p>
      </section>
    </template>

    <section v-else class="surface-card surface-card--padded">
      <el-alert
        :title="errorMessage || '未找到检测结果'"
        type="error"
        show-icon
        :closable="false"
      />
      <div class="result-error-actions">
        <RouterLink class="button button--primary" :to="{ name: 'detect' }">返回检测页</RouterLink>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus/es/components/message/index.mjs'
import { DocumentAdd, Download, Loading, RefreshRight } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { getDetectionDetail, reEvaluateDetection } from '@/api/detect'
import { downloadReport, generateReport } from '@/api/report'
import AgentSteps from '@/components/AgentSteps.vue'
import EmptyState from '@/components/EmptyState.vue'
import EvidenceList from '@/components/EvidenceList.vue'
import LoadingState from '@/components/LoadingState.vue'
import PageHeader from '@/components/PageHeader.vue'
import ResultSection from '@/components/ResultSection.vue'
import RiskLevelTag from '@/components/RiskLevelTag.vue'
import ScoreCard from '@/components/ScoreCard.vue'
import { useUserStore } from '@/stores/user'
import {
  readDetectionResultCache,
  writeDetectionResultCache
} from '@/utils/detectionResultCache'
import { formatDateTime, formatScore, isValidScore, scoreToPercent as normalizeScorePercent } from '@/utils/format'
import { getEvidenceQualityState } from '@/utils/evidenceQualityState'
import { unwrapApiResponse } from '@/utils/response'

const props = defineProps({
  id: {
    type: String,
    required: true
  }
})

const loading = ref(true)
const errorMessage = ref('')
const resultData = ref(null)
const reportGenerating = ref(false)
const reportDownloading = ref(false)
const reportError = ref('')
const qualityReevaluating = ref(false)
const router = useRouter()
const userStore = useUserStore()

const defaultDisclaimer =
  '本系统为新闻可信度辅助评估工具，检测结果仅供参考，不能替代人工事实核查、官方通报或权威媒体结论。'

const resultResponseErrorMessage = '获取检测结果失败'

function parseStoredResult(id) {
  return readDetectionResultCache(id, {
    unwrap: (value) => unwrapApiResponse(value, resultResponseErrorMessage)
  })
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

  if (Array.isArray(value?.rows)) {
    return value.rows.filter(Boolean)
  }

  if (Array.isArray(value?.data)) {
    return value.data.filter(Boolean)
  }

  if (typeof value === 'string') {
    return value
      .split(/[\n,，;；]/)
      .map((item) => item.trim())
      .filter(Boolean)
  }

  return []
}

function pick(...values) {
  return values.find((value) => value !== undefined && value !== null && value !== '') ?? ''
}

function getErrorMessage(error) {
  return (
    error?.response?.data?.message ||
    error?.response?.data?.detail ||
    error?.message ||
    '获取检测结果失败，请稍后重试'
  )
}

async function getReportErrorMessage(error, fallback) {
  const responseData = error?.response?.data

  if (typeof Blob !== 'undefined' && responseData instanceof Blob) {
    try {
      const text = await responseData.text()
      const payload = JSON.parse(text)
      return normalizeApiError(pickReportErrorDetail(payload), fallback)
    } catch {
      return fallback
    }
  }

  if (typeof responseData === 'string') {
    return normalizeApiError(responseData, fallback)
  }

  if (responseData && typeof responseData === 'object' && !Array.isArray(responseData)) {
    return normalizeApiError(pickReportErrorDetail(responseData), fallback)
  }

  return fallback
}

function pickReportErrorDetail(payload) {
  if (typeof payload === 'string') {
    return payload
  }

  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return ''
  }

  return [payload.message, payload.detail, payload.msg]
    .map((detail) => normalizeApiError(detail, ''))
    .find(Boolean) ?? ''
}

function normalizeApiError(detail, fallback) {
  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => item?.msg || item?.message || String(item || ''))
      .filter(Boolean)

    return messages.join('；') || fallback
  }

  return fallback
}

function ensureReportAccess() {
  if (userStore.isLoggedIn) {
    return true
  }

  ElMessage.warning('登录后可生成和下载 PDF 报告')
  router.push({
    name: 'login',
    query: { redirect: `/result/${props.id}` }
  })
  return false
}

function updateCachedReport(downloadUrl, id) {
  resultData.value = {
    ...resultData.value,
    report_url: downloadUrl,
    report_id: id
  }

  writeDetectionResultCache(props.id, resultData.value)
}

async function handleGenerateReport() {
  if (!ensureReportAccess() || reportBusy.value) {
    return
  }

  reportGenerating.value = true
  reportError.value = ''
  const isRegeneration = hasGeneratedReport.value

  try {
    const response = await generateReport(props.id)
    const report = unwrapApiResponse(response, resultResponseErrorMessage)
    const downloadUrl = pick(report?.download_url, report?.report_url)
    const id = pick(report?.id, extractReportId(downloadUrl))

    if (!downloadUrl || !id) {
      throw new Error('报告已生成，但后端未返回完整下载信息')
    }

    updateCachedReport(downloadUrl, id)
    ElMessage.success(isRegeneration ? 'PDF 报告已重新生成' : 'PDF 报告生成成功')
  } catch (error) {
    reportError.value = await getReportErrorMessage(error, 'PDF 报告生成失败，请稍后重试')
    ElMessage.error(reportError.value)
  } finally {
    reportGenerating.value = false
  }
}

async function handleDownloadReport() {
  if (!ensureReportAccess() || reportBusy.value) {
    return
  }

  if (!reportId.value) {
    reportError.value = '报告下载信息不完整，请重新生成报告'
    return
  }

  reportDownloading.value = true
  reportError.value = ''

  try {
    const payload = await downloadReport(reportId.value)
    const pdfBlob = payload instanceof Blob
      ? payload
      : new Blob([payload], { type: 'application/pdf' })
    const objectUrl = URL.createObjectURL(pdfBlob)
    const link = document.createElement('a')

    link.href = objectUrl
    link.download = `news-credibility-report-${reportId.value}.pdf`
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
    ElMessage.success('PDF 报告下载已开始')
  } catch (error) {
    reportError.value = await getReportErrorMessage(error, 'PDF 报告下载失败，请稍后重试')
    ElMessage.error(reportError.value)
  } finally {
    reportDownloading.value = false
  }
}

async function handleQualityReevaluation() {
  if (qualityReevaluating.value) return

  if (!userStore.isLoggedIn) {
    ElMessage.warning('登录后可重新评估证据质量')
    router.push({
      name: 'login',
      query: { redirect: `/result/${props.id}` }
    })
    return
  }

  qualityReevaluating.value = true
  try {
    const response = await reEvaluateDetection(props.id)
    const result = unwrapApiResponse(response, '重新评估失败')
    const newId = result?.detection_id || result?.id
    if (!newId) throw new Error('重新评估完成，但后端未返回新检测编号')

    writeDetectionResultCache(newId, result)
    ElMessage.success('证据质量已重新评估')
    await router.replace({ name: 'result', params: { id: String(newId) } })
  } catch (error) {
    ElMessage.error(getErrorMessage(error).replace('获取检测结果失败', '重新评估失败'))
  } finally {
    qualityReevaluating.value = false
  }
}

async function loadResult(id) {
  errorMessage.value = ''
  reportError.value = ''
  resultData.value = null

  const cached = parseStoredResult(id)
  if (cached) {
    resultData.value = cached
    loading.value = false
    return
  }

  loading.value = true

  try {
    const response = await getDetectionDetail(id)
    resultData.value = unwrapApiResponse(response, resultResponseErrorMessage)
  } catch (error) {
    errorMessage.value = getErrorMessage(error)
  } finally {
    loading.value = false
  }
}

const newsTitle = computed(() =>
  pick(
    resultData.value?.input_title,
    resultData.value?.news_title,
    resultData.value?.title,
    resultData.value?.headline,
    `检测结果 #${props.id}`
  )
)

const displayTime = computed(() =>
  formatDateTime(
    pick(
      resultData.value?.created_at,
      resultData.value?.detected_at,
      resultData.value?.detection_time,
      resultData.value?.create_time,
      resultData.value?.updated_at
    )
  )
)
const displayPublishTime = computed(() =>
  formatDateTime(
    pick(
      resultData.value?.publish_time,
      resultData.value?.published_at,
      resultData.value?.publishTime
    )
  )
)
const resultTimeDescription = computed(() =>
  `检测时间：${displayTime.value} · 新闻发布时间：${displayPublishTime.value}`
)

const finalScore = computed(() =>
  pick(resultData.value?.final_score, resultData.value?.credibility_score, resultData.value?.score)
)
const formattedFinalScore = computed(() => formatScore(finalScore.value))
const hasFinalScore = computed(() => isValidScore(finalScore.value))
const evidenceScore = computed(() => pick(resultData.value?.evidence_score, resultData.value?.retrieval_score))

const qualityState = computed(() => getEvidenceQualityState(resultData.value || {}))
const arbitrationUnavailable = computed(() =>
  ['unavailable', 'provider_error', 'retry_exhausted', 'invalid_response'].includes(
    String(resultData.value?.arbitration_status || '')
  )
)

const evidenceQuality = computed(() => {
  if (qualityState.value.status !== 'ok') return null
  const eq = resultData.value?.evidence_quality || resultData.value?.evidenceQuality
  if (!eq || (eq.coverage === null && eq.consistency === null && eq.score === null)) return null
  return eq
})
const eqScore = computed(() => qualityState.value.score)
const eqCoverage = computed(() => evidenceQuality.value?.coverage ?? null)
const eqConsistency = computed(() => evidenceQuality.value?.consistency ?? null)
const eqAssessment = computed(() => evidenceQuality.value?.assessment ?? '')
const llmScore = computed(() => pick(resultData.value?.llm_score, resultData.value?.model_score))
const ruleScore = computed(() => pick(resultData.value?.rule_score, resultData.value?.source_score))
const riskLevel = computed(() => pick(resultData.value?.risk_level, resultData.value?.riskLevel))
const judgementResult = computed(() =>
  pick(resultData.value?.judgement_result, resultData.value?.judgment_result, resultData.value?.conclusion, '暂无判断结论')
)
const reasonText = computed(() => pick(resultData.value?.reason, resultData.value?.analysis_reason, '后端未返回判断理由。'))
const suggestionText = computed(() => pick(resultData.value?.suggestion, resultData.value?.advice, '后端未返回辟谣建议。'))
const disclaimerText = computed(() => pick(resultData.value?.disclaimer, defaultDisclaimer))
const reportUrl = computed(() => pick(resultData.value?.report_url, resultData.value?.pdf_url, resultData.value?.reportUrl))
const reportId = computed(() =>
  pick(
    resultData.value?.report_id,
    resultData.value?.reportId,
    extractReportId(reportUrl.value)
  )
)
const hasGeneratedReport = computed(() => Boolean(reportUrl.value && reportId.value))
const reportBusy = computed(() => reportGenerating.value || reportDownloading.value)

const riskPoints = computed(() => getArray(resultData.value?.risk_points || resultData.value?.riskPoints))
const keywords = computed(() => getArray(resultData.value?.keywords || resultData.value?.keyword_list))
const candidateEvidenceList = computed(() =>
  getArray(resultData.value?.candidate_evidence_list || resultData.value?.candidateEvidenceList)
)
const evidenceList = computed(() => {
  const effective = getArray(
    resultData.value?.evidence_list || resultData.value?.evidenceList || resultData.value?.evidences || resultData.value?.evidence_matches
  )
  if (effective.length || !arbitrationUnavailable.value) return effective
  return candidateEvidenceList.value
})
const excludedEvidence = computed(() =>
  getArray(resultData.value?.excluded_evidence || resultData.value?.excludedEvidence)
)
const returnedSimilarNews = computed(() =>
  getArray(resultData.value?.similar_news || resultData.value?.similarNews || resultData.value?.similar_list)
)
const fallbackSimilarNews = computed(() => {
  if (!arbitrationUnavailable.value) return []
  const knowledgeCandidates = candidateEvidenceList.value.filter(
    (item) => (item.source_type || item.sourceType) === 'knowledge_base'
  )
  return knowledgeCandidates.length ? knowledgeCandidates : candidateEvidenceList.value
})
const similarNews = computed(() =>
  returnedSimilarNews.value.length ? returnedSimilarNews.value : fallbackSimilarNews.value
)
const similarNewsIsFallback = computed(() =>
  !returnedSimilarNews.value.length && fallbackSimilarNews.value.length > 0
)
const similarNewsDescription = computed(() =>
  similarNewsIsFallback.value
    ? `检索阶段召回的候选相似新闻，共 ${similarNews.value.length} 条。`
    : '经 LLM 证据仲裁后，与当前检测内容相近的新闻或案例。'
)
const agentSteps = computed(() =>
  getArray(resultData.value?.agent_steps || resultData.value?.agentSteps || resultData.value?.analysis_steps)
)
const webSearchTriggered = computed(() =>
  Boolean(resultData.value?.web_search_triggered || resultData.value?.webSearchTriggered)
)
const webSearchSources = computed(() =>
  Number(resultData.value?.web_search_sources || resultData.value?.webSearchSources || 0)
)
const evidenceDescription = computed(() => {
  if (arbitrationUnavailable.value) {
    return `证据仲裁暂不可用，当前展示检索阶段召回的全部候选证据，共 ${evidenceList.value.length} 条。`
  }
  const base = webSearchTriggered.value
    ? `经 LLM 证据仲裁后的有效证据，来自知识库（📚）和网络检索（🌐），共 ${evidenceList.value.length} 条。`
    : `经 LLM 证据仲裁后的有效证据，共 ${evidenceList.value.length} 条。`
  return base
})

function similarNewsRiskLevel(item) {
  const level = item.risk_level ?? item.riskLevel
  if (level) return level
  // web evidence without risk level → auxiliary
  if ((item.source_type || item.sourceType) === 'web_search') return '辅助证据'
  // knowledge_base without risk level → unrated
  if ((item.source_type || item.sourceType) === 'knowledge_base') return '未评级案例'
  return '未返回风险等级'
}

const scorePercent = computed(() => {
  const value = normalizeScorePercent(finalScore.value)

  if (value === null) {
    return '0%'
  }

  return `${value}%`
})

const normalizedRiskKey = computed(() => {
  const level = String(riskLevel.value || '').toLowerCase()
  const normalized = level.replace(/[\s-]+/g, '_')

  if (!level) {
    return 'unknown'
  }

  if (
    level.includes('高风险') ||
    normalized === 'high' ||
    normalized === 'high_risk' ||
    normalized === 'high_risk_rumor' ||
    normalized.startsWith('high_risk_')
  ) {
    return 'high'
  }

  if (level.includes('可信') || level.includes('trusted') || level.includes('credible')) {
    return 'trusted'
  }

  if (level.includes('存疑') || level.includes('suspicious') || level.includes('uncertain')) {
    return 'suspicious'
  }

  if (
    level.includes('疑似') ||
    normalized === 'suspected_rumor' ||
    normalized.includes('suspected_rumor') ||
    normalized === 'rumor' ||
    normalized === 'rumour' ||
    normalized.endsWith('_rumor') ||
    normalized.endsWith('_rumour')
  ) {
    return 'rumor'
  }

  return 'unknown'
})

const riskHeroClass = computed(() => `result-hero--${normalizedRiskKey.value}`)
const ruleTone = computed(() => {
  if (normalizedRiskKey.value === 'high') {
    return 'danger'
  }

  if (normalizedRiskKey.value === 'rumor') {
    return 'warning'
  }

  if (normalizedRiskKey.value === 'unknown') {
    return 'neutral'
  }

  return 'primary'
})
const riskHint = computed(() => {
  const hints = {
    trusted: '当前结果倾向可信，但仍建议保留核查意识。',
    suspicious: '当前结果存在不确定因素，建议继续核查权威来源。',
    rumor: '当前结果呈现明显风险，应谨慎传播并进一步核实。',
    high: '当前结果风险较高，建议不要转发未经证实的信息。',
    unknown: '后端未返回完整风险等级或分数，请结合证据和判断理由继续核查。'
  }

  return hints[normalizedRiskKey.value]
})

function extractReportId(url) {
  const match = String(url || '').match(/\/report\/download\/(\d+)(?:[/?#]|$)/)
  return match?.[1] || ''
}

onMounted(() => {
  loadResult(props.id)
})

watch(
  () => props.id,
  (id) => {
    loadResult(id)
  }
)
</script>

<style scoped>
.result-page {
  --hero-risk-color: var(--color-primary);
  --hero-risk-bg: var(--color-primary-soft);
}

.report-action-button {
  min-width: 148px;
}

.report-action-button .el-icon {
  width: 17px;
  height: 17px;
  font-size: 17px;
}

.report-action-icon--loading {
  animation: report-action-spin 900ms linear infinite;
}

.report-error-alert {
  border: 1px solid rgba(220, 38, 38, 0.22);
  box-shadow: var(--shadow-card);
}

.quality-status {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 20px 24px;
  border: 1px solid rgba(217, 119, 6, 0.24);
  background: #fffaf0;
}

.quality-status--no_evidence {
  border-color: var(--color-border);
  background: var(--color-surface);
}

.quality-status strong {
  color: var(--color-text-primary);
  font-size: 16px;
}

.quality-status p {
  margin: 6px 0 0;
  color: var(--color-text-secondary);
  line-height: 1.7;
}

.quality-status .button {
  flex: 0 0 auto;
}

@media (max-width: 720px) {
  .quality-status {
    align-items: flex-start;
    flex-direction: column;
  }
}

@keyframes report-action-spin {
  to {
    transform: rotate(360deg);
  }
}

.result-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: var(--space-8);
  align-items: center;
  min-height: 310px;
  padding: var(--space-8);
  border-color: color-mix(in srgb, var(--hero-risk-color) 28%, var(--color-border-soft));
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.96), var(--hero-risk-bg)),
    var(--color-bg-panel);
}

.result-hero--trusted {
  --hero-risk-color: var(--risk-trusted);
  --hero-risk-bg: #f0fdf4;
}

.result-hero--suspicious {
  --hero-risk-color: var(--risk-suspicious);
  --hero-risk-bg: #fffbeb;
}

.result-hero--rumor {
  --hero-risk-color: var(--risk-rumor);
  --hero-risk-bg: #fff7ed;
}

.result-hero--high {
  --hero-risk-color: var(--risk-high);
  --hero-risk-bg: #fff1f2;
}

.result-hero--unknown {
  --hero-risk-color: var(--color-text-muted);
  --hero-risk-bg: var(--color-bg-subtle);
}

.result-hero__main {
  display: grid;
  gap: var(--space-4);
}

.result-hero__eyebrow {
  margin: 0;
  color: var(--color-primary);
  font-size: 13px;
  font-weight: 800;
}

.result-score {
  display: flex;
  align-items: baseline;
  gap: 8px;
  color: var(--hero-risk-color);
}

.result-score strong {
  font-size: 76px;
  line-height: 0.95;
}

.result-score span {
  font-size: 18px;
  font-weight: 800;
}

.result-judgement {
  max-width: 720px;
  margin: 0;
  color: var(--color-text);
  font-size: 18px;
  font-weight: 700;
  line-height: 1.7;
}

.result-risk-warning {
  max-width: 760px;
  margin: 0;
  padding: var(--space-4);
  border: 1px solid rgba(220, 38, 38, 0.28);
  border-left: 4px solid var(--risk-high);
  border-radius: var(--radius-md);
  color: #991b1b;
  background: var(--risk-high-bg);
  font-weight: 700;
  line-height: 1.7;
}

.result-hero__side {
  display: grid;
  justify-items: center;
  gap: var(--space-4);
  text-align: center;
}

.result-hero__side p {
  margin: 0;
  color: var(--color-text-muted);
  line-height: 1.7;
}

.score-ring {
  display: grid;
  width: 190px;
  height: 190px;
  place-items: center;
  border-radius: 50%;
  background:
    radial-gradient(circle at center, #ffffff 0 58%, transparent 59%),
    conic-gradient(var(--hero-risk-color) var(--score-percent), #e6eef6 0);
}

.score-ring--empty {
  background:
    radial-gradient(circle at center, #ffffff 0 58%, transparent 59%),
    conic-gradient(var(--color-border) 0%, #e6eef6 0);
}

.score-ring div {
  display: grid;
  justify-items: center;
  gap: 3px;
}

.score-ring strong {
  color: var(--color-text-strong);
  font-size: 32px;
  line-height: 1;
}

.score-ring span {
  color: var(--color-text-muted);
  font-size: 13px;
  font-weight: 700;
}

.score-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-4);
}

.result-two-column {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-6);
}

.result-text {
  margin: 0;
  color: var(--color-text);
  line-height: 1.85;
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
  align-items: flex-start;
  padding: var(--space-3);
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-md);
  background: var(--color-bg-subtle);
}

.risk-point-list span {
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  border-radius: var(--radius-sm);
  color: #ffffff;
  background: var(--color-orange);
  font-size: 12px;
  font-weight: 800;
}

.risk-point-list p {
  margin: 3px 0 0;
  color: var(--color-text);
  line-height: 1.65;
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
  padding: 0 11px;
  border: 1px solid #bae6fd;
  border-radius: 999px;
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
  font-size: 13px;
  font-weight: 700;
}

.similar-news-list {
  display: grid;
  gap: var(--space-3);
}

.similar-news-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--space-4);
  align-items: center;
  padding: var(--space-4);
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-md);
  background: var(--color-bg-panel);
}

.similar-news-item h3 {
  margin: 0;
  color: var(--color-text-strong);
  font-size: 15px;
  line-height: 1.45;
}

.similar-news-item p {
  display: -webkit-box;
  margin: 6px 0 0;
  overflow: hidden;
  color: var(--color-text-muted);
  font-size: 13px;
  line-height: 1.6;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.similar-news-item__meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: 6px;
  color: var(--color-text-muted);
  font-size: 12px;
}

/* -- excluded evidence -- */
.excluded-evidence-list {
  display: grid;
  gap: var(--space-3);
}

.excluded-evidence-item {
  padding: var(--space-3) var(--space-4);
  border: 1px solid #e5e7eb;
  border-radius: var(--radius-md);
  background: #f9fafb;
}

.excluded-evidence-item__main h4 {
  margin: 0;
  color: var(--color-text);
  font-size: 14px;
  font-weight: 600;
}

.excluded-evidence-item__reason {
  margin: 4px 0 0;
  color: #6b7280;
  font-size: 12px;
  line-height: 1.5;
}

/* -- evidence quality panel -- */
.eq-panel {
  display: grid;
  gap: var(--space-4);
  padding: var(--space-4);
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-md);
  background: var(--color-bg-subtle);
}

.eq-row {
  display: grid;
  grid-template-columns: 60px 1fr 64px;
  gap: var(--space-3);
  align-items: center;
}

.eq-label {
  font-size: 13px;
  font-weight: 700;
  color: var(--color-text-muted);
}

.eq-bar {
  height: 10px;
  border-radius: 999px;
  background: #e6eef6;
  overflow: hidden;
}

.eq-bar i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--color-primary);
  transition: width 0.6s ease;
}

.eq-assessment {
  margin: 0;
  color: var(--color-text-muted);
  font-size: 13px;
  line-height: 1.7;
}

.result-disclaimer {
  display: grid;
  gap: var(--space-2);
  padding: var(--space-5);
  border: 1px solid #fde68a;
  border-radius: var(--radius-lg);
  color: #92400e;
  background: #fffbeb;
}

.result-disclaimer strong {
  color: #78350f;
}

.result-disclaimer p {
  margin: 0;
  line-height: 1.75;
}

.web-search-notice {
  margin-bottom: var(--space-4);
  padding: var(--space-3) var(--space-4);
  border: 1px solid #fde68a;
  border-radius: var(--radius-md);
  color: #92400e;
  background: #fffbeb;
  font-size: 13px;
  line-height: 1.7;
}

.web-search-notice strong {
  color: #78350f;
}

.result-error-actions {
  display: flex;
  gap: var(--space-3);
  margin-top: var(--space-5);
}

@media (max-width: 980px) {
  .result-hero,
  .result-two-column {
    grid-template-columns: 1fr;
  }

  .score-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .report-action-button {
    width: 100%;
  }

  .result-hero {
    padding: var(--space-5);
  }

  .result-score strong {
    font-size: 58px;
  }

  .score-ring {
    width: 156px;
    height: 156px;
  }

  .similar-news-item {
    grid-template-columns: 1fr;
  }
}
</style>
