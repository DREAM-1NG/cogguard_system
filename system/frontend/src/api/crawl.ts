/**
 * 数据采集相关 API
 *
 * 封装采集任务创建、任务列表查询、采集数据查询和平台列表请求。
 */
import request from '@/utils/request'

/** 获取支持的采集平台列表 */
export function getPlatforms() {
  return request.get('/crawl/platforms')
}

/** 创建社交媒体采集任务 */
export function createCrawlJob(data: {
  platform: string
  keywords?: string[]
  event_id?: string
  source_keyword?: string
  post_ids?: string[]
  max_posts?: number
  crawl_comments?: boolean
  recursive_comments?: boolean
  enrich_author_profiles?: boolean
  comment_sort?: 'none' | 'like_count_desc' | 'reply_count_desc'
  max_comments_per_post?: number
  execution_mode?: 'local' | 'queued'
}) {
  return request.post('/crawl/social', data)
}

/** 获取采集任务列表（分页） */
export function listCrawlJobs(params: { page?: number; page_size?: number }) {
  return request.get('/crawl/jobs', { params })
}

/** 删除采集任务及其关联数据 */
export function deleteCrawlJob(jobId: number) {
  return request.delete(`/crawl/jobs/${jobId}`)
}

/** 取消正在执行的采集任务 */
export function cancelCrawlJob(jobId: number) {
  return request.post(`/crawl/jobs/${jobId}/cancel`)
}

/** 查询已采集的帖子数据（分页 + 筛选） */
export function queryCrawlData(params: {
  platform?: string
  keyword?: string
  event_id?: string
  has_media?: boolean
  page?: number
  page_size?: number
}) {
  return request.get('/crawl/data', { params })
}

/** 创建已采集媒体下载任务 */
export function createMediaDownloadJob(data: {
  platform?: string
  keyword?: string
  event_id?: string
  post_ids?: string[]
  media_types?: Array<'video' | 'image'>
}) {
  return request.post('/crawl/media-downloads', data)
}

/** 获取媒体下载任务详情 */
export function getMediaDownloadJob(jobId: number) {
  return request.get(`/crawl/media-downloads/${jobId}`)
}
