import request from '@/utils/request'

export function getAccountProfiles(params?: { platform?: string }) {
  return request.get('/accounts/profiles', { params })
}

export function getAccountDetail(accountId: string) {
  return request.get(`/accounts/detail/${accountId}`)
}
