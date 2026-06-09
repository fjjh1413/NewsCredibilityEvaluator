<template>
  <section class="auth-page">
    <aside class="auth-intro surface-card">
      <p class="auth-intro__eyebrow">创建检测账户</p>
      <h1>把每次核查都留在自己的证据档案里</h1>
      <p>
        注册后可在后续阶段保存新闻检测记录、查看风险等级变化，并围绕证据、模型分析和规则评分形成完整报告。
      </p>

      <dl class="auth-feature-list">
        <div>
          <dt>安全登录态</dt>
          <dd>使用 JWT Token 进行身份识别，请求自动携带授权头。</dd>
        </div>
        <div>
          <dt>风险追踪</dt>
          <dd>后续可集中查看历史检测和高风险记录。</dd>
        </div>
        <div>
          <dt>报告沉淀</dt>
          <dd>为答辩展示和学习复盘保留结构化检测结果。</dd>
        </div>
      </dl>
    </aside>

    <section class="auth-card surface-card" aria-labelledby="register-title">
      <div class="auth-card__header">
        <p>账户访问</p>
        <h2 id="register-title">注册</h2>
        <span>填写基础信息后即可前往登录。</span>
      </div>

      <el-alert
        v-if="errorMessage"
        class="auth-alert"
        :title="errorMessage"
        type="error"
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
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model.trim="form.username"
            size="large"
            placeholder="请输入用户名"
            autocomplete="username"
            :prefix-icon="User"
          />
        </el-form-item>

        <el-form-item label="邮箱" prop="email">
          <el-input
            v-model.trim="form.email"
            size="large"
            placeholder="请输入邮箱"
            autocomplete="email"
            :prefix-icon="Message"
          />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            size="large"
            placeholder="请输入密码"
            autocomplete="new-password"
            type="password"
            show-password
            :prefix-icon="Lock"
          />
        </el-form-item>

        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            size="large"
            placeholder="请再次输入密码"
            autocomplete="new-password"
            type="password"
            show-password
            :prefix-icon="Lock"
          />
        </el-form-item>

        <el-button class="auth-submit" type="primary" native-type="submit" :loading="loading">
          注册账号
        </el-button>
      </el-form>

      <p class="auth-switch">
        已有账号？
        <RouterLink :to="{ name: 'login' }">去登录</RouterLink>
      </p>
    </section>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus/es/components/message/index.mjs'
import { Lock, Message, User } from '@element-plus/icons-vue'
import { register } from '@/api/auth'

const router = useRouter()
const formRef = ref(null)
const loading = ref(false)
const errorMessage = ref('')

const form = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: ''
})

function validateConfirmPassword(rule, value, callback) {
  if (!value) {
    callback(new Error('请再次输入密码'))
    return
  }

  if (value !== form.password) {
    callback(new Error('两次输入的密码不一致'))
    return
  }

  callback()
}

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 30, message: '用户名长度需在 2 到 30 个字符之间', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入有效的邮箱地址', trigger: ['blur', 'change'] }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 64, message: '密码长度需在 6 到 64 个字符之间', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, validator: validateConfirmPassword, trigger: ['blur', 'change'] }
  ]
}

function ensureSuccess(response) {
  if (response?.code !== undefined && ![0, 200, 201].includes(Number(response.code))) {
    throw new Error(response.message || '注册失败，请稍后重试')
  }
}

function getErrorMessage(error) {
  return (
    error?.response?.data?.message ||
    error?.response?.data?.detail ||
    error?.message ||
    '注册失败，请检查填写信息'
  )
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

  loading.value = true

  try {
    const response = await register({
      username: form.username,
      password: form.password,
      email: form.email
    })

    ensureSuccess(response)
    ElMessage.success('注册成功，请登录')
    await router.push({
      name: 'login',
      query: { username: form.username }
    })
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
  grid-template-columns: minmax(0, 1fr) minmax(380px, 460px);
  gap: var(--space-6);
  align-items: stretch;
}

.auth-intro {
  display: grid;
  align-content: center;
  gap: var(--space-5);
  min-height: 620px;
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
  max-width: 640px;
  margin: 0;
  color: var(--color-text-strong);
  font-size: 40px;
  line-height: 1.14;
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
  min-height: 620px;
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
