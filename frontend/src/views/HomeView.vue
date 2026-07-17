<template>
  <div class="page-stack home-page">
    <section class="home-hero surface-card">
      <div class="home-hero__content">
        <p class="home-eyebrow">RAG 证据检索 + DeepSeek 分析 + 规则评分</p>
        <h1>智闻辨真</h1>
        <p>
          面向普通用户的新闻可信度辅助评估系统。输入新闻标题与正文后，系统将组织证据、模型判断和规则评分，生成结构化风险结论。
        </p>
        <div class="home-actions">
          <RouterLink class="button button--primary" :to="{ name: 'detect' }">
            <el-icon><Search /></el-icon>
            立即检测新闻
          </RouterLink>
          <RouterLink class="button button--secondary" :to="{ name: 'highRisk' }">
            <el-icon><WarningFilled /></el-icon>
            查看高风险新闻
          </RouterLink>
        </div>
      </div>

      <div class="home-hero__signals" aria-label="系统能力">
        <span v-for="item in signals" :key="item">{{ item }}</span>
      </div>
    </section>

    <section class="home-section">
      <div class="home-section__heading">
        <p>核心能力</p>
        <h2>从输入到证据，再到可解释结论</h2>
      </div>

      <div class="home-card-grid">
        <article v-for="item in capabilityCards" :key="item.title" class="home-card surface-card">
          <span class="home-card__icon" aria-hidden="true">
            <component :is="item.icon" />
          </span>
          <h3>{{ item.title }}</h3>
          <p>{{ item.description }}</p>
        </article>
      </div>
    </section>

    <section class="home-section home-workflow surface-card surface-card--padded">
      <div class="home-section__heading">
        <p>检测流程</p>
        <h2>五步完成新闻可信度评估</h2>
      </div>

      <ol class="home-flow">
        <li v-for="(step, index) in workflow" :key="step.title">
          <span>{{ index + 1 }}</span>
          <div>
            <strong>{{ step.title }}</strong>
            <small>{{ step.description }}</small>
          </div>
        </li>
      </ol>
    </section>

    <section class="home-section">
      <div class="home-section__heading">
        <p>风险等级</p>
        <h2>颜色、文字和标签共同表达风险</h2>
      </div>

      <div class="home-risk-grid">
        <article v-for="item in riskLevels" :key="item.level" class="home-risk-card surface-card">
          <RiskLevelTag :level="item.level" size="default" />
          <strong>{{ item.range }}</strong>
          <p>{{ item.description }}</p>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup>
import {
  Connection,
  DataAnalysis,
  Files,
  Search,
  WarningFilled
} from '@element-plus/icons-vue'
import RiskLevelTag from '@/components/RiskLevelTag.vue'
import { RISK_LEVEL_OPTIONS } from '@/contracts/promptOutputContract'

const signals = ['证据检索', 'AI 分析', '规则评分', '风险等级', '报告沉淀']

const capabilityCards = [
  {
    title: '证据检索',
    description: '基于 RAG 检索相似新闻、核查材料和可参考证据，减少单纯文本判断的不确定性。',
    icon: Connection
  },
  {
    title: 'AI 辅助判断',
    description: '结合大语言模型输出判断结论、理由、风险点和辟谣建议，便于答辩展示和复盘。',
    icon: DataAnalysis
  },
  {
    title: '结构化结果',
    description: '结果页按总分、风险等级、三项评分、证据列表和分析过程分区展示，不平铺字段。',
    icon: Files
  }
]

const workflow = [
  { title: '文本输入', description: '填写新闻标题、正文和可选类别。' },
  { title: '证据检索', description: '召回知识库中的相似新闻与核查线索。' },
  { title: '模型分析', description: '结合检索证据生成判断理由和建议。' },
  { title: '规则评分', description: '检查来源、表述和风险特征。' },
  { title: '综合评估', description: '输出可信度评分、风险等级和报告入口。' }
]

const riskLevels = RISK_LEVEL_OPTIONS.map((item) => ({
  level: item.value,
  range: item.range,
  description: item.description
}))
</script>

<style scoped>
.home-page {
  align-items: stretch;
}

.home-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: var(--space-8);
  align-items: center;
  min-height: 420px;
  padding: var(--space-10);
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.96), rgba(224, 242, 254, 0.7)),
    var(--color-bg-panel);
}

.home-hero__content {
  display: grid;
  gap: var(--space-5);
}

.home-eyebrow,
.home-section__heading p {
  margin: 0;
  color: var(--color-primary);
  font-size: 13px;
  font-weight: 800;
}

.home-hero h1 {
  margin: 0;
  color: var(--color-text-strong);
  font-size: 52px;
  line-height: 1.06;
}

.home-hero p:not(.home-eyebrow) {
  max-width: 720px;
  margin: 0;
  color: var(--color-text-muted);
  font-size: 17px;
  line-height: 1.85;
}

.home-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.home-hero__signals {
  display: grid;
  gap: var(--space-3);
}

.home-hero__signals span {
  display: inline-flex;
  min-height: 44px;
  align-items: center;
  padding: 0 var(--space-4);
  border: 1px solid rgba(3, 105, 161, 0.18);
  border-radius: var(--radius-md);
  color: var(--color-primary-strong);
  background: rgba(255, 255, 255, 0.78);
  font-weight: 800;
}

.home-section {
  display: grid;
  gap: var(--space-5);
}

.home-section__heading {
  display: grid;
  gap: var(--space-2);
}

.home-section__heading h2 {
  margin: 0;
  color: var(--color-text-strong);
  font-size: 22px;
}

.home-card-grid,
.home-risk-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-4);
}

.home-risk-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.home-card,
.home-risk-card {
  display: grid;
  gap: var(--space-3);
  padding: var(--space-5);
}

.home-card__icon {
  display: grid;
  width: 44px;
  height: 44px;
  place-items: center;
  border-radius: var(--radius-md);
  color: var(--color-primary);
  background: var(--color-primary-soft);
}

.home-card__icon svg {
  width: 22px;
  height: 22px;
}

.home-card h3,
.home-risk-card strong {
  margin: 0;
  color: var(--color-text-strong);
  font-size: 16px;
}

.home-card p,
.home-risk-card p {
  margin: 0;
  color: var(--color-text-muted);
  line-height: 1.7;
}

.home-workflow {
  background: rgba(255, 255, 255, 0.94);
}

.home-flow {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: var(--space-3);
  margin: 0;
  padding: 0;
  list-style: none;
}

.home-flow li {
  display: grid;
  gap: var(--space-3);
  padding: var(--space-4);
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-md);
  background: var(--color-bg-subtle);
}

.home-flow li > span {
  display: grid;
  width: 32px;
  height: 32px;
  place-items: center;
  border-radius: var(--radius-sm);
  color: #ffffff;
  background: var(--color-primary);
  font-weight: 800;
}

.home-flow strong {
  display: block;
  color: var(--color-text-strong);
}

.home-flow small {
  display: block;
  margin-top: 6px;
  color: var(--color-text-muted);
  line-height: 1.6;
}

.home-risk-card {
  align-content: start;
}

@media (max-width: 1080px) {
  .home-hero,
  .home-card-grid,
  .home-risk-grid,
  .home-flow {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 640px) {
  .home-hero {
    grid-template-columns: 1fr;
    min-height: auto;
    padding: var(--space-5);
  }

  .home-hero h1 {
    font-size: 38px;
  }

  .home-card-grid,
  .home-risk-grid,
  .home-flow {
    grid-template-columns: 1fr;
  }
}
</style>
