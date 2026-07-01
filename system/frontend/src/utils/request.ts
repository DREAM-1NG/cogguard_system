import axios from 'axios'
import { message } from 'ant-design-vue'
import router from '@/router'

const request = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

request.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

request.interceptors.response.use(
  (response) => {
    const data = response.data
    if (data.code !== undefined && data.code !== 0) {
      if (!response.config.url?.includes('/auth/login')) {
        message.error(data.msg || '请求失败')
      }
      return Promise.reject(new Error(data.msg))
    }
    return data
  },
  (error) => {
    const isPreviewMode = localStorage.getItem('cogguard_preview') === '1'
    const requestUrl = String(error.config?.url || '')
    const isLoginRequest = requestUrl.includes('/auth/login')
    const suppressPreviewAuthToast = isPreviewMode && requestUrl.includes('/coordination/detect')
    if (error.response?.status === 401) {
      if (!isPreviewMode) {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        if (!isLoginRequest) {
          router.push('/login')
        }
      }
      if (!suppressPreviewAuthToast && !isLoginRequest) {
        message.error(isPreviewMode ? '预览态接口需要真实登录或数据库服务' : '登录已过期，请重新登录')
      }
    } else {
      const fallback = error.response?.status >= 500 ? '服务暂不可用，请稍后重试' : '网络错误'
      if (!isLoginRequest) {
        message.error(error.response?.data?.msg || error.message || fallback)
      }
    }
    return Promise.reject(error)
  },
)

export default request
