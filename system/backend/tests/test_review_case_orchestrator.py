from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from app.core.analysis import TimeWindow, build_event_snapshot
from app.models.review_case import CaseActivity, ReviewCase, ReviewCaseSnapshotRevision
from app.services.review_case_orchestrator import (
    CaseRevisionRef,
    ReviewCaseOrchestrator,
    SqlAlchemyReviewCaseRepository,
    derive_analysis_windows,
    record_teacher_advisory,
    teacher_routing_reasons,
)


def _dt(hour: int) -> datetime:
    return datetime(2026, 5, 21, hour, tzinfo=timezone.utc)


def _snapshot(*, quality: str = "pass"):
    snapshot = build_event_snapshot(
        event_id="trump_visit_2026_05_21",
        posts=[
            {
                "event_id": "trump_visit_2026_05_21",
                "platform": "weibo",
                "post_id": "p1",
                "author_id": "u1",
                "timestamp": _dt(8),
                "content": "event evidence",
            }
        ],
        comments=[],
        core_window=TimeWindow(start=_dt(7), end=_dt(9)),
        context_window=TimeWindow(start=_dt(6), end=_dt(10)),
    )
    snapshot.quality_report.status = quality
    return snapshot


class FakeRegistry:
    def __init__(self, snapshot) -> None:
        self.snapshot = snapshot
        self.created_runs: list[dict] = []

    async def create_run(self, **kwargs):
        run = {"run_id": f"run_{len(self.created_runs) + 1}", **kwargs}
        self.created_runs.append(run)
        return run


class FakeExecutor:
    def __init__(self, registry: FakeRegistry) -> None:
        self.registry = registry

    async def execute_run(self, run_id: str):
        run = next(item for item in self.registry.created_runs if item["run_id"] == run_id)
        if run["requested_stages"] == ["teacher"]:
            return {
                "run_id": run_id,
                "results": {
                    "teacher": {
                        "status": "queued",
                        "job_id": "teacher_job_1",
                        "verdict_type": "teacher_advisory",
                    }
                },
            }
        return {
            "run_id": run_id,
            "results": {
                "coordination_discover": {
                    "status": "ok",
                    "summary": {"coordinated_accounts": 2},
                    "community_lineage": [{"community_id": "community_1", "size": 2}],
                    "account_risk_tiers": [{"account_id": "u1"}],
                },
                "propagation_analysis": {
                    "status": "ok",
                    "scale_interval": [120, 180],
                    "next_hop_ranking": [{"node_id": "u2"}],
                },
                "student": {
                    "status": "ok",
                    "label": "harmful",
                    "risk_level": "high",
                    "abstain": True,
                    "review_required": True,
                    "review_reason": ["uncertain"],
                    "evidence": {"top_claims": ["claim"]},
                },
            },
        }


class FakeRepository:
    def __init__(self) -> None:
        self.created_revision = True
        self.projections: list[dict] = []
        self.teacher_submissions: list[dict] = []

    async def upsert_revision(self, **kwargs):
        return CaseRevisionRef(
            case_id="case_1",
            snapshot_revision_id="revision_1",
            revision_number=1,
            created_case=True,
            created_revision=self.created_revision,
        )

    async def apply_analysis_projection(self, **kwargs):
        self.projections.append(kwargs)

    async def has_active_teacher(self, **kwargs):
        return False

    async def record_teacher_submission(self, **kwargs):
        self.teacher_submissions.append(kwargs)


def test_analysis_windows_use_current_crawl_for_core_and_event_for_context():
    posts = [
        {"crawl_job_id": 7, "timestamp": _dt(8)},
        {"crawl_job_id": 8, "timestamp": _dt(6)},
    ]
    comments = [
        {"crawl_job_id": 7, "timestamp": _dt(9)},
        {"crawl_job_id": 8, "timestamp": _dt(10)},
    ]

    core, context = derive_analysis_windows(posts=posts, comments=comments, crawl_job_id=7)

    assert core.start == _dt(8)
    assert core.end > _dt(9)
    assert context.start == _dt(6)
    assert context.end > _dt(10)


def test_new_snapshot_runs_core_analysis_and_routes_uncertain_case_to_teacher():
    async def scenario():
        snapshot = _snapshot()
        registry = FakeRegistry(snapshot)
        repository = FakeRepository()
        orchestrator = ReviewCaseOrchestrator(
            registry=registry,
            executor=FakeExecutor(registry),
            repository=repository,
        )

        outcome = await orchestrator.analyze_snapshot(
            snapshot=snapshot,
            title="Trump visit",
            created_by=7,
        )

        assert outcome.created_revision is True
        assert registry.created_runs[0]["requested_stages"] == [
            "coordination_discover",
            "propagation_analysis",
            "student",
        ]
        assert registry.created_runs[1]["requested_stages"] == ["teacher"]
        assert outcome.teacher_requested is True
        assert "student_abstained" in outcome.teacher_reasons
        assert repository.projections[0]["projection"].conclusion == "harmful"
        assert repository.projections[0]["projection"].action_required == "add_evidence"
        assert repository.teacher_submissions[0]["teacher_verdict_id"] == "teacher_job_1"

        repository.created_revision = False
        repeated = await orchestrator.analyze_snapshot(
            snapshot=snapshot,
            title="Trump visit",
            created_by=7,
        )
        assert repeated.created_revision is False
        assert len(registry.created_runs) == 2

    asyncio.run(scenario())


def test_teacher_policy_does_not_submit_for_sufficient_routine_finding():
    reasons = teacher_routing_reasons(
        student={
            "status": "ok",
            "label": "non_harmful",
            "risk_level": "low",
            "abstain": False,
            "review_required": False,
        },
        evidence_sufficiency="sufficient",
        urgency="routine",
    )

    assert reasons == []


def test_advisory_for_older_revision_does_not_replace_current_case_projection():
    class Result:
        def __init__(self, value=None, *, first=None) -> None:
            self.value = value
            self.first_value = first

        def scalar_one_or_none(self):
            return self.value

        def scalar_one(self):
            return self.value

        def first(self):
            return self.first_value

    class FakeSession:
        def __init__(self, results) -> None:
            self.results = list(results)
            self.added = []

        async def execute(self, _statement):
            return self.results.pop(0)

        def add(self, row) -> None:
            self.added.append(row)

        async def flush(self) -> None:
            return None

    async def scenario():
        older = SimpleNamespace(
            case_id="case_1",
            snapshot_revision_id="revision_1",
            revision_number=1,
            teacher_verdict_id="teacher_job_1",
        )
        latest = SimpleNamespace(
            snapshot_revision_id="revision_2",
            revision_number=2,
        )
        case = SimpleNamespace(
            case_id="case_1",
            preliminary_conclusion="harmful",
            action_required="confirm_decision",
            business_summary_json='{"review_advisory":{"rationale":"current"}}',
        )
        db = FakeSession(
            [
                Result(older),
                Result(case),
                Result(latest),
                Result(first=None),
            ]
        )

        recorded = await record_teacher_advisory(
            snapshot_id="snapshot_1",
            verdict={"verdict_id": "teacher_advisory_1", "label": "non_harmful"},
            db=db,
        )

        assert recorded is True
        assert older.teacher_verdict_id == "teacher_advisory_1"
        assert case.action_required == "confirm_decision"
        assert case.business_summary_json == '{"review_advisory":{"rationale":"current"}}'
        assert len(db.added) == 1
        assert db.added[0].snapshot_revision_id == "revision_1"
        assert db.added[0].action_required == "none"

    asyncio.run(scenario())


def test_changed_fingerprint_requires_reconfirmation_when_case_has_decision():
    class Result:
        def __init__(self, value=None, *, first=None) -> None:
            self.value = value
            self.first_value = first

        def scalar_one_or_none(self):
            return self.value

        def first(self):
            return self.first_value

    class FakeSession:
        def __init__(self, results) -> None:
            self.results = list(results)
            self.added: list[object] = []

        async def execute(self, _statement):
            return self.results.pop(0)

        def add(self, row) -> None:
            self.added.append(row)

        async def flush(self) -> None:
            return None

    async def scenario():
        case = ReviewCase(
            case_id="case_1",
            event_id="trump_visit_2026_05_21",
            title="Trump visit",
            preliminary_conclusion="harmful",
            evidence_sufficiency="sufficient",
            urgency="watch",
            disposition="monitor",
            action_required="none",
            preliminary_finding_json="{}",
            business_summary_json="{}",
            created_by=7,
            updated_by=7,
        )
        db = FakeSession(
            [
                Result(case),
                Result(None),
                Result(1),
                Result(first=(1,)),
                Result(first=None),
            ]
        )

        ref = await SqlAlchemyReviewCaseRepository(db).upsert_revision(
            snapshot=_snapshot(),
            title="Trump visit updated",
            created_by=7,
        )

        revisions = [row for row in db.added if isinstance(row, ReviewCaseSnapshotRevision)]
        activities = [row for row in db.added if isinstance(row, CaseActivity)]
        assert ref.created_revision is True
        assert ref.revision_number == 2
        assert len(revisions) == 1
        assert case.action_required == "reconfirm_decision"
        assert len(activities) == 1
        assert activities[0].activity_type == "reconfirmation_required"
        assert activities[0].action_required == "reconfirm_decision"

    asyncio.run(scenario())
