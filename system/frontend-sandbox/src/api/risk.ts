/**
 * 风险研判相关 API。
 */
import request from '@/utils/request'

/** 执行风险评估。 */
export function assessRisk(params: {
  platform?: string
  event_id?: string
  time_window?: number
  min_participation?: number
  edge_weight?: number
}) {
  return request.post('/risk/assess', null, { params, timeout: 120000 })
}

/** 获取 Review Gate Dataset 机器可读契约。 */
export function getReviewGateDatasetContract() {
  return request.get('/risk/review/gate-dataset/contract')
}

/** 校验 Review Gate Dataset 契约，不执行风险评估。 */
export function validateReviewGateDataset(gate_dataset: Record<string, unknown>) {
  return request.post('/risk/review/gate-dataset/validate', { gate_dataset })
}

/** 执行 Review Gate Suite 离线验收，默认不持久化 gold/control 结果。 */
export function assessReviewGateSuite(body: {
  platform?: string
  event_id?: string
  time_window?: number
  min_participation?: number
  edge_weight?: number
  gate_dataset: Record<string, unknown>
}) {
  return request.post('/risk/review/gate-suite', body)
}

/** 创建人工触发的智能研判任务。 */
export function runReviewAgentReview(body: {
  report_id: string
  case_id?: string
  selected_post_ids?: string[]
  selected_tree_ids?: string[]
  agent_names: string[]
  runtime_mode?: 'auto' | 'simple' | 'complex'
  enable_active_retrieval?: boolean
  enable_light_debate?: boolean
  enable_full_debate?: boolean
  enable_deep_judge?: boolean
  debate_max_rounds?: number
  policy_id?: string
  active_policy_id?: string
  retrieval_top_k?: number
}) {
  return request.post('/risk/review/agent-reviews/run', body)
}

export function getReviewJob(jobId: number | string) {
  return request.get(`/risk/review/jobs/${jobId}`)
}

export function listReviewJobs(params?: {
  job_type?: string
  page?: number
  page_size?: number
}) {
  return request.get('/risk/review/jobs', { params })
}

export function recordReviewAgentFeedback(body: {
  report_id: string
  review_id?: string
  run_id?: string
  case_id?: string
  human_label?: string
  corrected_harmfulness?: string
  corrected_label?: string
  error_types?: string[]
  notes?: string
  evidence_refs?: Record<string, unknown>[]
  reviewer_confidence?: number
}) {
  return request.post('/risk/review/agent-feedback/record', body)
}

export function optimizeReviewPolicy(dataset_manifest: Record<string, unknown>) {
  return request.post('/risk/review/policies/optimize', { dataset_manifest })
}

export function refineReviewPolicy(body: {
  dataset_manifest: Record<string, unknown>
  feedback_report_ids?: string[]
  baseline_policy_id?: string
  max_iterations?: number
  enable_llm_rule_generator?: boolean
  held_out_required?: boolean
}) {
  return request.post('/risk/review/policies/refine', body)
}

export function listReviewPolicies(params?: {
  page?: number
  page_size?: number
}) {
  return request.get('/risk/review/policies', { params })
}

export function activateReviewPolicy(policyId: string) {
  return request.post(`/risk/review/policies/${policyId}/activate`)
}

export function getReviewPolicy(policyId: string) {
  return request.get(`/risk/review/policies/${policyId}`)
}

export function listReviewProviders() {
  return request.get('/risk/review/providers')
}

export function createReviewProvider(body: {
  name: string
  provider_type: string
  base_url?: string
  model?: string
  wire_api?: string
  api_key?: string
  supports_vision?: boolean
  metadata?: Record<string, unknown>
}) {
  return request.post('/risk/review/providers', body)
}

export function updateReviewProvider(providerId: number, body: {
  name?: string
  provider_type?: string
  base_url?: string
  model?: string
  wire_api?: string
  api_key?: string
  supports_vision?: boolean
  metadata?: Record<string, unknown>
}) {
  return request.put(`/risk/review/providers/${providerId}`, body)
}

export function activateReviewProvider(providerId: number, isActive = true) {
  return request.post(`/risk/review/providers/${providerId}/activate`, { is_active: isActive })
}

export function testReviewProvider(providerId: number) {
  return request.post(`/risk/review/providers/${providerId}/test`)
}

export function uploadReviewGateDataset(gate_dataset: Record<string, unknown>) {
  return request.post('/risk/review/gate-datasets', { gate_dataset })
}

export function listReviewGateDatasets(params?: {
  page?: number
  page_size?: number
}) {
  return request.get('/risk/review/gate-datasets', { params })
}

export function getReviewGateDatasetDetail(datasetDbId: number | string) {
  return request.get(`/risk/review/gate-datasets/${datasetDbId}`)
}

export function startReviewBackfill(body: {
  report_ids?: string[]
  limit?: number
}) {
  return request.post('/risk/review/backfill', body)
}

export function listRiskReports(params: {
  platform?: string
  event_id?: string
  risk_level?: string
  phase?: string
  page?: number
  page_size?: number
}) {
  return request.get('/risk/reports', { params })
}

/** 获取单个风险报告详情。 */
export function getRiskReportDetail(reportId: string) {
  return request.get(`/risk/reports/${reportId}`)
}
