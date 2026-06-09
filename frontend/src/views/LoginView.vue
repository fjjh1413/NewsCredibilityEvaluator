<template>
  <section class="auth-page">
    <aside class="auth-intro surface-card">
      <p class="auth-intro__eyebrow">可信新闻检测平台</p>
      <h1>欢迎回到智闻辨真</h1>
      <p>
        登录后可保存检测历史，查看 AI 分析结果，并在后续阶段追踪 RAG 证据检索与风险评分记录。
      </p>

      <dl class="auth-feature-list">
        <div>
          <dt>RAG 证据检索</dt>
          <dd>基于知识库召回相似新闻与核查线索。</dd>
        </div>
        <div>
          <dt>AI 辅助分析</dt>
          <dd>结合大语言模型输出风险理由与建议。</dd>
        </div>
        <div>
          <dt>个人检测记录</dt>
          <dd>登录后保留历史结果，便于复盘与答辩展示。</dd>
        </div>
      </dl>
    </aside>

    <section class="auth-card surface-card" aria-labelledby="login-title">
      <div class="auth-card__header">
        <p>账户访问</p>
        <h2 id="login-title">登录</h2>
        <span>使用用户名和密码进入用户端。</span>
      </div>

      <el-alert
        v-if="errorMessage"
        class="auth-alert"
        :title="errorMessage"
        type="error"
        show-icon
        :closable="false"
      />

      <el-alert
        v-if="adminNotice"
        class="auth-alert"
        title="管理员账号登录成功，正在进入后台管理。"
        type="warning"
        show-icon
        :closable="false"
      />

      <el-form
        ref="formRef"
        class="auth-form"
        :model="form"
        :rules="rules"
        label-position="top"
        @submit.prevent="handleSubmit"
      >
        <el-form-item label="账号/用户名" prop="username">
          <el-input
            v-model.trim="form.username"
            size="large"
            placeholder="请输入用户名"
            autocomplete="username"
            :prefix-icon="User"
          />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            size="large"
            placeholder="请输入密码"
            autocomplete="current-password"
            type="password"
            show-password
            :prefix-icon="Lock"
          />
        </el-form-item>

        <el-button class="auth-submit" type="primary" native-type="submit" :loading="loading">
          登录并进入检测
        </el-button>
      </el-form>

      <p class="auth-switch">
        还没有账号？
        <RouterLink :to="{ name: 'register' }">立即注册</RouterLink>
      </p>
    </section>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus/es/components/message/index.mjs'
import { Lock, User } from '@element-plus/icons-vue'
import { login } from '@/api/auth'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const formRef = ref(null)
const loading = ref(false)
const errorMessage = ref('')
const adminNotice = ref(false)

const form = reactive({
  username: String(route.query.username || ''),
  password: ''
})

const rules = {
  username: [
    { required: true, message: '请输入账号/用户名', trigger: 'blur' },
    { min: 2, max: 50, message: '账号长度需在 2 到 50 个字符之间', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 64, message: '密码长度需在 6 到 64 个字符之间', trigger: 'blur' }
  ]
}

function getApiData(response) {
  if (response?.code !== undefined && ![0, 200, 201].includes(Number(response.code))) {
    throw new Error(response.message || '登录失败，请稍后重试')
  }

  return response?.data ?? response
}

function getTokenFromData(data) {
  return data?.access_token || data?.accessToken || data?.token
}

function getErrorMessage(error) {
  return (
    error?.response?.data?.message ||
    error?.response?.data?.detail ||
    error?.message ||
    '登录失败，请检查账号或密码'
  )
}

function getRedirectTarget(role) {
  const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : ''
  const isInternalPath = redirect.startsWith('/')

  if (role === 'admin') {
    return isInternalPath && redirect.startsWith('/admin') ? redirect : { name: 'adminDashboard' }
  }

  return isInternalPath && !redirect.startsWith('/admin') ? redirect : { name: 'detect' }
}

async function handleSubmit() {
  if (!formRef.value) {
    return
  }

  errorMessage.value = ''
  adminNotice.value = false

  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) {
    return
  }

  loading.value = true

  try {
    const response = await login({
      username: form.username,
      password: form.password
    })
    const data = getApiData(response)

    if (!getTokenFromData(data)) {
      throw new Error('登录成功响应中缺少 Token')
    }

    userStore.setAuth(response)
    const userInfo = await userStore.fetchCurrentUser()

    if (userInfo?.role === 'admin') {
      adminNotice.value = true
      ElMessage.success('登录成功，正在进入后台管理')
      await router.push(getRedirectTarget('admin'))
      return
    }

    ElMessage.success('登录成功')
    await router.push(getRedirectTarget('user'))
  } catch (error) {
    errorMessage.value = getErrorMessage(error)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-page {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 440px);
  gap: var(--space-6);
  align-items: stretch;
}

.auth-intro {
  display: grid;
  align-content: center;
  gap: var(--space-5);
  min-height: 560px;
  padding: 44px;
  background:
    linear-gradient(135deg, rgba(224, 242, 254, 0.95), rgba(255, 255, 255, 0.96)),
    var(--color-bg-panel);
}

.auth-intro__eyebrow {
  margin: 0;
  color: var(--color-primary);
  font-size: 13px;
  font-weight: 800;
}

.auth-intro h1 {
  max-width: 620px;
  margin: 0;
  color: var(--color-text-strong);
  font-size: 42px;
  line-height: 1.12;
}

.auth-intro p {
  max-width: 680px;
  margin: 0;
  color: var(--color-text-muted);
  font-size: 16px;
  line-height: 1.8;
}

.auth-feature-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-3);
  margin: var(--space-3) 0 0;
}

.auth-feature-list div {
  padding: var(--space-4);
  border: 1px solid rgba(216, 227, 238, 0.9);
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.72);
}

.auth-feature-list dt {
  color: var(--color-text-strong);
  font-size: 14px;
  font-weight: 800;
}

.auth-feature-list dd {
  margin: 8px 0 0;
  color: var(--color-text-muted);
  font-size: 13px;
  line-height: 1.6;
}

.auth-card {
  display: grid;
  align-content: center;
  gap: var(--space-5);
  min-height: 560px;
  padding: 36px;
}

.auth-card__header {
  display: grid;
  gap: var(--space-2);
}

.auth-card__header p {
  margin: 0;
  color: var(--color-primary);
  font-size: 13px;
  font-weight: 800;
}

.auth-card__header h2 {
  margin: 0;
  color: var(--color-text-strong);
  font-size: 28px;
}

.auth-card__header span {
  color: var(--color-text-muted);
  line-height: 1.7;
}

.auth-alert {
  border-radius: var(--radius-md);
}

.auth-form {
  display: grid;
  gap: var(--space-2);
}

.auth-form :deep(.el-form-item__label) {
  color: var(--color-text-strong);
  font-weight: 700;
}

.auth-form :deep(.el-input__wrapper) {
  min-height: 44px;
  border-radius: var(--radius-sm);
  box-shadow: 0 0 0 1px var(--color-border) inset;
}

.auth-form :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px var(--color-primary) inset, var(--shadow-focus);
}

.auth-submit {
  width: 100%;
  min-height: 44px;
  margin-top: var(--space-2);
  border-radius: var(--radius-sm);
  font-weight: 800;
}

.auth-switch {
  margin: 0;
  color: var(--color-text-muted);
  text-align: center;
}

.auth-switch a {
  color: var(--color-primary-strong);
  font-weight: 800;
}

.auth-switch a:hover {
  color: var(--color-primary);
}

@media (max-width: 980px) {
  .auth-page {
    grid-template-columns: 1fr;
  }

  .auth-intro,
  .auth-card {
    min-height: auto;
  }
}

@media (max-width: 640px) {
  .auth-intro,
  .auth-card {
    padding: var(--space-5);
  }

  .auth-intro h1 {
    font-size: 32px;
  }

  .auth-feature-list {
    grid-template-columns: 1fr;
  }
}
</style>
