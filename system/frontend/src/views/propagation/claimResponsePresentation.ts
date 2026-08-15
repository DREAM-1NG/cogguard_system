import type {
  ClaimResponseClaimAnchor,
  ClaimResponseInfluentialResponse,
  ClaimResponseLandscapeProjection,
  ClaimResponsePathRef,
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
