export const TOKEN_STORAGE_KEY = 'zhiyun_bianzhen_token'
export const USER_STORAGE_KEY = 'zhiyun_bianzhen_user'

export function getToken() {
  return localStorage.getItem(TOKEN_STORAGE_KEY)
}

export function setToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_STORAGE_KEY, token)
  }
}

export function removeToken() {
  localStorage.removeItem(TOKEN_STORAGE_KEY)
}

export function getStoredUser() {
  const raw = localStorage.getItem(USER_STORAGE_KEY)

  if (!raw) {
    return null
  }

  try {
    return JSON.parse(raw)
  } catch {
    localStorage.removeItem(USER_STORAGE_KEY)
    return null
  }
}

export function setStoredUser(user) {
  if (user) {
    localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user))
  }
}

export function removeStoredUser() {
  localStorage.removeItem(USER_STORAGE_KEY)
}

export function clearAuthStorage() {
  removeToken()
  removeStoredUser()
}
