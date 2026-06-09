import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus/es/components/message/index.mjs'
import { useUserStore } from '@/stores/user'
import UserLayout from '@/layouts/UserLayout.vue'

const HomeView = () => import('@/views/HomeView.vue')
const LoginView = () => import('@/views/LoginView.vue')
const RegisterView = () => import('@/views/RegisterView.vue')
const DetectView = () => import('@/views/DetectView.vue')
const ResultView = () => import('@/views/ResultView.vue')
const HistoryView = () => import('@/views/HistoryView.vue')
const HighRiskView = () => import('@/views/HighRiskView.vue')
const ProfileView = () => import('@/views/ProfileView.vue')
const AdminLayout = () => import('@/layouts/AdminLayout.vue')
const AdminDashboardView = () => import('@/views/admin/AdminDashboardView.vue')
const AdminUsersView = () => import('@/views/admin/AdminUsersView.vue')
const AdminDetectionsView = () => import('@/views/admin/AdminDetectionsView.vue')
const AdminKnowledgeView = () => import('@/views/admin/AdminKnowledgeView.vue')
const AdminPromptsView = () => import('@/views/admin/AdminPromptsView.vue')
const AdminHighRiskView = () => import('@/views/admin/AdminHighRiskView.vue')
const AdminStatisticsView = () => import('@/views/admin/AdminStatisticsView.vue')
const AdminReportsView = () => import('@/views/admin/AdminReportsView.vue')
const AdminLogsView = () => import('@/views/admin/AdminLogsView.vue')

const routes = [
  {
    path: '/',
    component: UserLayout,
    children: [
      {
        path: '',
        name: 'home',
        component: HomeView,
        meta: { title: '首页', public: true }
      },
      {
        path: 'login',
        name: 'login',
        component: LoginView,
        meta: { title: '登录', public: true, guestOnly: true }
      },
      {
        path: 'register',
        name: 'register',
        component: RegisterView,
        meta: { title: '注册', public: true, guestOnly: true }
      },
      {
        path: 'detect',
        name: 'detect',
        component: DetectView,
        meta: { title: '新闻检测', public: true }
      },
      {
        path: 'result/:id',
        name: 'result',
        component: ResultView,
        props: true,
        meta: { title: '检测结果', public: true, allowGuestResult: true }
      },
      {
        path: 'history',
        name: 'history',
        component: HistoryView,
        meta: { title: '历史记录', requiresAuth: true }
      },
      {
        path: 'high-risk',
        name: 'highRisk',
        component: HighRiskView,
        meta: { title: '高风险新闻', public: true }
      },
      {
        path: 'profile',
        name: 'profile',
        component: ProfileView,
        meta: { title: '个人中心', requiresAuth: true }
      }
    ]
  },
  {
    path: '/admin',
    component: AdminLayout,
    redirect: { name: 'adminDashboard' },
    meta: { title: '管理员后台', requiresAuth: true, requiresAdmin: true },
    children: [
      {
        path: 'dashboard',
        name: 'adminDashboard',
        component: AdminDashboardView,
        meta: { title: '后台首页', requiresAuth: true, requiresAdmin: true }
      },
      {
        path: 'users',
        name: 'adminUsers',
        component: AdminUsersView,
        meta: { title: '用户管理', requiresAuth: true, requiresAdmin: true }
      },
      {
        path: 'detections',
        name: 'adminDetections',
        component: AdminDetectionsView,
        meta: { title: '检测记录管理', requiresAuth: true, requiresAdmin: true }
      },
      {
        path: 'knowledge',
        name: 'adminKnowledge',
        component: AdminKnowledgeView,
        meta: { title: '知识库管理', requiresAuth: true, requiresAdmin: true }
      },
      {
        path: 'prompts',
        name: 'adminPrompts',
        component: AdminPromptsView,
        meta: { title: 'Prompt 模板管理', requiresAuth: true, requiresAdmin: true }
      },
      {
        path: 'high-risk',
        name: 'adminHighRisk',
        component: AdminHighRiskView,
        meta: { title: '高风险新闻管理', requiresAuth: true, requiresAdmin: true }
      },
      {
        path: 'statistics',
        name: 'adminStatistics',
        component: AdminStatisticsView,
        meta: { title: '数据统计', requiresAuth: true, requiresAdmin: true }
      },
      {
        path: 'reports',
        name: 'adminReports',
        component: AdminReportsView,
        meta: { title: '报告管理', requiresAuth: true, requiresAdmin: true }
      },
      {
        path: 'logs',
        name: 'adminLogs',
        component: AdminLogsView,
        meta: { title: '系统日志', requiresAuth: true, requiresAdmin: true }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  }
})

router.beforeEach(async (to) => {
  const userStore = useUserStore()

  if (!userStore.restored) {
    await userStore.restoreSession()
  }

  if (to.meta.requiresAuth && !userStore.isLoggedIn) {
    return {
      name: 'login',
      query: { redirect: to.fullPath }
    }
  }

  if (to.meta.requiresAdmin && !userStore.isAdmin) {
    ElMessage.warning('当前账号无管理员权限')
    return { name: 'home' }
  }

  if (to.meta.guestOnly && userStore.isLoggedIn && userStore.sessionVerified) {
    if (userStore.isAdmin) {
      return { name: 'adminDashboard' }
    }

    return { name: 'home' }
  }

  return true
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} - 智闻辨真` : '智闻辨真'
})

export default router
