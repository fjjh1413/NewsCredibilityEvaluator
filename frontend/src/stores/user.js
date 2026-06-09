import { defineStore } from 'pinia'
import {
  clearAuthStorage,
  getStoredUser,
  getToken,
  removeStoredUser,
  setStoredUser,
  setToken
} from '@/utils/auth'

function unwrapResponseData(response) {
  const body = response?.data ?? response

  if (
    body?.data &&
    typeof body.data === 'object' &&
    (body.code !== undefined || body.success !== undefined || body.message !== undefined)
  ) {
    return unwrapResponseData(body.data)
  }

  return body
}

function extractToken(payload) {
  const data = unwrapResponseData(payload)

  return (
    data?.access_token ||
    data?.accessToken ||
    data?.token ||
    payload?.access_token ||
    payload?.accessToken ||
    payload?.token
  )
}

function extractUserInfo(response) {
  const data = unwrapResponseData(response)

  if (data?.user || data?.userInfo || data?.profile) {
    return data.user || data.userInfo || data.profile
  }

  if (!data || typeof data !== 'object') {
    return null
  }

  const userKeys = [
    'id',
    'user_id',
    'username',
    'email',
    'role',
    'created_at',
    'create_time',
    'registered_at',
    'stats',
    'statistics'
  ]

  return userKeys.some((key) => data[key] !== undefined) ? data : null
}

export const useUserStore = defineStore('user', {
  state: () => ({
    token: getToken(),
    userInfo: getStoredUser(),
    restored: false,
    restoring: false,
    sessionVerified: false
  }),
  getters: {
    isLoggedIn: (state) => Boolean(state.token),
    isAdmin: (state) => state.sessionVerified && state.userInfo?.role === 'admin',
    user: (state) => state.userInfo,
    displayName: (state) => state.userInfo?.username || state.userInfo?.email || '已登录用户',
    role: (state) => state.userInfo?.role || ''
  },
  actions: {
    restoreFromStorageOnly() {
      this.token = getToken()
      this.userInfo = getStoredUser()
      this.sessionVerified = false
    },
    setTokenValue(token) {
      this.token = token || null

      if (token) {
        setToken(token)
      }
    },
    setUserInfo(userInfo) {
      this.userInfo = userInfo || null

      if (userInfo) {
        setStoredUser(userInfo)
      } else {
        removeStoredUser()
      }
    },
    setAuth(payload) {
      const token = extractToken(payload)
      const userInfo = extractUserInfo(payload)

      if (token) {
        this.setTokenValue(token)
      }

      if (userInfo) {
        this.setUserInfo(userInfo)
      }

      this.sessionVerified = Boolean(token && userInfo)
    },
    async fetchCurrentUser() {
      if (!this.token) {
        return null
      }

      this.restoring = true

      try {
        const { getCurrentUser } = await import('@/api/auth')
        const response = await getCurrentUser()
        const userInfo = extractUserInfo(response)
        this.setUserInfo(userInfo)
        this.sessionVerified = Boolean(userInfo)
        return userInfo
      } catch (error) {
        this.setUserInfo(null)
        this.sessionVerified = false
        throw error
      } finally {
        this.restoring = false
      }
    },
    async restoreSession() {
      if (this.restored) {
        return this.userInfo
      }

      this.restoreFromStorageOnly()

      if (!this.token) {
        this.restored = true
        return null
      }

      try {
        await this.fetchCurrentUser()
      } catch {
        // The request interceptor handles 401 by clearing auth and redirecting.
      } finally {
        this.restored = true
      }

      return this.userInfo
    },
    logout() {
      this.token = null
      this.userInfo = null
      this.restored = true
      this.sessionVerified = false
      clearAuthStorage()
    }
  }
})
