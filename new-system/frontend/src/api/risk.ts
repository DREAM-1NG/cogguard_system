/**
 * 风险研判相关 API
 */
import request from '@/utils/request'

/** 执行风险评估 */
export function assessRisk(params: {
  platform?: string
  time_window?: number
  min_participation?: number
  edge_weight?: number
}) {
  return request.post('/risk/assess', null, { params })
}

/** 查询历史风险报告列表 */
export function listRiskReports(params: {
  platform?: string
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
