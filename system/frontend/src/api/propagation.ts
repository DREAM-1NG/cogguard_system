import request from '@/utils/request'

export function analyzePropagation(params?: { platform?: string; event_id?: string; node_limit?: number }) {
  return request.get('/propagation/analyze', { params })
}

export function analyzeObservedPropagation(params?: { platform?: string; event_id?: string; node_limit?: number }) {
  return request.get('/propagation/observed-analysis', { params })
}

export type PropagationPredictionParams = {
  platform?: string
  event_id?: string
  top_k?: number
  observed_until?: string
  observation_ratio?: number
}

export type PredictionCalibrationStatus = 'available' | 'unavailable'

export type PredictionTrendPoint = {
  step: number
  at?: string | null
  predicted_size: number
}

export type PredictionCumulativeTimelinePoint = {
  at: string
  cumulative_size: number
}

export type PropagationTimelineRange = 'active' | '24h' | '7d' | 'all'

export type PropagationTimelineWindow = {
  start: string
  end: string
}

export type PropagationEventTimelineProjection = {
  range: PropagationTimelineRange
  resolution: 'minute' | 'hour' | 'day' | 'week'
  active_window?: PropagationTimelineWindow | null
  window?: PropagationTimelineWindow | null
  observed_points: PredictionCumulativeTimelinePoint[]
  realized_points: PredictionCumulativeTimelinePoint[]
}

export type PropagationEventTimelineParams = {
  event_id: string
  platform?: string
  timeline_range?: PropagationTimelineRange
}

export type ClaimResponseLandscapeParams = {
  event_id: string
  platform?: string
}

export type ClaimResponseClaimAnchor = {
  case_id: string
  claim_id: string
  authority_source_id: string
  text: string
  source_url?: string | null
  account?: string | null
  published_at?: string | null
  role?: string | null
  source_review_status?: string | null
  source_tier?: string | null
  evidence_refs?: string[]
}

export type ClaimResponsePublication = {
  post_id: string
  platform: string
  author_id: string
  author_name?: string | null
  content?: string | null
  published_at?: string | null
  source_url?: string | null
  authority_binding?: {
    source_id: string
    platform: string
    author_id: string
  }
  verification_context?: Record<string, unknown>
  engagement_percentile?: number | null
  evidence_refs?: string[]
}

export type ClaimResponsePathRef = {
  path_id: string
  evidence_refs: string[]
  nodes?: string[]
  score?: number | null
}

export type ClaimResponseInfluentialResponse = {
  rank?: number
  platform: string
  author_id: string
  author_name?: string | null
  rank_scope?: string | null
  downstream_reach?: number | null
  path_contribution?: number | null
  path_count?: number | null
  engagement_percentile?: number | null
  first_seen_at?: string | null
  evidence_refs?: string[]
  path_refs?: ClaimResponsePathRef[]
  stance?: string | null
}

export type ClaimResponseTimelineItem = {
  type: 'official_publication' | 'influential_response' | string
  at?: string | null
  platform?: string | null
  author_id?: string | null
  post_id?: string | null
  rank?: number | null
  evidence_refs?: string[]
  path_refs?: ClaimResponsePathRef[]
}

export type ClaimResponseLandscapeProjection = {
  status: 'ready' | 'not_found' | 'blocked'
  event_id: string
  platform?: string | null
  blocking_reason?: string | null
  claim_anchor?: ClaimResponseClaimAnchor | null
  official_publications: ClaimResponsePublication[]
  influential_responses: ClaimResponseInfluentialResponse[]
  timeline: ClaimResponseTimelineItem[]
  coverage: Record<string, any>
  capability?: Record<string, unknown>
  data_scope?: Record<string, unknown>
}

export type PredictionInterval = {
  step: number | string
  at?: string | null
  timestamp?: string | null
  lower?: number | null
  upper?: number | null
}

export type PredictionCoverage = {
  mapped_candidate_buckets: number
  unmapped_candidate_buckets: number
  legal_candidate_buckets: number
  mapped_probability_mass: number
  new_activation_status: string
  identity_mapping_status: string
  ambiguous_mapped_buckets?: number
  excluded_ambiguous_users?: number
  unique_identity_probability_mass?: number
}

export type PredictionDataScope = {
  event_id?: string | null
  platform?: string | null
  observed_until?: string | null
  observation_ratio?: number
  actual_observation_ratio?: number
  checkpoint_conditioning_ratio?: number
  prediction_horizon_hours?: number | null
  trajectory_time_basis?: string
  posts?: number
  comments?: number
  observed_post_count?: number
  observed_comment_count?: number
  loaded_event_count?: number
  model_input_event_count?: number
  model_observed_event_count?: number
  prefix_selection?: 'timestamp_cutoff' | 'observation_ratio' | string
  excluded_after_cutoff?: {
    posts: number
    comments: number
  }
}

export type PredictionModelScope = {
  name?: string | null
  dataset?: string | null
  checkpoint?: string | null
  methodology?: string | null
  scope?: 'current_event' | 'research_benchmark' | string | null
}

export type PropagationPredictionData = {
  status: string
  model_status: 'available' | 'unavailable'
  event_id?: string | null
  platform?: string | null
  macro: {
    observed_size: number
    predicted_size?: number | null
    trend_points: PredictionTrendPoint[]
    observed_points?: PredictionCumulativeTimelinePoint[]
    realized_points?: PredictionCumulativeTimelinePoint[]
    intervals?: PredictionInterval[] | null
    direction?: string | null
    score_concentration?: number | null
    calibration_status: PredictionCalibrationStatus
  }
  micro: {
    top_users: unknown[]
    candidate_count: number
    candidate_bucket_count?: number
    coverage: PredictionCoverage
  }
  data_scope: PredictionDataScope
  model?: PredictionModelScope | null
  methodology?: Record<string, unknown> | null
  prediction_boundary?: Record<string, unknown> | null
  cache?: {
    hit: boolean
    stale: boolean
    snapshot_fingerprint?: string | null
    generated_at?: string | null
  } | null
  note?: string | null
}

export type PropagationPredictionResponse = {
  code: number
  data: PropagationPredictionData
  msg: string
}

export type PropagationAlertAction = 'acknowledge' | 'close' | 'ignore'

export type PropagationAlert = {
  id: number
  event_id: string
  platform?: string | null
  type: string
  severity: string
  state: string
  trigger_count: number
  first_triggered_at?: string | null
  last_triggered_at?: string | null
  snapshot_id?: string | null
  assigned_to?: number | null
  evidence?: Record<string, unknown>
  closed_at?: string | null
  actions?: Array<{
    id: number
    action: PropagationAlertAction
    note?: string | null
    actor_id: number
    created_at?: string | null
  }>
}

export function predictPropagationCurrentEvent(params?: PropagationPredictionParams): Promise<PropagationPredictionResponse> {
  return request.post('/propagation/model-event-predict', null, { params: { ...params, force_refresh: true } }) as unknown as Promise<PropagationPredictionResponse>
}

export function getCachedPropagationPrediction(params?: PropagationPredictionParams): Promise<PropagationPredictionResponse> {
  return request.get('/propagation/model-event-predict/cached', { params }) as unknown as Promise<PropagationPredictionResponse>
}

export function getPropagationEventTimeline(
  params: PropagationEventTimelineParams,
): Promise<{ code: number; data: PropagationEventTimelineProjection; msg: string }> {
  return request.get('/propagation/model-event-timeline', { params }) as unknown as Promise<{ code: number; data: PropagationEventTimelineProjection; msg: string }>
}

export function getClaimResponseLandscape(params: ClaimResponseLandscapeParams): Promise<{ code: number; data: ClaimResponseLandscapeProjection; msg: string }> {
  return request.get('/propagation/claim-response-landscape', { params }) as unknown as Promise<{ code: number; data: ClaimResponseLandscapeProjection; msg: string }>
}

export function getPropagationAlerts(params?: {
  event_id?: string
  platform?: string
  unresolved_only?: boolean
}): Promise<{ code: number; data: PropagationAlert[]; msg: string }> {
  return request.get('/propagation/alerts', { params }) as unknown as Promise<{ code: number; data: PropagationAlert[]; msg: string }>
}

export function getPropagationAlertDetail(alertId: number): Promise<{ code: number; data: PropagationAlert; msg: string }> {
  return request.get(`/propagation/alerts/${alertId}`) as unknown as Promise<{ code: number; data: PropagationAlert; msg: string }>
}

export function applyPropagationAlertAction(
  alertId: number,
  action: PropagationAlertAction,
  note?: string,
): Promise<{ code: number; data: PropagationAlert; msg: string }> {
  return request.post(`/propagation/alerts/${alertId}/actions`, { action, note }) as unknown as Promise<{ code: number; data: PropagationAlert; msg: string }>
}
