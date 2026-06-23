import request from '@/utils/request'

export function assessRisk(data: {
  platform?: string
  keyword?: string
  post_ids?: string[]
  max_posts?: number
  stance_target?: string
}) {
  return request.post('/risk/assess', data)
}

export function listRiskReports(params?: { platform?: string; limit?: number }) {
  return request.get('/risk/reports', { params })
}

export function getRiskReport(reportId: string) {
  return request.get(`/risk/reports/${reportId}`)
}
