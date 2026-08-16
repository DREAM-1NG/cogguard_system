import type {
  ClaimResponseClaimAnchor,
  ClaimResponseInfluentialResponse,
  ClaimResponseLandscapeProjection,
  ClaimResponsePathRef,
  ClaimResponseSemanticOverlay,
} from '@/api/propagation'

export type ClaimResponsePresentation = {
  status: ClaimResponseLandscapeProjection['status'] | 'empty'
  isReady: boolean
  anchor: ClaimResponseClaimAnchor | null
  lanes: {
    officialPublications: ClaimResponseLandscapeProjection['official_publications']
    influentialResponses: ClaimResponseInfluentialResponse[]
    timeline: ClaimResponseLandscapeProjection['timeline']
  }
  emptyLanes: {
    officialPublications: boolean
    influentialResponses: boolean
    timeline: boolean
  }
}

export type ClaimResponsePathDrilldown = {
  pathId: string
  nodes: string[]
  evidenceRefs: string[]
  authorityAccount: string
  authoritySourceId: string
  responseAccount: string
  pathScore?: number
  contribution?: number
}

export function presentClaimResponseLandscape(
  projection: ClaimResponseLandscapeProjection | null | undefined,
): ClaimResponsePresentation {
  const anchor = projection?.claim_anchor ?? null
  const lanes = {
    officialPublications: projection?.official_publications ?? [],
    influentialResponses: projection?.influential_responses ?? [],
    timeline: projection?.timeline ?? [],
  }
  return {
    status: projection?.status ?? 'empty',
    isReady: projection?.status === 'ready' && Boolean(anchor),
    anchor,
    lanes,
    emptyLanes: {
      officialPublications: lanes.officialPublications.length === 0,
      influentialResponses: lanes.influentialResponses.length === 0,
      timeline: lanes.timeline.length === 0,
    },
  }
}

export function createClaimResponsePathDrilldown({
  anchor,
  response,
  pathRef,
}: {
  anchor: ClaimResponseClaimAnchor | null | undefined
  response: ClaimResponseInfluentialResponse
  pathRef: ClaimResponsePathRef
  index?: number
}): ClaimResponsePathDrilldown | null {
  const nodes = (pathRef.nodes ?? []).map((node) => String(node || '').trim()).filter(Boolean)
  const evidenceRefs = (pathRef.evidence_refs ?? []).map((ref) => String(ref || '').trim()).filter(Boolean)
  if (!nodes.length || !evidenceRefs.length) return null
  const pathScore = pathRef.score ?? response.path_contribution ?? undefined
  const contribution = response.path_contribution ?? undefined
  return {
    pathId: pathRef.path_id,
    nodes,
    evidenceRefs,
    authorityAccount: String(anchor?.account || '').trim(),
    authoritySourceId: String(anchor?.authority_source_id || '').trim(),
    responseAccount: String(response.author_name || response.author_id || '').trim(),
    ...(pathScore === undefined ? {} : { pathScore }),
    ...(contribution === undefined ? {} : { contribution }),
  }
}

export function selectClaimResponseSemanticOverlay(path: unknown): ClaimResponseSemanticOverlay | null {
  if (!isRecord(path) || !isRecord(path.metadata) || path.metadata.claim_response !== true) return null
  const overlay = path.metadata.claim_response_semantic_overlay
  if (!isClaimResponseSemanticOverlay(overlay)) return null
  const pathRefs = canonicalEvidenceRefs(path.evidence_refs)
  const overlayRefs = canonicalEvidenceRefs(overlay.evidence_refs)
  if (!pathRefs.length || pathRefs.length !== overlayRefs.length) return null
  if (!pathRefs.slice().sort().every((ref, index) => ref === overlayRefs.slice().sort()[index])) return null
  return { ...overlay, evidence_refs: overlayRefs }
}

export function claimResponseDownstreamReachText(
  response: Pick<ClaimResponseInfluentialResponse, 'downstream_reach_status' | 'downstream_reach_reason'>,
): string | null {
  return response.downstream_reach_status === 'unavailable'
    && response.downstream_reach_reason === 'direct_comment_thread_network_reach_not_computed'
    ? '评论链路径，未计算网络下游覆盖'
    : null
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function canonicalEvidenceRefs(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  const refs = value.map(canonicalEvidenceRef)
  return refs.some((ref) => !ref) ? [] : refs
}

function canonicalEvidenceRef(value: unknown): string {
  if (typeof value !== 'string') return ''
  const [platform, kind, ...idParts] = value.trim().split(':')
  const id = idParts.join(':').trim()
  return platform?.trim() && id && (kind === 'post' || kind === 'comment')
    ? `${platform.trim()}:${kind}:${id}`
    : ''
}

function isClaimResponseSemanticOverlay(value: unknown): value is ClaimResponseSemanticOverlay {
  if (!isRecord(value) || !isRecord(value.time_range)) return false
  const evidenceRefs = value.evidence_refs
  return hasDistribution(value.sentiment)
    && hasFeatures(value.keywords, 'term')
    && hasFeatures(value.topics, 'label')
    && hasFeatures(value.entities, 'text')
    && hasDistribution(value.stance)
    && hasTextList(value.platforms)
    && hasText(value.time_range.start)
    && hasText(value.time_range.end)
    && Array.isArray(evidenceRefs)
    && canonicalEvidenceRefs(evidenceRefs).length === evidenceRefs.length
}

function hasDistribution(value: unknown): value is Record<string, number> {
  return isRecord(value) && Object.keys(value).length > 0 && Object.entries(value).every(
    ([label, count]) => hasText(label) && typeof count === 'number' && Number.isFinite(count) && count > 0,
  )
}

function hasFeatures(value: unknown, field: 'term' | 'label' | 'text'): boolean {
  return Array.isArray(value) && value.length > 0 && value.every((item) => (
    isRecord(item) && hasText(item[field]) && (item.count === undefined || (
      typeof item.count === 'number' && Number.isFinite(item.count) && item.count > 0
    ))
  ))
}

function hasTextList(value: unknown): value is string[] {
  return Array.isArray(value) && value.length > 0 && value.every(hasText)
}

function hasText(value: unknown): value is string {
  return typeof value === 'string' && Boolean(value.trim())
}
