export interface CrawlKeywordGroup {
  id: string
  name: string
  keywords: string[]
}

export interface CrawlPreviewState {
  selectedJobId: number | null
  selectedPostId: string | null
  comments: unknown[]
  media: unknown[]
}

export interface CrawlQueryState {
  jobId: number | null
  postId: string | null
  platform: string | undefined
  keyword: string
  hasMedia: boolean
}

export function flattenKeywordGroups(groups: CrawlKeywordGroup[]): string[] {
  const seen = new Set<string>()
  const flattened: string[] = []
  for (const group of groups) {
    for (const rawKeyword of group.keywords) {
      const keyword = String(rawKeyword || '').trim()
      if (!keyword || seen.has(keyword)) continue
      seen.add(keyword)
      flattened.push(keyword)
    }
  }
  return flattened
}

export function choosePrimaryKeyword(groups: CrawlKeywordGroup[], requested: string): string {
  const keywords = flattenKeywordGroups(groups)
  const normalized = String(requested || '').trim()
  return keywords.includes(normalized) ? normalized : (keywords[0] || '')
}

export function parseJobSummary(summary: string | null | undefined): { postsCount: number; commentsCount: number } {
  if (!summary) return { postsCount: 0, commentsCount: 0 }
  try {
    const parsed = JSON.parse(summary) as Record<string, unknown>
    return {
      postsCount: Number(parsed.posts_count) || 0,
      commentsCount: Number(parsed.comments_count) || 0,
    }
  } catch {
    return { postsCount: 0, commentsCount: 0 }
  }
}

export function resetPreviewForJob(
  _previous: CrawlPreviewState,
  selectedJobId: number | null,
): CrawlPreviewState {
  return {
    selectedJobId,
    selectedPostId: null,
    comments: [],
    media: [],
  }
}

export function getMediaPreviewState(media: { status?: string; previewable?: boolean }): 'ready' | 'not_downloaded' | 'unsupported' {
  if (media.status === 'ready' && media.previewable) return 'ready'
  if (media.previewable === false && media.status === 'ready') return 'unsupported'
  return 'not_downloaded'
}

export function readCrawlQuery(params: URLSearchParams): CrawlQueryState {
  const job = Number(params.get('job'))
  return {
    jobId: Number.isInteger(job) && job > 0 ? job : null,
    postId: params.get('post') || null,
    platform: params.get('platform') || undefined,
    keyword: params.get('keyword') || '',
    hasMedia: params.get('media') !== '0',
  }
}

export function writeCrawlQuery(state: CrawlQueryState): URLSearchParams {
  const params = new URLSearchParams()
  if (state.jobId) params.set('job', String(state.jobId))
  if (state.postId) params.set('post', state.postId)
  if (state.platform) params.set('platform', state.platform)
  if (state.keyword.trim()) params.set('keyword', state.keyword.trim())
  if (!state.hasMedia) params.set('media', '0')
  return params
}
