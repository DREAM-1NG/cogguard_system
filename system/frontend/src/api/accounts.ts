import { createApiClient } from '@/utils/request'

const accountRequest = createApiClient('/api/v1', 300000)

export type AccountQueryParams = {
  platform?: string
  event_id?: string
}

export type AccountModelPointerStatus = {
  status?: 'available' | 'unavailable' | 'invalid' | string
  reason?: string
  detail?: string
  model_version?: string
  artifact_hash?: string
  pointer_revision?: number
  governance_status?: string
  research_approved?: boolean
}

export type BotDetectionResult = {
  method?: string
  status?: 'available' | 'unavailable' | string
  reason?: string
  pointer_failure_reason?: string
  audit_status?: string
  audit_persisted_count?: number
  prediction_latency_ms?: number
  accounts?: Array<Record<string, any>>
  summary?: Record<string, any>
  model_card?: Record<string, any>
}

export function getAccountProfiles(params?: AccountQueryParams) {
  return accountRequest.get('/accounts/profiles', { params })
}

export function getAccountDetail(accountId: string, params?: AccountQueryParams) {
  return accountRequest.get(`/accounts/detail/${accountId}`, { params })
}

export function getActiveAccountModel() {
  return accountRequest.get('/accounts/models/active')
}

export function runSocialBotDetection(params?: AccountQueryParams) {
  return accountRequest.post('/accounts/bot-detection', undefined, { params })
}
