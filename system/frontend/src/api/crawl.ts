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
  crawl_job_id?: number
  platform?: string
  keyword?: string
  event_id?: string
  has_media?: boolean
  page?: number
  page_size?: number
}) {
  return request.get('/crawl/data', { params })
}

/** 获取选中任务内一条帖子的前三条评论摘要 */
export function getPostComments(platform: string, postId: string, params: { crawl_job_id: number; limit?: number }) {
  return request.get(`/crawl/posts/${encodeURIComponent(platform)}/${encodeURIComponent(postId)}/comments`, { params })
}

/** 获取一条帖子已下载且可验证的本地媒体 */
export function getPostMedia(platform: string, postId: string) {
  return request.get(`/crawl/posts/${encodeURIComponent(platform)}/${encodeURIComponent(postId)}/media`)
}

/** 受保护媒体内容地址；浏览器预览前必须带 Bearer 请求读取 */
export function getMediaContentPath(jobId: number, itemIndex: number) {
  return `/api/v1/crawl/media-downloads/${jobId}/items/${itemIndex}/content`
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
