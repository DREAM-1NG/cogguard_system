import request from '@/utils/request'

export function analyzePropagation(params?: { platform?: string }) {
  return request.get('/propagation/analyze', { params })
}
