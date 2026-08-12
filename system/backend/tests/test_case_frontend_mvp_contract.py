from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FRONTEND = ROOT / "system" / "frontend" / "src"


def test_case_frontend_mvp_files_routes_and_tabs_exist():
    paths = {
        "types": FRONTEND / "types" / "case.ts",
        "api": FRONTEND / "api" / "cases.ts",
        "view": FRONTEND / "views" / "cases" / "index.vue",
        "router": FRONTEND / "router" / "index.ts",
        "layout": FRONTEND / "components" / "layout" / "BasicLayout.vue",
    }
    for path in paths.values():
        assert path.exists(), path

    view = paths["view"].read_text(encoding="utf-8")
    router = paths["router"].read_text(encoding="utf-8")
    layout = paths["layout"].read_text(encoding="utf-8")
    api = paths["api"].read_text(encoding="utf-8")
    types = paths["types"].read_text(encoding="utf-8")

    assert view.index('class="case-context-bar"') < view.index("<a-tabs")
    for label in ("概览", "证据矩阵", "图谱", "处置", "报告"):
        assert f'tab="{label}"' in view
    for text in ("事件 -> 证据 -> Coordination -> Propagation -> Review -> 处置 -> 反馈", "candidate_unvalidated"):
        assert text in view
    assert "EvidenceDrawer" in view
    assert ':disabled="!record.html_url"' in view
    assert ':disabled="!record.pdf_url"' in view
    assert "caseDetail.value = null" in view
    assert "未找到匹配案例" in view
    assert "completeCaseAction" in view
    assert "submitCaseFeedback" in view
    assert "submitCaseCloseoutReview" in view
    assert "acknowledgeCaseBlocker" in view
    assert "确认平台缺口继续" in view
    assert "blocker_acknowledgements" in view
    assert "标记完成" in view
    assert "提交反馈" in view
    assert "提交结案复核" in view
    assert "getCase" in api
    assert "listCases" in api
    assert "completeCaseAction" in api
    assert "waiveCaseAction" in api
    assert "submitCaseFeedback" in api
    assert "submitCaseCloseoutReview" in api
    assert "acknowledgeCaseBlocker" in api
    assert "CaseDetail" in types
    assert "SemanticArtifact" in types
    assert "CaseActionDecisionRequest" in types
    assert "CaseFeedbackRequest" in types
    assert "CaseCloseoutReviewRequest" in types
    assert "CaseBlockerAcknowledgement" in types
    assert "CaseBlockerAcknowledgementRequest" in types
    assert "blocker_acknowledgements" in types
    assert ":disabled=\"caseDetail.state !== 'ready_to_close'\"" in view
    assert "path: 'cases'" in router
    assert "path: '/cases'" in layout
    assert "\u6848\u4f8b\u95ed\u73af" in layout


def test_case_frontend_fetches_reports_with_authenticated_blob_flow_and_disables_closed_mutations():
    api = (FRONTEND / "api" / "cases.ts").read_text(encoding="utf-8")
    view = (FRONTEND / "views" / "cases" / "index.vue").read_text(encoding="utf-8")

    assert "fetchCaseReport" in api
    assert "caseRequest.get<Blob, Blob>" in api
    assert "responseType: 'blob'" in api
    assert "fetchCaseReport as fetchCaseReportRequest" in view
    assert "URL.createObjectURL(blob)" in view
    assert "window.open(blobUrl, '_blank', 'noopener,noreferrer')" in view
    assert "window.open(url, '_blank', 'noopener,noreferrer')" not in view

    assert ':disabled="caseDetail.state === \'closed\' || record.status === \'completed\'"' in view
    assert ':disabled="caseDetail.state === \'closed\' || record.status === \'waived\'"' in view
    assert view.count(":disabled=\"caseDetail.state === 'closed'\"") >= 3


def test_case_evidence_matrix_exposes_semantic_assistance_bindings():
    view = (FRONTEND / "views" / "cases" / "index.vue").read_text(encoding="utf-8")
    layout = (FRONTEND / "components" / "layout" / "BasicLayout.vue").read_text(encoding="utf-8")

    for binding in (
        "summary?.sentiment?.distribution",
        "summary?.stance",
        "summary?.community_comparison?.items",
        "summary?.near_duplicates",
        "summary?.decision_support",
        "semanticDecisionSupport?.coverage",
        "semanticDecisionSupport?.confidence",
        "semanticDecisionSupport?.time_slices",
        "semanticDecisionSupport?.platform_slices",
    ):
        assert binding in view
    for label in (
        "Sentiment",
        "Stance",
        "Community comparison",
        "Near duplicates",
        "Semantic decision support",
        "Coverage",
        "Confidence",
        "Time slices",
        "Platform slices",
    ):
        assert label in view
    assert "案例闭环" in layout


def test_case_workbench_surfaces_semantic_review_hints_and_action_evidence_refs():
    view = (FRONTEND / "views" / "cases" / "index.vue").read_text(encoding="utf-8")

    for binding in (
        "semanticReviewHints",
        "semanticDecisionSupport.value?.review_hints",
        "semanticModuleCoverageEntries",
        "semanticDecisionSupport.value?.module_coverage",
        "moduleCoverageColor",
        "record.evidence_refs",
        "record.evidence_refs || []",
        "Evidence refs",
        "action_evidence_refs",
    ):
        assert binding in view
    for label in (
        "Review hints",
        "Module coverage",
        "Action evidence refs",
        "candidate_unvalidated",
        "evidence_overlay_only",
    ):
        assert label in view

    service = ROOT / "system" / "backend" / "app" / "services" / "case_workbench_service.py"
    service_source = service.read_text(encoding="utf-8")
    assert "semantic_case_workbench_demo" in service_source


def test_case_workbench_exposes_semantic_example_traceability():
    view = (FRONTEND / "views" / "cases" / "index.vue").read_text(encoding="utf-8")
    types = (FRONTEND / "types" / "case.ts").read_text(encoding="utf-8")

    for binding in (
        "semanticTraceExamples",
        "summary?.sentiment?.examples",
        "summary?.stance?.examples",
        "example.content_id",
        "example.platform",
        "example.author_id",
        "example.excerpt",
        "example.source",
        "item.content_ids",
        "Semantic examples",
    ):
        assert binding in view
    for field in (
        "export interface SemanticTraceExample",
        "content_id: string",
        "content_kind?: string",
        "platform?: string",
        "author_id?: string",
        "excerpt?: string",
        "examples?: Record<string, SemanticTraceExample[]>",
        "examples?: SemanticTraceExample[]",
    ):
        assert field in types


def test_case_workbench_exports_prototype_limitations_and_excerpt_boundary():
    view = (FRONTEND / "views" / "cases" / "index.vue").read_text(encoding="utf-8")
    types = (FRONTEND / "types" / "case.ts").read_text(encoding="utf-8")

    for binding in (
        "prototypeConstraints",
        "prototype_constraints",
        "Prototype limitations",
        "excerpt_only_not_full_source_text",
        "semantic_artifacts_do_not_mutate_coordination_propagation_review_scores",
        "prototype_limitations",
        "semantic_examples_text_scope",
        "risk_score_boundary",
    ):
        assert binding in view
    for field in (
        "export interface CasePrototypeConstraints",
        "platform_evidence_scope: string",
        "semantic_examples_text_scope: string",
        "risk_score_boundary: string",
        "prototype_constraints: CasePrototypeConstraints",
    ):
        assert field in types


def test_case_workbench_exposes_semantic_correction_bindings():
    view = (FRONTEND / "views" / "cases" / "index.vue").read_text(encoding="utf-8")
    api = (FRONTEND / "api" / "cases.ts").read_text(encoding="utf-8")
    types = (FRONTEND / "types" / "case.ts").read_text(encoding="utf-8")

    for binding in (
        "semanticCorrections",
        "semanticCorrectionForm",
        "recordSemanticCorrection",
        "submitSemanticCorrection",
        "semantic_corrections",
        "Semantic corrections",
        "advisory_overlay",
        "record_semantic_correction",
        "semantic_artifacts_do_not_mutate_coordination_propagation_review_scores",
    ):
        assert binding in view
    for binding in (
        "recordSemanticCorrection",
        "/semantic-artifacts/${encodeURIComponent(artifactId)}/corrections",
        "CaseSemanticCorrectionRequest",
    ):
        assert binding in api
    for field in (
        "export interface CaseSemanticCorrection",
        "export interface CaseSemanticCorrectionRequest",
        "semantic_corrections: CaseSemanticCorrection[]",
        "module: string",
        "target_ref: string",
        "corrected_value: string",
        "reason: string",
    ):
        assert field in types


def test_case_evidence_matrix_exposes_semantic_truth_boundary_bindings():
    view = (FRONTEND / "views" / "cases" / "index.vue").read_text(encoding="utf-8")
    types = (FRONTEND / "types" / "case.ts").read_text(encoding="utf-8")

    for binding in (
        "semanticArtifact?.model_status",
        "semanticProvenanceEntries",
        "stanceSummary.code",
        "stanceSummary.message",
    ):
        assert binding in view
    for field in (
        "embedding_reuse?: string",
        "device?: string",
        "degradation_reason?: string",
        "score_policy?: string",
    ):
        assert field in types


def test_case_evidence_matrix_exposes_claim_archive_provenance_bindings():
    view = (FRONTEND / "views" / "cases" / "index.vue").read_text(encoding="utf-8")
    types = (FRONTEND / "types" / "case.ts").read_text(encoding="utf-8")

    for binding in (
        "source_archive_id",
        "source_content_hash",
        "source_markdown_hash",
        "source_content_capture",
    ):
        assert binding in view
    for field in (
        "content_capture?: string",
        "source_archive_id?: string",
        "source_markdown_hash?: string",
        "source_content_capture?: string",
    ):
        assert field in types


def test_case_graph_evidence_layers_tab_exposes_cpr_bindings():
    view = (FRONTEND / "views" / "cases" / "index.vue").read_text(encoding="utf-8")

    for binding in (
        "graphEvidenceLayers",
        "layer.key",
        "layer.metrics",
        "formatMetrics",
        "caseDetail.value?.graph?.evidence_layers",
    ):
        assert binding in view


def test_case_report_tab_exposes_acceptance_summary_bindings():
    view = (FRONTEND / "views" / "cases" / "index.vue").read_text(encoding="utf-8")

    for binding in (
        "Acceptance summary",
        "acceptanceSummary",
        "archiveCoverage",
        "cprCoverage",
        "semanticOverlayPolicy",
        "noFabricatedSecondPlatformEvidence",
    ):
        assert binding in view


def test_case_report_tab_exposes_backend_closure_checklist_bindings():
    view = (FRONTEND / "views" / "cases" / "index.vue").read_text(encoding="utf-8")
    types = (FRONTEND / "types" / "case.ts").read_text(encoding="utf-8")

    for binding in (
        "Closure checklist",
        "closureChecklist",
        "caseDetail.value?.closure_checklist",
        "check.evidence",
        "check.status",
    ):
        assert binding in view
    for field in (
        "export interface CaseClosureChecklistItem",
        "closure_checklist: CaseClosureChecklistItem[]",
        "status: 'passed' | 'pending' | 'blocked' | string",
        "evidence: Record<string, any>",
    ):
        assert field in types


def test_case_report_tab_can_export_acceptance_evidence_summary():
    view = (FRONTEND / "views" / "cases" / "index.vue").read_text(encoding="utf-8")

    for binding in (
        "导出验收摘要",
        "copyAcceptanceSummary",
        "downloadAcceptanceSummary",
        "acceptanceEvidencePayload",
        "closure_checklist",
        "semantic_decision_support",
        "semanticDecisionSupport?.coverage",
        "semanticDecisionSupport?.confidence",
        "semanticDecisionSupport?.platform_slices",
        "semanticDecisionSupport?.time_slices",
        "semantic_traceability",
        "semanticTraceExamples",
        "semanticModuleCoverageEntries",
        "semanticReviewHints",
        "action_evidence_refs",
        "navigator.clipboard.writeText",
        "case-acceptance-summary",
    ):
        assert binding in view


def test_case_report_tab_can_export_semantic_support_pack():
    view = (FRONTEND / "views" / "cases" / "index.vue").read_text(encoding="utf-8")

    for binding in (
        "semanticSupportPackPayload",
        "copySemanticSupportPack",
        "downloadSemanticSupportPack",
        "cogguard.semantic_support_pack.v1",
        "semantic-support-pack",
        "复制语义辅助包",
        "导出语义辅助包",
        "schema",
        "case_id",
        "event_id",
        "semantic_artifact_id",
        "model_status",
        "artifact_sha256",
        "score_policy",
        "risk_score_boundary",
        "prototype_constraints",
        "sentiment",
        "keywords",
        "topics",
        "entities",
        "stance",
        "near_duplicates",
        "community_comparison",
        "decision_support",
        "semantic_examples",
        "semantic_corrections",
        "provenance",
        "evidence_overlay_only",
        "candidate_unvalidated",
        "excerpt_only_not_full_source_text",
        "semantic_artifacts_do_not_mutate_coordination_propagation_review_scores",
        "weibo_only_with_xhs_gap",
    ):
        assert binding in view


def test_case_report_tab_exposes_closed_loop_audit_trail():
    view = (FRONTEND / "views" / "cases" / "index.vue").read_text(encoding="utf-8")

    for binding in (
        "auditTrailSummary",
        "auditTrailItems",
        "audit_trail",
        "caseDetail.audit_events",
        "Closed-loop audit trail",
        "record_semantic_correction",
        "semantic_correction_audited",
        "closed_loop_mutations",
    ):
        assert binding in view


def test_case_workbench_surfaces_semantic_action_recommendations():
    view = (FRONTEND / "views" / "cases" / "index.vue").read_text(encoding="utf-8")
    types = (FRONTEND / "types" / "case.ts").read_text(encoding="utf-8")

    for binding in (
        "semanticActionRecommendations",
        "summary?.action_recommendations",
        "Semantic action recommendations",
        "recommendation.action_id",
        "recommendation.evidence_refs",
        "action_recommendations",
        "semantic_action_recommendations",
    ):
        assert binding in view
    for field in (
        "export interface SemanticActionRecommendation",
        "recommendation_id: string",
        "action_id: string",
        "status: string",
        "score_policy: string",
        "evidence_refs?: string[]",
        "action_recommendations?: SemanticActionRecommendation[]",
    ):
        assert field in types
