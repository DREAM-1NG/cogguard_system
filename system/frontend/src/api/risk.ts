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
  return request.post('/risk/assess', null, { params })
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
  enable_active_retrieval?: boolean
  enable_light_debate?: boolean
  enable_full_debate?: boolean
  debate_max_rounds?: number
  policy_id?: string
  active_policy_id?: string
  retrieval_top_k?: number
}) {
  return request.post('/risk/kt3/agent-reviews/run', body)
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

export function activateKT3Policy(policyId: string) {
  return request.post(`/risk/kt3/policies/${policyId}/activate`)
}

export function getKT3Policy(policyId: string) {
  return request.get(`/risk/kt3/policies/${policyId}`)
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
