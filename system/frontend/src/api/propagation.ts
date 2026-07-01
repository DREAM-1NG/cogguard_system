import request from '@/utils/request'

export function analyzePropagation(params?: { platform?: string; event_id?: string }) {
  return request.get('/propagation/analyze', { params })
}

export function predictPropagationTrend(params?: { platform?: string; event_id?: string }) {
  return request.post('/propagation/predict-trend', null, { params })
}
