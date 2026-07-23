"""Run Review trainable post-level student experiments.

The default path is now the teacher-student first-stage student:

- frozen encoder features from XLM-R-base or Chinese RoBERTa
- post text plus claim/context input
- two main semantic axes: attack/offense and misinformation/claim risk
- claim-linked stance auxiliary head
- separate selective/defer routing head

Legacy view-level experiments remain available behind ``--legacy-view-experiments``.
The default smoke mode caps cases per split to keep local runs practical.
Use ``--max-cases-per-split 0`` for full available local data.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import sys
import zipfile
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from app.core.review.trainable_post import (  # noqa: E402
    ClaimEvidenceCrossEncoder,
    CrossModalAttentionAdapter,
    FeatureBundle,
    FeedForwardBinaryClassifier,
    GatingFusionModel,
    MultitaskTextDetector,
    POSITIVE_LABEL,
    STANCE_ORDER,
    TemporalC3DTransformer,
    binary_classification_metrics,
    binary_label,
    build_agent_review,
    build_gating_feature_matrix,
    claim_context_text,
    confidence_from_probability,
    coverage_risk_curve,
    encode_clip_image_text_features,
    encode_text_features,
    expected_calibration_error,
    fuse_detector_outputs,
    hash_case_image_features,
    label_of,
    predict_probabilities,
    standard_detector_output,
    stance_proxy_of,
    text_of,
    train_binary_torch_model,
    train_cross_modal_torch_model,
    train_multitask_text_model,
    multitask_targets,
    write_jsonl,
)
from app.core.review.selective_student import (  # noqa: E402
    ATTACK_AXIS,
    MISINFO_AXIS,
    SelectiveStudentEncoder,
    build_selective_student_prediction_rows,
    build_selective_student_targets,
    load_teacher_silver_index,
    predict_selective_student_outputs,
    student_main_axis_metrics,
    student_overall_probability_for_case,
    train_selective_student_model,
)
from app.core.review.teacher_silver import build_teacher_silver_record  # noqa: E402
from app.core.review.rag import LocalHashRag, augment_context_with_rag  # noqa: E402
from run_review_post_multiview_ablation import build_splits, video_id_of  # noqa: E402


DEFAULT_DATASETS = ["HateXplain", "MultiOFF", "PHEME", "mcfend", "FakeSV"]
STUDENT_BACKBONE_MODELS = {
    "xlm-r-base": "FacebookAI/xlm-roberta-base",
    "chinese-roberta-wwm-ext": "hfl/chinese-roberta-wwm-ext",
}


def resolve_student_model_name(backbone: str) -> str:
    if backbone in STUDENT_BACKBONE_MODELS:
        return STUDENT_BACKBONE_MODELS[backbone]
    return STUDENT_BACKBONE_MODELS["xlm-r-base"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Review trainable post-level v1 on prepared local cases.")
    parser.add_argument("--case-dir", default=r"G:\CISCN\.tmp\review_post_cases_full")
    parser.add_argument("--output-dir", default=r"G:\CISCN\.tmp\trainable_post_v1")
    parser.add_argument("--datasets", nargs="*", default=DEFAULT_DATASETS)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--hidden-dim", type=int, default=128)
    parser.add_argument("--student-backbone", choices=["xlm-r-base", "chinese-roberta-wwm-ext", "auto"], default="xlm-r-base")
    parser.add_argument(
        "--student-encoder-backend",
        choices=["hash", "hf-transformer", "auto", "sentence-transformer"],
        default="hf-transformer",
    )
    parser.add_argument("--teacher-silver-dir", default="")
    parser.add_argument("--legacy-view-experiments", action="store_true")
    parser.add_argument(
        "--text-backend",
        choices=["hash", "sentence-transformer", "hf-transformer", "auto"],
        default="hash",
        help=(
            "Use hash for deterministic CPU smoke. Use hf-transformer with "
            "hfl/chinese-roberta-wwm-ext for Chinese RoBERTa features."
        ),
    )
    parser.add_argument(
        "--text-model",
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        help=(
            "Frozen text encoder. For Chinese RoBERTa, use "
            "FacebookAI/xlm-roberta-base with --text-backend hf-transformer for safetensors."
        ),
    )
    parser.add_argument("--text-revision", default="")
    parser.add_argument(
        "--hf-model-dir",
        "--hf-cache-dir",
        dest="hf_cache_dir",
        default=r"G:\CISCN\hf_models",
        help=(
            "Dedicated HuggingFace model cache directory. "
            "The --hf-cache-dir alias is kept for backward compatibility."
        ),
    )
    parser.add_argument("--clip-model", default="openai/clip-vit-base-patch32")
    parser.add_argument(
        "--clip-revision",
        default="",
        help="Optional CLIP model revision, e.g. a safetensors revision.",
    )
    parser.add_argument(
        "--allow-model-download",
        action="store_true",
        help="Allow transformers to download missing model weights. Default uses local cache or explicit fallback.",
    )
    parser.add_argument("--hash-dim", type=int, default=256)
    parser.add_argument(
        "--c3d-projection-dim",
        type=int,
        default=256,
        help=(
            "Project each 4096-d C3D frame feature to this dimension before the temporal Transformer. "
            "0 disables projection, which can require several GiB on full FakeSV."
        ),
    )
    parser.add_argument(
        "--max-cases-per-split",
        type=int,
        default=80,
        help="0 means use every available case. Default is a practical CPU smoke run.",
    )
    parser.add_argument("--fakesv-c3d-zip", default=r"G:\CISCN\dataset\review_public\FakeSV\features\c3d.zip")
    parser.add_argument("--enable-rag", action="store_true", help="Augment claim/evidence context with local DISARM RAG.")
    parser.add_argument("--rag-corpus", default=r"G:\CISCN\dataset\review_public\DISARM_RAG\disarm_corpus.jsonl")
    parser.add_argument("--rag-top-k", type=int, default=3)
    args = parser.parse_args()

    case_dir = Path(args.case_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {
        "schema": "review-trainable-post-v1",
        "case_dir": str(case_dir),
        "output_dir": str(output_dir),
        "datasets_requested": args.datasets,
        "method": {
            "student_mainline": {
                "schema": "review-student-2plus1-v1",
                "task_protocol": ["attack_hate_offense", "misinfo_claim_risk", "stance_aux", "defer_route"],
                "backbone": resolve_student_model_name(args.student_backbone),
                "encoder_backend": args.student_encoder_backend,
                "teacher_silver_dir": str(args.teacher_silver_dir or ""),
                "teacher_silver": bool(args.teacher_silver_dir.strip()),
                "teacher_silver_schema": "review-teacher-silver-v1",
            },
            "legacy_view_experiments": bool(args.legacy_view_experiments),
            "legacy_view_modules": {
                "text": "kept for comparison only",
                "meme_img": "kept for comparison only",
                "video": "kept for comparison only",
                "claim_evidence": "kept for comparison only",
                "fusion": "kept for comparison only",
            },
        },
        "capability_boundary": {
            "full_validation_gate": "not modified; strict P0 full-validation remains separate",
            "new_datasets_acquired": False,
            "raw_video_encoder": False,
            "external_rag": False,
            "online_llm_agent": False,
            "smoke_mode": args.max_cases_per_split > 0,
            "teacher_silver_structured_json": True,
            "student_encoder_mainline": True,
            "teacher_silver_available": bool(args.teacher_silver_dir.strip()),
        },
        "datasets": {},
    }

    try:
        for dataset in args.datasets:
            report["datasets"][dataset] = evaluate_student_dataset(
                dataset,
                case_dir=case_dir,
                output_dir=output_dir / safe_name(dataset),
                args=args,
            )
    finally:
        report["summary"] = summarize_report(report["datasets"])
        combined_prediction_path = output_dir / "trainable_post_predictions.jsonl"
        report["combined_prediction_count"] = write_combined_predictions(report["datasets"], combined_prediction_path)
        report["combined_prediction_path"] = str(combined_prediction_path)
        report_path = output_dir / "report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
        print(f"wrote {report_path}")
    return 0


def evaluate_dataset(dataset: str, *, case_dir: Path, output_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    case_path = case_dir / f"{dataset}.jsonl"
    cases = load_cases(case_path)
    if not cases:
        return {"dataset": dataset, "status": "skipped", "skip_reason": f"case jsonl missing or empty: {case_path}"}

    split_cases, split_policy = build_splits(dataset, cases, args.random_state)
    split_cases = cap_splits(split_cases, args.max_cases_per_split)
    split_status = validate_splits(split_cases)
    if split_status:
        return {"dataset": dataset, "status": "skipped", "skip_reason": split_status, "split_policy": split_policy}

    result: dict[str, Any] = {
        "dataset": dataset,
        "status": "evaluated",
        "split_policy": split_policy,
        "split_counts": {split: len(rows) for split, rows in split_cases.items()},
        "experiments": {},
    }

    train = split_cases["train"]
    validation = split_cases["validation"]
    test = split_cases["test"]

    text_result = run_text_detector(
        split_cases,
        output_dir=output_dir,
        args=args,
    )
    result["experiments"]["text_trainable"] = compact_experiment(text_result)

    view_probabilities: dict[str, dict[str, float]] = {
        "tweet": text_result.get("validation_probabilities", {}) | text_result.get("test_probabilities", {})
    }
    validation_view_probabilities: dict[str, dict[str, float]] = {"tweet": text_result.get("validation_probabilities", {})}
    test_view_probabilities: dict[str, dict[str, float]] = {"tweet": text_result.get("test_probabilities", {})}

    detector_predictions: dict[str, list[dict[str, Any]]] = {}
    test_outputs = build_detector_outputs(
        test,
        view="tweet",
        probabilities=text_result.get("test_probabilities", {}),
        capability_boundary=text_result.get("capability_boundary", ""),
    )
    detector_predictions["tweet"] = test_outputs

    if dataset == "MultiOFF":
        image_result = run_multioff_cross_modal(
            split_cases,
            output_dir=output_dir,
            args=args,
        )
        result["experiments"]["cross_modal_meme_img"] = compact_experiment(image_result)
        if image_result.get("status") == "evaluated":
            validation_view_probabilities["meme"] = image_result.get("validation_probabilities", {})
            test_view_probabilities["meme"] = image_result.get("test_probabilities", {})
            view_probabilities["meme"] = image_result.get("validation_probabilities", {}) | image_result.get("test_probabilities", {})
            detector_predictions["meme"] = build_detector_outputs(
                test,
                view="meme",
                probabilities=image_result.get("test_probabilities", {}),
                capability_boundary=image_result.get("capability_boundary", ""),
            )

    if dataset == "FakeSV":
        video_result = run_fakesv_temporal_video(
            split_cases,
            output_dir=output_dir,
            c3d_zip=Path(args.fakesv_c3d_zip),
            args=args,
        )
        result["experiments"]["video_temporal_c3d"] = compact_experiment(video_result)
        if video_result.get("status") == "evaluated":
            validation_view_probabilities["video"] = video_result.get("validation_probabilities", {})
            test_view_probabilities["video"] = video_result.get("test_probabilities", {})
            view_probabilities["video"] = video_result.get("validation_probabilities", {}) | video_result.get("test_probabilities", {})
            detector_predictions["video"] = build_detector_outputs(
                test,
                view="video",
                probabilities=video_result.get("test_probabilities", {}),
                capability_boundary=video_result.get("capability_boundary", ""),
            )

    if any(claim_context_text(case) for case in train + validation + test):
        claim_result = run_claim_cross_encoder(
            split_cases,
            output_dir=output_dir,
            args=args,
        )
        result["experiments"]["claim_cross_encoder"] = compact_experiment(claim_result)
        if claim_result.get("status") == "evaluated":
            validation_view_probabilities["claim"] = claim_result.get("validation_probabilities", {})
            test_view_probabilities["claim"] = claim_result.get("test_probabilities", {})
            view_probabilities["claim"] = claim_result.get("validation_probabilities", {}) | claim_result.get("test_probabilities", {})
            detector_predictions["claim"] = build_detector_outputs(
                test,
                view="claim",
                probabilities=claim_result.get("test_probabilities", {}),
                capability_boundary=claim_result.get("capability_boundary", ""),
                claim_stance=True,
            )

    gating_result = run_gating_fusion(
        split_cases,
        validation_view_probabilities=validation_view_probabilities,
        test_view_probabilities=test_view_probabilities,
        output_dir=output_dir,
        args=args,
    )
    result["experiments"]["gating_fusion"] = compact_experiment(gating_result)

    if gating_result.get("status") == "evaluated":
        test_probs = gating_result["test_probabilities"]
    else:
        test_probs = text_result.get("test_probabilities", {})

    prediction_rows = build_unified_predictions(
        test,
        detector_predictions,
        test_probs,
    )
    prediction_path = output_dir / "trainable_post_predictions.jsonl"
    write_jsonl(prediction_path, prediction_rows)
    result["prediction_path"] = str(prediction_path)
    result["summary"] = summarize_dataset(result["experiments"])
    result["calibration"] = {
        "ece": gating_result.get("ece") if gating_result.get("status") == "evaluated" else text_result.get("ece"),
        "coverage_risk_curve": (
            gating_result.get("coverage_risk_curve")
            if gating_result.get("status") == "evaluated"
            else text_result.get("coverage_risk_curve")
        ),
    }
    return result


def load_teacher_silver_for_dataset(teacher_silver_root: Path | None, dataset: str) -> dict[str, dict[str, Any]]:
    if teacher_silver_root is None or not teacher_silver_root.exists():
        return {}
    candidates = [
        teacher_silver_root / safe_name(dataset) / "teacher_silver.jsonl",
        teacher_silver_root / f"{safe_name(dataset)}.jsonl",
        teacher_silver_root / "teacher_silver.jsonl",
    ]
    for path in candidates:
        if path.exists():
            return load_teacher_silver_index(load_cases(path))
    return {}


def evaluate_student_dataset(dataset: str, *, case_dir: Path, output_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    case_path = case_dir / f"{dataset}.jsonl"
    cases = load_cases(case_path)
    if not cases:
        return {"dataset": dataset, "status": "skipped", "skip_reason": f"case jsonl missing or empty: {case_path}"}

    split_cases, split_policy = build_splits(dataset, cases, args.random_state)
    split_cases = cap_splits(split_cases, args.max_cases_per_split)
    split_status = validate_splits(split_cases)
    if split_status:
        return {"dataset": dataset, "status": "skipped", "skip_reason": split_status, "split_policy": split_policy}

    teacher_silver_root = Path(args.teacher_silver_dir).expanduser() if str(args.teacher_silver_dir or "").strip() else None
    teacher_silver_index = load_teacher_silver_for_dataset(teacher_silver_root, dataset)
    student_model_name = resolve_student_model_name(args.student_backbone)
    student_backend = args.student_encoder_backend
    if student_backend == "auto":
        student_backend = "hf-transformer"

    result: dict[str, Any] = {
        "dataset": dataset,
        "status": "evaluated",
        "split_policy": split_policy,
        "split_counts": {split: len(rows) for split, rows in split_cases.items()},
        "experiments": {},
    }

    train = split_cases["train"]
    validation = split_cases["validation"]
    test = split_cases["test"]
    all_cases = train + validation + test

    post_bundle = encode_text_features(
        [text_of(case) for case in all_cases],
        backend=student_backend,
        model_name=student_model_name,
        revision=None,
        cache_dir=args.hf_cache_dir,
        dim=args.hash_dim,
        batch_size=args.batch_size,
        local_files_only=not args.allow_model_download,
    )
    claim_bundle = encode_text_features(
        [claim_context_text(case) for case in all_cases],
        backend=student_backend,
        model_name=student_model_name,
        revision=None,
        cache_dir=args.hf_cache_dir,
        dim=args.hash_dim,
        batch_size=args.batch_size,
        local_files_only=not args.allow_model_download,
    )
    student_matrix = np.concatenate([post_bundle.matrix, claim_bundle.matrix], axis=-1)
    train_x, validation_x, test_x = split_feature_matrix(student_matrix, train, validation, test)
    targets = build_selective_student_targets(all_cases, teacher_silver_index)
    train_target_count = len(train)
    train_targets = {key: value[:train_target_count] for key, value in targets.items()}

    model = SelectiveStudentEncoder(input_dim=train_x.shape[1], hidden_dim=args.hidden_dim, stance_count=len(STANCE_ORDER))
    train_info = train_selective_student_model(
        model,
        train_x,
        train_targets,
        epochs=args.epochs,
        batch_size=args.batch_size,
    )
    validation_predictions = predict_selective_student_outputs(model, validation_x)
    test_predictions = predict_selective_student_outputs(model, test_x)
    validation_metrics = student_main_axis_metrics(validation, validation_predictions, teacher_silver_index=teacher_silver_index)
    test_metrics = student_main_axis_metrics(test, test_predictions, teacher_silver_index=teacher_silver_index)

    prediction_rows = build_selective_student_prediction_rows(test, test_predictions, teacher_silver_index=teacher_silver_index)
    prediction_path = output_dir / "trainable_post_predictions.jsonl"
    write_jsonl(prediction_path, prediction_rows)

    student_experiment = {
        "status": "evaluated",
        "schema": "review-student-2plus1-v1",
        "task_protocol": ["attack_hate_offense", "misinfo_claim_risk", "stance_aux", "defer_route"],
        "model_name": student_model_name,
        "model_backend": student_backend,
        "teacher_silver_root": str(teacher_silver_root or ""),
        "teacher_silver_used": bool(teacher_silver_index),
        "teacher_silver_count": len(teacher_silver_index),
        "train_count": len(train),
        "validation_count": len(validation),
        "test_count": len(test),
        "validation_metrics": validation_metrics,
        "test_metrics": test_metrics,
        "train_info": train_info,
        "prediction_path": str(prediction_path),
        "capability_boundary": {
            "teacher_silver_structured_json": True,
            "rationale_summary_not_a_student_target": True,
            "claim_context_required_for_stance": True,
            "selective_routing_head": True,
        },
    }
    if validation_predictions:
        validation_overall = np.asarray(
            [
                student_overall_probability_for_case(
                    case,
                    float(validation_predictions[ATTACK_AXIS][index]),
                    float(validation_predictions[MISINFO_AXIS][index]),
                )
                for index, case in enumerate(validation)
            ],
            dtype="float32",
        )
        student_experiment["validation_probabilities"] = {case["case_id"]: float(prob) for case, prob in zip(validation, validation_overall)}
    if test_predictions:
        test_overall = np.asarray(
            [
                student_overall_probability_for_case(
                    case,
                    float(test_predictions[ATTACK_AXIS][index]),
                    float(test_predictions[MISINFO_AXIS][index]),
                )
                for index, case in enumerate(test)
            ],
            dtype="float32",
        )
        student_experiment["test_probabilities"] = {case["case_id"]: float(prob) for case, prob in zip(test, test_overall)}

    result["experiments"]["student_2p1"] = compact_experiment(student_experiment)
    result["prediction_path"] = str(prediction_path)
    result["summary"] = summarize_dataset(result["experiments"])
    result["calibration"] = {
        "ece": test_metrics["overall"]["ece"],
        "coverage_risk_curve": test_metrics["overall"]["coverage_risk_curve"],
        "abstain_rate": test_metrics["overall"]["abstain_rate"],
        "high_risk_recall": test_metrics["overall"]["high_risk_recall"],
    }

    if args.legacy_view_experiments:
        legacy_result = evaluate_dataset(dataset, case_dir=case_dir, output_dir=output_dir / "legacy_view", args=args)
        result["legacy_view_experiments"] = legacy_result

    return result


def run_text_detector(
    split_cases: dict[str, list[dict[str, Any]]],
    *,
    output_dir: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    train = split_cases["train"]
    validation = split_cases["validation"]
    test = split_cases["test"]
    all_cases = train + validation + test
    features = encode_text_features(
        [text_of(case) for case in all_cases],
        backend=args.text_backend,
        model_name=args.text_model,
        revision=args.text_revision or None,
        cache_dir=args.hf_cache_dir,
        dim=args.hash_dim,
        batch_size=args.batch_size,
        local_files_only=not args.allow_model_download,
    )
    train_x, validation_x, test_x = split_feature_matrix(features.matrix, train, validation, test)
    model = MultitaskTextDetector(input_dim=train_x.shape[1], hidden_dim=args.hidden_dim)
    train_info = train_multitask_text_model(
        model,
        train_x,
        multitask_targets(train),
        epochs=args.epochs,
        batch_size=args.batch_size,
    )
    val_prob = predict_probabilities(model, validation_x)
    test_prob = predict_probabilities(model, test_x)
    result = experiment_result(
        view="tweet",
        train=train,
        validation=validation,
        test=test,
        validation_probabilities=val_prob,
        test_probabilities=test_prob,
        capability_boundary=features.capability_boundary,
        model_backend=features.backend,
        train_info=train_info,
        output_dir=output_dir,
        prediction_name="text_trainable_predictions.jsonl",
    )
    result["model_name"] = features.model_name
    result["tasks"] = ["harmfulness", "harm_type", "stance", "rationale_or_target"]
    return result


def run_multioff_cross_modal(
    split_cases: dict[str, list[dict[str, Any]]],
    *,
    output_dir: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    image_splits = {
        split: [case for case in rows if image_path_of(case)]
        for split, rows in split_cases.items()
    }
    if any(not rows for rows in image_splits.values()):
        return {
            "status": "skipped",
            "skip_reason": "one or more splits have no aligned local image cases",
            "split_counts_with_images": {split: len(rows) for split, rows in image_splits.items()},
        }
    train = image_splits["train"]
    validation = image_splits["validation"]
    test = image_splits["test"]
    all_cases = train + validation + test
    text_features, image_features = encode_clip_image_text_features(
        all_cases,
        model_name=args.clip_model,
        revision=args.clip_revision or None,
        cache_dir=args.hf_cache_dir,
        batch_size=args.batch_size,
        local_files_only=not args.allow_model_download,
        fallback_dim=args.hash_dim,
    )
    train_text, validation_text, test_text = split_feature_matrix(text_features.matrix, train, validation, test)
    train_image, validation_image, test_image = split_feature_matrix(image_features.matrix, train, validation, test)
    model = CrossModalAttentionAdapter(
        text_dim=train_text.shape[1],
        image_dim=train_image.shape[1],
        hidden_dim=args.hidden_dim,
    )
    train_info = train_cross_modal_torch_model(
        model,
        train_text,
        train_image,
        np.asarray([binary_label(case) for case in train], dtype=int),
        epochs=args.epochs,
        batch_size=args.batch_size,
    )
    val_prob = predict_probabilities(model, (validation_text, validation_image))
    test_prob = predict_probabilities(model, (test_text, test_image))
    result = experiment_result(
        view="meme",
        train=train,
        validation=validation,
        test=test,
        validation_probabilities=val_prob,
        test_probabilities=test_prob,
        capability_boundary=(
            f"{text_features.capability_boundary}; {image_features.capability_boundary}; "
            "trainable cross-attention adapter with supervised contrastive auxiliary loss"
        ),
        model_backend=f"cross_attention_adapter+{text_features.backend}+{image_features.backend}",
        train_info=train_info,
        output_dir=output_dir,
        prediction_name="cross_modal_meme_img_predictions.jsonl",
    )
    result["retrieval_contrastive"] = {
        "status": "enabled",
        "method": "supervised contrastive auxiliary loss over cross-modal embeddings",
        "weight": train_info.get("contrastive_weight"),
    }
    return result


def run_fakesv_temporal_video(
    split_cases: dict[str, list[dict[str, Any]]],
    *,
    output_dir: Path,
    c3d_zip: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    if not c3d_zip.exists():
        return {"status": "skipped", "skip_reason": "FakeSV C3D feature zip missing", "feature_zip": str(c3d_zip)}
    video_splits = {
        split: [case for case in rows if c3d_member_exists(c3d_zip, video_id_of(case))]
        for split, rows in split_cases.items()
    }
    if any(not rows for rows in video_splits.values()):
        return {
            "status": "skipped",
            "skip_reason": "one or more splits have no matching C3D feature rows",
            "feature_zip": str(c3d_zip),
            "split_counts_with_c3d": {split: len(rows) for split, rows in video_splits.items()},
        }
    train = video_splits["train"]
    validation = video_splits["validation"]
    test = video_splits["test"]
    all_cases = train + validation + test
    sequences = load_c3d_sequences(
        all_cases,
        c3d_zip=c3d_zip,
        max_steps=32,
        projection_dim=args.c3d_projection_dim,
        random_state=args.random_state,
    )
    train_x, validation_x, test_x = split_feature_matrix(sequences, train, validation, test)
    model = TemporalC3DTransformer(input_dim=train_x.shape[-1], hidden_dim=args.hidden_dim)
    train_info = train_binary_torch_model(
        model,
        train_x,
        np.asarray([binary_label(case) for case in train], dtype=int),
        epochs=args.epochs,
        batch_size=args.batch_size,
    )
    val_prob = predict_probabilities(model, validation_x)
    test_prob = predict_probabilities(model, test_x)
    return experiment_result(
        view="video",
        train=train,
        validation=validation,
        test=test,
        validation_probabilities=val_prob,
        test_probabilities=test_prob,
        capability_boundary=(
            "FakeSV public pre-extracted C3D sequence features + temporal Transformer; "
            f"4096-d frame features are deterministically projected to {train_x.shape[-1]} dims for full-data validation; "
            "not raw-video, ASR, OCR, comments, or publisher-context encoding"
        ),
        model_backend="temporal_transformer_over_projected_c3d_sequences",
        train_info={
            **train_info,
            "c3d_projection_dim": int(train_x.shape[-1]),
            "c3d_sequence_shape": list(sequences.shape),
        },
        output_dir=output_dir,
        prediction_name="video_temporal_c3d_predictions.jsonl",
    )


def run_claim_cross_encoder(
    split_cases: dict[str, list[dict[str, Any]]],
    *,
    output_dir: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    claim_splits = {
        split: [case for case in rows if claim_context_text(case)]
        for split, rows in split_cases.items()
    }
    if any(not rows for rows in claim_splits.values()):
        return {
            "status": "skipped",
            "skip_reason": "one or more splits have no claim/evidence context cases",
            "split_counts_with_claim": {split: len(rows) for split, rows in claim_splits.items()},
        }
    train = claim_splits["train"]
    validation = claim_splits["validation"]
    test = claim_splits["test"]
    all_cases = train + validation + test
    rag = LocalHashRag.from_jsonl(args.rag_corpus) if args.enable_rag else None
    claim_texts = [rag_augmented_claim_context(case, rag, top_k=args.rag_top_k) for case in all_cases]
    post_features = encode_text_features(
        [text_of(case) for case in all_cases],
        backend=args.text_backend,
        model_name=args.text_model,
        revision=args.text_revision or None,
        cache_dir=args.hf_cache_dir,
        dim=args.hash_dim,
        batch_size=args.batch_size,
        local_files_only=not args.allow_model_download,
    )
    claim_features = encode_text_features(
        claim_texts,
        backend=args.text_backend,
        model_name=args.text_model,
        revision=args.text_revision or None,
        cache_dir=args.hf_cache_dir,
        dim=args.hash_dim,
        batch_size=args.batch_size,
        local_files_only=not args.allow_model_download,
    )
    train_post, validation_post, test_post = split_feature_matrix(post_features.matrix, train, validation, test)
    train_claim, validation_claim, test_claim = split_feature_matrix(claim_features.matrix, train, validation, test)
    model = ClaimEvidenceCrossEncoder(feature_dim=train_post.shape[1], hidden_dim=args.hidden_dim)
    train_info = train_binary_torch_model(
        model,
        (train_post, train_claim),
        np.asarray([binary_label(case) for case in train], dtype=int),
        epochs=args.epochs,
        batch_size=args.batch_size,
    )
    val_prob = predict_probabilities(model, (validation_post, validation_claim))
    test_prob = predict_probabilities(model, (test_post, test_claim))
    result = experiment_result(
        view="claim",
        train=train,
        validation=validation,
        test=test,
        validation_probabilities=val_prob,
        test_probabilities=test_prob,
        capability_boundary=(
            "claim_context cross-encoder augmented with local DISARM RAG corpus"
            if args.enable_rag
            else "local claim_context cross-encoder; uses dataset annotations/content, not external RAG"
        ),
        model_backend=f"claim_cross_encoder+{post_features.backend}",
        train_info=train_info,
        output_dir=output_dir,
        prediction_name="claim_cross_encoder_predictions.jsonl",
    )
    result["tasks"] = ["claim_conditioned_harmfulness", "stance_proxy", "veracity_or_fake_harm"]
    result["rag"] = {
        "enabled": bool(args.enable_rag),
        "corpus_path": str(args.rag_corpus),
        "document_count": len(rag.documents) if rag else 0,
        "top_k": args.rag_top_k,
    }
    return result


def rag_augmented_claim_context(case: dict[str, Any], rag: LocalHashRag | None, *, top_k: int) -> str:
    context = claim_context_text(case)
    if rag is None:
        return context
    query = " ".join([text_of(case), context]).strip()
    evidence = rag.retrieve(query, top_k=top_k)
    return augment_context_with_rag(context, evidence)


def run_gating_fusion(
    split_cases: dict[str, list[dict[str, Any]]],
    *,
    validation_view_probabilities: dict[str, dict[str, float]],
    test_view_probabilities: dict[str, dict[str, float]],
    output_dir: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    validation = split_cases["validation"]
    test = split_cases["test"]
    validation_x, feature_names = build_gating_feature_matrix(validation, validation_view_probabilities)
    test_x, _ = build_gating_feature_matrix(test, test_view_probabilities)
    if validation_x.shape[1] == 0 or len({binary_label(case) for case in validation}) < 2:
        return {"status": "skipped", "skip_reason": "gating validation split has insufficient labels or features"}
    model = GatingFusionModel(input_dim=validation_x.shape[1], hidden_dim=32)
    train_info = train_binary_torch_model(
        model,
        validation_x,
        np.asarray([binary_label(case) for case in validation], dtype=int),
        epochs=args.epochs,
        batch_size=args.batch_size,
    )
    test_prob = predict_probabilities(model, test_x)
    labels = np.asarray([binary_label(case) for case in test], dtype=int)
    metrics = binary_classification_metrics(labels, test_prob)
    ece = expected_calibration_error(labels, test_prob)
    curve = coverage_risk_curve(labels, test_prob)
    prediction_path = output_dir / "gating_fusion_predictions.jsonl"
    write_probability_rows(prediction_path, test, test_prob)
    return {
        "status": "evaluated",
        "fusion_policy": "trainable_gating_over_view_probability_confidence_availability_conflict",
        "feature_names": feature_names,
        "validation_count": len(validation),
        "test_count": len(test),
        "test_metrics": metrics,
        "ece": ece,
        "coverage_risk_curve": curve,
        "train_info": train_info,
        "test_probabilities": {case["case_id"]: float(prob) for case, prob in zip(test, test_prob)},
        "prediction_path": str(prediction_path),
    }


def experiment_result(
    *,
    view: str,
    train: list[dict[str, Any]],
    validation: list[dict[str, Any]],
    test: list[dict[str, Any]],
    validation_probabilities: np.ndarray,
    test_probabilities: np.ndarray,
    capability_boundary: str,
    model_backend: str,
    train_info: dict[str, Any],
    output_dir: Path,
    prediction_name: str,
) -> dict[str, Any]:
    validation_labels = np.asarray([binary_label(case) for case in validation], dtype=int)
    test_labels = np.asarray([binary_label(case) for case in test], dtype=int)
    prediction_path = output_dir / prediction_name
    write_probability_rows(prediction_path, test, test_probabilities)
    return {
        "status": "evaluated",
        "view": view,
        "model_backend": model_backend,
        "capability_boundary": capability_boundary,
        "train_count": len(train),
        "validation_count": len(validation),
        "test_count": len(test),
        "validation_metrics": binary_classification_metrics(validation_labels, validation_probabilities),
        "test_metrics": binary_classification_metrics(test_labels, test_probabilities),
        "ece": expected_calibration_error(test_labels, test_probabilities),
        "coverage_risk_curve": coverage_risk_curve(test_labels, test_probabilities),
        "train_info": train_info,
        "validation_probabilities": {case["case_id"]: float(prob) for case, prob in zip(validation, validation_probabilities)},
        "test_probabilities": {case["case_id"]: float(prob) for case, prob in zip(test, test_probabilities)},
        "prediction_path": str(prediction_path),
    }


def build_detector_outputs(
    cases: list[dict[str, Any]],
    *,
    view: str,
    probabilities: dict[str, float],
    capability_boundary: str,
    claim_stance: bool = False,
) -> list[dict[str, Any]]:
    rows = []
    for case in cases:
        case_id = str(case.get("case_id"))
        if case_id not in probabilities:
            continue
        evidence = [claim_context_text(case)[:240]] if view == "claim" else [text_of(case)[:240]]
        rows.append(
            standard_detector_output(
                case,
                view=view,
                probability=float(probabilities[case_id]),
                evidence=evidence,
                capability_boundary=capability_boundary,
                stance=stance_proxy_of(case) if claim_stance else None,
            )
        )
        rows[-1]["case_id"] = case_id
    return rows


def build_unified_predictions(
    test_cases: list[dict[str, Any]],
    detector_predictions: dict[str, list[dict[str, Any]]],
    gating_probabilities: dict[str, float],
) -> list[dict[str, Any]]:
    output_rows = []
    for case in test_cases:
        case_id = str(case.get("case_id"))
        detectors = []
        for rows in detector_predictions.values():
            for item in rows:
                if item.get("case_id") == case_id:
                    detectors.append(item)
        fusion = fuse_detector_outputs(detectors, model_probability=gating_probabilities.get(case_id))
        agent_review = build_agent_review(detectors, fusion)
        output_rows.append(
            {
                "case_id": case.get("case_id"),
                "dataset": case.get("dataset"),
                "split": case.get("split"),
                "source_id": case.get("source_id"),
                "y_true": label_of(case),
                "detectors": detectors,
                "fusion": fusion,
                "agent_review": agent_review,
                "text_excerpt": text_of(case)[:240],
            }
        )
    return output_rows


def compact_experiment(result: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in result.items()
        if key not in {"validation_probabilities", "test_probabilities"}
    }


def summarize_dataset(experiments: dict[str, dict[str, Any]]) -> dict[str, Any]:
    evaluated = {
        name: result
        for name, result in experiments.items()
        if result.get("status") == "evaluated"
    }
    skipped = {
        name: result.get("skip_reason", "")
        for name, result in experiments.items()
        if result.get("status") == "skipped"
    }
    best = None
    for name, result in evaluated.items():
        metrics = result.get("test_metrics") or {}
        macro_f1 = metrics.get("macro_f1")
        if macro_f1 is None and isinstance(metrics.get("overall"), dict):
            macro_f1 = metrics["overall"].get("macro_f1")
        if macro_f1 is None:
            attack_f1 = (metrics.get("attack") or {}).get("macro_f1")
            misinfo_f1 = (metrics.get("misinfo") or {}).get("macro_f1")
            if attack_f1 is not None and misinfo_f1 is not None:
                macro_f1 = (float(attack_f1) + float(misinfo_f1)) / 2.0
        if macro_f1 is None:
            continue
        if best is None or macro_f1 > best["macro_f1"]:
            best = {"experiment": name, "macro_f1": macro_f1}
    return {
        "status": "evaluated" if evaluated else "skipped",
        "evaluated": sorted(evaluated),
        "skipped": skipped,
        "best_test_macro_f1": best,
    }


def summarize_report(datasets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    evaluated = {
        name: result
        for name, result in datasets.items()
        if result.get("status") == "evaluated"
    }
    return {
        "dataset_count": len(datasets),
        "evaluated_datasets": sorted(evaluated),
        "skipped_datasets": {
            name: result.get("skip_reason", "")
            for name, result in datasets.items()
            if result.get("status") != "evaluated"
        },
        "claim": "existing_data_trainable_post_loop_complete" if evaluated else "no_dataset_evaluated",
        "full_validation_gate": "not_claimed",
    }


def validate_splits(split_cases: dict[str, list[dict[str, Any]]]) -> str:
    for split in ("train", "validation", "test"):
        if not split_cases.get(split):
            return f"{split} split empty"
        if len({label_of(case) for case in split_cases[split]}) < 2:
            return f"{split} split lost a class"
    return ""


def cap_splits(split_cases: dict[str, list[dict[str, Any]]], max_cases: int) -> dict[str, list[dict[str, Any]]]:
    if max_cases <= 0:
        return split_cases
    capped = {}
    for split, rows in split_cases.items():
        positives = [case for case in rows if label_of(case) == POSITIVE_LABEL]
        negatives = [case for case in rows if label_of(case) != POSITIVE_LABEL]
        each = max(1, max_cases // 2)
        selected = positives[:each] + negatives[:each]
        capped[split] = selected[:max_cases]
    return capped


def split_feature_matrix(
    matrix: np.ndarray,
    train: list[dict[str, Any]],
    validation: list[dict[str, Any]],
    test: list[dict[str, Any]],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    train_end = len(train)
    validation_end = train_end + len(validation)
    return matrix[:train_end], matrix[train_end:validation_end], matrix[validation_end:]


def write_probability_rows(path: Path, cases: list[dict[str, Any]], probabilities: np.ndarray) -> None:
    rows = []
    for case, prob in zip(cases, probabilities):
        rows.append(
            {
                "case_id": case.get("case_id"),
                "dataset": case.get("dataset"),
                "split": case.get("split"),
                "source_id": case.get("source_id"),
                "y_true": label_of(case),
                "y_pred": POSITIVE_LABEL if float(prob) >= 0.5 else "non_harmful",
                "harmful_probability": round(float(prob), 6),
                "confidence": confidence_from_probability(float(prob)),
                "text_excerpt": text_of(case)[:240],
            }
        )
    write_jsonl(path, rows)


def write_combined_predictions(datasets: dict[str, Any], path: Path) -> int:
    rows = []
    for dataset, result in datasets.items():
        if not isinstance(result, dict):
            continue
        prediction_path = result.get("prediction_path")
        if not prediction_path:
            continue
        source_path = Path(prediction_path)
        if not source_path.exists():
            continue
        with source_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                row.setdefault("dataset", dataset)
                rows.append(row)
    write_jsonl(path, rows)
    return len(rows)


def load_cases(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    cases = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def image_path_of(case: dict[str, Any]) -> str:
    path = str(((case.get("views") or {}).get("img") or {}).get("media_path") or "").strip()
    return path if path and Path(path).exists() else ""


def c3d_member_exists(c3d_zip: Path, video_id: str) -> bool:
    try:
        with zipfile.ZipFile(c3d_zip) as archive:
            return f"c3d/{video_id}.hdf5" in set(archive.namelist())
    except Exception:
        return False


def load_c3d_sequences(
    cases: list[dict[str, Any]],
    *,
    c3d_zip: Path,
    max_steps: int,
    projection_dim: int = 256,
    random_state: int = 42,
) -> np.ndarray:
    rows = []
    projection = None
    with zipfile.ZipFile(c3d_zip) as archive:
        for case in cases:
            video_id = video_id_of(case)
            data = archive.read(f"c3d/{video_id}.hdf5")
            sequence = read_c3d_sequence(data, video_id, max_steps=max_steps)
            if projection_dim > 0 and sequence.shape[-1] > projection_dim:
                if projection is None:
                    projection = build_c3d_projection(
                        sequence.shape[-1],
                        projection_dim,
                        random_state=random_state,
                    )
                sequence = project_c3d_sequence(sequence, projection)
            rows.append(sequence)
    return np.stack(rows).astype("float32")


def build_c3d_projection(input_dim: int, output_dim: int, *, random_state: int) -> np.ndarray:
    rng = np.random.default_rng(random_state)
    projection = rng.normal(0.0, 1.0 / math.sqrt(float(output_dim)), size=(input_dim, output_dim))
    return projection.astype("float32")


def project_c3d_sequence(sequence: np.ndarray, projection: np.ndarray) -> np.ndarray:
    projected = np.asarray(sequence @ projection, dtype="float32")
    norms = np.linalg.norm(projected, axis=1, keepdims=True)
    return np.divide(projected, np.maximum(norms, 1e-8)).astype("float32")


def read_c3d_sequence(data: bytes, video_id: str, *, max_steps: int) -> np.ndarray:
    import h5py

    with h5py.File(io.BytesIO(data), "r") as handle:
        group_key = video_id if video_id in handle else next(iter(handle.keys()))
        group = handle[group_key]
        features = np.asarray(group["c3d_features"][:], dtype="float32")
    if features.ndim == 1:
        features = features.reshape(1, -1)
    features = np.nan_to_num(features, copy=False)
    if features.shape[0] >= max_steps:
        indices = np.linspace(0, features.shape[0] - 1, max_steps).round().astype(int)
        sampled = features[indices]
    else:
        pad = np.zeros((max_steps - features.shape[0], features.shape[1]), dtype="float32")
        sampled = np.vstack([features, pad])
    norms = np.linalg.norm(sampled, axis=1, keepdims=True)
    sampled = np.divide(sampled, np.maximum(norms, 1e-8))
    return sampled.astype("float32")


def safe_name(value: str) -> str:
    return value.replace("/", "_").replace("\\", "_").replace(" ", "_")


if __name__ == "__main__":
    raise SystemExit(main())
