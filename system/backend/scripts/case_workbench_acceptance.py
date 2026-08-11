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


async def run_acceptance() -> dict[str, Any]:
    """Exercise the default Weibo-only demo case through closeout."""
    service = CaseWorkbenchService(mongo_db={})
    initial = await service.get_case("case_trump_visit_2026_05_21")
    _require(initial["case_id"] == "case_trump_visit_2026_05_21", "unexpected case id")
    _require(initial["evidence"]["source_mode"] == "demo_fixture", "expected demo fixture")
    _require(initial["platforms"] == ["weibo"], "fallback evidence must remain Weibo-only")
    _require(initial["active_blockers"][0]["code"] == "platform_gap", "expected platform gap")
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
    _require(ready["state"] == "ready_to_close", "expected ready_to_close after actions and feedback")

    closed = await service.submit_closeout_review(
        ready["case_id"], actor_id="acceptance_script", summary="Local prototype closeout accepted."
    )
    _require(closed["state"] == "closed", "expected closed after closeout review")
    report_html = await service.render_report_html(closed["case_id"], 1, pdf_fallback=True)
    _require("Policy acknowledgements" in report_html, "report must show policy acknowledgements")
    _require("candidate_unvalidated" in report_html, "report must show semantic model status")
    _require("Production PDF rendering is pending." in report_html, "report must show PDF fallback")
    _require("archive_cctv_primary_claim_20260811" in report_html, "report must show primary archive provenance")
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
