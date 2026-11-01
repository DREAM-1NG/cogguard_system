from __future__ import annotations

import asyncio
import importlib
from datetime import datetime, timezone

from app.core.analysis.contracts import AnalysisStageContext, TimeWindow
from app.core.analysis.executor import AnalysisExecutor
from app.core.analysis.snapshots import build_event_snapshot
from app.core.analysis.stages import default_analysis_stage_registry


def _snapshot():
    return build_event_snapshot(
        event_id="event-1",
        posts=[
            {
                "event_id": "event-1",
                "platform": "weibo",
                "post_id": "p1",
                "author_id": "u1",
                "timestamp": datetime(2026, 5, 1, tzinfo=timezone.utc),
                "content": "text",
            }
        ],
        comments=[],
        core_window=TimeWindow(
            start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            end=datetime(2026, 5, 2, tzinfo=timezone.utc),
        ),
        context_window=TimeWindow(
            start=datetime(2026, 4, 30, tzinfo=timezone.utc),
            end=datetime(2026, 5, 3, tzinfo=timezone.utc),
        ),
    )


def test_stage_context_builds_one_case_shape_for_review_adapters():
    context = AnalysisStageContext(
        stage="student",
        run_id="run-1",
        snapshot=_snapshot(),
        options={"active_model": {"version": "v1"}},
        prior_results={"coordination_discover": {"status": "ok"}},
    )

    case = context.review_case()

    assert case["run_id"] == "run-1"
    assert case["snapshot_id"] == context.snapshot.snapshot_id
    assert case["options"]["active_model"]["version"] == "v1"
    assert case["posts"][0]["post_id"] == "p1"


def test_default_stage_registry_has_one_execute_interface_per_stage():
    core = importlib.import_module("app.core")
    registry = default_analysis_stage_registry()

    assert "semantic" in core.__all__
    assert set(registry) == {
        "coordination_discover",
        "propagation_analysis",
        "semantic_enrichment",
        "student",
        "teacher",
    }
    assert all(callable(stage.execute) for stage in registry.values())


def test_executor_dispatches_through_stage_registry():
    calls = []

    class RecordingStage:
        async def execute(self, context):
            calls.append(context)
            return {"status": "ok", "stage": context.stage}

    class Registry:
        async def get_run(self, run_id):
            return {
                "run_id": run_id,
                "snapshot_id": "snapshot-1",
                "requested_stages": ["coordination_discover"],
                "options": {},
            }

        async def load_event_snapshot(self, snapshot_id):
            return _snapshot()

        async def transition_run_status(self, run_id, status, **kwargs):
            return {"run_id": run_id, "status": str(status)}

        async def append_run_event(self, *args, **kwargs):
            return None

        async def save_run_artifact(self, **kwargs):
            return {"artifact_key": kwargs["artifact_key"]}

        async def update_artifact_manifest(self, *args, **kwargs):
            return None

        async def get_active_model(self, technology):
            return None

    executor = AnalysisExecutor(
        registry=Registry(),
        stages={"coordination_discover": RecordingStage()},
    )
    result = asyncio.run(executor.execute_run("run-1"))

    assert result["results"]["coordination_discover"]["stage"] == "coordination_discover"
    assert calls[0].run_id == "run-1"
    assert calls[0].prior_results == {}
