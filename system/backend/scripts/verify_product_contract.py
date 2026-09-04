"""Run a deterministic, non-persistent current-product contract smoke."""

from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from app.core.analysis.executor import SnapshotCoordinationEngine
from app.core.analysis.runtime import build_student_verdict, build_teacher_advisory_verdict
from app.services.propagation_prediction_service import predict_event_macro_micro


def _load_prototype_module():
    path = Path(__file__).with_name("prototype_acceptance.py")
    spec = importlib.util.spec_from_file_location("cogguard_prototype_acceptance", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load prototype fixture: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    prototype = _load_prototype_module()
    snapshot = prototype._build_fixture_snapshot()
    case = prototype._case_from_snapshot(snapshot)

    with TemporaryDirectory(prefix="cogguard-product-contract-") as artifact_dir:
        discover = prototype._run_discover_research(snapshot, artifact_dir)
        fallback = asyncio.run(
            SnapshotCoordinationEngine().analyze(snapshot, {"artifact_dir": artifact_dir})
        )
        available_propagation = asyncio.run(
            predict_event_macro_micro(posts=snapshot.posts, comments=snapshot.comments, top_k=5)
        )
        missing_propagation = asyncio.run(
            predict_event_macro_micro(
                posts=snapshot.posts,
                comments=snapshot.comments,
                top_k=5,
                checkpoint_path=str(Path(artifact_dir) / "missing-checkpoint.pt"),
            )
        )
        student = build_student_verdict(case)
        teacher = build_teacher_advisory_verdict(case, job_id="product_contract_teacher_job")

    projection = {
        "event_id": snapshot.event_id,
        "evidence_sufficiency": "pass" if snapshot.quality_report.status == "pass" else "warn",
        "preliminary_finding": student.get("label"),
        "review_advisory": teacher.get("label"),
    }
    internal_fields = {
        "model", "checkpoint", "checkpoint_path", "artifact", "artifact_uri", "job_id", "run_id", "stage"
    }
    leaked = sorted(internal_fields.intersection(projection))
    payload = {
        "schema": "cogguard.product_contract_smoke.v1",
        "snapshot": {
            "snapshot_id": snapshot.snapshot_id,
            "event_id": snapshot.event_id,
            "data_fingerprint": snapshot.data_fingerprint,
            "quality_status": snapshot.quality_report.status,
        },
        "coordination_discover": {
            "research_status": discover["status"],
            "backend_mode": "fallback" if fallback.get("fallback") else "artifact",
            "claimability": discover["manifest"]["claimability"],
        },
        "propagation": {
            "status": missing_propagation.get("status"),
            "model_status": missing_propagation.get("model_status"),
            "abstain": missing_propagation.get("status") in {"missing_checkpoint", "model_unavailable"},
            "available_status": available_propagation.get("status"),
        },
        "student_review": {
            "status": student.get("status"),
            "model_status": student.get("model_status"),
            "abstain": student.get("abstain"),
        },
        "teacher_review": {
            "status": teacher.get("status"),
            "verdict_type": teacher.get("verdict_type"),
            "canonical_allowed": teacher.get("canonical_allowed"),
        },
        "projection": {
            "fields": projection,
            "internal_fields_leaked": leaked,
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not leaked else 1


if __name__ == "__main__":
    raise SystemExit(main())
