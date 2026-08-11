import axios from 'axios'
import { message } from 'ant-design-vue'
import router from '@/router'
import type {
  ApiEnvelope,
  CaseActionDecisionRequest,
  CaseBlockerAcknowledgementRequest,
  CaseCloseoutReviewRequest,
  CaseDetail,
  CaseFeedbackRequest,
  CasePage,
  CaseSemanticCorrectionRequest,
} from '@/types/case'

const caseRequest = axios.create({
  baseURL: '/api/v2/cases',
  timeout: 120000,
})

caseRequest.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

caseRequest.interceptors.response.use(
  (response) => {
    const data = response.data
    if (data.code !== undefined && data.code !== 0) {
      message.error(data.msg || '请求失败')
      return Promise.reject(new Error(data.msg))
    }
    return data
  },
  (error) => {
    const isPreviewMode = localStorage.getItem('cogguard_preview') === '1'
    if (error.response?.status === 401 && !isPreviewMode) {
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

export interface CaseListParams {
  event_id?: string
}

export function listCases(params: CaseListParams = {}): Promise<ApiEnvelope<CasePage>> {
  return caseRequest.get('', { params })
}

export function getCase(caseId: string): Promise<ApiEnvelope<CaseDetail>> {
  return caseRequest.get(`/${encodeURIComponent(caseId)}`)
}

export function completeCaseAction(
  caseId: string,
  actionId: string,
  body: CaseActionDecisionRequest = {},
): Promise<ApiEnvelope<CaseDetail>> {
  return caseRequest.post(
    `/${encodeURIComponent(caseId)}/actions/${encodeURIComponent(actionId)}/complete`,
    body,
  )
}

export function waiveCaseAction(
  caseId: string,
  actionId: string,
  body: CaseActionDecisionRequest = {},
): Promise<ApiEnvelope<CaseDetail>> {
  return caseRequest.post(
    `/${encodeURIComponent(caseId)}/actions/${encodeURIComponent(actionId)}/waive`,
    body,
  )
}

export function submitCaseFeedback(
  caseId: string,
  body: CaseFeedbackRequest,
): Promise<ApiEnvelope<CaseDetail>> {
  return caseRequest.post(`/${encodeURIComponent(caseId)}/feedback`, body)
}

export function recordSemanticCorrection(
  caseId: string,
  artifactId: string,
  body: CaseSemanticCorrectionRequest,
): Promise<ApiEnvelope<CaseDetail>> {
  return caseRequest.post(
    `/${encodeURIComponent(caseId)}/semantic-artifacts/${encodeURIComponent(artifactId)}/corrections`,
    body,
  )
}

export function submitCaseCloseoutReview(
  caseId: string,
  body: CaseCloseoutReviewRequest,
): Promise<ApiEnvelope<CaseDetail>> {
  return caseRequest.post(`/${encodeURIComponent(caseId)}/closeout`, body)
}

export function acknowledgeCaseBlocker(
  caseId: string,
  blockerId: string,
  body: CaseBlockerAcknowledgementRequest,
): Promise<ApiEnvelope<CaseDetail>> {
  return caseRequest.post(
    `/${encodeURIComponent(caseId)}/blockers/${encodeURIComponent(blockerId)}/acknowledge`,
    body,
  )
}

export function fetchCaseReport(reportUrl: string): Promise<Blob> {
  const requestUrl = reportUrl.startsWith('/api/v2/cases')
    ? reportUrl.slice('/api/v2/cases'.length)
    : reportUrl
  return caseRequest.get<Blob, Blob>(requestUrl, { responseType: 'blob' })
}

export function caseReportUrl(caseId: string, version: number, format: 'html' | 'pdf'): string {
  return `/api/v2/cases/${encodeURIComponent(caseId)}/reports/${version}.${format}`
}

export function caseEventStreamUrl(caseId: string, afterId = 0): string {
  return `/api/v2/cases/${encodeURIComponent(caseId)}/events/stream?after_id=${Math.max(0, afterId)}`
}
