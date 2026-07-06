/**
 * 风险研判相关 API
 */
import request from '@/utils/request'

/** 执行风险评估 */
export function assessRisk(params: {
  platform?: string
  event_id?: string
  time_window?: number
  min_participation?: number
  edge_weight?: number
}) {
  return request.post('/risk/assess', null, { params, timeout: 120000 })
}

/** 获取 KT3 Gate Dataset 机器可读契约 */
export function getKT3GateDatasetContract() {
  return request.get('/risk/kt3/gate-dataset/contract')
}

/** 校验 KT3 Gate Dataset 契约，不执行风险评估 */
export function validateKT3GateDataset(kt3_gate_dataset: Record<string, unknown>) {
  return request.post('/risk/kt3/gate-dataset/validate', { kt3_gate_dataset })
}

/** 执行 KT3 Gate Suite 离线验收，默认不持久化 gold/control 结果 */
export function assessKT3GateSuite(body: {
  platform?: string
  event_id?: string
  time_window?: number
  min_participation?: number
  edge_weight?: number
  kt3_gate_dataset: Record<string, unknown>
}) {
  return request.post('/risk/kt3/gate-suite', body)
}

/** 查询历史风险报告列表 */
export function runKT3AgentReview(body: {
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
  return request.post('/risk/kt3/agent-reviews/run', body)
}

export function getKT3Job(jobId: number | string) {
  return request.get(`/risk/kt3/jobs/${jobId}`)
}

export function listKT3Jobs(params?: {
  job_type?: string
  page?: number
  page_size?: number
}) {
  return request.get('/risk/kt3/jobs', { params })
}

export function recordKT3AgentFeedback(body: {
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
  return request.post('/risk/kt3/agent-feedback/record', body)
}

export function optimizeKT3Policy(dataset_manifest: Record<string, unknown>) {
  return request.post('/risk/kt3/policies/optimize', { dataset_manifest })
}

export function refineKT3Policy(body: {
  dataset_manifest: Record<string, unknown>
  feedback_report_ids?: string[]
  baseline_policy_id?: string
  max_iterations?: number
  enable_llm_rule_generator?: boolean
  held_out_required?: boolean
}) {
  return request.post('/risk/kt3/policies/refine', body)
}

export function listKT3Policies(params?: {
  page?: number
  page_size?: number
}) {
  return request.get('/risk/kt3/policies', { params })
}

export function activateKT3Policy(policyId: string) {
  return request.post(`/risk/kt3/policies/${policyId}/activate`)
}

export function getKT3Policy(policyId: string) {
  return request.get(`/risk/kt3/policies/${policyId}`)
}

export function listKT3Providers() {
  return request.get('/risk/kt3/providers')
}

export function createKT3Provider(body: {
  name: string
  provider_type: string
  base_url?: string
  model?: string
  wire_api?: string
  api_key?: string
  supports_vision?: boolean
  metadata?: Record<string, unknown>
}) {
  return request.post('/risk/kt3/providers', body)
}

export function updateKT3Provider(providerId: number, body: {
  name?: string
  provider_type?: string
  base_url?: string
  model?: string
  wire_api?: string
  api_key?: string
  supports_vision?: boolean
  metadata?: Record<string, unknown>
}) {
  return request.put(`/risk/kt3/providers/${providerId}`, body)
}

export function activateKT3Provider(providerId: number, isActive = true) {
  return request.post(`/risk/kt3/providers/${providerId}/activate`, { is_active: isActive })
}

export function testKT3Provider(providerId: number) {
  return request.post(`/risk/kt3/providers/${providerId}/test`)
}

export function uploadKT3GateDataset(kt3_gate_dataset: Record<string, unknown>) {
  return request.post('/risk/kt3/gate-datasets', { kt3_gate_dataset })
}

export function listKT3GateDatasets(params?: {
  page?: number
  page_size?: number
}) {
  return request.get('/risk/kt3/gate-datasets', { params })
}

export function getKT3GateDatasetDetail(datasetDbId: number | string) {
  return request.get(`/risk/kt3/gate-datasets/${datasetDbId}`)
}

export function startKT3Backfill(body: {
  report_ids?: string[]
  limit?: number
}) {
  return request.post('/risk/kt3/backfill', body)
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

/** 获取单个风险报告详情 */
export function getRiskReportDetail(reportId: string) {
  return request.get(`/risk/reports/${reportId}`)
}
