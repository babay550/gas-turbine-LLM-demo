/**认证状态管理 — token 持久化 + 用户信息。 */

import { reactive, readonly } from 'vue'
import { login as apiLogin, getMe as apiGetMe } from '../api'
import type { UserInfo } from '../types'

const TOKEN_KEY = 'gas_turbine_token'

// 私有状态
const _state = reactive({
  token: localStorage.getItem(TOKEN_KEY) || '',
  user: null as UserInfo | null,
  loading: false,
})

// 公开只读状态
export const authStore = readonly(_state)

// 计算属性
export function isAuthenticated(): boolean {
  return !!_state.token
}

export function currentUser(): UserInfo | null {
  return _state.user
}

export function userRole(): string {
  return _state.user?.role || ''
}

export function isAdmin(): boolean {
  return _state.user?.role === 'admin'
}

// Actions
export async function login(username: string, password: string) {
  _state.loading = true
  try {
    const res = await apiLogin({ username, password })
    _state.token = res.access_token
    _state.user = res.user
    localStorage.setItem(TOKEN_KEY, res.access_token)
    return res
  } finally {
    _state.loading = false
  }
}

export async function fetchCurrentUser() {
  if (!_state.token) return null
  try {
    const user = await apiGetMe()
    _state.user = user
    return user
  } catch {
    // token 无效，清除
    logout()
    return null
  }
}

export function logout() {
  _state.token = ''
  _state.user = null
  localStorage.removeItem(TOKEN_KEY)
}

export function getToken(): string {
  return _state.token
}
