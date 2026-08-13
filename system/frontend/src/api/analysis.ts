import { createApiClient } from '@/utils/request'

interface ApiEnvelope<T> {
  code?: number
  msg?: string
  data: T
}

export interface SemanticArtifactProjection {
  event_id: string
  run_id: string | null
  snapshot_id: string | null
  status: 'ready' | 'blocked' | 'not_found'
  blocking_reason: string | null
  artifact: Record<string, unknown> | null
}

export interface SemanticEvidenceProjection {
  event_id: string
  run_id: string | null
  snapshot_id: string | null
  status: 'ready' | 'blocked' | 'not_found'
  blocking_reason: string | null
  evidence: Record<string, unknown> | null
}

const analysisRequest = createApiClient('/api/v2/analysis', 120000)

export function getAnalysisArtifact(runId: string, artifactKey = 'stage:semantic_enrichment:result') {
  return analysisRequest.get<unknown, ApiEnvelope<Record<string, any>>>(
    `/runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(artifactKey)}`,
  )
}

export function getEventSemantic(eventId: string): Promise<ApiEnvelope<SemanticEvidenceProjection>> {
  return analysisRequest
    .get<unknown, ApiEnvelope<SemanticArtifactProjection>>(
      `/events/${encodeURIComponent(eventId)}/semantic`,
    )
    .then((response) => ({
      ...response,
      data: {
        event_id: response.data.event_id,
        run_id: response.data.run_id,
        snapshot_id: response.data.snapshot_id,
        status: response.data.status,
        blocking_reason: response.data.blocking_reason,
        evidence: response.data.artifact,
      },
    }))
}
