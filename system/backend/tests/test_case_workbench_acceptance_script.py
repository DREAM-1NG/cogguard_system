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
        "content_hash_changed": True,
    }
    assert result["semantic"] == {
        "policy": "evidence_overlay_only",
        "requested_stage": "semantic_enrichment",
    }
    assert {
        "acknowledge_case_blocker",
        "complete_case_action",
        "submit_case_feedback",
        "submit_closeout_review",
    }.issubset(result["audit_actions"])
    assert result["claim_boundary"] == {
        "second_platform_evidence_claimed": False,
        "statement": "No second-platform evidence is fabricated.",
    }
