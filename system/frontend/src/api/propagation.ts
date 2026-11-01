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
  horizon_hours?: number | null
  at?: string | null
  predicted_size: number
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
  note?: string | null
}

export type PropagationPredictionResponse = {
  code: number
  data: PropagationPredictionData
  msg: string
}

export function predictPropagationCurrentEvent(params?: PropagationPredictionParams): Promise<PropagationPredictionResponse> {
  return request.post('/propagation/model-event-predict', null, { params }) as unknown as Promise<PropagationPredictionResponse>
}

export type PropagationMonitorProfile = {
  id: number
  event_id: string
  platform?: string | null
  enabled: boolean
  interval_minutes: number
  thresholds: Record<string, Record<string, number>>
  last_snapshot_id?: string | null
  last_success_at?: string | null
  last_error?: string | null
}

export type PropagationAlert = {
  id: number
  event_id: string
  platform?: string | null
  alert_type: string
  alert_type_label: string
  severity: 'medium' | 'high' | 'critical' | string
  severity_label: string
  state: 'new' | 'acknowledged' | 'closed' | 'ignored' | string
  state_label: string
  trigger_count: number
  first_triggered_at?: string | null
  last_triggered_at?: string | null
  snapshot_id?: string | null
  model_version_id?: number | null
  assigned_to?: number | null
  evidence: Record<string, unknown>
  closed_at?: string | null
  actions?: Array<{
    id: number
    action: string
    note?: string | null
    actor_id: number
    created_at?: string | null
  }>
}

export function getPropagationMonitorProfiles(params?: { event_id?: string }) {
  return request.get('/propagation/monitor-profiles', { params }) as unknown as Promise<{ data: PropagationMonitorProfile[] }>
}

export function putPropagationMonitorProfile(payload: {
  event_id: string
  platform?: string
  enabled: boolean
  interval_minutes: number
  thresholds?: Record<string, Record<string, number>>
}) {
  return request.put('/propagation/monitor-profiles', payload) as unknown as Promise<{ data: PropagationMonitorProfile }>
}

export function getPropagationAlerts(params?: {
  event_id?: string
  platform?: string
  state?: string
  unresolved_only?: boolean
  limit?: number
}) {
  return request.get('/propagation/alerts', { params }) as unknown as Promise<{ data: PropagationAlert[] }>
}

export function getPropagationAlertDetail(alertId: number) {
  return request.get(`/propagation/alerts/${alertId}`) as unknown as Promise<{ data: PropagationAlert }>
}

export function postPropagationAlertAction(alertId: number, payload: { action: 'acknowledge' | 'close' | 'ignore'; note?: string }) {
  return request.post(`/propagation/alerts/${alertId}/actions`, payload) as unknown as Promise<{ data: PropagationAlert }>
}

export function getPropagationUnresolvedAlertCount() {
  return request.get('/propagation/alerts/unresolved-count') as unknown as Promise<{ data: { count: number } }>
}
