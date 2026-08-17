from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any


def _bootstrap_backend_path() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))


async def _dataset_source_path(dataset_id: int) -> Path:
    from sqlalchemy import select

    from app.db.mysql import async_session_factory
    from app.models.coordination_registry import CoordinationDataset

    async with async_session_factory() as session:
        result = await session.execute(select(CoordinationDataset).where(CoordinationDataset.id == dataset_id))
        dataset = result.scalar_one_or_none()
        if dataset is None:
            raise ValueError(f"CoordinationDataset {dataset_id} not found")
        return Path(str(dataset.source_path)).expanduser().resolve()


def main(argv: list[str] | None = None) -> int:
    _bootstrap_backend_path()

    from app.core.analysis.coordination_runtime.socgfm_artifact_builder import (
        build_socgfm_detection_artifact,
    )
    from app.core.analysis.coordination_runtime.socgfm_local_precompute import (
        default_socgfm_local_precompute_output_dir,
        precompute_socgfm_china_local_detection,
    )

    parser = argparse.ArgumentParser(
        description="Run offline China SocGFM CrossAttention/SAGE checkpoint precompute for local Coordination data.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--event-table", default=None, help="CSV/JSON/JSONL standard Coordination event table.")
    source.add_argument("--snapshot-json", default=None, help="Analysis EventSnapshot export JSON.")
    source.add_argument("--dataset-id", type=int, default=None, help="Registered CoordinationDataset id.")
    parser.add_argument("--output-dir", default=None, help="G-drive precompute output directory.")
    parser.add_argument("--checkpoint-root", default=None, help="Root containing best_models_f1_macro/model0..4.pth.")
    parser.add_argument("--device", default="auto", help="Torch device for offline neural forward.")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic isolated-node repair seed.")
    parser.add_argument("--build-artifact", action="store_true", help="Build deployable SocGFM artifact after precompute.")
    parser.add_argument("--artifact-output-dir", default=None, help="G-drive artifact directory for --build-artifact.")
    parser.add_argument("--version", default=None, help="Artifact version string for --build-artifact.")
    parser.add_argument("--registration-json", default=None, help="Optional G-drive model registration payload JSON.")
    args = parser.parse_args(argv)

    event_table = args.event_table
    if args.dataset_id is not None:
        event_table = str(asyncio.run(_dataset_source_path(int(args.dataset_id))))
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else default_socgfm_local_precompute_output_dir()
    summary = precompute_socgfm_china_local_detection(
        event_table=event_table,
        snapshot_json=args.snapshot_json,
        output_dir=output_dir,
        checkpoint_root=args.checkpoint_root,
        device=args.device,
        seed=args.seed,
        dataset_id=args.dataset_id,
    )
    if args.build_artifact:
        version = args.version or f"china_local_precomputed_{Path(summary['output_dir']).name.rsplit('-', 1)[-1]}"
        artifact_output_dir = (
            Path(args.artifact_output_dir).expanduser().resolve()
            if args.artifact_output_dir
            else Path(__file__).resolve().parents[2]
            / "artifacts"
            / "coordination_detection"
            / "socgfm_cross_attention"
            / version
        )
        artifact_summary = build_socgfm_detection_artifact(
            source_run_dir=summary["output_dir"],
            output_dir=artifact_output_dir,
            version=version,
            account_namespace="local",
        )
        summary["artifact"] = artifact_summary
        if args.registration_json:
            _write_registration_payload(Path(args.registration_json), artifact_summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0


def _write_registration_payload(path: Path, artifact_summary: dict[str, Any]) -> None:
    output_path = path.expanduser().resolve()
    if output_path.drive.upper() != "G:":
        raise ValueError("SocGFM coordination detection registration payload must be written under the G: drive")
    artifact_dir = Path(str(artifact_summary["artifact_dir"])).resolve()
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    registration = {
        "technology": "coordination_detection",
        "model": "socgfm_cross_attention",
        "version": manifest.get("version"),
        "artifact_uri": str(artifact_dir),
        "artifact_hash": artifact_summary["checkpoint_sha256"],
        "config": {
            "backend": "socgfm_cross_attention",
            "inference_mode": manifest.get("inference_mode"),
            "claim_scope": manifest.get("claim_scope"),
            "online_neural_forward": manifest.get("online_neural_forward"),
            "unsupported_claims": manifest.get("unsupported_claims", []),
        },
        "metrics": dict(manifest.get("metrics") or {}),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(registration, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
