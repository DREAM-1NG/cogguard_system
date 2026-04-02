/**
 * 认证状态管理 (Pinia)
 *
 * 管理用户的登录状态、令牌存储和用户信息。
 * Token 持久化到 localStorage，页面刷新后自动恢复。
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as loginApi, getProfile as getProfileApi } from '@/api/auth'
import router from '@/router'

export const useAuthStore = defineStore('auth', () => {
  /** JWT access token */
  const accessToken = ref(localStorage.getItem('access_token') || '')
  /** JWT refresh token */
  const refreshToken = ref(localStorage.getItem('refresh_token') || '')
  /** 当前用户信息 */
  const userInfo = ref<Record<string, unknown> | null>(null)

  /** 是否已登录 */
  const isLoggedIn = computed(() => !!accessToken.value)

  /** 登录：调用 API 并存储令牌 */
  async function login(username: string, password: string) {
    const res = await loginApi({ username, password }) as { data: { access_token: string; refresh_token: string } }
    accessToken.value = res.data.access_token
    refreshToken.value = res.data.refresh_token
    localStorage.setItem('access_token', res.data.access_token)
    localStorage.setItem('refresh_token', res.data.refresh_token)
  }

  /** 获取当前用户信息 */
  async function fetchProfile() {
    const res = await getProfileApi() as { data: Record<string, unknown> }
    userInfo.value = res.data
  }

  /** 登出：清除令牌和用户信息，跳转登录页 */
  function logout() {
    accessToken.value = ''
    refreshToken.value = ''
    userInfo.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    router.push('/login')
  }

  return { accessToken, refreshToken, userInfo, isLoggedIn, login, fetchProfile, logout }
})
