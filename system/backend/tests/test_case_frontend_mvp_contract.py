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
    assert "标记完成" in view
    assert "提交反馈" in view
    assert "提交结案复核" in view
    assert "getCase" in api
    assert "listCases" in api
    assert "completeCaseAction" in api
    assert "waiveCaseAction" in api
    assert "submitCaseFeedback" in api
    assert "submitCaseCloseoutReview" in api
    assert "CaseDetail" in types
    assert "SemanticArtifact" in types
    assert "CaseActionDecisionRequest" in types
    assert "CaseFeedbackRequest" in types
    assert "CaseCloseoutReviewRequest" in types
    assert ":disabled=\"caseDetail.state !== 'ready_to_close'\"" in view
    assert "path: 'cases'" in router
    assert "path: '/cases'" in layout
    assert "案例闭环" in layout
