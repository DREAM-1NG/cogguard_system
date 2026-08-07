from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import app.services.review_case_service as review_case_service
from app.models.risk_assessment import RiskAssessment
from app.models.review_system import ReviewAgentFeedback, ReviewAgentReport
from app.models.review_case import ReviewDecisionDraft
from app.services.review_case_service import (
    ReviewCaseService,
    _with_snapshot_account_names,
    build_case_summary,
    build_evidence_item,
)


def _case_row() -> SimpleNamespace:
    return SimpleNamespace(
        case_id="case_trump_visit",
        event_id="trump_visit_2026_05_21",
        title="Trump visit discussion",
        preliminary_conclusion="insufficient_evidence",
        evidence_sufficiency="limited",
        urgency="watch",
        disposition="gather_evidence",
        action_required="confirm_decision",
        preliminary_finding_json=(
            '{"conclusion":"harmful","rationale":"Observed coordinated sharing.",'
            '"key_evidence_refs":["weibo:post:p1"],"model_version":"hidden"}'
        ),
        business_summary_json=(
            '{"sufficiency_reasons":["Cross-platform agreement is incomplete."],'
            '"missing_evidence":["Independent source"],'
            '"coordination":{"narrative":"Shared targets were observed.",'
            '"key_communities":["Community 1"],"key_accounts":["Account A"],'
            '"artifact_uri":"hidden"},'
            '"propagation":{"narrative":"Spread remains active.","trend":"rising",'
            '"forecast_range":"120-180 accounts","likely_next_targets":["Community 2"],'
            '"run_id":"hidden"},"checkpoint":"hidden"}'
        ),
        updated_at=datetime(2026, 8, 3, tzinfo=timezone.utc),
    )


def test_case_summary_is_a_business_whitelist_projection():
    result = build_case_summary(_case_row()).model_dump(mode="json")
    serialized = str(result).lower()

    assert result["preliminary_finding"]["conclusion"] == "harmful"
    assert result["coordination_summary"]["key_communities"] == ["Community 1"]
    assert result["propagation_summary"]["forecast_range"] == "120 至 180 个账号"
    for forbidden in ("artifact", "checkpoint", "model_version", "run_id"):
        assert forbidden not in serialized


def test_case_summary_uses_business_text_for_system_generated_sections():
    row = _case_row()
    row.title = "Teacher Agent model checkpoint review"
    row.preliminary_finding_json = (
        '{"conclusion":"harmful","rationale":"Student Agent exposed raw confidence and runtime state."}'
    )
    row.business_summary_json = (
        '{"coordination":{"narrative":"model artifact checkpoint leaked"},'
        '"propagation":{"narrative":"Teacher task run state","trend":"Agent run"}}'
    )

    result = build_case_summary(row).model_dump(mode="json")

    assert result["preliminary_finding"]["rationale"] == "现有材料显示该事件存在需要持续关注的风险线索。"
    assert result["coordination_summary"]["narrative"] == "协同行为线索仍在核验中。"
    assert result["propagation_summary"]["narrative"] == "传播情况已纳入事件分析结果。"


def test_case_summary_does_not_reuse_internal_source_text_for_system_generated_sections():
    row = _case_row()
    row.title = "Coordinated sharing remains under analyst review"
    row.preliminary_finding_json = (
        '{"conclusion":"harmful",'
        '"rationale":"Coordinated sharing remains active; raw_confidence=0.94 '
        'runtime_status:queued runtime_state=warm model_version=v2 '
        'run_id=run_1 job_id=job_1 task_id=task_1 student_agent=alpha."}'
    )
    row.business_summary_json = (
        '{"coordination":{"narrative":"Community reporting is consistent; '
        'artifact_uri=s3://internal/artifact artifact_hash=abc123 '
        'checkpoint_uri=file://internal/checkpoint checkpoint_path=/tmp/checkpoint '
        'teacher=reviewer student=worker agent=runner."},'
        '"propagation":{"narrative":"Spread remains active.","trend":"rising"}}'
    )

    result = build_case_summary(row).model_dump(mode="json")
    assert result["title"] == "Coordinated sharing remains under analyst review"
    assert result["preliminary_finding"]["rationale"] == "现有材料显示该事件存在需要持续关注的风险线索。"
    assert result["coordination_summary"]["narrative"] == "协同行为线索仍在核验中。"
    assert result["propagation_summary"]["narrative"] == "传播情况已纳入事件分析结果。"


def test_case_detail_projection_replaces_opaque_key_accounts_with_collected_names():
    row = _case_row()
    row.business_summary_json = (
        '{"coordination":{"narrative":"Shared targets were observed.",'
        '"key_communities":["Community 1"],"key_accounts":["123", "456"]}}'
    )
    summary = build_case_summary(row)

    projected = _with_snapshot_account_names(
        summary,
        [
            {"author_id": "123", "author_name": "观察员甲"},
            {"author_id": "456", "author_name": "观察员乙"},
        ],
    )

    assert projected.coordination_summary.key_accounts == ["观察员甲", "观察员乙"]


def test_case_detail_resolves_key_accounts_without_rehydrating_the_full_snapshot(monkeypatch):
    class Result:
        def __init__(self, value):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    class Session:
        def __init__(self):
            self.results = [
                Result(
                    SimpleNamespace(
                        snapshot_revision_id="revision_1",
                        snapshot_id="snapshot_1",
                    )
                ),
                Result(None),
                Result(None),
            ]

        async def execute(self, _statement):
            return self.results.pop(0)

    class Registry:
        mongo_db = object()

        async def load_event_snapshot(self, _snapshot_id):
            raise AssertionError("Case detail must not load the complete event snapshot for account names")

    calls = []

    async def resolve_names(mongo_db, *, event_id, account_ids):
        calls.append((mongo_db, event_id, list(account_ids)))
        return {"123": "Observer A", "456": "Observer B"}

    async def scenario():
        row = _case_row()
        row.business_summary_json = (
            '{"review_advisory":{"conclusion":"insufficient_evidence",'
            '"urgency":"watch","disposition":"gather_evidence",'
            '"rationale":"Review remains open.",'
            '"received_at":"2026-08-03T00:00:00Z"},'
            '"coordination":{"narrative":"Shared targets were observed.",'
            '"key_accounts":["123","456"]}}'
        )
        service = ReviewCaseService.__new__(ReviewCaseService)
        service.db = Session()
        service.registry = Registry()
        monkeypatch.setattr(review_case_service, "load_event_account_names", resolve_names, raising=False)

        detail = await service._detail_from_row(row)

        assert detail.coordination_summary.key_accounts == ["Observer A", "Observer B"]
        assert calls == [(service.registry.mongo_db, row.event_id, ["123", "456"])]

    asyncio.run(scenario())


def test_raw_snapshot_content_is_projected_to_immutable_evidence_fields():
    raw = {
        "platform": "weibo",
        "post_id": "p1",
        "content": "Observed post content",
        "author_id": "account-1",
        "timestamp": "2026-05-21T08:00:00Z",
        "url": "https://weibo.example/p1",
        "artifact_hash": "hidden",
        "confidence": 0.99,
    }

    item = build_evidence_item(raw, evidence_kind="post").model_dump(mode="json")

    assert item["evidence_ref"] == "weibo:post:p1"
    assert item["excerpt"] == "Observed post content"
    assert item["assessment"] == "unresolved"
    assert "author_id" not in item
    assert "artifact_hash" not in item
    assert "confidence" not in item


def test_raw_evidence_text_and_source_url_are_not_rewritten_by_product_sanitizer():
    raw = {
        "platform": "news",
        "post_id": "p2",
        "title": "Teacher model checkpoint policy debate",
        "content": "The source discusses agent jobs and model checkpoints as its subject.",
        "url": "https://example.test/model/checkpoint-policy",
    }

    item = build_evidence_item(raw, evidence_kind="post").model_dump(mode="json")

    assert item["title"] == raw["title"]
    assert item["excerpt"] == raw["content"]
    assert item["source_url"] == raw["url"]


def test_case_detail_restores_only_the_current_snapshot_draft():
    class Result:
        def __init__(self, value):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

        def all(self):
            return self.value

    class Session:
        def __init__(self, results):
            self.results = list(results)

        async def execute(self, _statement):
            return self.results.pop(0)

    async def scenario():
        revision = SimpleNamespace(snapshot_revision_id="revision_2")
        draft = ReviewDecisionDraft(
            case_id="case_trump_visit",
            snapshot_revision_id="revision_2",
            version=4,
            conclusion="harmful",
            urgency="urgent",
            disposition="escalate",
            rationale="Current snapshot draft.",
            key_evidence_refs_json="[]",
            unresolved_items_json="[]",
            updated_at=datetime(2026, 8, 3, tzinfo=timezone.utc),
        )
        service = ReviewCaseService.__new__(ReviewCaseService)
        service.db = Session([Result([]), Result(revision), Result(draft), Result(None)])

        detail = await service._detail_from_row(_case_row())

        assert detail.decision_draft is not None
        assert detail.decision_draft.draft_version == 4
        assert detail.decision_draft.rationale == "Current snapshot draft."

    asyncio.run(scenario())


def test_case_detail_replaces_legacy_system_draft_rationale():
    draft = SimpleNamespace(
        case_id="case_trump_visit",
        version=1,
        conclusion="non_harmful",
        urgency="routine",
        disposition="gather_evidence",
        rationale="Independent review completed.",
        key_evidence_refs_json="[]",
        unresolved_items_json='["Evidence resolving the preliminary uncertainty"]',
        updated_at=datetime(2026, 8, 3, tzinfo=timezone.utc),
    )

    from app.services.review_case_product_projection import _draft_model

    projected = _draft_model(draft)

    assert projected.rationale == "现有材料未显示需要进一步处置的明确风险。"
    assert projected.unresolved_items == ["补充能够支撑或反驳当前结论的独立来源材料"]


def test_case_activity_localizes_legacy_system_actor():
    from app.services.review_case_product_projection import _activity_model

    activity = _activity_model(
        SimpleNamespace(
            id=1,
            case_id="case_trump_visit",
            activity_type="case_created",
            action_required="none",
            summary="Case created",
            detail_lines_json="[]",
            evidence_refs_json="[]",
            actor_name="System",
            created_at=datetime(2026, 8, 3, tzinfo=timezone.utc),
        )
    )

    assert activity.actor_name == "系统"


class ListResult:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values

    def scalars(self):
        return self


class LegacySession:
    def __init__(self, results):
        self.results = list(results)
        self.added = []

    async def execute(self, _statement):
        return self.results.pop(0)

    def add(self, row):
        self.added.append(row)


def test_legacy_tables_are_projected_as_business_activities_without_writes():
    async def scenario():
        assessed_at = datetime(2026, 8, 3, tzinfo=timezone.utc)
        case = _case_row()
        risk = RiskAssessment(
            report_id="legacy_report_1",
            event_id=case.event_id,
            platform="weibo",
            current_phase="breakout",
            phase_confidence=0.7,
            hazard_breakout=0.4,
            overall_risk_score=81,
            risk_level="high",
            manipulation_belief=0.1,
            authenticity_belief=0.1,
            impact_belief=0.1,
            conflict_mass=0.2,
            escalation_required=1,
            attack_path_score=0.3,
            attack_path_depth=2,
            report_json="{}",
            assessed_by=1,
        )
        risk.assessed_at = assessed_at
        advisory = ReviewAgentReport(
            run_id="run_hidden",
            review_id="review_1",
            report_id="legacy_report_1",
            agent_name="TeacherAgent",
            report_role="expert_initial",
            status="completed",
            model="model-hidden",
            analysis_text="Teacher Agent model checkpoint says review is needed.",
            input_hash="hash",
            confidence=0.9,
            sidecar_json="{}",
            created_by=1,
        )
        advisory.id = 1
        advisory.created_at = assessed_at
        feedback = ReviewAgentFeedback(
            feedback_id="feedback_1",
            report_id="legacy_report_1",
            review_id="review_1",
            run_id="run_hidden",
            case_id=case.case_id,
            human_label="Agent error",
            corrected_label="Teacher correction",
            error_types_json="[]",
            notes="raw confidence should not leak",
            evidence_refs_json='["weibo:post:p1"]',
            reviewer_confidence=0.8,
            created_by=7,
        )
        feedback.id = 1
        feedback.created_at = assessed_at
        db = LegacySession(
            [
                ListResult([("legacy_report_1",)]),
                ListResult([risk]),
                ListResult([advisory]),
                ListResult([feedback]),
            ]
        )
        service = ReviewCaseService.__new__(ReviewCaseService)
        service.db = db

        activities = await service._legacy_activities(case, after_id=0, cursor_offset=0, limit=10)

        assert [item.activity_type.value for item in activities] == [
            "snapshot_added",
            "review_advisory_available",
            "correction_recorded",
        ]
        assert activities[0].summary == "已更新事件材料"
        assert activities[1].summary == "已收到复核建议"
        assert activities[2].summary == "已记录分析员修正"
        assert db.added == []

    asyncio.run(scenario())
