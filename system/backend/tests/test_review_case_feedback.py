from types import SimpleNamespace

from app.services.review_case_service import (
    _canonical_source_id,
    _decision_feedback_payload,
    _feedback_id,
)


def _decision():
    return SimpleNamespace(
        decision_id="decision_1",
        version=2,
        conclusion="harmful",
        urgency="urgent",
        disposition="escalate",
        rationale="Evidence supports escalation.",
        key_evidence_refs_json='["weibo:post:p1"]',
        unresolved_items_json='["source ownership"]',
    )


def test_confirmed_decision_feedback_is_structured_and_deterministic():
    payload = _decision_feedback_payload(_decision())

    assert payload == {
        "source": "confirmed_decision",
        "decision_id": "decision_1",
        "decision_version": 2,
        "conclusion": "harmful",
        "urgency": "urgent",
        "disposition": "escalate",
        "rationale": "Evidence supports escalation.",
        "key_evidence_refs": ["weibo:post:p1"],
        "unresolved_items": ["source ownership"],
    }
    assert _feedback_id("decision_1") == _feedback_id("decision_1")
    assert _feedback_id("decision_1") != _feedback_id("decision_2")


def test_canonical_source_identity_binds_case_snapshot_and_draft_version():
    first = _canonical_source_id(
        case_id="case_1",
        snapshot_revision_id="revision_1",
        draft_version=3,
    )
    repeated = _canonical_source_id(
        case_id="case_1",
        snapshot_revision_id="revision_1",
        draft_version=3,
    )
    changed = _canonical_source_id(
        case_id="case_1",
        snapshot_revision_id="revision_2",
        draft_version=3,
    )

    assert first == repeated
    assert first != changed
    assert len(first) <= 128
