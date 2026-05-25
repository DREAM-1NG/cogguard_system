import request from '@/utils/request'

export interface DashboardOverviewParams {
  event_id?: string
}

export interface DashboardSummary {
  event_count: number
  posts: number
  comments: number
  collected_items: number
  risk_reports: number
  coordination_groups: number
  platform_count: number
}

export interface PlatformSummary {
  platform: string
  posts: number
  comments: number
  total: number
}

export interface EventLocation {
  event_id: string | null
  event_name: string
  keywords: string[]
  origin_author: string | null
  origin_author_id: string | null
  origin_platform: string | null
  origin_post_id: string | null
  first_post_time: string | null
  ip_location: string | null
  origin_ip_location: string | null
  location_source_author: string | null
  location_source_author_id: string | null
  location_source_platform: string | null
  location_source_post_id: string | null
  location_source_time: string | null
  location_source_ip_location: string | null
  location_resolution_method: string
  location_name: string
  location_region: string
  location_country: string | null
  coordinates: [number, number] | null
  resolved: boolean
  posts: number
  comments: number
  platforms: string[]
}

export interface RecentPost {
  post_id: string | null
  platform: string | null
  author_id: string | null
  author_name: string | null
  timestamp: string | null
  content: string
  ip_location: string | null
}

export interface DashboardOverview {
  summary: DashboardSummary
  platforms: PlatformSummary[]
  event_locations: EventLocation[]
  unresolved_locations: EventLocation[]
  recent_posts: RecentPost[]
  meta: {
    event_id: string | null
    default_event_id: string
    generated_at: string
    mongo_filter: Record<string, unknown>
    data_source_status: Record<string, string>
  }
}

export function getDashboardOverview(params?: DashboardOverviewParams) {
  return request.get('/dashboard/overview', { params })
}
