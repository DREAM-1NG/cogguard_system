import request from '@/utils/request'

export function analyzePropagation(params?: { platform?: string; event_id?: string }) {
  return request.get('/propagation/analyze', { params })
}

export function predictPropagationTrend(params?: { platform?: string; event_id?: string }) {
  return request.post('/propagation/predict-trend', null, { params })
}

export function predictPropagationEventModel(params?: { platform?: string; event_id?: string; top_k?: number }) {
  return request.post('/propagation/model-event-predict', null, { params })
}

export function predictPropagationModel(params?: { dataset?: string; seed?: number; run_live?: boolean }) {
  return request.post('/propagation/model-predict', null, { params })
}
