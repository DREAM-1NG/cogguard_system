import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { login as loginApi, getProfile as getProfileApi } from '@/api/auth'
import router from '@/router'

export interface AuthUserInfo {
  id: number
  username: string
  email: string
  role: string
}

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref(localStorage.getItem('access_token') || '')
  const refreshToken = ref(localStorage.getItem('refresh_token') || '')
  const userInfo = ref<AuthUserInfo | null>(null)

  const isLoggedIn = computed(() => !!accessToken.value)

  async function login(username: string, password: string) {
    const res = await loginApi({ username, password }) as { data: { access_token: string; refresh_token: string } }
    accessToken.value = res.data.access_token
    refreshToken.value = res.data.refresh_token
    userInfo.value = null
    localStorage.setItem('access_token', res.data.access_token)
    localStorage.setItem('refresh_token', res.data.refresh_token)
  }

  async function fetchProfile() {
    const res = await getProfileApi() as { data: AuthUserInfo }
    userInfo.value = res.data
  }

  function logout() {
    accessToken.value = ''
    refreshToken.value = ''
    userInfo.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    router.push('/login')
  }

  return {
    accessToken,
    refreshToken,
    userInfo,
    isLoggedIn,
    login,
    fetchProfile,
    logout,
  }
})
