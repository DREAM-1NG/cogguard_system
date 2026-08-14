"""Import and precompute the real three-platform Trump visit semantic run.

This command is intentionally fail-closed: missing databases or local model
weights stop the run before any successful semantic artifact is reported.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from app.core.analysis.contracts import TimeWindow
from app.core.analysis.executor import AnalysisExecutor, default_analysis_engine_ports
from app.core.analysis.registry import AnalysisRegistry, SqlAlchemyAnalysisStore
from app.db.mongodb import close_mongo, get_mongo_db
from app.db.mysql import async_session_factory
from app.core.semantic.runtime import ModelWeightsBlockedError, SemanticEnrichmentRuntime
from sqlalchemy import text
import import_mediacrawler_data_runs

EVENT_ID = "trump_visit_2026_05_21"
PLATFORMS = ("weibo", "xhs", "douyin")


async def _check_database_readiness() -> None:
    """Verify both stores before any import or analysis mutation."""

    mongo = get_mongo_db()
    command = getattr(mongo, "command", None)
    if not callable(command):
        raise RuntimeError("MongoDB readiness check is unavailable")
    await command("ping")
    async with async_session_factory() as db:
        execute = getattr(db, "execute", None)
        if not callable(execute):
            raise RuntimeError("MySQL readiness check is unavailable")
        await execute(text("SELECT 1"))


async def _close_mongo_safely() -> None:
    try:
        await close_mongo()
    except Exception:
        # Readiness failures should retain their original diagnostic.
        return


def _platform_counts(normalized: list[Any]) -> dict[str, dict[str, int]]:
    return {
        str(result.platform): {
            "posts": len(result.posts),
            "comments": len(result.comments),
        }
        for result in normalized
    }


def _summary(
    *,
    snapshot: Any | None = None,
    result: dict[str, Any] | None = None,
    platform_counts: dict[str, dict[str, int]] | None = None,
    reconciliation: dict[str, int] | None = None,
    semantic_status: str,
    blocking_reason: str | None = None,
) -> dict[str, Any]:
    semantic = ((result or {}).get("results") or {}).get("semantic_enrichment") or {}
    return {
        "event_id": EVENT_ID,
        "snapshot_id": getattr(snapshot, "snapshot_id", None),
        "run_id": (result or {}).get("run_id"),
        "platform_counts": platform_counts or {},
        "reconciliation": reconciliation or {},
        "status": (result or {}).get("status") or semantic_status,
        "semantic_status": semantic.get("status") or semantic_status,
        "blocking_reason": blocking_reason or semantic.get("blocking_reason"),
        "model_versions": semantic.get("model_versions") or {},
        "embedding_manifest": semantic.get("embedding_manifest") or {},
        "quality": (
            snapshot.quality_report.model_dump(mode="json")
            if snapshot is not None and hasattr(snapshot, "quality_report")
            else None
        ),
    }


class VerifiedSemanticInputEngine:
    """Inject already verified same-snapshot analysis inputs into semantic enrichment."""

    def __init__(
        self,
        runtime: SemanticEnrichmentRuntime,
        *,
        coordination: dict[str, Any] | None = None,
        propagation: dict[str, Any] | None = None,
    ) -> None:
        self.runtime = runtime
        self.coordination = coordination
        self.propagation = propagation

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
            coordination=self.coordination if self.coordination is not None else coordination,
            propagation=self.propagation if self.propagation is not None else propagation,
            claim=str(options.get("claim") or "") or None,
        )


def _semantic_input_overrides(args: argparse.Namespace) -> dict[str, dict[str, Any] | None]:
    coordination_artifact_dir = str(getattr(args, "coordination_artifact_dir", "") or "").strip()
    propagation_artifact_path = str(getattr(args, "propagation_artifact_path", "") or "").strip()
    propagation_artifact_sha256 = str(getattr(args, "propagation_artifact_sha256", "") or "").strip()
    return {
        "coordination": {"artifact_dir": coordination_artifact_dir} if coordination_artifact_dir else None,
        "propagation": (
            {
                "artifact_key": "stage:propagation_analysis:result",
                "artifact_path": propagation_artifact_path,
                "payload_sha256": propagation_artifact_sha256,
            }
            if propagation_artifact_path and propagation_artifact_sha256
            else None
        ),
    }


async def main_async(args: argparse.Namespace) -> int:
    sources = import_mediacrawler_data_runs.build_latest_trump_visit_sources(Path(args.data_runs_root))
    normalized = [
        import_mediacrawler_data_runs.normalize_platform_files(
            platform=source.platform,
            posts_path=source.posts_path,
            comments_path=source.comments_path,
            creator_profiles_path=source.creator_profiles_path,
            post_details_path=source.post_details_path,
            event_id=EVENT_ID,
            keyword="特朗普访华",
        )
        for source in sources.values()
    ]
    if any(not result.posts for result in normalized):
        raise RuntimeError("真实三平台数据缺失：每个平台必须至少有一条帖子")

    platform_counts = _platform_counts(normalized)
    try:
        SemanticEnrichmentRuntime.ensure_runtime_dependencies()
        runtime = SemanticEnrichmentRuntime(
            model_root=args.model_root,
            embedding_output_root=args.embedding_root,
        )
        await _check_database_readiness()
    except ModelWeightsBlockedError as exc:
        await _close_mongo_safely()
        print(json.dumps(_summary(platform_counts=platform_counts, semantic_status="model_weights_blocked", blocking_reason=str(exc)), ensure_ascii=False, indent=2, default=str))
        return 2
    except Exception as exc:
        await _close_mongo_safely()
        print(json.dumps(_summary(platform_counts=platform_counts, semantic_status="database_blocked", blocking_reason=str(exc)), ensure_ascii=False, indent=2, default=str))
        return 3

    if not args.execute:
        await _close_mongo_safely()
        print(json.dumps(_summary(platform_counts=platform_counts, semantic_status="validation_only"), ensure_ascii=False, indent=2, default=str))
        return 0

    if args.execute:
        for result in normalized:
            job_id = import_mediacrawler_data_runs.ensure_mysql_import_job(
                result,
                event_id=EVENT_ID,
                keyword="特朗普访华",
            )
            await import_mediacrawler_data_runs.upsert_platform_result(result, job_id=job_id)
        reconciliation = await import_mediacrawler_data_runs.reconcile_legacy_weibo_manifest(
            normalized,
            event_id=EVENT_ID,
            execute=True,
        )

    async with async_session_factory() as db:
        semantic_inputs = _semantic_input_overrides(args)
        semantic_engine = (
            VerifiedSemanticInputEngine(runtime, **semantic_inputs)
            if semantic_inputs["coordination"] is not None or semantic_inputs["propagation"] is not None
            else None
        )
        registry = AnalysisRegistry(mongo_db=get_mongo_db(), store=SqlAlchemyAnalysisStore(db))
        snapshot = await registry.create_event_snapshot(
            event_id=EVENT_ID,
            core_window=TimeWindow(start=datetime(2026, 5, 21, tzinfo=timezone.utc), end=datetime(2026, 5, 22, tzinfo=timezone.utc)),
            context_window=TimeWindow(start=datetime(2026, 5, 1, tzinfo=timezone.utc), end=datetime(2026, 5, 31, tzinfo=timezone.utc)),
            created_by=0,
        )
        run = await registry.create_run(
            event_id=EVENT_ID,
            snapshot_id=snapshot.snapshot_id,
            requested_stages=["semantic_enrichment"],
            options={"semantic_enrichment": {"claim": args.primary_claim}},
            created_by=0,
            run_id=f"run_{EVENT_ID}_semantic_v6",
        )
        result = await AnalysisExecutor(
            registry=registry,
            engines=default_analysis_engine_ports(
                semantic_runtime=None if semantic_engine is not None else runtime,
                semantic_engine=semantic_engine,
            ),
        ).execute_run(run["run_id"])
        await db.commit()
        summary = _summary(
            snapshot=snapshot,
            result=result,
            platform_counts=platform_counts,
            reconciliation=reconciliation,
            semantic_status="completed",
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    await _close_mongo_safely()
    semantic = ((result.get("results") or {}).get("semantic_enrichment") or {})
    semantic_status = str(semantic.get("status") or "").strip().lower()
    runtime_status = str(semantic.get("runtime_status") or "").strip().lower()
    if (
        str(result.get("status") or "").strip().lower() != "completed"
        or semantic_status in {"blocked", "unavailable", "failed", "model_weights_blocked"}
        or runtime_status in {"blocked", "unavailable", "failed"}
    ):
        return 4
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-runs-root", default=r"G:\CISCN\CogGuard\MediaCrawler-main\data_runs")
    parser.add_argument("--model-root", default=r"G:\CISCN\hf_models")
    parser.add_argument("--embedding-root", default=None)
    parser.add_argument("--primary-claim", default="央视新闻：特朗普访华期间，中美双方就经贸与合作议题开展会谈")
    parser.add_argument("--coordination-artifact-dir", default="")
    parser.add_argument("--propagation-artifact-path", default="")
    parser.add_argument("--propagation-artifact-sha256", default="")
    parser.add_argument("--execute", action="store_true", help="写入三平台原始数据；默认只校验来源")
    return asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
