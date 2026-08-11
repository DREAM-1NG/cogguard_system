from __future__ import annotations

import argparse
import json
from datetime import datetime
from typing import Sequence

from research.coordination_experiments import (
    ClaimGate,
    CANONICAL_REPRODUCTION_OUTPUT_ROOT,
    ExperimentSplit,
    ResearchDatasetManifest,
    ResultRow,
    default_local_public_detection_configs,
    default_baseline_registry,
    run_public_detection_comparison,
    validate_reproduction_output_dir,
    write_reproduction_artifacts,
)
from research.coordination_detect.contracts import (
    DetectionFeatureSchema,
    DetectionModelArtifact,
    case_id_fingerprint,
)


DEFAULT_OUTPUT = CANONICAL_REPRODUCTION_OUTPUT_ROOT


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
    mode.add_argument(
        "--public-detection",
        action="store_true",
        help="run LEN and ALClassification public Coordination Detection comparison",
    )
    parser.add_argument(
        "--output",
        type=validate_reproduction_output_dir,
        default=DEFAULT_OUTPUT,
        help="artifact directory for --smoke-fixture",
    )
    parser.add_argument(
        "--seeds",
        default="11,23,37,41,53",
        help="comma-separated seed list for --public-detection",
    )
    parser.add_argument(
        "--methods",
        default="",
        help="optional comma-separated execution/public method ids for --public-detection",
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=0,
        help="optional per-dataset case cap for smoke/debug public Detection runs",
    )
    parser.add_argument(
        "--bootstrap-resamples",
        type=int,
        default=2000,
        help="bootstrap resamples for aggregate confidence intervals",
    )
    return parser


def _csv_text(value: str, field_name: str) -> tuple[str, ...]:
    if not value:
        return ()
    result = tuple(item.strip() for item in value.split(",") if item.strip())
    if not result:
        raise ValueError(f"{field_name} must contain at least one value")
    return result


def _csv_ints(value: str, field_name: str) -> tuple[int, ...]:
    result = tuple(int(item) for item in _csv_text(value, field_name))
    if any(item < 0 for item in result):
        raise ValueError(f"{field_name} must contain non-negative integers")
    return result


def _smoke_model_artifact(split: ExperimentSplit) -> DetectionModelArtifact:
    feature_schema = DetectionFeatureSchema(version="task6-smoke/v1", names=("score",))
    validation_fingerprint = case_id_fingerprint(split.validation_ids)
    return DetectionModelArtifact(
        feature_schema=feature_schema,
        scaler_mean=(0.5,),
        scaler_scale=(0.25,),
        coefficients=(1.0,),
        intercept=0.0,
        calibrator_slope=1.0,
        calibrator_intercept=0.0,
        lower_decision_threshold=0.3,
        upper_decision_threshold=0.7,
        validation_ood_min=(0.0,),
        validation_ood_max=(1.0,),
        optimizer_config={"algorithm": "embedded_fixture"},
        calibrator_config={"algorithm": "embedded_fixture"},
        threshold_objective="embedded_fixture",
        train_fit_case_ids_fingerprint=case_id_fingerprint(split.train_ids),
        validation_calibration_case_ids_fingerprint=validation_fingerprint,
        validation_threshold_case_ids_fingerprint=validation_fingerprint,
        validation_ood_case_ids_fingerprint=validation_fingerprint,
    )


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
        model_artifact = _smoke_model_artifact(split)
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
                metrics={
                    "auprc": score,
                    "macro_f1": 0.75,
                    "roc_auc": 0.85,
                    "ece": 0.1,
                    "selective_coverage": 0.75,
                    "selective_risk": 0.1,
                    "abstain_rate": 0.25,
                },
                claim_markers=manifest.claim_markers,
                selection_eligible=True,
                audit={
                    "audit_version": "coordination-execution-audit/v2",
                    "stage": "detection",
                    "implementation_id": "embedded-smoke-fixture",
                    "evaluation_after_execution": True,
                    "test_evaluation_only": True,
                },
                model_artifact=model_artifact.to_dict(),
                train_partition_fingerprint=case_id_fingerprint(split.train_ids),
                validation_partition_fingerprint=case_id_fingerprint(split.validation_ids),
                test_partition_fingerprint=case_id_fingerprint(split.test_ids),
            )
        )
    return tuple(rows)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    output_dir = validate_reproduction_output_dir(args.output)
    if args.list_methods:
        print(json.dumps(
            [spec.to_dict() for spec in default_baseline_registry().specs()],
            ensure_ascii=False, sort_keys=True, indent=2,
        ))
        return 0
    if args.public_detection:
        if args.max_cases < 0:
            raise ValueError("--max-cases must be non-negative")
        if args.bootstrap_resamples <= 0:
            raise ValueError("--bootstrap-resamples must be positive")
        if output_dir == DEFAULT_OUTPUT:
            output_dir = DEFAULT_OUTPUT / (
                "public-detection-"
                + datetime.now().strftime("%Y%m%d-%H%M%S")
            )
        manifest = run_public_detection_comparison(
            default_local_public_detection_configs(max_cases=args.max_cases),
            output_dir,
            seeds=_csv_ints(args.seeds, "seeds"),
            method_ids=(_csv_text(args.methods, "methods") or None),
            bootstrap_resamples=args.bootstrap_resamples,
        )
        rows = manifest["rows"]
        print(json.dumps({
            "output": str(output_dir),
            "status": "public_detection_complete",
            "row_count": len(rows),
            "success_count": sum(1 for row in rows if row["status"] == "success"),
            "blocked_count": sum(1 for row in rows if row["status"] == "blocked"),
            "failed_count": sum(1 for row in rows if row["status"] == "failed"),
            "artifact_identity": manifest["artifact_paths"]["identity"],
        }, ensure_ascii=False, sort_keys=True))
        return 0
    artifacts = write_reproduction_artifacts(
        _smoke_rows(),
        output_dir,
        claim_gates=(
            ClaimGate(
                "smoke-auprc", "auprc", "maximize", 0.70,
                claim_scope="auxiliary",
                minimum_successful_seeds=2,
            ),
        ),
        bootstrap_seed=0,
        bootstrap_resamples=200,
    )
    print(json.dumps({
        "artifact_identity": artifacts.artifact_identity,
        "output": str(output_dir),
        "status": "smoke_fixture_only",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
