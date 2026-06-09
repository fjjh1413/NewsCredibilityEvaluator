<template>
  <div class="page-stack profile-page">
    <PageHeader
      eyebrow="账户信息"
      title="个人中心"
      description="查看当前登录账号、检测统计和常用入口。统计数据仅展示后端已返回的真实字段。"
    />

    <LoadingState v-if="loading" :lines="5" label="个人中心加载中" />

    <template v-else>
      <el-alert
        v-if="errorMessage"
        class="profile-alert"
        type="warning"
        :title="errorMessage"
        description="已优先展示本地登录态中的用户信息，可稍后刷新重试。"
        show-icon
        :closable="false"
      />

      <section class="profile-grid">
        <article class="profile-card surface-card surface-card--padded">
          <div class="profile-card__top">
            <div class="profile-avatar" aria-hidden="true">
              <UserFilled />
            </div>
            <div class="profile-identity">
              <span>当前用户</span>
              <h2>{{ displayName }}</h2>
              <span class="profile-role-tag">{{ roleLabel }}</span>
            </div>
          </div>

          <dl class="profile-fields">
            <div>
              <dt>用户名</dt>
              <dd>{{ userInfo.username || '--' }}</dd>
            </div>
            <div>
              <dt>邮箱</dt>
              <dd>{{ userInfo.email || '--' }}</dd>
            </div>
            <div>
              <dt>角色</dt>
              <dd>{{ roleLabel }}</dd>
            </div>
            <div>
              <dt>注册时间</dt>
              <dd>{{ formatDateTime(createdAt) }}</dd>
            </div>
          </dl>

          <div class="profile-card__actions">
            <RouterLink class="button button--primary" :to="{ name: 'detect' }">
              <el-icon><DocumentChecked /></el-icon>
              去检测新闻
            </RouterLink>
            <el-button class="profile-logout" :loading="logoutLoading" @click="confirmLogout">
              <el-icon><SwitchButton /></el-icon>
              退出登录
            </el-button>
          </div>
        </article>

        <section class="profile-actions surface-card surface-card--padded" aria-label="快捷入口">
          <div class="profile-section-heading">
            <h2>快捷入口</h2>
            <p>从账户中心快速进入常用功能。</p>
          </div>

          <div class="quick-actions">
            <RouterLink
              v-for="item in quickActions"
              :key="item.name"
              class="quick-action"
              :to="item.to"
            >
              <span class="quick-action__icon">
                <component :is="item.icon" />
              </span>
              <span>
                <strong>{{ item.title }}</strong>
                <small>{{ item.description }}</small>
              </span>
              <el-icon><ArrowRight /></el-icon>
            </RouterLink>
          </div>
        </section>
      </section>

      <section class="profile-stats surface-card surface-card--padded">
        <div class="profile-section-heading">
          <h2>检测统计</h2>
          <p>{{ hasAnyStat ? '以下统计来自 /api/auth/me 返回字段。' : '当前后端未提供用户统计字段，暂以待统计状态展示。' }}</p>
        </div>

        <div class="profile-stat-grid">
          <article
            v-for="item in statCards"
            :key="item.key"
            class="profile-stat-card"
            :class="`profile-stat-card--${item.tone}`"
          >
            <div class="profile-stat-card__icon" aria-hidden="true">
              <component :is="item.icon" />
            </div>
            <div>
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
              <p>{{ item.description }}</p>
            </div>
          </article>
        </div>
      </section>

      <section v-if="!hasAnyStat" class="profile-note">
        用户统计接口尚未单独提供。本页没有调用不存在的统计接口，后续可由后端在 `/api/auth/me` 中补充检测次数、高风险数量和报告数量字段。
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus/es/components/message/index.mjs'
import { ElMessageBox } from 'element-plus/es/components/message-box/index.mjs'
import {
  ArrowRight,
  DataAnalysis,
  DocumentChecked,
  Files,
  SwitchButton,
  Tickets,
  UserFilled,
  WarningFilled
} from '@element-plus/icons-vue'
import LoadingState from '@/components/LoadingState.vue'
import PageHeader from '@/components/PageHeader.vue'
import { useUserStore } from '@/stores/user'
import { formatDateTime } from '@/utils/format'

const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const logoutLoading = ref(false)
const errorMessage = ref('')

const userInfo = computed(() => unwrapUserPayload(userStore.user) || {})
const displayName = computed(() => userInfo.value.username || userInfo.value.email || userStore.displayName)
const createdAt = computed(() =>
  userInfo.value.created_at ??
  userInfo.value.create_time ??
  userInfo.value.createdAt ??
  userInfo.value.registered_at ??
  userInfo.value.registeredAt ??
  ''
)

const roleLabel = computed(() => {
  const role = String(userInfo.value.role || userStore.role || '').toLowerCase()

  if (role === 'admin') {
    return '管理员'
  }

  if (role === 'user' || role === 'normal') {
    return '普通用户'
  }

  return role || '普通用户'
})

const quickActions = [
  {
    name: 'detect',
    title: '新闻检测',
    description: '提交标题和正文进行可信度评估',
    to: { name: 'detect' },
    icon: DocumentChecked
  },
  {
    name: 'history',
    title: '历史记录',
    description: '查看当前账号的检测历史',
    to: { name: 'history' },
    icon: Tickets
  },
  {
    name: 'highRisk',
    title: '高风险新闻',
    description: '浏览公开高风险案例和统计',
    to: { name: 'highRisk' },
    icon: WarningFilled
  }
]

const statsSource = computed(() => userInfo.value.stats || userInfo.value.statistics || userInfo.value.profile_stats || {})

function unwrapUserPayload(value) {
  if (!value || typeof value !== 'object') {
    return value || {}
  }

  if (value.user || value.userInfo) {
    return value.user || value.userInfo
  }

  if (value.data && typeof value.data === 'object' && (value.code !== undefined || value.success !== undefined || value.message !== undefined)) {
    return unwrapUserPayload(value.data)
  }

  return value
}

function pickStat(keys) {
  for (const key of keys) {
    const directValue = userInfo.value[key]
    const nestedValue = statsSource.value[key]
    const value = directValue ?? nestedValue

    if (value !== undefined && value !== null && value !== '') {
      const numberValue = Number(value)
      return Number.isNaN(numberValue) ? String(value) : String(numberValue)
    }
  }

  return '待统计'
}

const detectionCount = computed(() =>
  pickStat(['detection_count', 'detectionCount', 'total_detections', 'totalDetections', 'detect_count', 'detectCount'])
)
const highRiskCount = computed(() =>
  pickStat(['high_risk_count', 'highRiskCount', 'high_risk_detections', 'highRiskDetections'])
)
const reportCount = computed(() =>
  pickStat(['report_count', 'reportCount', 'reports_count', 'reportsCount', 'pdf_count', 'pdfCount'])
)

const hasAnyStat = computed(() =>
  [detectionCount.value, highRiskCount.value, reportCount.value].some((value) => value !== '待统计')
)

const statCards = computed(() => [
  {
    key: 'detection',
    label: '检测次数',
    value: detectionCount.value,
    description: '当前账号累计提交的检测记录',
    icon: DataAnalysis,
    tone: 'primary'
  },
  {
    key: 'high-risk',
    label: '高风险检测数量',
    value: highRiskCount.value,
    description: '后端统计的高风险检测记录',
    icon: WarningFilled,
    tone: 'danger'
  },
  {
    key: 'report',
    label: '报告数量',
    value: reportCount.value,
    description: '后端已生成的检测报告数量',
    icon: Files,
    tone: 'success'
  }
])

async function refreshProfile() {
  if (!userStore.token) {
    return
  }

  loading.value = true
  errorMessage.value = ''

  try {
    await userStore.fetchCurrentUser()
  } catch (error) {
    errorMessage.value =
      error?.response?.data?.message ||
      error?.response?.data?.detail ||
      error?.message ||
      '用户信息刷新失败'
  } finally {
    loading.value = false
  }
}

async function confirmLogout() {
  try {
    await ElMessageBox.confirm('确认退出当前账号吗？退出后需要重新登录才能查看历史记录和个人中心。', '退出登录', {
      confirmButtonText: '退出登录',
      cancelButtonText: '取消',
      type: 'warning',
      customClass: 'profile-confirm'
    })
  } catch {
    return
  }

  logoutLoading.value = true
  userStore.logout()
  logoutLoading.value = false
  ElMessage.success('已退出登录')
  router.replace({ name: 'home' })
}

onMounted(refreshProfile)
</script>

<style scoped>
.profile-page {
  align-items: stretch;
}

.profile-alert {
  border-radius: var(--radius-lg);
}

.profile-grid {
  display: grid;
  grid-template-columns: minmax(320px, 0.9fr) minmax(0, 1.1fr);
  gap: var(--space-6);
  align-items: stretch;
}

.profile-card,
.profile-actions,
.profile-stats {
  display: grid;
  gap: var(--space-5);
}

.profile-card__top {
  display: flex;
  gap: var(--space-4);
  align-items: center;
}

.profile-avatar {
  display: grid;
  width: 64px;
  height: 64px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: var(--radius-lg);
  color: #ffffff;
  background: var(--color-primary-strong);
}

.profile-avatar svg {
  width: 30px;
  height: 30px;
}

.profile-identity {
  display: grid;
  gap: var(--space-2);
  min-width: 0;
}

.profile-identity span {
  color: var(--color-text-muted);
  font-size: 13px;
  font-weight: 800;
}

.profile-identity h2 {
  margin: 0;
  overflow: hidden;
  color: var(--color-text-strong);
  font-size: 26px;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.profile-role-tag {
  display: inline-flex;
  min-height: 26px;
  align-items: center;
  justify-self: start;
  padding: 0 10px;
  border: 1px solid rgba(3, 105, 161, 0.24);
  border-radius: 999px;
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
  font-size: 12px;
  font-weight: 800;
}

.profile-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
  margin: 0;
}

.profile-fields div {
  min-width: 0;
  padding: var(--space-4);
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-md);
  background: var(--color-bg-subtle);
}

.profile-fields dt {
  margin: 0 0 var(--space-2);
  color: var(--color-text-muted);
  font-size: 12px;
  font-weight: 800;
}

.profile-fields dd {
  margin: 0;
  overflow: hidden;
  color: var(--color-text-strong);
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.profile-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.profile-logout {
  min-height: 40px;
  border-radius: var(--radius-sm);
  color: var(--color-danger);
  border-color: rgba(220, 38, 38, 0.26);
  background: var(--risk-high-bg);
  font-weight: 800;
}

.profile-logout:hover,
.profile-logout:focus {
  color: #ffffff;
  border-color: var(--color-danger);
  background: var(--color-danger);
}

.profile-section-heading {
  display: grid;
  gap: var(--space-2);
}

.profile-section-heading h2 {
  margin: 0;
  color: var(--color-text-strong);
  font-size: 18px;
}

.profile-section-heading p {
  margin: 0;
  color: var(--color-text-muted);
  line-height: 1.7;
}

.quick-actions {
  display: grid;
  gap: var(--space-3);
}

.quick-action {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr) 20px;
  gap: var(--space-3);
  align-items: center;
  min-height: 76px;
  padding: var(--space-4);
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-md);
  background: var(--color-bg-subtle);
  transition: border-color 200ms ease, background-color 200ms ease, box-shadow 200ms ease;
}

.quick-action:hover,
.quick-action:focus-visible {
  border-color: rgba(3, 105, 161, 0.32);
  background: var(--color-primary-soft);
  box-shadow: var(--shadow-card);
}

.quick-action__icon {
  display: grid;
  width: 44px;
  height: 44px;
  place-items: center;
  border-radius: var(--radius-md);
  color: var(--color-primary);
  background: #ffffff;
}

.quick-action__icon svg,
.quick-action > svg {
  width: 18px;
  height: 18px;
}

.quick-action span:not(.quick-action__icon) {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.quick-action strong {
  color: var(--color-text-strong);
  font-size: 15px;
}

.quick-action small {
  overflow: hidden;
  color: var(--color-text-muted);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.profile-stat-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-4);
}

.profile-stat-card {
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr);
  gap: var(--space-4);
  min-height: 136px;
  padding: var(--space-5);
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-lg);
  background: var(--color-bg-subtle);
}

.profile-stat-card__icon {
  display: grid;
  width: 48px;
  height: 48px;
  place-items: center;
  border-radius: var(--radius-md);
  color: var(--stat-color, var(--color-primary));
  background: var(--stat-bg, var(--color-primary-soft));
}

.profile-stat-card__icon svg {
  width: 22px;
  height: 22px;
}

.profile-stat-card span {
  color: var(--color-text-muted);
  font-size: 13px;
  font-weight: 800;
}

.profile-stat-card strong {
  display: block;
  margin: var(--space-2) 0;
  color: var(--stat-color, var(--color-primary-strong));
  font-size: 30px;
  line-height: 1;
}

.profile-stat-card p {
  margin: 0;
  color: var(--color-text-muted);
  font-size: 13px;
  line-height: 1.6;
}

.profile-stat-card--primary {
  --stat-color: var(--color-primary);
  --stat-bg: var(--color-primary-soft);
}

.profile-stat-card--danger {
  --stat-color: var(--color-danger);
  --stat-bg: var(--risk-high-bg);
}

.profile-stat-card--success {
  --stat-color: var(--color-success);
  --stat-bg: var(--risk-trusted-bg);
}

.profile-note {
  padding: var(--space-5);
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-lg);
  color: var(--color-text-muted);
  background: rgba(255, 255, 255, 0.9);
  line-height: 1.8;
}

@media (max-width: 1040px) {
  .profile-grid,
  .profile-stat-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .profile-fields {
    grid-template-columns: 1fr;
  }

  .profile-card__top {
    align-items: flex-start;
  }

  .profile-card__actions {
    align-items: stretch;
    flex-direction: column;
  }

  .quick-action {
    grid-template-columns: 40px minmax(0, 1fr);
  }

  .quick-action > svg {
    display: none;
  }

  .profile-stat-card {
    grid-template-columns: 1fr;
  }
}
</style>
