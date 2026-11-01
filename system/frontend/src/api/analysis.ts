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

export type SemanticPageView = 'evidence' | 'clusters' | 'entities' | 'temporal' | 'verifiable'

export interface SemanticCount {
  key: string
  label: string
  count: number
}

export interface SemanticCommunityProjection {
  community_id: string
  member_count: number
  item_count: number
  topics: SemanticCount[]
}

export interface SemanticEntityGroupProjection {
  type: string
  total: number
  items: SemanticCount[]
}

export interface SemanticTraceableRecord {
  id: string
  layer: 'posts' | 'comments'
  platform: string
  timestamp: string
  text: string
  source_url: string | null
  evidence_ref: string
  date?: string
  text_truncated?: boolean
  keywords?: string[]
  topics?: string[]
  sentiment?: string
  stance?: string
  entities?: Array<{
    key: string
    text: string
    label: string
  }>
}

export interface SemanticPageContent {
  keywords?: SemanticCount[]
  sentiment?: SemanticCount[]
  stance?: SemanticCount[]
  topics?: SemanticCount[]
  communities?: SemanticCommunityProjection[]
  groups?: SemanticEntityGroupProjection[]
  time_slices?: SemanticCount[]
  platforms?: SemanticCount[]
  items?: SemanticTraceableRecord[]
  page?: number
  page_size?: number
  total?: number
}

export interface SemanticPageProjection {
  event_id: string
  run_id: string | null
  snapshot_id: string | null
  status: 'ready' | 'blocked' | 'not_found'
  blocking_reason: string | null
  view: SemanticPageView
  summary: {
    record_count: number
    platform_count: number
  } | null
  content: SemanticPageContent | null
}

export type SemanticWorkspaceLayer = 'all' | 'posts' | 'comments'

export interface SemanticWorkspaceFilters {
  layer: SemanticWorkspaceLayer
  platforms: string[]
  date: string | null
  keyword: string | null
  topic: string | null
  sentiment: string | null
  stance: string | null
  entity: string | null
}

export interface SemanticFacetRelation {
  key: string
  label: string
  type: string | null
  count: number
  sentiment: SemanticCount[]
  stance: SemanticCount[]
  topics: SemanticCount[]
  keywords: SemanticCount[]
  entities: SemanticCount[]
  platforms: SemanticCount[]
  time_slices: SemanticCount[]
}

export interface SemanticWorkspaceContent {
  evidence: {
    keywords: SemanticCount[]
    sentiment: SemanticCount[]
    stance: SemanticCount[]
  }
  clusters: {
    topics: SemanticCount[]
    communities: SemanticCommunityProjection[]
  }
  entities: {
    groups: SemanticEntityGroupProjection[]
  }
  temporal: {
    time_slices: SemanticCount[]
    platforms: SemanticCount[]
  }
  relations: Record<string, SemanticFacetRelation[]>
  traceable: {
    items: SemanticTraceableRecord[]
    page: number
    page_size: number
    total: number
  }
}

export interface SemanticWorkspaceProjection {
  event_id: string
  run_id: string | null
  snapshot_id: string | null
  status: 'ready' | 'blocked' | 'not_found'
  blocking_reason: string | null
  summary: {
    record_count: number
    platform_count: number
  } | null
  content: SemanticWorkspaceContent | null
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

export function getSemanticPageProjection(
  eventId: string,
  view: SemanticPageView,
  page = 1,
  pageSize = 40,
) {
  return analysisRequest.get<unknown, ApiEnvelope<SemanticPageProjection>>(
    `/events/${encodeURIComponent(eventId)}/semantic/views/${encodeURIComponent(view)}`,
    { params: { page, page_size: pageSize } },
  )
}

export function getSemanticWorkspace(
  eventId: string,
  filters: Partial<SemanticWorkspaceFilters> & { page?: number; pageSize?: number } = {},
) {
  const platforms = filters.platforms?.filter(Boolean).join(',') || undefined
  return analysisRequest.get<unknown, ApiEnvelope<SemanticWorkspaceProjection>>(
    `/events/${encodeURIComponent(eventId)}/semantic/workspace`,
    {
      params: {
        page: filters.page || 1,
        page_size: filters.pageSize || 40,
        layer: filters.layer || 'all',
        platforms,
        date: filters.date || undefined,
        keyword: filters.keyword || undefined,
        topic: filters.topic || undefined,
        sentiment: filters.sentiment || undefined,
        stance: filters.stance || undefined,
        entity: filters.entity || undefined,
      },
    },
  )
}
