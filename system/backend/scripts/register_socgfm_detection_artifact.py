from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def _bootstrap_backend_path() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))


def main(argv: list[str] | None = None) -> int:
    _bootstrap_backend_path()
    parser = argparse.ArgumentParser(
        description="Register a SocGFM Coordination Detection artifact with the analysis model governance service.",
    )
    parser.add_argument("--artifact-dir", required=True, help="G-drive SocGFM artifact directory.")
    parser.add_argument("--created-by", type=int, required=True, help="Accountable operator/admin user id.")
    parser.add_argument("--version", default=None, help="Optional version override. Defaults to manifest version.")
    parser.add_argument("--activate", action="store_true", help="Approve and activate after registration.")
    parser.add_argument("--reason", default="Activate SocGFM Coordination Detection precomputed artifact.")
    parser.add_argument("--dry-run", action="store_true", help="Print the registration payload without writing DB state.")
    args = parser.parse_args(argv)

    payload = _registration_payload(Path(args.artifact_dir), version=args.version)
    if args.dry_run:
        print(json.dumps({"payload": payload, "dry_run": True}, ensure_ascii=False, sort_keys=True, allow_nan=False))
        return 0
    result = asyncio.run(
        _register(
            payload=payload,
            created_by=int(args.created_by),
            activate=bool(args.activate),
            reason=str(args.reason),
        )
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str, allow_nan=False))
    return 0


def _registration_payload(artifact_dir: Path, *, version: str | None = None) -> dict[str, Any]:
    root = artifact_dir.expanduser().resolve()
    if root.drive.upper() != "G:":
        raise ValueError("SocGFM coordination detection artifacts must be registered from the G: drive")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    checkpoint_path = root / str(manifest.get("checkpoint_path") or "checkpoint.json")
    checkpoint_hash = hashlib.sha256(checkpoint_path.read_bytes()).hexdigest()
    return {
        "technology": "coordination_detection",
        "model": "socgfm_cross_attention",
        "version": version or manifest.get("version") or "socgfm_cross_attention/v1",
        "artifact_uri": str(root),
        "artifact_hash": checkpoint_hash,
        "config": {
            "backend": "socgfm_cross_attention",
            "inference_mode": manifest.get("inference_mode"),
            "claim_scope": manifest.get("claim_scope"),
            "online_neural_forward": manifest.get("online_neural_forward"),
            "unsupported_claims": manifest.get("unsupported_claims", []),
        },
        "metrics": dict(manifest.get("metrics") or {}),
    }


async def _register(
    *,
    payload: dict[str, Any],
    created_by: int,
    activate: bool,
    reason: str,
) -> dict[str, Any]:
    from app.db.mysql import async_session_factory
    from app.services.analysis_governance_service import (
        activate_model_version,
        approve_model_candidate,
        register_model_version,
    )

    async with async_session_factory() as session:
        model_version = await register_model_version(
            payload=payload,
            created_by=created_by,
            db=session,
        )
        response: dict[str, Any] = {
            "model_version": model_version,
            "activated": False,
        }
        if activate:
            approval = await approve_model_candidate(
                model_version_id=int(model_version["id"]),
                approved_by=created_by,
                approval_notes=reason,
                db=session,
            )
            activation = await activate_model_version(
                model_version_id=int(model_version["id"]),
                operator_id=created_by,
                reason=reason,
                db=session,
            )
            response.update({"approval": approval, "activation": activation, "activated": True})
        await session.commit()
        return response


if __name__ == "__main__":
    raise SystemExit(main())
