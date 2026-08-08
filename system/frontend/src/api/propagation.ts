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
