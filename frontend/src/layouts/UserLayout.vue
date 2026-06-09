<template>
  <div class="user-shell">
    <header class="user-header">
      <div class="user-header__inner">
        <RouterLink class="brand" :to="{ name: 'home' }" aria-label="智闻辨真首页">
          <span class="brand__mark">真</span>
          <span class="brand__text">
            <strong>智闻辨真</strong>
            <small>AI 新闻可信度评估</small>
          </span>
        </RouterLink>

        <nav class="main-nav" aria-label="用户端导航">
          <RouterLink
            v-for="item in navItems"
            :key="item.name"
            class="main-nav__item"
            :to="{ name: item.name }"
          >
            <component :is="item.icon" class="main-nav__icon" aria-hidden="true" />
            <span>{{ item.label }}</span>
          </RouterLink>
        </nav>

        <div class="user-actions">
          <template v-if="userStore.isLoggedIn">
            <RouterLink class="user-pill" :to="{ name: 'profile' }">
              <User class="user-pill__icon" aria-hidden="true" />
              <span class="user-pill__name">{{ userStore.displayName }}</span>
              <small v-if="userStore.role">{{ roleLabel }}</small>
            </RouterLink>
            <button class="icon-button" type="button" aria-label="退出登录" @click="handleLogout">
              <SwitchButton aria-hidden="true" />
            </button>
          </template>

          <template v-else>
            <RouterLink class="text-link" :to="{ name: 'login' }">登录</RouterLink>
            <RouterLink class="button button--primary button--small" :to="{ name: 'register' }">
              注册
            </RouterLink>
          </template>
        </div>
      </div>
    </header>

    <main class="user-main">
      <div class="page-container">
        <RouterView />
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus/es/components/message/index.mjs'
import { ElMessageBox } from 'element-plus/es/components/message-box/index.mjs'
import {
  Clock,
  HomeFilled,
  Search,
  SwitchButton,
  User,
  WarningFilled
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const roleLabel = computed(() => (userStore.role === 'admin' ? '管理员' : '用户'))

const navItems = [
  { name: 'home', label: '首页', icon: HomeFilled },
  { name: 'detect', label: '新闻检测', icon: Search },
  { name: 'history', label: '历史记录', icon: Clock },
  { name: 'highRisk', label: '高风险新闻', icon: WarningFilled },
  { name: 'profile', label: '个人中心', icon: User }
]

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确认退出当前账号吗？', '退出登录', {
      confirmButtonText: '退出登录',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch {
    return
  }

  userStore.logout()
  ElMessage.success('已退出登录')
  router.push({ name: 'home' })
}
</script>
