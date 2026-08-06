from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from research.coordination_experiments import (
    ClaimGate,
    ExperimentSplit,
    ResearchDatasetManifest,
    ResultRow,
    default_baseline_registry,
    write_reproduction_artifacts,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build research-only CogGuard two-stage reproduction artifacts."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--list-methods", action="store_true", help="print registered comparison methods")
    mode.add_argument(
        "--smoke-fixture", action="store_true",
        help="write a deterministic fixture artifact without loading IOHunter",
    )
    parser.add_argument("--output", type=Path, help="artifact directory for --smoke-fixture")
    return parser


def _smoke_rows() -> tuple[ResultRow, ...]:
    rows: list[ResultRow] = []
    for seed, score in ((42, 0.75), (43, 0.80)):
        manifest = ResearchDatasetManifest(
            dataset_id="task6-smoke-fixture",
            seed=seed,
            source_paths=("fixture://task6",),
            source_checksums={"fixture://task6": "sha256:" + "0" * 64},
            source_checksum_scope="canonical_embedded_fixture",
            label_semantics="sealed_external_binary_labels",
            sample_count=6,
            source_case_ids=("train-0", "train-1", "val-0", "val-1", "test-0", "test-1"),
            campaign_axis=("train", "validation", "test"),
            platform_axis=("fixture",),
            time_axis="observed_utc",
            quality_markers=("smoke_fixture",),
            claim_markers=("not_empirical_claim",),
        )
        split = ExperimentSplit(
            policy="campaign_holdout",
            seed=seed,
            train_ids=("train-0", "train-1"),
            validation_ids=("val-0", "val-1"),
            test_ids=("test-0", "test-1"),
            train_group_ids=("train",),
            validation_group_ids=("validation",),
            test_group_ids=("test",),
            transform_fit_ids=("train-0", "train-1"),
        )
        rows.append(
            ResultRow(
                dataset_id=manifest.dataset_id,
                dataset_manifest_fingerprint=manifest.fingerprint,
                evaluator_fingerprint="sha256:" + "1" * 64,
                split_policy=split.policy,
                split_fingerprint=split.fingerprint,
                method_id="learned_fused_detector",
                method_version="learned-coordination-logistic-v1",
                model_role="primary_learned",
                seed=seed,
                runtime_seconds=0.01,
                peak_memory_bytes=1024,
                status="success",
                metrics={"auprc": score},
                claim_markers=manifest.claim_markers,
            )
        )
    return tuple(rows)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.list_methods:
        print(json.dumps(
            [spec.to_dict() for spec in default_baseline_registry().specs()],
            ensure_ascii=False, sort_keys=True, indent=2,
        ))
        return 0
    if args.output is None:
        parser.error("--output is required with --smoke-fixture")
    artifacts = write_reproduction_artifacts(
        _smoke_rows(),
        args.output,
        claim_gates=(
            ClaimGate(
                "smoke-auprc", "auprc", "maximize", 0.70,
                minimum_successful_seeds=2,
            ),
        ),
        bootstrap_seed=0,
        bootstrap_resamples=200,
    )
    print(json.dumps({
        "artifact_identity": artifacts.artifact_identity,
        "output": str(args.output),
        "status": "smoke_fixture_only",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
