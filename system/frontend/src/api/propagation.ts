import request from '@/utils/request'

export function analyzePropagation(params?: { platform?: string; event_id?: string; node_limit?: number }) {
  return request.get('/propagation/analyze', { params })
}

export function analyzeObservedPropagation(params?: { platform?: string; event_id?: string; node_limit?: number }) {
  return request.get('/propagation/observed-analysis', { params })
}

export function predictPropagationEventModel(params?: { platform?: string; event_id?: string; top_k?: number }) {
  return request.post('/propagation/model-event-predict', null, { params })
}

export function predictPropagationCurrentEvent(params?: { platform?: string; event_id?: string; top_k?: number }) {
  return request.post('/propagation/model-event-predict', null, { params })
}

export function predictPropagationModel(params?: { dataset?: string; seed?: number; run_live?: boolean }) {
  return request.post('/propagation/model-predict', null, { params })
}
