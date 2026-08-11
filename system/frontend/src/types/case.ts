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
  source_content_hash?: string
  excerpt_hash?: string
}

export interface SemanticArtifact {
  artifact_id: string
  artifact_type: string
  status: string
  model_status: string
  artifact_sha256?: string
  summary?: Record<string, any>
  provenance?: Record<string, any>
}

export interface CaseAction {
  action_id: string
  title: string
  status: string
  required?: boolean
  assignee?: string
  evidence_refs?: string[]
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
  feedback: Array<Record<string, any>>
  reports: CaseReportVersion[]
  active_blockers: CaseBlocker[]
  workflow_summary: Record<string, string>
}

export interface CasePage {
  items: CaseDetail[]
  total: number
  meta?: Record<string, any>
}

export interface CaseCreateRequest {
  event_id: string
  title: string
}

export interface ApiEnvelope<T> {
  code: number
  data: T
  msg: string
}
