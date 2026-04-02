/**
 * Axios 请求封装
 *
 * - 自动附加 JWT Token 到 Authorization header
 * - 401 响应时清除本地 Token 并跳转登录页
 * - 统一处理后端 { code, data, msg } 响应格式
 */
import axios from 'axios'
import { message } from 'ant-design-vue'
import router from '@/router'

const request = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

/** 请求拦截器：注入 Token */
request.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

/** 响应拦截器：统一错误处理 */
request.interceptors.response.use(
  (response) => {
    const data = response.data
    if (data.code !== undefined && data.code !== 0) {
      message.error(data.msg || '请求失败')
      return Promise.reject(new Error(data.msg))
    }
    return data
  },
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      router.push('/login')
      message.error('登录已过期，请重新登录')
    } else {
      message.error(error.response?.data?.msg || error.message || '网络错误')
    }
    return Promise.reject(error)
  },
)

export default request
