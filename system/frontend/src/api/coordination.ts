/**
 * Coordination model APIs
 */
import request from '@/utils/request'

export type CoordinationGraphNode = {
  id: string
  label: string
  nickname?: string | null
  platform?: string | null
  profile_url?: string | null
  cluster_id?: string | number | null
  node_score?: number | null
  score_role?: string | null
  archive_detection_score?: number | null
  archive_detection_label?: string | number | null
  community_score?: number | null
  community_size?: number | null
}

export type CoordinationGraphLink = {
  source: string
  target: string
  weight?: number | null
  edge_score?: number | null
  relations?: Record<string, number> | string[] | null
}

export type CoordinationGraphPayload = {
  nodes: CoordinationGraphNode[]
  links: CoordinationGraphLink[]
  summary: {
    total_nodes: number
    total_edges: number
    rendered_node_count: number
    rendered_edge_count: number
    filters: {
      node_limit: number
      min_node_score: number
    }
  }
}

export type CoordinationCommunityDetail = {
  cluster_id: string | number
  size?: number | null
  community_score?: number | null
  density?: number | null
  object_concentration?: number | null
  relation_breakdown?: Record<string, number> | null
  members: Array<{
    id: string
    label: string
    nickname?: string | null
    platform?: string | null
    profile_url?: string | null
    node_score?: number | null
    score_role?: string | null
    archive_detection_score?: number | null
    archive_detection_label?: string | number | null
    directed_out_weight?: number | null
    directed_in_weight?: number | null
  }>
  topwords?: Array<{
    term: string
    account_count: number
    frequency: number
  }>
  top_objects: Array<{
    object_id: string
    relation?: string | null
    relation_label?: string | null
    display_value?: string | null
    object_url?: string | null
    evidence_examples?: Array<{
      account_id?: string | null
      nickname?: string | null
      content?: string | null
      post_url?: string | null
      timestamp?: string | null
    }>
    count?: number | null
    share?: number | null
  }>
  run_summary?: {
    result_source?: string
    run_id?: number | null
    status?: string
  }
}

export type CoordinationDetectionVerdict = {
  cluster_id: string | number
  decision: 'harmful_coordination' | 'benign_coordination' | string
  harmful_probability: number
  model_version: string
  model_role: 'primary_socgfm_cross_attention' | string
  artifact_hash?: string | null
  warning?: string | null
  inference_mode: 'precomputed_member_probability_cluster_aggregation' | string
  member_probability_coverage: number
  online_neural_forward: false
  claim_scope: 'account_level_io_membership_to_cluster_proxy' | string
}

export type CoordinationGroupLabelReviewPayload = {
  case: Record<string, unknown>
  cluster_harm_label: 'harmful_coordination' | 'benign_coordination'
  reviewer_notes?: string
}

export function runCoordinationDetection(params: {
  time_window?: number
  min_participation?: number
  edge_weight?: number
  platform?: string
  event_id?: string
}) {
  return request.post('/coordination/detect', null, { params })
}

export function listCoordinationDatasets() {
  return request.get('/coordination/datasets')
}

export function getCoordinationDatasetDetail(datasetId: number) {
  return request.get(`/coordination/datasets/${datasetId}`)
}

export function getCoordinationDatasetLatestResult(datasetId: number) {
  return request.get(`/coordination/datasets/${datasetId}/latest-result`)
}

export function getCoordinationGraph(
  datasetId: number,
  params: { node_limit?: number; min_node_score?: number } = {},
) {
  return request.get(`/coordination/datasets/${datasetId}/graph`, { params })
}

export function getCoordinationCommunityDetail(
  datasetId: number,
  clusterId: string | number,
  params: { member_limit?: number } = {},
) {
  return request.get(`/coordination/datasets/${datasetId}/communities/${clusterId}`, { params })
}

export function createCoordinationRun(datasetId: number) {
  return request.post('/coordination/runs', { dataset_id: datasetId })
}

export function getCoordinationRun(runId: number) {
  return request.get(`/coordination/runs/${runId}`)
}

export function submitCoordinationGroupLabelReview(payload: CoordinationGroupLabelReviewPayload) {
  return request.post('/coordination/group-label-cases/reviews', payload)
}

export function uploadCoordinationDataset(file: File, displayName = '') {
  const formData = new FormData()
  formData.append('file', file)
  if (displayName.trim()) {
    formData.append('display_name', displayName.trim())
  }
  return request.post('/coordination/datasets/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
