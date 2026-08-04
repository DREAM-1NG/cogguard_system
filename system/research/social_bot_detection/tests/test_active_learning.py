from __future__ import annotations

from research.social_bot_detection.active_learning import (
    AccountAcquisitionCandidate,
    AcquisitionInputError,
    badge_select,
    calibrated_uncertainty,
    core_set_select,
    select_account_labeling_batch,
)
from research.social_bot_detection.evaluate_active_round import evaluate_active_round_gates
from research.social_bot_detection.evaluate_active_round import build_frozen_holdout_manifest
from research.social_bot_detection.evaluate_active_round import compare_active_learning_efficiency


def _candidate(
    account_id: str,
    *,
    platform: str = "weibo",
    probability: float | None = None,
    calibrated: bool = False,
    approved: bool = False,
    alps: list[float] | None = None,
    badge: list[float] | None = None,
    calibration_source: str = "",
) -> AccountAcquisitionCandidate:
    return AccountAcquisitionCandidate(
        case_id=f"case-{account_id}",
        account_id=account_id,
        platform=platform,
        event_id="event-1",
        text=f"{account_id} discussed the event with repeated public posts",
        post_ids=[f"post-{account_id}"],
        model_probability=probability,
        model_is_calibrated=calibrated,
        calibrated_probability=probability if calibrated else None,
        calibration_source=calibration_source,
        alps_embedding=alps,
        badge_embedding=badge,
        has_approved_label=approved,
    )


def test_cold_start_uses_alps_embeddings_and_core_set_selection():
    selected = select_account_labeling_batch(
        [
            _candidate("near-a", alps=[1.0, 0.0]),
            _candidate("near-b", alps=[0.9, 0.1]),
            _candidate("far-c", alps=[0.0, 1.0]),
        ],
        budget=2,
        cold_start=True,
    )

    assert selected.strategy == "cold_start_alps_core_set"
    assert [item.case_id for item in selected.items] == ["case-near-a", "case-far-c"]
    assert all(item.selection_bucket == "alps_core_set" for item in selected.items)
    assert "non_claimable_fallback_used" not in selected.manifest


def test_cold_start_requires_real_alps_vectors():
    try:
        select_account_labeling_batch(
            [_candidate("missing-alps")],
            budget=1,
            cold_start=True,
        )
    except AcquisitionInputError as error:
        assert "alps_embedding" in str(error)
    else:
        raise AssertionError("cold-start selector accepted a missing ALPS vector")


def test_warm_start_uses_calibrated_uncertainty_and_badge_gradient_embeddings():
    selected = select_account_labeling_batch(
        [
            _candidate(
                "uncertain-a",
                probability=0.51,
                calibrated=True,
                calibration_source="temperature_scaling",
                badge=[1.0, 0.0, 0.0, 0.0],
            ),
            _candidate(
                "uncertain-b",
                probability=0.49,
                calibrated=True,
                calibration_source="temperature_scaling",
                badge=[0.95, 0.05, 0.0, 0.0],
            ),
            _candidate(
                "diverse-c",
                probability=0.8,
                calibrated=True,
                calibration_source="temperature_scaling",
                badge=[0.0, 1.0, 0.0, 0.0],
            ),
        ],
        budget=2,
    )

    assert selected.strategy == "warm_start_calibrated_uncertainty_badge"
    assert selected.items[0].case_id == "case-uncertain-a"
    assert selected.items[1].case_id == "case-diverse-c"
    assert "badge_vector_norm" in selected.items[0].scores
    assert selected.items[0].scores["calibrated_uncertainty"] > 0.9


def test_warm_start_rejects_uncalibrated_probabilities_and_missing_badge():
    try:
        select_account_labeling_batch(
            [_candidate("missing-badge", probability=0.51, calibrated=True, calibration_source="temperature_scaling")],
            budget=1,
        )
    except AcquisitionInputError as error:
        assert "badge_embedding" in str(error)
    else:
        raise AssertionError("warm-start selector accepted a missing BADGE vector")

    try:
        select_account_labeling_batch(
            [_candidate("uncalibrated", probability=0.51, calibrated=False, badge=[1.0, 0.0])],
            budget=1,
        )
    except AcquisitionInputError as error:
        assert "alps_embedding" in str(error)
    else:
        raise AssertionError("auto selector accepted uncalibrated output without ALPS cold-start input")


def test_core_set_and_badge_helpers_are_deterministic():
    assert core_set_select([[1.0, 0.0], [0.8, 0.2], [0.0, 1.0]], budget=2) == [0, 2]
    selected = badge_select(
        [
            _candidate("a", probability=0.51, calibrated=True, calibration_source="temperature_scaling", badge=[1.0, 0.0]),
            _candidate("b", probability=0.9, calibrated=True, calibration_source="temperature_scaling", badge=[0.0, 1.0]),
        ],
        budget=1,
    )
    assert selected == [0]
    assert calibrated_uncertainty(0.51, calibrated=True) > 0.9


def test_platform_stratification_prevents_one_platform_from_owning_the_batch():
    candidates = [
        _candidate(f"w{i}", platform="weibo", alps=[1.0, float(i)])
        for i in range(8)
    ] + [
        _candidate("xhs-a", platform="xhs", alps=[0.0, 1.0]),
        _candidate("douyin-a", platform="douyin", alps=[-1.0, 0.0]),
    ]

    selected = select_account_labeling_batch(
        candidates,
        budget=6,
        cold_start=True,
    )

    platforms = {item.platform for item in selected.items}
    assert {"weibo", "xhs", "douyin"}.issubset(platforms)
    assert selected.manifest["stratified_by"] == ["platform", "event_id"]


def test_active_round_gate_details_are_serializable():
    result = evaluate_active_round_gates(
        {
            "frozen_holdout_passed": True,
            "time_forward_passed": True,
            "platform_stratified_passed": True,
            "community_disjoint_passed": True,
            "ece": 0.04,
            "false_positive_burden_passed": True,
        }
    )

    assert result["activation_allowed"] is True
    assert result["details"][0]["name"] == "frozen_holdout"


def test_frozen_holdout_manifest_detects_active_pool_leakage():
    result = build_frozen_holdout_manifest(
        holdout_case_ids={"case-a", "case-b"},
        active_pool_case_ids={"case-b", "case-c"},
    )

    assert result["passed"] is False
    assert result["leakage_case_ids"] == ["case-b"]


def test_active_learning_efficiency_requires_equal_budget_random_baseline():
    result = compare_active_learning_efficiency(
        {
            "random": [0.40, 0.45, 0.50],
            "uncertainty": [0.42, 0.47, 0.56],
        }
    )

    row = next(item for item in result["rows"] if item["strategy"] == "uncertainty")
    assert result["equal_budget"] is True
    assert row["final_delta_vs_random"] == 0.06
    assert row["per_round_delta_vs_random"] == [0.02, 0.02, 0.06]
