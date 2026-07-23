import axios from 'axios'
import { message } from 'ant-design-vue'
import router from '@/router'

export type AnalysisStage = 'coordination_discover' | 'propagation_analysis' | 'student' | 'teacher'

export interface AnalysisTimeWindow {
  start: string
  end: string
}

export interface AnalysisSnapshotCreateRequest {
  event_id: string
  platform?: string
  core_window: AnalysisTimeWindow
  context_window: AnalysisTimeWindow
}

export interface AnalysisRunCreateRequest {
  event_id: string
  snapshot_id: string
  requested_stages: AnalysisStage[]
  options?: Record<string, unknown>
}

export interface AnalysisRunEvent {
  id: number
  run_id: string
  event_type: string
  status: string
  payload: Record<string, unknown>
}

const analysisRequest = axios.create({
  baseURL: '/api/v2/analysis',
  timeout: 120000,
})

analysisRequest.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

analysisRequest.interceptors.response.use(
  (response) => {
    const data = response.data
    if (data.code !== undefined && data.code !== 0) {
      message.error(data.msg || '请求失败')
      return Promise.reject(new Error(data.msg))
    }
    return data
  },
  (error) => {
    const requestUrl = String(error.config?.url || '')
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      router.push('/login')
      message.error('登录已过期，请重新登录')
    } else {
      const fallback = error.response?.status >= 500 ? '服务暂不可用，请稍后重试' : '网络错误'
      message.error(error.response?.data?.msg || error.message || fallback)
    }
    return Promise.reject(Object.assign(error, { requestUrl }))
  },
)

export function createAnalysisSnapshot(data: AnalysisSnapshotCreateRequest) {
  return analysisRequest.post('/snapshots', data)
}

export function createAnalysisRun(data: AnalysisRunCreateRequest) {
  return analysisRequest.post('/runs', data)
}

export function executeAnalysisRun(runId: string) {
  return analysisRequest.post(`/runs/${encodeURIComponent(runId)}/execute`)
}

export function getAnalysisRun(runId: string) {
  return analysisRequest.get(`/runs/${encodeURIComponent(runId)}`)
}

export function listAnalysisRunEvents(
  runId: string,
  params: { after_id?: number; limit?: number } = {},
) {
  return analysisRequest.get(`/runs/${encodeURIComponent(runId)}/events`, { params })
}

export function analysisStreamUrl(runId: string, afterId = 0) {
  const params = new URLSearchParams({ after_id: String(Math.max(0, afterId)) })
  return `/api/v2/analysis/runs/${encodeURIComponent(runId)}/events/stream?${params.toString()}`
}

export function analysisAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}
