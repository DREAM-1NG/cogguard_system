"""Run the local, non-claimable prototype acceptance path.

This command uses a small synthetic EventSnapshot only to verify wiring. It
does not create labels, activate models, persist database rows, or promote a
result to a research claim.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from app.core.analysis.contracts import TimeWindow
from app.core.analysis.executor import SnapshotCoordinationEngine
from app.core.analysis.runtime import build_student_verdict, build_teacher_advisory_verdict
from app.core.analysis.snapshots import build_event_snapshot
from app.services.propagation_prediction_service import predict_event_macro_micro


SYSTEM_ROOT = Path(__file__).resolve().parents[2]
DISCOVER_ROOT = SYSTEM_ROOT / "research" / "coordination_discover"


def main() -> None:
    snapshot = _build_fixture_snapshot()
    with TemporaryDirectory(prefix="cogguard-prototype-") as artifact_dir:
        research_result = _run_discover_research(snapshot, artifact_dir)
        fallback_result = asyncio.run(
            SnapshotCoordinationEngine().analyze(snapshot, {"artifact_dir": artifact_dir})
        )
        propagation_result = asyncio.run(
            predict_event_macro_micro(posts=snapshot.posts, comments=snapshot.comments, top_k=5)
        )
        case = _case_from_snapshot(snapshot)
        student_result = build_student_verdict(case)
        teacher_result = build_teacher_advisory_verdict(case, job_id="prototype_teacher_job")

    payload = {
        "schema": "cogguard.prototype_acceptance.v1",
        "snapshot": {
            "snapshot_id": snapshot.snapshot_id,
            "event_id": snapshot.event_id,
            "platforms": snapshot.platforms,
            "data_fingerprint": snapshot.data_fingerprint,
            "quality_status": snapshot.quality_report.status,
        },
        "coordination_discover": {
            "research_status": research_result["status"],
            "partition_backend": research_result["manifest"]["partition_backend"],
            "claimability": research_result["manifest"]["claimability"],
            "artifact_hash_count": len(research_result["manifest"].get("artifact_hashes", {})),
            "backend_mode": "fallback" if fallback_result.get("fallback") else "artifact",
            "backend_fallback_reason": fallback_result.get("fallback_reason"),
        },
        "propagation_analysis": {
            "status": propagation_result.get("status"),
            "model": propagation_result.get("model"),
            "claim_status": (propagation_result.get("protocol") or {}).get("claim_status"),
            "abstain": propagation_result.get("abstain"),
        },
        "student_review": {
            "status": student_result.get("status"),
            "model_status": student_result.get("model_status"),
            "verdict_type": student_result.get("verdict_type"),
            "abstain": student_result.get("abstain"),
        },
        "teacher_review": {
            "status": teacher_result.get("status"),
            "verdict_type": teacher_result.get("verdict_type"),
            "canonical_allowed": teacher_result.get("canonical_allowed"),
            "dag_nodes": len((teacher_result.get("dag") or {}).get("nodes") or []),
        },
        "claim_boundary": "Prototype wiring is verified; no field in this output is a publication-grade claim.",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _run_discover_research(snapshot: Any, artifact_dir: str) -> dict[str, Any]:
    module_name = "_cogguard_prototype_coordination_discover"
    spec = importlib.util.spec_from_file_location(
        module_name,
        DISCOVER_ROOT / "__init__.py",
        submodule_search_locations=[str(DISCOVER_ROOT)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load Coordination Discover package: {DISCOVER_ROOT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    result = module.run_dynamic_discover(
        module.DynamicDiscoverRequest(
            snapshot=snapshot,
            artifact_dir=artifact_dir,
            model_config=module.TemporalMAGNNConfig(
                device="cpu",
                epochs=1,
                embedding_dim=8,
                negative_ratio=1,
                min_learned_edge_score=0.0,
            ),
            source_dataset="prototype_fixture",
            source_event=snapshot.event_id,
        )
    )
    return {"status": result.status, "manifest": result.manifest.to_dict()}


def _build_fixture_snapshot() -> Any:
    def timestamp(minute: int) -> datetime:
        return datetime(2026, 5, 11, 0, minute, tzinfo=timezone.utc)

    posts = [
        {
            "event_id": "trump_visit_prototype",
            "platform": "weibo",
            "post_id": "prototype_p1",
            "author_id": "prototype_u1",
            "timestamp": timestamp(0),
            "content": "Trump visit shared narrative alpha beta gamma",
            "url": "https://example.test/trump-visit",
            "hashtags": ["TrumpVisit"],
            "entities": ["Trump"],
        },
        {
            "event_id": "trump_visit_prototype",
            "platform": "douyin",
            "post_id": "prototype_p2",
            "author_id": "prototype_u2",
            "timestamp": timestamp(5),
            "content": "Trump visit shared narrative alpha beta delta",
            "url": "https://example.test/trump-visit",
            "hashtags": ["TrumpVisit"],
            "entities": ["Trump"],
            "repost_id": "prototype_p1",
        },
        {
            "event_id": "trump_visit_prototype",
            "platform": "xhs",
            "post_id": "prototype_p3",
            "author_id": "prototype_u3",
            "timestamp": timestamp(10),
            "content": "Trump visit shared narrative alpha beta epsilon",
            "url": "https://example.test/trump-visit",
            "hashtags": ["TrumpVisit"],
            "entities": ["Trump"],
            "quote_post_id": "prototype_p2",
        },
    ]
    return build_event_snapshot(
        event_id="trump_visit_prototype",
        posts=posts,
        comments=[],
        core_window=TimeWindow(start=timestamp(0), end=datetime(2026, 5, 12, tzinfo=timezone.utc)),
        context_window=TimeWindow(start=datetime(2026, 5, 1, tzinfo=timezone.utc), end=datetime(2026, 5, 31, tzinfo=timezone.utc)),
    )


def _case_from_snapshot(snapshot: Any) -> dict[str, Any]:
    return {
        "snapshot_id": snapshot.snapshot_id,
        "event_id": snapshot.event_id,
        "platforms": list(snapshot.platforms),
        "posts": list(snapshot.posts),
        "comments": list(snapshot.comments),
        "relationships": [edge.model_dump(mode="json") for edge in snapshot.relationships],
        "quality_report": snapshot.quality_report.model_dump(mode="json"),
        "options": {},
    }


if __name__ == "__main__":
    main()
