export type ReviewConclusion = 'harmful' | 'non_harmful' | 'insufficient_evidence'
export type EvidenceSufficiency = 'sufficient' | 'limited' | 'insufficient'
export type ReviewUrgency = 'routine' | 'watch' | 'urgent' | 'critical'
export type Disposition = 'monitor' | 'gather_evidence' | 'escalate' | 'respond' | 'archive'
export type EvidenceAssessment = 'supports' | 'contradicts' | 'irrelevant' | 'unresolved'
export type ActionRequired =
  | 'none'
  | 'add_evidence'
  | 'review_available'
  | 'confirm_decision'
  | 'reconfirm_decision'

export type CaseActivityType =
  | 'case_created'
  | 'snapshot_added'
  | 'evidence_annotated'
  | 'evidence_requested'
  | 'review_requested'
  | 'review_advisory_available'
  | 'decision_draft_saved'
  | 'decision_confirmed'
  | 'correction_recorded'
  | 'reconfirmation_required'

export interface PreliminaryFinding {
  conclusion: ReviewConclusion
  rationale: string
  key_evidence_refs: string[]
}

export interface CoordinationBusinessSummary {
  narrative: string
  key_communities: string[]
  key_accounts: string[]
}

export interface PropagationBusinessSummary {
  narrative: string
  trend: string
  forecast_range: string | null
  likely_next_targets: string[]
}

export interface ReviewAdvisory {
  conclusion: ReviewConclusion
  urgency: ReviewUrgency
  disposition: Disposition
  rationale: string
  differences_from_preliminary: string[]
  key_evidence_refs: string[]
  received_at: string
}

export interface ConfirmedDecision {
  decision_id: string
  decision_version: number
  conclusion: ReviewConclusion
  urgency: ReviewUrgency
  disposition: Disposition
  rationale: string
  key_evidence_refs: string[]
  unresolved_items: string[]
  confirmed_by_name: string
  confirmed_at: string
}

export interface ReviewCaseSummary {
  case_id: string
  event_id: string
  title: string
  preliminary_finding: PreliminaryFinding
  evidence_sufficiency: EvidenceSufficiency
  sufficiency_reasons: string[]
  missing_evidence: string[]
  urgency: ReviewUrgency
  disposition: Disposition
  action_required: ActionRequired
  coordination_summary: CoordinationBusinessSummary
  propagation_summary: PropagationBusinessSummary
  updated_at: string
}

export interface ReviewCaseDetail extends ReviewCaseSummary {
  review_advisory: ReviewAdvisory | null
  confirmed_decision: ConfirmedDecision | null
  decision_draft: DecisionDraft | null
}

export interface ReviewCaseList {
  items: ReviewCaseSummary[]
  total: number
}

export interface EvidenceAnnotationCreate {
  evidence_ref: string
  assessment: EvidenceAssessment
  note: string
  source_url?: string | null
}

export interface EvidenceAnnotation {
  annotation_id: string
  evidence_ref: string
  assessment: EvidenceAssessment
  note: string
  source_url: string | null
  created_by_name: string
  created_at: string
}

export interface EvidenceItem {
  evidence_ref: string
  evidence_type: string
  assessment: EvidenceAssessment
  title: string
  excerpt: string
  source_url: string | null
  platform: string | null
  observed_at: string | null
  annotations: EvidenceAnnotation[]
}

export interface EvidencePage {
  assessment: EvidenceAssessment
  cursor: number
  limit: number
  total: number
  next_cursor: number | null
}

export interface ReviewCaseEvidence {
  case_id: string
  supports: EvidenceItem[]
  contradicts: EvidenceItem[]
  irrelevant: EvidenceItem[]
  unresolved: EvidenceItem[]
  group_counts: Partial<Record<EvidenceAssessment, number>>
  page: EvidencePage | null
}

export interface ReviewRequestCreate {
  reason: string
  evidence_refs: string[]
}

export interface ReviewRequestReceipt {
  case_id: string
  action_required: ActionRequired
  message: string
}

export interface DecisionDraftUpsert {
  conclusion: ReviewConclusion
  urgency: ReviewUrgency
  disposition: Disposition
  rationale: string
  key_evidence_refs: string[]
  unresolved_items: string[]
  expected_version: number
}

export interface DecisionDraft {
  case_id: string
  draft_version: number
  conclusion: ReviewConclusion
  urgency: ReviewUrgency
  disposition: Disposition
  rationale: string
  key_evidence_refs: string[]
  unresolved_items: string[]
  saved_at: string
}

export interface DecisionConfirmRequest {
  expected_draft_version: number
  confirmation_note: string
}

export interface DecisionConfirmation {
  case_id: string
  decision: ConfirmedDecision
  action_required: ActionRequired
}

export interface CaseActivity {
  cursor: number
  case_id: string
  activity_type: CaseActivityType
  action_required: ActionRequired
  summary: string
  detail_lines: string[]
  evidence_refs: string[]
  actor_name: string
  occurred_at: string
}

export interface CaseActivityList {
  items: CaseActivity[]
  next_cursor: number | null
}

export interface CaseEvent {
  cursor: number
  case_id: string
  activity_type: CaseActivityType
  action_required: ActionRequired
  message: string
  occurred_at: string
}
