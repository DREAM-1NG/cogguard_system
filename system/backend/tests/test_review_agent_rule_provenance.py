from app.core.review.agent_policy import normalize_rule_provenance, refine_agent_policy_loop


def test_rule_provenance_normalizes_current_rule_artifact_fields():
    result = normalize_rule_provenance(
        {
            "rule_id": "rule-7",
            "source": "human_feedback",
            "source_detail": "case-review calibration",
            "round": 2,
            "validation_metrics": {"macro_f1": 0.8},
            "held_out_metrics": {"macro_f1": 0.75},
            "split_fingerprint": "split-a",
            "case_fingerprint": "cases-b",
            "validation_split_fingerprint": "validation-split-a",
            "held_out_split_fingerprint": "held-out-split-a",
            "validation_case_fingerprint": "validation-cases-a",
            "held_out_case_fingerprint": "held-out-cases-a",
            "evaluator_version": "policy-evaluator-v2",
            "approval_ref": "approval-42",
            "evidence_refs": ["evidence-1"],
            "feedback_refs": ["feedback-1"],
        }
    )

    assert result == {
        "rule_id": "rule-7",
        "source": "human_feedback",
        "source_detail": "case-review calibration",
        "validation_round": 2,
        "validation_metrics": {"macro_f1": 0.8},
        "held_out_metrics": {"macro_f1": 0.75},
        "split_fingerprint": "split-a",
        "case_fingerprint": "cases-b",
        "validation_split_fingerprint": "validation-split-a",
        "held_out_split_fingerprint": "held-out-split-a",
        "validation_case_fingerprint": "validation-cases-a",
        "held_out_case_fingerprint": "held-out-cases-a",
        "evaluator_version": "policy-evaluator-v2",
        "approval_ref": "approval-42",
        "evidence_refs": ["evidence-1"],
        "feedback_refs": ["feedback-1"],
    }


def test_rule_provenance_keeps_legacy_artifacts_with_safe_defaults():
    result = normalize_rule_provenance(
        {
            "rule_id": "legacy-rule",
            "source": "validation metric search",
            "round": "3",
            "raw_rule": {"evidence_refs": ["legacy-evidence"]},
        }
    )

    assert result["rule_id"] == "legacy-rule"
    assert result["source"] == "validation_metric"
    assert result["source_detail"] == "validation metric search"
    assert result["validation_round"] == 3
    assert result["validation_metrics"] is None
    assert result["held_out_metrics"] is None
    assert result["split_fingerprint"] is None
    assert result["case_fingerprint"] is None
    assert result["validation_split_fingerprint"] is None
    assert result["held_out_split_fingerprint"] is None
    assert result["validation_case_fingerprint"] is None
    assert result["held_out_case_fingerprint"] is None
    assert result["evaluator_version"] is None
    assert result["approval_ref"] is None
    assert result["evidence_refs"] == ["legacy-evidence"]
    assert result["feedback_refs"] == []


def test_refinement_records_generated_provenance_for_candidates_and_accepted_rules():
    manifest = {
        "dataset_id": "provenance-loop",
        "splits": {
            "validation": [
                {"case_id": "validation-harmful", "gold_label": "harmful", "harm_score": 0.56},
                {"case_id": "validation-safe", "gold_label": "non_harmful", "harm_score": 0.22},
            ],
            "held_out": [
                {"case_id": "held-out-harmful", "gold_label": "harmful", "harm_score": 0.57},
                {"case_id": "held-out-safe", "gold_label": "non_harmful", "harm_score": 0.25},
            ],
        },
        "baseline_policy": {"review_threshold": 0.6},
    }
    feedback_memory = [
        {
            "memory_id": "feedback-memory-1",
            "review_id": "review-1",
            "error_types": ["false_negative"],
            "evidence_refs": ["evidence-1"],
        }
    ]

    result = refine_agent_policy_loop(
        manifest,
        feedback_memory=feedback_memory,
        max_iterations=1,
        enable_llm_rule_generator=True,
        rule_generator=lambda **_kwargs: [
            {
                "rule_id": "accepted-lower-review",
                "source": "human_feedback",
                "policy_patch": {"review_threshold": 0.54},
            }
        ],
    )

    candidate = next(rule for rule in result["candidate_rules"] if rule["rule_id"] == "accepted-lower-review")
    accepted = next(rule for rule in result["candidate_rules"] if rule["status"] == "accepted_for_round")
    for rule in (candidate, accepted):
        assert rule["validation_metrics"]
        assert rule["held_out_metrics"]
        assert rule["split_fingerprint"]
        assert rule["case_fingerprint"]
        assert rule["validation_split_fingerprint"]
        assert rule["held_out_split_fingerprint"]
        assert rule["validation_case_fingerprint"]
        assert rule["held_out_case_fingerprint"]
        assert rule["evaluator_version"]
        assert rule["feedback_refs"] == ["feedback-memory-1"]
        assert rule["evidence_refs"] == ["evidence-1"]
        assert rule["approval_state"] == "candidate_pending_human_approval"
        assert rule["approval_ref"] is None
    assert result["activation_status"] == "candidate_pending_human_approval"


def test_refinement_hides_held_out_data_from_rule_generator():
    generator_calls = []

    refine_agent_policy_loop(
        _refinement_manifest(),
        max_iterations=1,
        enable_llm_rule_generator=True,
        rule_generator=lambda **kwargs: generator_calls.append(kwargs) or [],
    )

    assert generator_calls
    assert all("held_out" not in key for key in generator_calls[0])
    assert "held-out" not in repr(generator_calls[0])


def test_refinement_selection_ignores_held_out_labels():
    baseline = _refinement_manifest()
    changed_held_out = _refinement_manifest()
    changed_held_out["splits"]["held_out"] = [
        {**case, "gold_label": "non_harmful" if case["gold_label"] == "harmful" else "harmful"}
        for case in changed_held_out["splits"]["held_out"]
    ]

    rule_generator = lambda **_kwargs: [
        {"rule_id": "lower-review", "policy_patch": {"review_threshold": 0.54}},
        {"rule_id": "raise-review", "policy_patch": {"review_threshold": 0.64}},
    ]
    baseline_result = refine_agent_policy_loop(
        baseline,
        max_iterations=1,
        enable_llm_rule_generator=True,
        rule_generator=rule_generator,
    )
    changed_result = refine_agent_policy_loop(
        changed_held_out,
        max_iterations=1,
        enable_llm_rule_generator=True,
        rule_generator=rule_generator,
    )

    assert baseline_result["policy"] == changed_result["policy"]
    assert baseline_result["refinement_trace"][0]["accepted_rule_id"] == changed_result["refinement_trace"][0]["accepted_rule_id"]


def _refinement_manifest():
    return {
        "dataset_id": "held-out-isolation",
        "baseline_policy": {"review_threshold": 0.6},
        "splits": {
            "validation": [
                {"case_id": "validation-harmful", "gold_label": "harmful", "harm_score": 0.56},
                {"case_id": "validation-safe", "gold_label": "non_harmful", "harm_score": 0.22},
            ],
            "held_out": [
                {"case_id": "held-out-harmful", "gold_label": "harmful", "harm_score": 0.57},
                {"case_id": "held-out-safe", "gold_label": "non_harmful", "harm_score": 0.25},
            ],
        },
    }
