<template>
  <div class="admin-shell">
    <aside class="admin-sidebar" aria-label="管理员后台侧边栏">
      <RouterLink class="admin-brand" :to="{ name: 'adminDashboard' }" aria-label="管理员后台首页">
        <span class="admin-brand__mark">真</span>
        <span class="admin-brand__text">
          <strong>智闻辨真</strong>
          <small>管理后台</small>
        </span>
      </RouterLink>

      <nav class="admin-menu" aria-label="管理员后台导航">
        <RouterLink
          v-for="item in menuItems"
          :key="item.name"
          class="admin-menu__item"
          :to="{ name: item.name }"
        >
          <component :is="item.icon" class="admin-menu__icon" aria-hidden="true" />
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>

      <RouterLink class="admin-sidebar__return" :to="{ name: 'home' }">
        返回用户端
      </RouterLink>
    </aside>

    <div class="admin-workspace">
      <header class="admin-topbar">
        <nav class="admin-breadcrumb" aria-label="后台面包屑">
          <RouterLink :to="{ name: 'adminDashboard' }">管理员后台</RouterLink>
          <ArrowRight class="admin-breadcrumb__separator" aria-hidden="true" />
          <span>{{ currentTitle }}</span>
        </nav>

        <div class="admin-account">
          <div class="admin-account__identity">
            <UserFilled aria-hidden="true" />
            <span>{{ userStore.displayName }}</span>
            <small>管理员</small>
          </div>
          <button
            class="icon-button admin-account__logout"
            type="button"
            aria-label="退出管理员后台"
            @click="handleLogout"
          >
            <SwitchButton aria-hidden="true" />
          </button>
        </div>
      </header>

      <main class="admin-main">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus/es/components/message/index.mjs'
import { ElMessageBox } from 'element-plus/es/components/message-box/index.mjs'
import {
  ArrowRight,
  DataAnalysis,
  Document,
  Files,
  HomeFilled,
  Operation,
  Search,
  SwitchButton,
  Tickets,
  UserFilled,
  WarningFilled
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const menuItems = [
  { name: 'adminDashboard', label: '后台首页', icon: HomeFilled },
  { name: 'adminAiEngineering', label: 'AI 工程质量', icon: DataAnalysis },
  { name: 'adminOperationPolicies', label: '操作策略', icon: Operation },
  { name: 'adminUsers', label: '用户管理', icon: UserFilled },
  { name: 'adminDetections', label: '检测记录管理', icon: Search },
  { name: 'adminKnowledge', label: '知识库管理', icon: Files },
  { name: 'adminPrompts', label: 'Prompt 模板管理', icon: Tickets },
  { name: 'adminHighRisk', label: '高风险新闻管理', icon: WarningFilled },
  { name: 'adminStatistics', label: '数据统计', icon: DataAnalysis },
  { name: 'adminReports', label: '报告管理', icon: Document },
  { name: 'adminLogs', label: '系统日志', icon: Tickets }
]

const currentTitle = computed(() => route.meta.title || '后台首页')

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确认退出管理员后台吗？', '退出登录', {
      confirmButtonText: '退出登录',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch {
    return
  }

  userStore.logout()
  ElMessage.success('已退出登录')
  router.push({ name: 'login' })
}
</script>

<style scoped>
.admin-shell {
  display: grid;
  grid-template-columns: 264px minmax(0, 1fr);
  min-height: 100vh;
  background:
    linear-gradient(180deg, rgba(224, 242, 254, 0.7) 0, rgba(245, 249, 252, 0) 320px),
    var(--color-bg-page);
}

.admin-sidebar {
  position: sticky;
  top: 0;
  display: grid;
  grid-template-rows: auto 1fr auto;
  gap: var(--space-5);
  height: 100vh;
  padding: var(--space-5);
  border-right: 1px solid rgba(216, 227, 238, 0.86);
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 8px 0 24px rgba(15, 23, 42, 0.04);
}

.admin-brand {
  display: inline-flex;
  align-items: center;
  gap: var(--space-3);
  min-height: 48px;
}

.admin-brand__mark {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  border-radius: var(--radius-md);
  color: #ffffff;
  background: var(--color-primary-strong);
  font-size: 18px;
  font-weight: 800;
}

.admin-brand__text {
  display: grid;
  gap: 2px;
}

.admin-brand__text strong {
  color: var(--color-text-strong);
  font-size: 17px;
  line-height: 1.15;
}

.admin-brand__text small {
  color: var(--color-text-muted);
  font-size: 12px;
  font-weight: 700;
}

.admin-menu {
  display: grid;
  align-content: start;
  gap: var(--space-2);
  min-width: 0;
  overflow-y: auto;
}

.admin-menu__item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-height: 42px;
  padding: 0 var(--space-3);
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
  font-weight: 700;
  transition: color 200ms ease, background-color 200ms ease, border-color 200ms ease;
}

.admin-menu__item:hover,
.admin-menu__item.router-link-active {
  color: var(--color-primary-strong);
  border-color: rgba(3, 105, 161, 0.12);
  background: var(--color-primary-soft);
}

.admin-menu__icon {
  width: 17px;
  height: 17px;
  flex: 0 0 auto;
}

.admin-sidebar__return {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 38px;
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-sm);
  color: var(--color-primary-strong);
  background: var(--color-bg-subtle);
  font-weight: 800;
  transition: background-color 200ms ease, border-color 200ms ease;
}

.admin-sidebar__return:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
}

.admin-workspace {
  min-width: 0;
}

.admin-topbar {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-height: 72px;
  padding: 14px 32px;
  border-bottom: 1px solid rgba(216, 227, 238, 0.78);
  background: rgba(245, 249, 252, 0.88);
  backdrop-filter: blur(12px);
}

.admin-breadcrumb {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
  color: var(--color-text-muted);
  font-size: 13px;
  font-weight: 700;
}

.admin-breadcrumb a {
  color: var(--color-primary-strong);
}

.admin-breadcrumb a:hover {
  color: var(--color-primary);
}

.admin-breadcrumb span {
  overflow: hidden;
  color: var(--color-text-strong);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.admin-breadcrumb__separator {
  width: 14px;
  height: 14px;
  flex: 0 0 auto;
  color: var(--color-text-muted);
}

.admin-account {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.admin-account__identity {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  max-width: 260px;
  min-height: 38px;
  padding: 0 10px;
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-sm);
  color: var(--color-text);
  background: rgba(255, 255, 255, 0.9);
}

.admin-account__identity svg {
  width: 16px;
  height: 16px;
  flex: 0 0 auto;
  color: var(--color-primary);
}

.admin-account__identity span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.admin-account__identity small {
  flex: 0 0 auto;
  padding: 2px 7px;
  border-radius: 999px;
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
  font-size: 11px;
  font-weight: 800;
}

.admin-account__logout:hover {
  color: var(--color-danger);
}

.admin-main {
  padding: 28px 32px 48px;
}

@media (max-width: 1024px) {
  .admin-shell {
    grid-template-columns: 1fr;
  }

  .admin-sidebar {
    position: static;
    height: auto;
    grid-template-rows: auto auto auto;
    border-right: 0;
    border-bottom: 1px solid rgba(216, 227, 238, 0.86);
  }

  .admin-menu {
    grid-auto-flow: column;
    grid-auto-columns: max-content;
    overflow-x: auto;
    overflow-y: hidden;
    padding-bottom: 2px;
  }

  .admin-sidebar__return {
    justify-self: start;
    padding: 0 var(--space-4);
  }
}

@media (max-width: 720px) {
  .admin-sidebar,
  .admin-topbar,
  .admin-main {
    padding-right: var(--space-4);
    padding-left: var(--space-4);
  }

  .admin-topbar {
    align-items: stretch;
    flex-direction: column;
  }

  .admin-account {
    justify-content: space-between;
  }

  .admin-account__identity {
    min-width: 0;
  }
}
</style>
