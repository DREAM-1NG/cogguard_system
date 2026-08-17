from __future__ import annotations

import argparse
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

    from app.core.analysis.coordination_runtime.socgfm_artifact_builder import (
        build_socgfm_detection_artifact,
    )

    parser = argparse.ArgumentParser(
        description="Build a deployable SocGFM Coordination Detection artifact from account-level predictions.",
    )
    parser.add_argument("--source-run-dir", required=True, help="SocGFM run directory containing predictions.csv files.")
    parser.add_argument("--output-dir", required=True, help="G-drive artifact output directory.")
    parser.add_argument("--version", required=True, help="Deployable artifact version string.")
    parser.add_argument(
        "--account-namespace",
        default="iohunter",
        help="Namespace used when predictions do not include a platform column.",
    )
    parser.add_argument(
        "--registration-json",
        default=None,
        help="Optional path for a model registry payload JSON. Must be under G: when provided.",
    )
    args = parser.parse_args(argv)

    summary = build_socgfm_detection_artifact(
        source_run_dir=args.source_run_dir,
        output_dir=args.output_dir,
        version=args.version,
        account_namespace=args.account_namespace,
    )
    if args.registration_json:
        _write_registration_payload(Path(args.registration_json), summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0


def _write_registration_payload(path: Path, summary: dict[str, Any]) -> None:
    output_path = path.expanduser().resolve()
    if output_path.drive.upper() != "G:":
        raise ValueError("SocGFM coordination detection registration payload must be written under the G: drive")
    artifact_dir = Path(str(summary["artifact_dir"])).resolve()
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    registration = {
        "technology": "coordination_detection",
        "model": "socgfm_cross_attention",
        "version": manifest.get("version"),
        "artifact_uri": str(artifact_dir),
        "artifact_hash": summary["checkpoint_sha256"],
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
