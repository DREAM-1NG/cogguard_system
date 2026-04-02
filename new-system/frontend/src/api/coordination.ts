/**
 * 协同检测相关 API
 */
import request from '@/utils/request'

/** 运行协同检测分析 */
export function runCoordinationDetection(params: {
  time_window?: number
  min_participation?: number
  edge_weight?: number
  platform?: string
}) {
  return request.post('/coordination/detect', null, { params })
}
