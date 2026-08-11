"""Run the Case Workbench's evidence-honest demo lifecycle locally."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from app.services.case_workbench_service import CaseWorkbenchService

__all__ = ["main", "run_acceptance"]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _checklist_statuses(case: dict[str, Any]) -> dict[str, str]:
    return {item["key"]: item["status"] for item in case["closure_checklist"]}


async def run_acceptance() -> dict[str, Any]:
    """Exercise the default Weibo-only demo case through closeout."""
    service = CaseWorkbenchService(mongo_db={})
    initial = await service.get_case("case_trump_visit_2026_05_21")
    checklist_keys = [
        "canonical_verdict",
        "required_actions",
        "feedback",
        "closeout_review",
        "active_blockers",
        "claim_archive",
        "semantic_overlay_policy",
    ]
    initial_checklist = _checklist_statuses(initial)
    _require(initial["case_id"] == "case_trump_visit_2026_05_21", "unexpected case id")
    _require(initial["evidence"]["source_mode"] == "demo_fixture", "expected demo fixture")
    _require(initial["platforms"] == ["weibo"], "fallback evidence must remain Weibo-only")
    _require(initial["active_blockers"][0]["code"] == "platform_gap", "expected platform gap")
    _require(list(initial_checklist) == checklist_keys, "closure checklist keys must remain stable")
    _require(initial_checklist["canonical_verdict"] == "passed", "canonical verdict gate should initially pass")
    _require(initial_checklist["required_actions"] == "pending", "required actions gate should initially pend")
    _require(initial_checklist["feedback"] == "pending", "feedback gate should initially pend")
    _require(initial_checklist["closeout_review"] == "pending", "closeout review gate should initially pend")
    _require(initial_checklist["active_blockers"] == "blocked", "platform gap should block initial closeout")
    _require(initial_checklist["claim_archive"] == "passed", "archive-backed claims should satisfy archive gate")
    _require(initial_checklist["semantic_overlay_policy"] == "passed", "semantic overlay policy gate should pass")
    initial_hash = initial["reports"][0]["content_hash"]

    acknowledged = await service.acknowledge_blocker(
        initial["case_id"],
        initial["active_blockers"][0]["blocker_id"],
        actor_id="acceptance_script",
        reason="The documented XHS gap is acknowledged for local prototype acceptance.",
    )
    acknowledgement = acknowledged["blocker_acknowledgements"][0]
    _require(acknowledged["active_blockers"] == [], "acknowledgement must clear active blockers")
    _require(acknowledgement["missing_platforms"] == ["xhs"], "XHS gap must remain recorded")

    case = acknowledged
    for action in case["actions"]:
        case = await service.complete_action(
            case["case_id"], action["action_id"], actor_id="acceptance_script", note="Acceptance action completed."
        )
    ready = await service.submit_feedback(
        case["case_id"], actor_id="acceptance_script", content="Acceptance feedback recorded."
    )
    ready_checklist = _checklist_statuses(ready)
    _require(ready["state"] == "ready_to_close", "expected ready_to_close after actions and feedback")
    _require(ready_checklist["active_blockers"] == "passed", "acknowledged platform gap should clear blocker gate")
    _require(ready_checklist["required_actions"] == "passed", "completed actions should pass action gate")
    _require(ready_checklist["feedback"] == "passed", "feedback should pass feedback gate")
    _require(ready_checklist["closeout_review"] == "pending", "closeout review should pend before submission")

    closed = await service.submit_closeout_review(
        ready["case_id"], actor_id="acceptance_script", summary="Local prototype closeout accepted."
    )
    closed_checklist = _checklist_statuses(closed)
    _require(closed["state"] == "closed", "expected closed after closeout review")
    _require(set(closed_checklist.values()) == {"passed"}, "all closure gates should pass after closeout")
    report_html = await service.render_report_html(closed["case_id"], 1, pdf_fallback=True)
    _require("Policy acknowledgements" in report_html, "report must show policy acknowledgements")
    _require("candidate_unvalidated" in report_html, "report must show semantic model status")
    _require("Production PDF rendering is pending." in report_html, "report must show PDF fallback")
    _require("archive_cctv_primary_claim_20260811" in report_html, "report must show primary archive provenance")
    _require("Closure checklist" in report_html, "report must show closure checklist")
    _require(closed["reports"][0]["content_hash"] != initial_hash, "report hash must track visible mutations")

    requested_stages = closed["analysis_runs"][0]["requested_stages"]
    semantic_policy = closed["workflow_summary"]["semantic_score_policy"]
    _require(semantic_policy == "evidence_overlay_only", "semantic policy must remain overlay-only")
    _require("semantic_enrichment" in requested_stages, "semantic stage must be explicitly requested")
    _require(closed["platforms"] == ["weibo"], "no second-platform evidence may be claimed")
    primary_claim = closed["primary_claim"]
    supplementary_claim = closed["supplementary_claims"][0]
    graph_layers = closed["graph"]["evidence_layers"]
    _require(primary_claim["status"] == "candidate_unvalidated", "primary claim must remain unapproved")
    _require(supplementary_claim["status"] == "candidate_unvalidated", "supplementary claim must remain unapproved")
    _require(primary_claim["source_content_capture"] == "markitdown_archive", "primary source capture must use archive")
    _require(
        [layer["key"] for layer in graph_layers] == ["coordination", "propagation", "review"],
        "graph must expose CPR evidence layers",
    )

    return {
        "schema": "cogguard.case_workbench_acceptance.v1",
        "case_id": closed["case_id"],
        "event_id": closed["event_id"],
        "initial_state": initial["state"],
        "ready_state": ready["state"],
        "final_state": closed["state"],
        "platforms": closed["platforms"],
        "acknowledged_missing_platforms": acknowledgement["missing_platforms"],
        "report_preview": {
            "policy_acknowledgements_visible": True,
            "candidate_unvalidated_visible": True,
            "pdf_fallback_visible": True,
            "content_hash_changed": True,
        },
        "semantic": {"policy": semantic_policy, "requested_stage": "semantic_enrichment"},
        "claim_archive": {
            "primary_archive_id": primary_claim["source_archive_id"],
            "supplementary_archive_id": supplementary_claim["source_archive_id"],
            "claim_status": primary_claim["status"],
            "source_capture": primary_claim["source_content_capture"],
            "report_archive_provenance_visible": True,
        },
        "graph_layers": {
            "keys": [layer["key"] for layer in graph_layers],
            "review_canonical_verdict_status": graph_layers[2]["metrics"]["canonical_verdict_status"],
        },
        "closure_checklist": {
            "keys": checklist_keys,
            "initial_statuses": initial_checklist,
            "ready_statuses": ready_checklist,
            "closed_statuses": closed_checklist,
            "report_visible": True,
        },
        "audit_actions": [event["action"] for event in closed["audit_events"]],
        "claim_boundary": {
            "second_platform_evidence_claimed": False,
            "statement": "No second-platform evidence is fabricated.",
        },
    }


def main() -> None:
    print(json.dumps(asyncio.run(run_acceptance()), ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
