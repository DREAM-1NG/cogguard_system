import { createApiClient } from '@/utils/request'

const accountRequest = createApiClient('/api/v1', 120000)

export function getAccountProfiles(params?: { platform?: string; event_id?: string }) {
  return accountRequest.get('/accounts/profiles', { params })
}

export function getAccountDetail(accountId: string) {
  return accountRequest.get(`/accounts/detail/${accountId}`)
}
