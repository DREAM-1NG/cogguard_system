import axios from 'axios'
import type { AxiosInstance } from 'axios'
import { message } from 'ant-design-vue'
import router from '@/router'

export function createApiClient(baseURL: string, timeout = 30000): AxiosInstance {
  const client = axios.create({ baseURL, timeout })

  client.interceptors.request.use((config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  })

  client.interceptors.response.use(
    (response) => {
      const data = response.data
      if (data.code !== undefined && data.code !== 0) {
        if (!response.config.url?.includes('/auth/login')) {
          message.error(data.msg || '请求失败')
        }
        return Promise.reject(new Error(data.msg || '请求失败'))
      }
      return data
    },
    (error) => {
      const requestUrl = String(error.config?.url || '')
      const isLoginRequest = requestUrl.includes('/auth/login')
      if (error.response?.status === 401) {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        if (!isLoginRequest) {
          router.push('/login')
          message.error('登录已过期，请重新登录')
        }
      } else if (!isLoginRequest) {
        const fallback = error.response?.status >= 500 ? '服务暂不可用，请稍后重试' : '网络错误'
        message.error(error.response?.data?.detail || error.response?.data?.msg || error.message || fallback)
      }
      return Promise.reject(Object.assign(error, { requestUrl }))
    },
  )

  return client
}

const request = createApiClient('/api/v1')
export default request
