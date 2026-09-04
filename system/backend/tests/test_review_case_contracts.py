"""Public product contracts for event review cases."""

from datetime import datetime, timezone

import pytest
from pydantic import BaseModel, ValidationError

from app.schemas.review_case import (
    ActionRequired,
    CaseActivity,
    CaseEvent,
    DecisionConfirmRequest,
    DecisionDraftUpsert,
    Disposition,
    EvidenceAnnotationCreate,
    EvidenceAssessment,
    EvidenceSufficiency,
    ReviewCaseDetail,
    ReviewCaseEvidence,
    ReviewCaseSummary,
    ReviewConclusion,
    ReviewRequestCreate,
    ReviewUrgency,
)
from app.schemas.analysis import ModelActivationRequest, ModelCandidateApprovalRequest


def enum_values(enum_type) -> set[str]:
    return {member.value for member in enum_type}


def nested_model_types(model_type: type[BaseModel]) -> set[type[BaseModel]]:
    discovered = {model_type}
    pending = [model_type]
    while pending:
        current = pending.pop()
        for field in current.model_fields.values():
            annotation = field.annotation
            candidates = getattr(annotation, "__args__", ()) or (annotation,)
            for candidate in candidates:
                nested = getattr(candidate, "__args__", ()) or (candidate,)
                for item in nested:
                    if isinstance(item, type) and issubclass(item, BaseModel) and item not in discovered:
                        discovered.add(item)
                        pending.append(item)
    return discovered


def test_review_case_enums_are_exact_string_contracts():
    assert enum_values(ReviewConclusion) == {
        "harmful",
        "non_harmful",
        "insufficient_evidence",
    }
    assert enum_values(EvidenceSufficiency) == {"sufficient", "limited", "insufficient"}
    assert enum_values(ReviewUrgency) == {"routine", "watch", "urgent", "critical"}
    assert enum_values(Disposition) == {
        "monitor",
        "gather_evidence",
        "escalate",
        "respond",
        "archive",
    }
    assert enum_values(EvidenceAssessment) == {
        "supports",
        "contradicts",
        "irrelevant",
        "unresolved",
    }
    assert enum_values(ActionRequired) == {
        "none",
        "add_evidence",
        "review_available",
        "confirm_decision",
        "reconfirm_decision",
    }
    for enum_type in (
        ReviewConclusion,
        EvidenceSufficiency,
        ReviewUrgency,
        Disposition,
        EvidenceAssessment,
        ActionRequired,
    ):
        assert issubclass(enum_type, str)


@pytest.mark.parametrize(
    ("request_type", "payload"),
    [
        (
            EvidenceAnnotationCreate,
            {
                "evidence_ref": "weibo:post:1",
                "assessment": "supports",
                "note": "Supports the event-level finding.",
            },
        ),
        (ReviewRequestCreate, {"reason": "The available evidence conflicts."}),
        (
            DecisionDraftUpsert,
            {
                "conclusion": "insufficient_evidence",
                "urgency": "watch",
                "disposition": "gather_evidence",
                "rationale": "More independent sources are required.",
                "expected_version": 0,
            },
        ),
        (DecisionConfirmRequest, {"expected_draft_version": 1}),
    ],
)
def test_write_requests_forbid_unknown_fields(request_type, payload):
    request_type.model_validate(payload)

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        request_type.model_validate({**payload, "run_id": "must-not-be-accepted"})


def test_product_response_models_have_no_runtime_or_model_governance_fields():
    forbidden_names = {
        "artifact",
        "artifact_hash",
        "artifact_uri",
        "checkpoint",
        "model",
        "model_version",
        "agent",
        "agent_name",
        "run_id",
        "job_id",
        "task_id",
        "confidence",
        "raw_confidence",
        "runtime_status",
        "status",
    }
    response_types = {
        ReviewCaseSummary,
        ReviewCaseDetail,
        ReviewCaseEvidence,
        CaseActivity,
        CaseEvent,
    }

    all_models = set()
    for response_type in response_types:
        all_models.update(nested_model_types(response_type))

    leaked_fields = {
        field_name
        for model_type in all_models
        for field_name in model_type.model_fields
        if field_name in forbidden_names
    }
    assert leaked_fields == set()


def test_case_event_serializes_only_business_safe_sse_fields():
    event = CaseEvent(
        cursor=17,
        case_id="case-trump-visit",
        activity_type="review_requested",
        action_required=ActionRequired.NONE,
        message="复核申请已提交",
        occurred_at=datetime(2026, 8, 3, tzinfo=timezone.utc),
    )

    assert event.model_dump(mode="json") == {
        "cursor": 17,
        "case_id": "case-trump-visit",
        "activity_type": "review_requested",
        "action_required": "none",
        "message": "复核申请已提交",
        "occurred_at": "2026-08-03T00:00:00Z",
    }


def test_model_activation_request_cannot_supply_quality_gate_booleans_or_approvers():
    request = ModelActivationRequest(reason="Activate the approved candidate.")
    assert request.reason

    with pytest.raises(ValidationError):
        ModelActivationRequest.model_validate(
            {
                "reason": "client override",
                "quality_gates": {"safety_passed": True},
                "approved_by": [1, 2],
            }
        )


def test_model_candidate_approval_request_uses_the_authenticated_administrator():
    request = ModelCandidateApprovalRequest(approval_notes="Metrics and artifact were reviewed.")
    assert request.approval_notes

    with pytest.raises(ValidationError):
        ModelCandidateApprovalRequest.model_validate(
            {"approval_notes": "attempted impersonation", "approver_id": 8}
        )
