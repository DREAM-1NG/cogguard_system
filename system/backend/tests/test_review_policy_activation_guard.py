import asyncio
import json

from app.services import risk_service


class FakeResult:
    def __init__(self, row):
        self.row = row

    def scalar_one_or_none(self):
        return self.row


class FakeSession:
    def __init__(self, row):
        self.row = row

    async def execute(self, _statement):
        return FakeResult(self.row)

    async def flush(self):
        pass


def _db_with_report():
    report = {"review_harmfulness": {}}
    row = type("RiskRow", (), {"report_json": json.dumps(report)})()
    return FakeSession(row)


async def _capture_manual_review(calls, **kwargs):
    calls.append(kwargs)
    return {
        "agent_reports": [],
        "summary": {"completed": 0},
        "audit": {"run_id": "fake-run"},
    }


def test_run_agent_review_ignores_unapproved_explicit_policy_and_memory(monkeypatch):
    policy = {
        "policy_id": "candidate-policy",
        "activation_status": "candidate_pending_human_approval",
        "policy": {"review_threshold": 0.54},
        "error_memory_summary": {"feedback_count": 99, "must_not_control_review": True},
    }
    calls = []
    monkeypatch.setattr(risk_service, "_Review_POLICY_REGISTRY", {policy["policy_id"]: policy})
    monkeypatch.setattr(
        risk_service,
        "run_manual_agent_review",
        lambda **kwargs: _capture_manual_review(calls, **kwargs),
    )

    result = asyncio.run(
        risk_service.run_agent_review(
            report_id="report-1",
            agent_names=["HarmfulnessJudgeAgent"],
            policy_id=policy["policy_id"],
            db=_db_with_report(),
        )
    )

    assert calls[0]["policy"] is None
    assert calls[0]["error_memory_summary"] == {}
    assert result["review_result"]["audit"]["policy_provenance"] == {
        "status": "ignored_not_human_approved",
        "policy_id": policy["policy_id"],
        "activation_status": "candidate_pending_human_approval",
    }


def test_run_agent_review_passes_human_approved_policy_unchanged(monkeypatch):
    policy = {
        "policy_id": "approved-policy",
        "activation_status": "active_human_approved",
        "policy": {"review_threshold": 0.54},
        "error_memory_summary": {"feedback_count": 2},
    }
    calls = []
    monkeypatch.setattr(risk_service, "_Review_POLICY_REGISTRY", {policy["policy_id"]: policy})
    monkeypatch.setattr(
        risk_service,
        "run_manual_agent_review",
        lambda **kwargs: _capture_manual_review(calls, **kwargs),
    )

    asyncio.run(
        risk_service.run_agent_review(
            report_id="report-1",
            agent_names=["HarmfulnessJudgeAgent"],
            policy_id=policy["policy_id"],
            db=_db_with_report(),
        )
    )

    assert calls[0]["policy"] is policy
    assert calls[0]["error_memory_summary"] == policy["error_memory_summary"]
