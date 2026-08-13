import { createApiClient } from '@/utils/request'

interface ApiEnvelope<T> {
  code?: number
  msg?: string
  data: T
}

const analysisRequest = createApiClient('/api/v2/analysis', 120000)

export function getAnalysisArtifact(runId: string, artifactKey = 'stage:semantic_enrichment:result') {
  return analysisRequest.get<unknown, ApiEnvelope<Record<string, any>>>(
    `/runs/${encodeURIComponent(runId)}/artifacts/${artifactKey}`,
  )
}

