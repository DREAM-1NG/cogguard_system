from pydantic import ValidationError

from app.schemas.analysis import AnalysisRunCreateRequest


def test_analysis_run_create_request_defaults_to_complete_prototype_chain():
    request = AnalysisRunCreateRequest(event_id="event-1", snapshot_id="snapshot-1")

    assert request.requested_stages == [
        "coordination_discover",
        "propagation_analysis",
        "student",
        "teacher",
    ]


def test_analysis_run_create_request_normalizes_legacy_stage_aliases():
    request = AnalysisRunCreateRequest(
        event_id="event-1",
        snapshot_id="snapshot-1",
        requested_stages=["coordination", "propagation_engine", "review_student"],
    )

    assert request.requested_stages == ["coordination_discover", "propagation_analysis", "student"]


def test_analysis_run_create_request_rejects_unknown_stage():
    try:
        AnalysisRunCreateRequest(
            event_id="event-1",
            snapshot_id="snapshot-1",
            requested_stages=["coordination_discover", "bogus"],
        )
    except ValidationError as exc:
        assert "Unknown analysis stage" in str(exc)
    else:
        raise AssertionError("AnalysisRunCreateRequest accepted an unknown stage")
