"""Precompute the real three-platform Trump visit analysis into AnalysisRun."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.analysis import TimeWindow, build_event_snapshot
from app.core.analysis.executor import AnalysisExecutor
from app.core.analysis.registry import AnalysisRegistry, SqlAlchemyAnalysisStore
from app.core.analysis.stages import SemanticEnrichmentStage, default_analysis_stage_registry
from app.core.semantic.runtime import ModelWeightsBlockedError, SemanticEnrichmentRuntime
from app.db.mongodb import close_mongo, get_mongo_db
from app.db.mysql import async_session_factory
from app.services.event_data import load_event_comments, load_event_posts

EVENT_ID = "trump_visit_2026_05_21"
EXPECTED_PLATFORMS = {"weibo", "xhs", "douyin"}
COMMENTS_PER_PLATFORM = 800
PRECOMPUTED_RUN_ID = f"precomputed_{EVENT_ID}_semantic_v5"
PRIMARY_CLAIM = "\u7279\u6717\u666e\u8bbf\u534e\u76f8\u5173\u53d9\u4e8b"
REQUESTED_STAGES = [
    "coordination_discover",
    "propagation_analysis",
    "semantic_enrichment",
    "student",
    "teacher",
]
OUTPUT = Path(__file__).resolve().parents[2] / "output" / "semantic_precompute" / f"{EVENT_ID}_v5.json"


class _PreloadedSemanticEngine:
    """Use the preflight-loaded real models for the executor's semantic stage."""

    def __init__(self, runtime: SemanticEnrichmentRuntime) -> None:
        self.runtime = runtime

    async def enrich(
        self,
        snapshot: Any,
        *,
        options: dict[str, Any],
        coordination: dict[str, Any] | None,
        propagation: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return self.runtime.enrich(
            snapshot,
            coordination=coordination,
            propagation=propagation,
            claim=options.get("claim"),
        )


async def main() -> int:
    try:
        runtime = SemanticEnrichmentRuntime()
    except ModelWeightsBlockedError as exc:
        print(json.dumps({"event_id": EVENT_ID, "status": "blocked", "blocking_reason": str(exc)}, ensure_ascii=False))
        return 2

    mongo = get_mongo_db()
    try:
        posts = await load_event_posts(mongo, event_id=EVENT_ID)
        comments = await load_event_comments(mongo, event_id=EVENT_ID)
        observed = {str(row.get("platform")) for row in [*posts, *comments] if row.get("platform")}
        missing = sorted(EXPECTED_PLATFORMS - observed)
        if missing:
            print(json.dumps({"event_id": EVENT_ID, "status": "blocked", "blocking_reason": "missing_platform_data", "missing_platforms": missing}, ensure_ascii=False))
            return 3

        snapshot = build_event_snapshot(
            event_id=EVENT_ID,
            posts=posts,
            comments=_sample_comments(comments),
            core_window=TimeWindow(
                start=datetime(2026, 5, 11, tzinfo=timezone.utc),
                end=datetime(2026, 5, 22, tzinfo=timezone.utc),
            ),
            context_window=TimeWindow(
                start=datetime(2026, 5, 1, tzinfo=timezone.utc),
                end=datetime(2026, 5, 31, tzinfo=timezone.utc),
            ),
        )
        run, results = await _execute_precomputation(mongo=mongo, snapshot=snapshot, runtime=runtime)
        coverage = {
            "posts": {"available": len(posts), "analyzed": len(snapshot.posts)},
            "comments": {
                "available": len(comments),
                "analyzed": len(snapshot.comments),
                "sampling": f"first {COMMENTS_PER_PLATFORM} timestamp-sorted comments per platform",
            },
        }
        payload = {
            "event_id": EVENT_ID,
            "status": "ready",
            "coverage": coverage,
            "snapshot": snapshot.model_dump(mode="json"),
            "analysis_run": _run_summary(run),
            **results,
        }
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(json.dumps({
            "event_id": EVENT_ID,
            "status": "ready",
            "output": str(OUTPUT),
            "coverage": coverage,
            "platforms": snapshot.platforms,
            "analysis_run": _run_summary(run),
            "embedding_manifest": results["semantic"]["embedding_manifest"],
        }, ensure_ascii=False, default=str))
        return 0
    finally:
        await close_mongo()


async def _execute_precomputation(
    *,
    mongo: Any,
    snapshot: Any,
    runtime: SemanticEnrichmentRuntime,
) -> tuple[dict[str, Any], dict[str, Any]]:
    existing_run = await _prepare_precomputed_run(mongo=mongo, snapshot=snapshot)
    if existing_run is not None:
        return existing_run, await _load_precomputed_artifacts(mongo=mongo)

    async with async_session_factory() as session:
        registry = AnalysisRegistry(mongo_db=mongo, store=SqlAlchemyAnalysisStore(session))
        stages = default_analysis_stage_registry()
        stages["semantic_enrichment"] = SemanticEnrichmentStage(_PreloadedSemanticEngine(runtime))
        run = await AnalysisExecutor(registry=registry, stages=stages).execute_run(PRECOMPUTED_RUN_ID)
        await session.commit()
        return run, {
            "coordination": run["results"].get("coordination_discover", {}),
            "propagation": run["results"].get("propagation_analysis", {}),
            "semantic": run["results"].get("semantic_enrichment", {}),
            "student": run["results"].get("student", {}),
            "teacher": run["results"].get("teacher", {}),
        }


async def _prepare_precomputed_run(*, mongo: Any, snapshot: Any) -> dict[str, Any] | None:
    """Commit setup before the lengthy CPU inference begins."""
    async with async_session_factory() as session:
        registry = AnalysisRegistry(mongo_db=mongo, store=SqlAlchemyAnalysisStore(session))
        await registry.register_event_snapshot(snapshot, created_by=0)
        existing = await registry.get_run(PRECOMPUTED_RUN_ID)
        if existing is not None:
            if str(existing.get("snapshot_id")) != snapshot.snapshot_id:
                raise RuntimeError(
                    f"Precomputed run id is bound to a different snapshot: {existing.get('snapshot_id')}"
                )
            manifest = existing.get("artifact_manifest") or {}
            semantic_ref = ((manifest.get("stages") or {}).get("semantic_enrichment") or {}).get("result_artifact") or {}
            if str(existing.get("status")) in {"awaiting_review", "completed", "needs_evidence"} and semantic_ref.get("stored"):
                await session.commit()
                return existing
            # An interrupted precompute leaves its queued run as a durable
            # retry target. Reuse that id and snapshot instead of duplicating
            # either record.
            await session.commit()
            return None

        await registry.create_run(
            event_id=EVENT_ID,
            snapshot_id=snapshot.snapshot_id,
            requested_stages=REQUESTED_STAGES,
            options={
                "coordination_discover": {"time_window": 3600, "min_participation": 2, "edge_weight": 0.5},
                "propagation_analysis": {"top_k": 10},
                "semantic_enrichment": {"claim": PRIMARY_CLAIM},
                "student": {},
                "teacher": {"teacher_max_review_items": 20},
                "precomputed": True,
            },
            created_by=0,
            run_id=PRECOMPUTED_RUN_ID,
        )
        await session.commit()
    return None


async def _load_precomputed_artifacts(*, mongo: Any) -> dict[str, Any]:
    async with async_session_factory() as session:
        registry = AnalysisRegistry(mongo_db=mongo, store=SqlAlchemyAnalysisStore(session))
        return await _load_stage_artifacts(registry)


async def _load_stage_artifacts(registry: AnalysisRegistry) -> dict[str, Any]:
    keys = {
        "coordination": "coordination_discover",
        "propagation": "propagation_analysis",
        "semantic": "semantic_enrichment",
        "student": "student",
        "teacher": "teacher",
    }
    results = {
        name: await registry.load_run_artifact(
            run_id=PRECOMPUTED_RUN_ID,
            artifact_key=f"stage:{stage}:result",
        )
        for name, stage in keys.items()
    }
    if any(result is None for result in results.values()):
        missing = [name for name, result in results.items() if result is None]
        raise RuntimeError(f"Precomputed run is missing persisted artifacts: {', '.join(missing)}")
    return results


def _sample_comments(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for platform in sorted(EXPECTED_PLATFORMS):
        candidates = [row for row in rows if str(row.get("platform")) == platform]
        selected.extend(
            sorted(candidates, key=lambda row: (str(row.get("timestamp") or ""), str(row.get("comment_id") or "")))
            [:COMMENTS_PER_PLATFORM]
        )
    return selected


def _run_summary(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": run["run_id"],
        "snapshot_id": run["snapshot_id"],
        "status": run["status"],
        "requested_stages": run.get("requested_stages", REQUESTED_STAGES),
        "artifact_manifest": run.get("artifact_manifest", {}),
    }


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
