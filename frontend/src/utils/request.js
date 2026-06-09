import axios from 'axios'
import router from '@/router'
import { getToken } from './auth'
import { useUserStore } from '@/stores/user'

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 15000
})

request.interceptors.request.use((config) => {
  const token = getToken()

  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }

  return config
})

request.interceptors.response.use(
  (response) => (response.config?.rawResponse ? response : response.data),
  (error) => {
    const status = error?.response?.status

    if (status === 401) {
      const userStore = useUserStore()
      userStore.logout()

      if (router.currentRoute.value.name !== 'login') {
        router.replace({
          name: 'login',
          query: { redirect: router.currentRoute.value.fullPath }
        })
      }
    }

    return Promise.reject(error)
  }
)

export default request
