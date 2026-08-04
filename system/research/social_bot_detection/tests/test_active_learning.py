from __future__ import annotations

from research.social_bot_detection.active_learning import (
    AccountAcquisitionCandidate,
    AccountAcquisitionWeights,
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
    ood: float = 0.0,
    approved: bool = False,
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
        ood_score=ood,
        has_approved_label=approved,
    )


def test_selector_excludes_approved_labels_and_keeps_random_audit_quota():
    selected = select_account_labeling_batch(
        [
            _candidate("already-labeled", probability=0.5, approved=True),
            _candidate("uncertain-a", probability=0.51),
            _candidate("uncertain-b", probability=0.49),
            _candidate("stable-human", probability=0.05),
            _candidate("stable-bot", probability=0.95),
        ],
        budget=3,
        weights=AccountAcquisitionWeights(random_audit=0.34),
    )

    assert len(selected.items) == 3
    assert "case-already-labeled" not in {item.case_id for item in selected.items}
    assert any(item.selection_bucket == "random_audit" for item in selected.items)
    assert selected.manifest["budget"] == 3
    assert selected.manifest["excluded_approved_label_count"] == 1


def test_cold_start_uses_surprisal_and_diversity_before_uncalibrated_uncertainty():
    selected = select_account_labeling_batch(
        [
            _candidate("low-surprisal", probability=None),
            _candidate("high-surprisal", probability=None),
            _candidate("medium-surprisal", probability=None),
        ],
        budget=2,
        cold_start=True,
        surprisal_by_case={
            "case-low-surprisal": 0.1,
            "case-high-surprisal": 0.9,
            "case-medium-surprisal": 0.5,
        },
        weights=AccountAcquisitionWeights(random_audit=0.0),
    )

    assert selected.strategy == "cold_start_surprisal_diversity"
    assert selected.items[0].case_id == "case-high-surprisal"
    assert all("surprisal" in item.scores for item in selected.items)
    assert selected.manifest["model_state"] == "cold_start_no_reliable_ranker"


def test_warm_start_manifest_requires_model_ranker_for_uncertainty():
    selected = select_account_labeling_batch(
        [_candidate("warm-a", probability=0.51, calibrated=True)],
        budget=1,
        weights=AccountAcquisitionWeights(random_audit=0.0),
    )

    assert selected.strategy == "uncertainty_disagreement_diversity"
    assert selected.manifest["model_state"] == "warm_start_calibrated_model_ranker"
    assert selected.items[0].scores["uncertainty"] > 0.9


def test_uncalibrated_probabilities_do_not_trigger_warm_start_uncertainty():
    selected = select_account_labeling_batch(
        [
            _candidate("uncalibrated-a", probability=0.51, calibrated=False),
            _candidate("uncalibrated-b", probability=0.99, calibrated=False),
        ],
        budget=1,
        weights=AccountAcquisitionWeights(random_audit=0.0),
    )

    assert selected.strategy == "cold_start_coverage_diversity"
    assert selected.manifest["ranker_status"] == "no_calibrated_model"
    assert selected.items[0].scores["uncertainty"] == 0.0


def test_platform_stratification_prevents_one_platform_from_owning_the_batch():
    candidates = [
        _candidate(f"w{i}", platform="weibo", probability=0.5 + (i * 0.001))
        for i in range(8)
    ] + [
        _candidate("xhs-a", platform="xhs", probability=0.52),
        _candidate("douyin-a", platform="douyin", probability=0.53),
    ]

    selected = select_account_labeling_batch(
        candidates,
        budget=6,
        weights=AccountAcquisitionWeights(random_audit=0.0),
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
