import { createApiClient, handleUnauthorizedResponse } from '@/utils/request'
import type {
  CaseActivityList,
  CaseEvent,
  DecisionConfirmRequest,
  DecisionConfirmation,
  DecisionDraft,
  DecisionDraftUpsert,
  EvidenceAnnotation,
  EvidenceAnnotationCreate,
  EvidenceAssessment,
  ReviewCaseDetail,
  ReviewCaseEvidence,
  ReviewCaseList,
  ReviewRequestCreate,
  ReviewRequestReceipt,
  ReviewAudit,
} from '@/types/reviewCase'

interface ApiEnvelope<T> {
  code?: number
  msg?: string
  data: T
}

const reviewCaseRequest = createApiClient('/api/v2/review-cases', 120000)

export class CaseEventStreamError extends Error {
  constructor(readonly status: number) {
    super(`Event stream request failed (${status})`)
    this.name = 'CaseEventStreamError'
  }
}

export function isUnauthorizedCaseEventStreamError(error: unknown): boolean {
  return error instanceof CaseEventStreamError && error.status === 401
}

export function getLatestReviewCase() {
  return reviewCaseRequest.get<unknown, ApiEnvelope<ReviewCaseDetail>>('/latest')
}

export function searchReviewCases(params: { query?: string; limit?: number } = {}) {
  return reviewCaseRequest.get<unknown, ApiEnvelope<ReviewCaseList>>('', { params })
}

export function getReviewCase(caseId: string) {
  return reviewCaseRequest.get<unknown, ApiEnvelope<ReviewCaseDetail>>(`/${encodeURIComponent(caseId)}`)
}

export function getReviewCaseEvidence(
  caseId: string,
  params: { assessment?: EvidenceAssessment; cursor?: number; limit?: number } = {},
) {
  return reviewCaseRequest.get<unknown, ApiEnvelope<ReviewCaseEvidence>>(
    `/${encodeURIComponent(caseId)}/evidence`,
    { params },
  )
}

export function getReviewAudit(caseId: string) {
  return reviewCaseRequest.get<unknown, ApiEnvelope<ReviewAudit>>(
    `/${encodeURIComponent(caseId)}/teacher-audit`,
  )
}

export function annotateReviewCaseEvidence(caseId: string, body: EvidenceAnnotationCreate) {
  return reviewCaseRequest.post<unknown, ApiEnvelope<EvidenceAnnotation>>(
    `/${encodeURIComponent(caseId)}/evidence-annotations`,
    body,
  )
}

export function requestReviewAdvisory(caseId: string, body: ReviewRequestCreate) {
  return reviewCaseRequest.post<unknown, ApiEnvelope<ReviewRequestReceipt>>(
    `/${encodeURIComponent(caseId)}/review-requests`,
    body,
  )
}

export function saveDecisionDraft(caseId: string, body: DecisionDraftUpsert) {
  return reviewCaseRequest.put<unknown, ApiEnvelope<DecisionDraft>>(
    `/${encodeURIComponent(caseId)}/decision-draft`,
    body,
  )
}

export function confirmDecision(caseId: string, body: DecisionConfirmRequest) {
  return reviewCaseRequest.post<unknown, ApiEnvelope<DecisionConfirmation>>(
    `/${encodeURIComponent(caseId)}/decisions/confirm`,
    body,
  )
}

export function listCaseActivities(caseId: string, params: { after_id?: number; limit?: number } = {}) {
  return reviewCaseRequest.get<unknown, ApiEnvelope<CaseActivityList>>(
    `/${encodeURIComponent(caseId)}/activities`,
    { params },
  )
}

export async function readCaseEventStream(
  caseId: string,
  lastEventId = 0,
  signal?: AbortSignal,
): Promise<CaseEvent[]> {
  const token = localStorage.getItem('access_token')
  const response = await fetch(
    `/api/v2/review-cases/${encodeURIComponent(caseId)}/events/stream?after_id=${lastEventId}`,
    {
      headers: {
        Accept: 'text/event-stream',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(lastEventId > 0 ? { 'Last-Event-ID': String(lastEventId) } : {}),
      },
      signal,
    },
  )
  if (!response.ok) {
    if (response.status === 401) {
      handleUnauthorizedResponse()
    }
    throw new CaseEventStreamError(response.status)
  }
  return parseCaseEventStream(await response.text())
}

export function parseCaseEventStream(payload: string): CaseEvent[] {
  const events: CaseEvent[] = []
  for (const block of payload.split(/\r?\n\r?\n/)) {
    if (!block.trim()) continue
    let cursor = 0
    let activityType = ''
    let data = ''
    for (const line of block.split(/\r?\n/)) {
      if (line.startsWith('id:')) cursor = Number(line.slice(3).trim())
      if (line.startsWith('event:')) activityType = line.slice(6).trim()
      if (line.startsWith('data:')) data += line.slice(5).trim()
    }
    if (!cursor || !activityType || !data) continue
    const parsed = JSON.parse(data) as Omit<CaseEvent, 'cursor' | 'activity_type'>
    events.push({ ...parsed, cursor, activity_type: activityType as CaseEvent['activity_type'] })
  }
  return events
}
