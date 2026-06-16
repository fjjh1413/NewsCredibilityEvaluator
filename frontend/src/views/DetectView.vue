<template>
  <div class="page-stack">
    <PageHeader
      eyebrow="新闻可信度评估"
      title="新闻检测"
      description="输入新闻标题和正文，系统将通过证据检索、DeepSeek 分析、规则评分和综合评估生成可信度结果。"
    >
      <template #actions>
        <RouterLink class="button button--secondary" :to="{ name: 'highRisk' }">高风险新闻</RouterLink>
        <RouterLink class="button button--secondary" :to="{ name: 'history' }">历史记录</RouterLink>
      </template>
    </PageHeader>

    <section class="detect-layout">
      <section class="detect-card surface-card" aria-labelledby="detect-form-title">
        <div class="detect-card__header">
          <div>
            <p>AI 风控检测入口</p>
            <h2 id="detect-form-title">提交待核查新闻</h2>
          </div>
          <el-button class="detect-example" :icon="DocumentAdd" @click="fillExample">
            填充示例新闻
          </el-button>
        </div>

        <el-alert
          v-if="errorMessage"
          class="detect-alert"
          :title="errorMessage"
          type="error"
          show-icon
          :closable="false"
        />

        <el-form
          ref="formRef"
          class="detect-form"
          :model="form"
          :rules="rules"
          label-position="top"
          @submit.prevent="handleSubmit"
        >
          <el-form-item label="新闻标题" prop="title">
            <el-input
              v-model.trim="form.title"
              size="large"
              maxlength="255"
              show-word-limit
              placeholder="请输入需要检测的新闻标题"
            />
          </el-form-item>

          <div class="detect-form__row">
            <el-form-item label="新闻类别" prop="category">
              <el-select v-model="form.category" size="large" clearable placeholder="可选">
                <el-option v-for="category in categories" :key="category" :label="category" :value="category" />
              </el-select>
            </el-form-item>

            <el-form-item label="来源名称" prop="source_name">
              <el-input
                v-model.trim="form.source_name"
                size="large"
                maxlength="40"
                placeholder="可选，如媒体名称或平台"
              />
            </el-form-item>
          </div>

          <el-form-item label="新闻正文" prop="content">
            <el-input
              v-model.trim="form.content"
              type="textarea"
              :rows="11"
              maxlength="5000"
              show-word-limit
              resize="vertical"
              placeholder="请输入新闻正文、转述内容或需要核查的主要信息"
            />
          </el-form-item>

          <el-form-item class="detect-web-search-item">
            <div class="detect-web-search-toggle">
              <div class="detect-web-search-label">
                <span>🌐 启用联网搜索</span>
                <el-switch v-model="form.enable_web_search" :disabled="submitting" />
              </div>
              <p class="detect-web-search-hint">
                开启后，当本地知识库证据不足时，自动通过搜索引擎检索相关新闻作为补充证据，提升检测准确性。
              </p>
            </div>
          </el-form-item>

          <div class="detect-actions">
            <el-button class="detect-submit" type="primary" native-type="submit" :loading="submitting">
              {{ submitting ? '检测中请耐心等待' : '提交可信度检测' }}
            </el-button>
            <el-button class="detect-reset" @click="resetForm">清空输入</el-button>
            <p v-if="submitting" class="detect-loading-hint">长文本可能需要更长时间，启用联网搜索时检测时间会略有延长。</p>
          </div>
        </el-form>
      </section>

      <aside class="detect-side">
        <section class="surface-card detect-process">
          <h2>检测流程</h2>
          <ol>
            <li v-for="(step, index) in processSteps" :key="step.title">
              <span>{{ index + 1 }}</span>
              <div>
                <strong>{{ step.title }}</strong>
                <small>{{ step.description }}</small>
              </div>
            </li>
          </ol>
        </section>

        <section class="surface-card detect-note">
          <h2>检测说明</h2>
          <p>
            本页面支持游客和登录用户直接检测。检测成功后，系统会跳转到结果页；游客结果会临时保存在当前浏览器会话中。
          </p>
          <p class="detect-disclaimer">{{ disclaimer }}</p>
        </section>
      </aside>
    </section>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { DocumentAdd } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus/es/components/message/index.mjs'
import { submitNewsDetection } from '@/api/detect'
import PageHeader from '@/components/PageHeader.vue'
import { writeDetectionResultCache } from '@/utils/detectionResultCache'
import { unwrapApiResponse } from '@/utils/response'

const router = useRouter()
const formRef = ref(null)
const submitting = ref(false)
const errorMessage = ref('')

const disclaimer =
  '本系统为新闻可信度辅助评估工具，检测结果仅供参考，不能替代人工事实核查、官方通报或权威媒体结论。'

const categories = ['社会', '财经', '科技', '健康', '教育', '国际', '娱乐', '体育', '其他']

const processSteps = [
  { title: '文本输入', description: '提交标题、正文和可选类别。' },
  { title: '证据检索', description: '从知识库中召回相似新闻与核查材料。' },
  { title: 'DeepSeek 分析', description: '结合 RAG 证据生成可信度判断理由。' },
  { title: '规则评分', description: '检查来源、夸张表达和风险特征。' },
  { title: '综合评估', description: '返回最终分数、风险等级和建议。' }
]

const form = reactive({
  title: '',
  content: '',
  category: '',
  source_name: '',
  enable_web_search: true
})

const rules = {
  title: [
    { required: true, message: '请输入新闻标题', trigger: 'blur' },
    { min: 4, max: 255, message: '标题长度需在 4 到 255 个字符之间', trigger: 'blur' }
  ],
  content: [
    { required: true, message: '请输入新闻正文', trigger: 'blur' },
    { min: 20, message: '正文至少需要 20 个字符，便于系统检索和分析', trigger: 'blur' }
  ]
}

const exampleNews = {
  title: '网传某地出现异常天气并引发大规模抢购，官方回应正在核查',
  category: '社会',
  source_name: '网络来源',
  content:
    '近日，社交平台流传一则消息称某地将出现罕见异常天气，并建议居民立即囤积生活物资。相关内容在多个群组中快速传播，但消息中未注明明确发布机构，也未附权威气象部门通报。当地有关部门表示，已关注到网传信息，正在核查相关情况，并提醒公众以官方渠道发布的信息为准，不要盲目转发未经证实的内容。'
}

function getDetectionId(data) {
  return data?.detection_id ?? data?.id ?? data?.record_id ?? data?.result_id
}

function getErrorMessage(error) {
  return (
    error?.response?.data?.message ||
    error?.response?.data?.detail ||
    error?.message ||
    '检测失败，请稍后重试'
  )
}

function fillExample() {
  Object.assign(form, exampleNews)
  errorMessage.value = ''
}

function resetForm() {
  formRef.value?.resetFields()
  Object.assign(form, {
    title: '',
    content: '',
    category: '',
    source_name: '',
    enable_web_search: true
  })
  errorMessage.value = ''
}

async function handleSubmit() {
  if (!formRef.value) {
    return
  }

  errorMessage.value = ''

  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) {
    return
  }

  submitting.value = true

  try {
    const payload = {
      title: form.title,
      content: form.content,
      category: form.category || undefined,
      source_name: form.source_name || undefined,
      enable_web_search: form.enable_web_search
    }

    const response = await submitNewsDetection(payload)
    const data = unwrapApiResponse(response, '检测失败，请稍后重试')
    const detectionId = getDetectionId(data)

    if (!detectionId) {
      throw new Error('检测完成但响应中缺少 detection_id，无法进入结果页')
    }

    const cachedResult = {
      ...data,
      detection_id: detectionId,
      input_title: data.input_title || data.title || form.title,
      input_content: data.input_content || form.content,
      category: data.category || form.category,
      source_name: data.source_name || form.source_name
    }

    writeDetectionResultCache(detectionId, cachedResult)
    ElMessage.success('检测完成，正在打开结果页')
    await router.push({ name: 'result', params: { id: detectionId } })
  } catch (error) {
    errorMessage.value = getErrorMessage(error)
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.detect-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: var(--space-6);
  align-items: start;
}

.detect-card {
  display: grid;
  gap: var(--space-5);
  padding: var(--space-6);
}

.detect-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
}

.detect-card__header p {
  margin: 0 0 8px;
  color: var(--color-primary);
  font-size: 13px;
  font-weight: 800;
}

.detect-card__header h2,
.detect-process h2,
.detect-note h2 {
  margin: 0;
  color: var(--color-text-strong);
  font-size: 20px;
}

.detect-example {
  flex: 0 0 auto;
  border-radius: var(--radius-sm);
  font-weight: 700;
}

.detect-alert {
  border-radius: var(--radius-md);
}

.detect-form {
  display: grid;
  gap: var(--space-3);
}

.detect-form__row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
}

.detect-form :deep(.el-form-item__label) {
  color: var(--color-text-strong);
  font-weight: 700;
}

.detect-form :deep(.el-input__wrapper),
.detect-form :deep(.el-textarea__inner) {
  border-radius: var(--radius-sm);
  box-shadow: 0 0 0 1px var(--color-border) inset;
}

.detect-form :deep(.el-input__wrapper) {
  min-height: 44px;
}

.detect-form :deep(.el-input__wrapper.is-focus),
.detect-form :deep(.el-textarea__inner:focus) {
  box-shadow: 0 0 0 1px var(--color-primary) inset, var(--shadow-focus);
}

.detect-form :deep(.el-textarea__inner) {
  min-height: 240px !important;
  line-height: 1.7;
}

.detect-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  padding-top: var(--space-2);
}

.detect-submit {
  min-width: 180px;
  min-height: 44px;
  border-radius: var(--radius-sm);
  font-weight: 800;
}

.detect-reset {
  min-height: 44px;
  border-radius: var(--radius-sm);
  font-weight: 700;
}

.detect-web-search-item {
  margin-bottom: 0;
}

.detect-web-search-item :deep(.el-form-item__label) {
  display: none;
}

.detect-web-search-toggle {
  display: grid;
  gap: var(--space-2);
  padding: var(--space-4);
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-md);
  background: var(--color-bg-subtle);
}

.detect-web-search-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.detect-web-search-label span {
  color: var(--color-text-strong);
  font-weight: 700;
  font-size: 14px;
}

.detect-web-search-hint {
  margin: 0;
  color: var(--color-text-muted);
  font-size: 13px;
  line-height: 1.6;
}

.detect-loading-hint {
  flex-basis: 100%;
  margin: 0;
  color: var(--color-text-muted);
  font-size: 13px;
  line-height: 1.6;
}

.detect-side {
  display: grid;
  gap: var(--space-6);
  position: sticky;
  top: 96px;
}

.detect-process,
.detect-note {
  display: grid;
  gap: var(--space-4);
  padding: var(--space-5);
}

.detect-process ol {
  display: grid;
  gap: var(--space-3);
  margin: 0;
  padding: 0;
  list-style: none;
}

.detect-process li {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  gap: var(--space-3);
  align-items: flex-start;
}

.detect-process li > span {
  display: grid;
  width: 32px;
  height: 32px;
  place-items: center;
  border-radius: var(--radius-sm);
  color: #ffffff;
  background: var(--color-primary);
  font-weight: 800;
}

.detect-process strong {
  display: block;
  color: var(--color-text-strong);
  font-size: 14px;
}

.detect-process small {
  display: block;
  margin-top: 4px;
  color: var(--color-text-muted);
  line-height: 1.55;
}

.detect-note p {
  margin: 0;
  color: var(--color-text-muted);
  line-height: 1.75;
}

.detect-disclaimer {
  padding: var(--space-4);
  border: 1px solid #fde68a;
  border-radius: var(--radius-md);
  color: #92400e !important;
  background: #fffbeb;
}

@media (max-width: 1040px) {
  .detect-layout {
    grid-template-columns: 1fr;
  }

  .detect-side {
    position: static;
  }
}

@media (max-width: 680px) {
  .detect-card,
  .detect-process,
  .detect-note {
    padding: var(--space-5);
  }

  .detect-card__header {
    flex-direction: column;
  }

  .detect-form__row {
    grid-template-columns: 1fr;
  }

  .detect-submit,
  .detect-reset,
  .detect-example {
    width: 100%;
  }
}
</style>
