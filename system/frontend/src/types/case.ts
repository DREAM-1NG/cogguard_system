export type CaseState =
  | 'draft'
  | 'collecting'
  | 'evidence_ready'
  | 'analyzing'
  | 'awaiting_review'
  | 'actioning'
  | 'ready_to_close'
  | 'closed'

export interface CaseLifecycleStep {
  key: string
  label: string
  status: 'done' | 'active' | 'pending'
}

export interface AuthoritySourceRef {
  source_id?: string
  name: string
  tier: 'government_official' | 'central_mainstream_original' | 'provincial_official_media' | string
  url: string
  status?: string
  content_capture?: string
}

export interface CaseClaim {
  claim_id: string
  role: 'primary' | 'supplementary' | string
  status: string
  excerpt: string
  span?: { start: number; end: number }
  url?: string
  account?: string
  published_at?: string
  source_tier?: string
  source: AuthoritySourceRef
  source_archive_id?: string
  source_content_hash?: string
  source_markdown_hash?: string
  source_content_capture?: string
  excerpt_hash?: string
}

export interface SemanticDistribution {
  [label: string]: number
}

export interface SemanticCommunityComparisonItem {
  community_id: string
  texts: number
  top_keywords?: string[]
  sentiment?: SemanticDistribution
}

export interface SemanticNearDuplicateGroup {
  group_id: string
  size: number
  content_ids?: string[]
  representative_text?: string
}

export interface SemanticArtifactProvenance {
  embedding_reuse?: string
  device?: string
  degradation_reason?: string
  score_policy?: string
  [key: string]: string | string[] | undefined
}

export interface SemanticArtifactSummary {
  sentiment?: { distribution?: SemanticDistribution; average_score?: number }
  stance?: { status?: string; code?: string; distribution?: SemanticDistribution; message?: string }
  community_comparison?: { group_by?: string; items?: SemanticCommunityComparisonItem[] }
  near_duplicates?: SemanticNearDuplicateGroup[]
  top_keywords?: Array<{ term: string; count?: number }>
  topics?: { items?: Array<Record<string, any>> }
  entities?: Array<{ entity: string }>
}

export interface SemanticArtifact {
  artifact_id: string
  artifact_type: string
  status: string
  model_status: string
  artifact_sha256?: string
  summary?: SemanticArtifactSummary
  provenance?: SemanticArtifactProvenance
}

export interface CaseAction {
  action_id: string
  title: string
  status: string
  required?: boolean
  assignee?: string
  evidence_refs?: string[]
  history?: Array<Record<string, any>>
}

export interface CaseFeedback {
  feedback_id: string
  actor_id: string
  content: string
  created_at: string
}

export interface CaseCloseoutReview {
  review_id: string
  actor_id: string
  summary: string
  submitted_at: string
}

export interface CaseReportVersion {
  version: number
  status: string
  format: string
  content_hash: string
  html_url?: string
  pdf_url?: string
  contains?: string[]
}

export interface CaseBlocker {
  blocker_id: string
  code: string
  scope: string
  operation: string
  severity: string
  message: string
  missing_platforms?: string[]
}

export interface CaseBlockerAcknowledgement {
  acknowledgement_id: string
  blocker_id: string
  actor_id: string
  reason: string
  missing_platforms?: string[]
  status: string
  created_at: string
}

export interface CaseClosureChecklistItem {
  key: string
  label: string
  status: 'passed' | 'pending' | 'blocked' | string
  evidence: Record<string, any>
}

export interface CaseDetail {
  case_id: string
  event_id: string
  title: string
  description?: string
  state: CaseState
  state_options?: CaseState[]
  created_at?: string
  updated_at?: string
  expected_platforms: string[]
  platforms: string[]
  evidence: Record<string, any>
  lifecycle: CaseLifecycleStep[]
  primary_claim?: CaseClaim | null
  supplementary_claims: CaseClaim[]
  analysis_runs: Array<Record<string, any>>
  semantic_artifacts: SemanticArtifact[]
  evidence_matrix: Record<string, any>
  graph: Record<string, any>
  actions: CaseAction[]
  feedback: CaseFeedback[]
  closeout_review?: CaseCloseoutReview | null
  reports: CaseReportVersion[]
  active_blockers: CaseBlocker[]
  blocker_acknowledgements?: CaseBlockerAcknowledgement[]
  closure_checklist: CaseClosureChecklistItem[]
  audit_events?: Array<Record<string, any>>
  workflow_summary: Record<string, string>
}

export interface CasePage {
  items: CaseDetail[]
  total: number
  meta?: Record<string, any>
}

export interface CaseActionDecisionRequest {
  note?: string
}

export interface CaseFeedbackRequest {
  content: string
}

export interface CaseCloseoutReviewRequest {
  summary: string
}

export interface CaseBlockerAcknowledgementRequest {
  reason: string
}

export interface ApiEnvelope<T> {
  code: number
  data: T
  msg: string
}
