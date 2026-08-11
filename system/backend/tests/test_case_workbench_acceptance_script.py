import asyncio

from scripts.case_workbench_acceptance import run_acceptance


def test_case_workbench_acceptance_closes_the_weibo_only_demo_case():
    result = asyncio.run(run_acceptance())

    assert result["schema"] == "cogguard.case_workbench_acceptance.v1"
    assert result["case_id"] == "case_trump_visit_2026_05_21"
    assert result["event_id"] == "trump_visit_2026_05_21"
    assert result["initial_state"] == "evidence_ready"
    assert result["ready_state"] == "ready_to_close"
    assert result["final_state"] == "closed"
    assert result["platforms"] == ["weibo"]
    assert result["acknowledged_missing_platforms"] == ["xhs"]
    assert result["report_preview"] == {
        "policy_acknowledgements_visible": True,
        "candidate_unvalidated_visible": True,
        "pdf_fallback_visible": True,
        "acceptance_summary_visible": True,
        "semantic_decision_support_visible": True,
        "semantic_evidence_appendix_visible": True,
        "semantic_traceability_pack_visible": True,
        "semantic_corrections_visible": True,
        "closed_loop_audit_trail_visible": True,
        "prototype_limitations_visible": True,
        "content_hash_changed": True,
    }
    assert result["semantic"] == {
        "policy": "evidence_overlay_only",
        "requested_stage": "semantic_enrichment",
        "decision_support": {
            "coverage_ratio": 1.0,
            "confidence_status": "candidate_unvalidated",
            "platform_slices": ["weibo"],
            "time_slices_present": True,
            "operator_prompt": "Use semantic outputs as triage hints, not as risk-score inputs.",
        },
        "appendix": {
            "sections": [
                "sentiment",
                "keywords",
                "topics",
                "entities",
                "stance",
                "near_duplicates",
                "community_comparison",
            ],
            "sentiment_total_texts": 3,
            "keyword_count": 4,
            "topic_count": 2,
            "entity_count": 3,
            "stance_status": "ok",
            "near_duplicate_group_count": 0,
            "community_count": 1,
            "model_status": "candidate_unvalidated",
        },
        "traceability": {
            "review_hints_present": True,
            "module_coverage_modules": [
                "sentiment",
                "keywords",
                "topics",
                "entities",
                "stance",
                "near_duplicates",
                "community_comparison",
            ],
            "semantic_example_ids": ["weibo_demo_1", "weibo_demo_2", "weibo_comment_1"],
            "action_evidence_refs": [
                {
                    "action_id": "action_review_public_response",
                    "evidence_refs": ["claim_cctv_primary", "semantic_case_workbench_demo"],
                },
                {
                    "action_id": "action_record_feedback",
                    "evidence_refs": ["run_case_workbench_demo"],
                },
            ],
        },
        "corrections": {
            "count": 1,
            "ids": ["semantic_correction_1"],
            "statuses": ["advisory_overlay"],
            "modules": ["sentiment"],
        },
    }
    assert result["claim_archive"] == {
        "primary_archive_id": "archive_cctv_primary_claim_20260811",
        "supplementary_archive_id": "archive_xinhua_supplementary_claim_20260811",
        "claim_status": "candidate_unvalidated",
        "source_capture": "markitdown_archive",
        "report_archive_provenance_visible": True,
    }
    assert result["graph_layers"] == {
        "keys": ["coordination", "propagation", "review"],
        "review_canonical_verdict_status": "approved",
    }
    assert result["closure_checklist"] == {
        "keys": [
            "canonical_verdict",
            "required_actions",
            "feedback",
            "closeout_review",
            "active_blockers",
            "claim_archive",
            "semantic_overlay_policy",
        ],
        "initial_statuses": {
            "canonical_verdict": "passed",
            "required_actions": "pending",
            "feedback": "pending",
            "closeout_review": "pending",
            "active_blockers": "blocked",
            "claim_archive": "passed",
            "semantic_overlay_policy": "passed",
        },
        "ready_statuses": {
            "canonical_verdict": "passed",
            "required_actions": "passed",
            "feedback": "passed",
            "closeout_review": "pending",
            "active_blockers": "passed",
            "claim_archive": "passed",
            "semantic_overlay_policy": "passed",
        },
        "closed_statuses": {
            "canonical_verdict": "passed",
            "required_actions": "passed",
            "feedback": "passed",
            "closeout_review": "passed",
            "active_blockers": "passed",
            "claim_archive": "passed",
            "semantic_overlay_policy": "passed",
        },
        "report_visible": True,
    }
    assert {
        "acknowledge_case_blocker",
        "complete_case_action",
        "submit_case_feedback",
        "submit_closeout_review",
        "record_semantic_correction",
    }.issubset(result["audit_actions"])
    assert result["audit_trail"] == {
        "count": 6,
        "actions": [
            "acknowledge_case_blocker",
            "complete_case_action",
            "complete_case_action",
            "submit_case_feedback",
            "record_semantic_correction",
            "submit_closeout_review",
        ],
        "semantic_correction_audited": True,
        "closed_loop_mutations": [
            "acknowledge_case_blocker",
            "complete_case_action",
            "submit_case_feedback",
            "record_semantic_correction",
            "submit_closeout_review",
        ],
    }
    assert result["claim_boundary"] == {
        "second_platform_evidence_claimed": False,
        "statement": "No second-platform evidence is fabricated.",
    }
    assert result["prototype_constraints"] == {
        "platform_evidence_scope": "weibo_only_with_xhs_gap",
        "semantic_examples_text_scope": "excerpt_only_not_full_source_text",
        "semantic_score_policy": "evidence_overlay_only",
        "risk_score_boundary": "semantic_artifacts_do_not_mutate_coordination_propagation_review_scores",
        "model_validation_status": "candidate_unvalidated",
        "pdf_export_status": "html_pdf_fallback",
    }
