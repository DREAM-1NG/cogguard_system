import request from '@/utils/request'

export function getAccountProfiles(params?: { platform?: string; event_id?: string }) {
  return request.get('/accounts/profiles', { params })
}

export function runSocialBotDetection(params?: {
  platform?: string
  event_id?: string
  routing_budget?: number
}) {
  return request.post('/accounts/bot-detection', null, { params })
}

export function getAccountDetail(accountId: string) {
  return request.get(`/accounts/detail/${accountId}`)
}
