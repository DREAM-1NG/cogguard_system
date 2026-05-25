import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { login as loginApi, getProfile as getProfileApi } from '@/api/auth'
import router from '@/router'

const PREVIEW_ACCESS_TOKEN = 'cogguard-preview-token'
const PREVIEW_REFRESH_TOKEN = 'cogguard-preview-refresh-token'

export interface AuthUserInfo {
  id: number
  username: string
  email: string
  role: string
}

const PREVIEW_USER = {
  id: 0,
  username: 'Preview',
  email: 'preview@local',
  role: 'designer',
} satisfies AuthUserInfo

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref(localStorage.getItem('access_token') || '')
  const refreshToken = ref(localStorage.getItem('refresh_token') || '')
  const userInfo = ref<AuthUserInfo | null>(
    localStorage.getItem('cogguard_preview') === '1' ? PREVIEW_USER : null,
  )

  const isLoggedIn = computed(() => !!accessToken.value)
  const isPreviewMode = computed(() => accessToken.value === PREVIEW_ACCESS_TOKEN)

  async function login(username: string, password: string) {
    const res = await loginApi({ username, password }) as { data: { access_token: string; refresh_token: string } }
    accessToken.value = res.data.access_token
    refreshToken.value = res.data.refresh_token
    userInfo.value = null
    localStorage.removeItem('cogguard_preview')
    localStorage.setItem('access_token', res.data.access_token)
    localStorage.setItem('refresh_token', res.data.refresh_token)
  }

  async function fetchProfile() {
    if (isPreviewMode.value) {
      userInfo.value = PREVIEW_USER
      return
    }
    const res = await getProfileApi() as { data: AuthUserInfo }
    userInfo.value = res.data
  }

  function enablePreview() {
    accessToken.value = PREVIEW_ACCESS_TOKEN
    refreshToken.value = PREVIEW_REFRESH_TOKEN
    userInfo.value = PREVIEW_USER
    localStorage.setItem('access_token', PREVIEW_ACCESS_TOKEN)
    localStorage.setItem('refresh_token', PREVIEW_REFRESH_TOKEN)
    localStorage.setItem('cogguard_preview', '1')
  }

  function logout() {
    accessToken.value = ''
    refreshToken.value = ''
    userInfo.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('cogguard_preview')
    router.push('/login')
  }

  return {
    accessToken,
    refreshToken,
    userInfo,
    isLoggedIn,
    isPreviewMode,
    login,
    fetchProfile,
    enablePreview,
    logout,
  }
})
