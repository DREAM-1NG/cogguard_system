import { createApiClient } from '@/utils/request'

export type ServicePurpose = 'text_review' | 'media_verification' | 'source_retrieval'

export interface ServiceConfig {
  id: number | null
  name: string
  purpose: ServicePurpose
  endpoint: string
  enabled: boolean
  credential_configured: boolean
  supports_media: boolean
  source: 'configured' | 'environment'
}

export interface OperationHealth {
  processing_count: number
  waiting_count: number
  completed_count: number
  attention_required_count: number
  message: string
}

const systemOperationsRequest = createApiClient('/api/v2')

export function getOperationHealth() {
  return systemOperationsRequest.get('/system/operation-health')
}

export function listServiceConfigs() {
  return systemOperationsRequest.get('/system/services')
}

export function createServiceConfig(body: {
  name: string
  purpose: ServicePurpose
  endpoint?: string
  service_identifier?: string
  protocol?: string
  credential?: string
  supports_media?: boolean
}) {
  return systemOperationsRequest.post('/system/services', body)
}

export function setServiceEnabled(serviceId: number, enabled = true) {
  return systemOperationsRequest.post(`/system/services/${serviceId}/activation`, { enabled })
}

export function checkServiceConnection(serviceId: number) {
  return systemOperationsRequest.post(`/system/services/${serviceId}/connection-check`)
}
