from pathlib import Path


SYSTEM_ROOT = Path(__file__).resolve().parents[1].parent


def read_text(relative: str) -> str:
    return (SYSTEM_ROOT / relative).read_text(encoding="utf-8")


def test_accounts_page_shows_botrhg_outputs_without_rule_risk_copy():
    source = read_text("frontend/src/views/accounts/index.vue")

    assert "BotRHG 判别" in source
    assert "BotRHG 概率" in source
    assert "模型概率" in source
    assert "自动化评分" not in source
    assert "高风险" not in source
    assert "deterministic fallback" not in source
    assert "No verified internal checkpoint" not in source
    assert "基础分类" not in source


def test_coordination_page_does_not_block_graph_on_latest_result_loading():
    source = read_text("frontend/src/views/coordination/index.vue")

    assert ':spinning="loadingDetail || loadingResult"' not in source
    assert 'await Promise.all([loadDatasetDetail(datasetId), loadLatestResult(datasetId), loadGraph()])' not in source
    assert "void loadLatestResult(datasetId)" in source


def test_propagation_objects_use_a_single_category_and_are_collapsed():
    source = read_text("frontend/src/views/propagation/index.vue")

    assert "高频共享对象 · {{ activeClaimGroup.label }}" in source
    assert "activeClaimGroup" in source
    assert "claimGroupMenuOpen" in source
    assert "CLAIM_GROUP_COLLAPSED_LIMIT" in source
    assert "... 查看全部" in source
    assert "edgeSymbol: ['none', 'arrow']" in source


def test_propagation_objects_use_one_active_category_and_hide_internal_diagnostics():
    source = read_text("frontend/src/views/propagation/index.vue")

    assert "activeClaimGroup" in source
    assert "claimGroupMenuOpen" in source
    assert "暂无 hashtag 对象" not in source
    assert "哈希分桶" not in source
    assert "候选桶" not in source
    assert "身份映射" not in source
    assert "getCachedPropagationPrediction" in source
    assert "Math.max(observedSize" not in source


def test_accounts_page_hides_calibration_status_copy():
    source = read_text("frontend/src/views/accounts/index.vue")

    assert "未校准或暂时无校准" not in source
    assert "暂无校准" not in source
    assert "校准状态" not in source


def test_system_page_available_to_demo_analyst_without_delete_action():
    router = read_text("frontend/src/router/index.ts")
    layout = read_text("frontend/src/components/layout/BasicLayout.vue")
    system_view = read_text("frontend/src/views/system/index.vue")

    assert "roles: ['admin', 'analyst']" in router
    assert "roles: ['admin', 'analyst']" in layout
    assert "roles: ['admin']" not in layout
    assert "删除" not in system_view
    assert "canManageServices" in system_view
