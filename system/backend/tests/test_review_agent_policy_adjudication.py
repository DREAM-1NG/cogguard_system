from app.core.review.agent_policy import adjudicate_policy


def test_adjudication_ignores_unapproved_policy_but_preserves_audit_status():
    result = adjudicate_policy(
        {
            "policy_id": "candidate-1",
            "activation_status": "candidate_pending_human_approval",
            "policy": {"review_threshold": 0.2},
        },
        case_score=0.9,
        uncertainty=0.1,
        trigger_facts={"claim_uncertainty": True},
        completed_experts=["ClaimEvidenceAgent"],
    )

    assert result["policy_binding"] is False
    assert result["advisory_only"] is True
    assert result["policy_provenance"]["status"] == "ignored_not_human_approved"
    assert result["recommendations"] == {
        "review": False,
        "retrieval": False,
        "abstain": False,
        "countermeasure": False,
    }


def test_adjudication_is_deterministic_and_reports_thresholds_triggers_coverage_and_conflicts():
    policy = {
        "policy_id": "approved-1",
        "activation_status": "active_human_approved",
        "policy": {
            "review_threshold": 0.6,
            "abstain_threshold": 0.3,
            "retrieval_threshold": 0.7,
            "countermeasure_threshold": 0.8,
            "trigger_conditions": {
                "retrieval_on_claim_uncertainty": True,
                "review_on_cross_view_conflict": True,
                "countermeasure_requires_human_review": True,
            },
            "agent_weights": {
                "ClaimEvidenceAgent": 2,
                "HarmfulnessJudgeAgent": 1,
            },
        },
    }
    kwargs = {
        "case_score": 0.85,
        "uncertainty": 0.6,
        "trigger_facts": {
            "claim_uncertainty": True,
            "cross_view_conflict": True,
            "human_review_completed": False,
            "conflict_score": 0.8,
            "conflicting_experts": ["ClaimEvidenceAgent", "PostHarmAgent"],
        },
        "completed_experts": ["HarmfulnessJudgeAgent", "ClaimEvidenceAgent", "UnknownAgent"],
    }

    result = adjudicate_policy(policy, **kwargs)

    assert result == adjudicate_policy(policy, **kwargs)
    assert result["policy_binding"] is True
    assert result["advisory_only"] is True
    assert result["threshold_comparisons"] == {
        "review": {"score": 0.85, "threshold": 0.6, "met": True},
        "abstain": {
            "score": 0.85,
            "threshold": 0.3,
            "score_below": False,
            "uncertainty": 0.6,
            "uncertainty_threshold": 0.55,
            "met": True,
        },
        "retrieval": {"score": 0.85, "threshold": 0.7, "met": True},
        "countermeasure": {"score": 0.85, "threshold": 0.8, "met": True},
    }
    assert result["trigger_matches"] == {
        "retrieval_on_claim_uncertainty": True,
        "review_on_cross_view_conflict": True,
        "countermeasure_requires_human_review": False,
    }
    assert result["expert_coverage"] == {
        "completed_experts": ["ClaimEvidenceAgent", "HarmfulnessJudgeAgent"],
        "unknown_completed_experts": ["UnknownAgent"],
        "covered_weight": 1.0,
        "missing_weight": 0.0,
        "applicable_weights": {
            "ClaimEvidenceAgent": 0.666667,
            "HarmfulnessJudgeAgent": 0.333333,
        },
    }
    assert result["recommendations"] == {
        "review": True,
        "retrieval": True,
        "abstain": True,
        "countermeasure": False,
    }
    assert result["conflict"] == {
        "present": True,
        "score": 0.8,
        "experts": ["ClaimEvidenceAgent", "PostHarmAgent"],
    }


def test_adjudication_recommends_review_for_low_score_abstention():
    result = adjudicate_policy(
        {
            "policy_id": "approved-low-score",
            "activation_status": "active_human_approved",
            "policy": {"abstain_threshold": 0.4, "review_threshold": 0.9},
        },
        case_score=0.3,
        uncertainty=0.1,
        trigger_facts={},
        completed_experts=[],
    )

    assert result["threshold_comparisons"]["abstain"] == {
        "score": 0.3,
        "threshold": 0.4,
        "score_below": True,
        "uncertainty": 0.1,
        "uncertainty_threshold": 0.55,
        "met": True,
    }
    assert result["recommendations"]["abstain"] is True
    assert result["recommendations"]["review"] is True
    assert result["recommendations"]["countermeasure"] is False
