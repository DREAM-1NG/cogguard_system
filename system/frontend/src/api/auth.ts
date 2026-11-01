/**
 * 认证相关 API
 *
 * 封装登录、注册、令牌刷新和用户信息获取请求。
 */
import request from '@/utils/request'

/** 用户登录，返回 access_token + refresh_token */
export function login(data: { username: string; password: string }) {
  return request.post('/auth/login', data)
}

/** 用户注册 */
export function register(data: { username: string; email: string; password: string }) {
  return request.post('/auth/register', data)
}

/** 使用 refresh_token 换取新令牌对 */
export function refreshToken(refreshToken: string) {
  return request.post('/auth/refresh', { refresh_token: refreshToken })
}

/** 获取当前登录用户信息 */
export function getProfile() {
  return request.get('/auth/profile')
}
