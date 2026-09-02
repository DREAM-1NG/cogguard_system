from pathlib import Path


ROOT = Path(__file__).parents[2]
FRONTEND = ROOT / "frontend" / "src"


def read_frontend(path: str) -> str:
    return (FRONTEND / path).read_text(encoding="utf-8")


def test_preview_mode_can_open_system_management() -> None:
    auth_source = read_frontend("stores/auth.ts")
    router_source = read_frontend("router/index.ts")
    layout_source = read_frontend("components/layout/BasicLayout.vue")

    assert "role: 'admin'" in auth_source
    assert "role: 'designer'" not in auth_source
    assert "path: 'system'" in router_source
    assert "roles: ['admin']" in router_source
    assert "path: '/system'" in layout_source


def test_accounts_page_hides_non_claimable_fallback_notices_from_main_view() -> None:
    source = read_frontend("views/accounts/index.vue")

    assert "detectionSummaryMessage" not in source
    assert "detectionMethodCard.note" not in source
    assert "method-note" not in source
    assert "No verified internal checkpoint" not in source


def test_propagation_objects_prioritize_hashtags_and_collapse_other_categories() -> None:
    source = read_frontend("views/propagation/index.vue")

    assert "primaryHashtagClaims" in source
    assert "secondaryClaimGroups" in source
    assert "showMoreClaimGroup" in source
    assert "['hashtag', 'keyword', 'url', 'tweet', 'other']" in source
    assert 'v-for="group in claimGroups"' not in source


def test_propagation_path_graph_uses_stable_layered_layout_not_backend_coordinates() -> None:
    source = read_frontend("views/propagation/index.vue")
    graph_start = source.index("function buildPathGraphOption")
    graph_source = source[graph_start:]

    assert "hasBackendLayout" not in graph_source
    assert "Number(node.layout_x)" not in graph_source
    assert "stableLayeredPositions" in graph_source
    assert "edgeSymbol: ['none', 'arrow']" in graph_source
    assert "curveness: stableEdgeCurveness" in graph_source


def test_risk_page_does_not_auto_recompute_on_first_open_or_report_detail() -> None:
    source = read_frontend("views/risk/index.vue")

    assert "await handleAssess(false)" not in source
    assert "openLatest && !report.value && historyItems.value.length === 0" not in source
    assert "activeTab.value = 'history'" in source


def test_coordination_page_does_not_block_whole_page_on_latest_result_loading() -> None:
    source = read_frontend("views/coordination/index.vue")

    assert '<a-spin :spinning="loadingDetail || loadingResult">' not in source
    assert "<a-spin :spinning=\"loadingDetail\">" in source
    assert "void loadLatestResult(datasetId)" in source


def test_analysis_page_shows_community_unavailable_reason() -> None:
    source = read_frontend("views/analysis/index.vue")

    assert "community_slices_unavailable_reason" in source
    assert ':description="communitySlicesUnavailableReason || \'No coordination community available\'"' in source
