"""Run Review post-level multiview ablations across available review-post-case datasets.

This runner generalizes the MultiOFF-only validation lane. For each dataset it
builds a reproducible train/validation/test split, evaluates the available
views, and records skipped views explicitly when local data does not contain
aligned media. The current scope is still an ablation runner, not a full
end-to-end MV-PostGuard training system.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from run_review_multioff_multiview_ablation import (
    LABELS,
    compute_metrics,
    image_path_of,
    label_of,
    labels_from_probabilities,
    load_cases,
    POSITIVE_LABEL,
    positive_probabilities,
    run_learned_fusion_experiment,
    run_fusion_experiment,
    run_image_experiment,
    run_majority_vote_experiment,
    run_text_experiment,
    safe_name,
    stack_embeddings,
    text_of,
    write_probability_predictions,
)

DEFAULT_DATASETS = [
    "MultiOFF",
    "HateXplain",
    "Jigsaw Toxicity",
    "Hateful Memes",
    "MAMI",
    "MMHS150K",
    "PHEME",
    "RumourEval 2019",
    "MOCHEG",
    "FACTIFY3M",
    "FakeSV",
    "mcfend",
    "Twitter15_16_dataset",
    "Fakeddit",
    "MuMiN",
]

EXPECTED_DATASET_VIEWS = {
    "MultiOFF": ["tweet", "meme", "img"],
    "HateXplain": ["tweet"],
    "Jigsaw Toxicity": ["tweet"],
    "Hateful Memes": ["tweet", "meme", "img"],
    "MAMI": ["tweet", "meme", "img"],
    "MMHS150K": ["tweet", "img"],
    "PHEME": ["tweet", "claim"],
    "RumourEval 2019": ["tweet", "claim"],
    "MOCHEG": ["tweet", "img", "claim", "evidence"],
    "FACTIFY3M": ["tweet", "img", "claim", "evidence"],
    "FakeSV": ["tweet", "video"],
    "mcfend": ["tweet"],
    "Twitter15_16_dataset": ["tweet"],
    "Fakeddit": ["tweet", "img"],
    "MuMiN": ["tweet", "img", "claim", "graph"],
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-dir", default=r"G:\CISCN\.tmp\review_post_cases_full")
    parser.add_argument("--output-dir", default=r"G:\CISCN\.tmp\review_post_multiview_ablation")
    parser.add_argument("--datasets", nargs="*", default=DEFAULT_DATASETS)
    parser.add_argument("--clip-model", default="openai/clip-vit-base-patch32")
    parser.add_argument("--hf-cache-dir", default=r"G:\CISCN\.cache\huggingface")
    parser.add_argument("--hf-endpoint", default="")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--max-cases-per-dataset", type=int, default=0)
    parser.add_argument(
        "--fakesv-c3d-zip",
        default=r"G:\CISCN\dataset\review_public\FakeSV\features\c3d.zip",
        help="Optional FakeSV pre-extracted C3D feature zip. This is a video-feature baseline, not raw-video encoding.",
    )
    args = parser.parse_args()

    os.environ.setdefault("HF_HOME", args.hf_cache_dir)
    os.environ.setdefault("TRANSFORMERS_CACHE", args.hf_cache_dir)
    if args.hf_endpoint:
        os.environ["HF_ENDPOINT"] = args.hf_endpoint

    case_dir = Path(args.case_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "schema": "review-post-multiview-ablation-suite-v1",
        "case_dir": str(case_dir),
        "output_dir": str(output_dir),
        "datasets_requested": args.datasets,
        "method": {
            "text_view": "TF-IDF char n-gram + Logistic Regression",
            "image_view": "Frozen CLIP image encoder + Logistic Regression when aligned local images exist",
            "video_feature_view": "FakeSV pre-extracted C3D frame features + temporal mean pooling + Logistic Regression when c3d.zip exists",
            "claim_context_view": "TF-IDF char n-gram + Logistic Regression over claim text and annotation-level evidence metadata when available",
            "fusion": "Selective majority vote, validation-tuned weighted late fusion, and learned Logistic Regression fusion over available view harmful probabilities",
            "clip_model": args.clip_model,
            "hf_endpoint": os.environ.get("HF_ENDPOINT", ""),
            "fakesv_c3d_zip": str(Path(args.fakesv_c3d_zip)),
        },
        "capability_boundary": {
            "runner_type": "cross_dataset_ablation",
            "trained_end_to_end_mv_postguard": False,
            "video_view": Path(args.fakesv_c3d_zip).exists(),
            "raw_video_encoder": False,
            "preextracted_video_feature_baseline": Path(args.fakesv_c3d_zip).exists(),
            "video_metadata_proxy": True,
            "claim_conditioned_model": False,
            "claim_context_metadata_baseline": True,
            "uses_shallow_image_metadata_fallback": False,
            "description": (
                "Evaluates available tweet/text and image views per dataset. Missing image "
                "media views are skipped with reasons rather than approximated from metadata. "
                "FakeSV can evaluate public pre-extracted C3D video features when c3d.zip is "
                "present; this is still not raw-video end-to-end encoding. Claim-context "
                "experiments use dataset-provided claim/evidence annotations when present; "
                "they are not external RAG."
            ),
        },
        "datasets": {},
        "summary": {},
    }

    for dataset in args.datasets:
        case_path = case_dir / f"{safe_name(dataset)}.jsonl"
        if not case_path.exists():
            report["datasets"][dataset] = {
                "dataset": dataset,
                "case_count": 0,
                "usable_text_labelled_cases": 0,
                "summary": {
                    "status": "skipped",
                    "skip_reason": "case jsonl missing; run converter after acquiring dataset",
                },
                "case_path": str(case_path),
            }
            continue
        cases = load_cases(case_path)
        if args.max_cases_per_dataset > 0:
            cases = cases[: args.max_cases_per_dataset]
        dataset_dir = output_dir / safe_name(dataset)
        dataset_dir.mkdir(parents=True, exist_ok=True)
        report["datasets"][dataset] = evaluate_dataset(
            dataset,
            cases,
            output_dir=dataset_dir,
            clip_model_name=args.clip_model,
            hf_cache_dir=Path(args.hf_cache_dir),
            batch_size=args.batch_size,
            random_state=args.random_state,
            fakesv_c3d_zip=Path(args.fakesv_c3d_zip),
        )

    report["summary"] = summarize_suite(report["datasets"])
    report_path = output_dir / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"wrote {report_path}")
    return 0


def evaluate_dataset(
    dataset: str,
    cases: list[dict[str, Any]],
    *,
    output_dir: Path,
    clip_model_name: str,
    hf_cache_dir: Path,
    batch_size: int,
    random_state: int,
    fakesv_c3d_zip: Path,
) -> dict[str, Any]:
    usable = [
        case
        for case in cases
        if text_of(case) and label_of(case) in set(LABELS)
    ]
    report: dict[str, Any] = {
        "dataset": dataset,
        "case_count": len(cases),
        "usable_text_labelled_cases": len(usable),
        "label_distribution": dict(Counter(label_of(case) for case in usable)),
        "view_availability": summarize_view_availability(usable),
        "split_policy": "",
        "split_counts": {},
        "experiments": {},
        "summary": {},
    }
    if len(usable) < 30 or len({label_of(case) for case in usable}) < 2:
        report["summary"] = {
            "status": "skipped",
            "skip_reason": "not enough usable text-labelled cases or only one class",
        }
        return report

    split_cases, split_policy = build_splits(dataset, usable, random_state)
    report["split_policy"] = split_policy
    report["split_counts"] = {split: len(rows) for split, rows in split_cases.items()}

    if any(not rows for rows in split_cases.values()):
        report["summary"] = {
            "status": "skipped",
            "skip_reason": "split policy produced an empty split",
        }
        return report
    if any(len({label_of(case) for case in rows}) < 2 for rows in split_cases.values()):
        report["summary"] = {
            "status": "skipped",
            "skip_reason": "one or more splits lost a class",
        }
        return report

    text_result = run_text_experiment(split_cases, output_dir, random_state)
    report["experiments"]["text_only"] = compact_experiment_result(text_result)

    claim_cases = {
        split: [case for case in rows if claim_context_text(case)]
        for split, rows in split_cases.items()
    }
    if any(not rows for rows in claim_cases.values()):
        claim_result = {
            "status": "skipped",
            "skip_reason": "one or more splits have no claim/evidence context cases",
            "split_counts_with_claim_context": {split: len(rows) for split, rows in claim_cases.items()},
        }
        claim_fusion_result = {
            "status": "skipped",
            "skip_reason": "claim_context_only skipped",
        }
    elif any(len({label_of(case) for case in rows}) < 2 for rows in claim_cases.values()):
        claim_result = {
            "status": "skipped",
            "skip_reason": "claim/evidence subset lost a class in one or more splits",
            "split_counts_with_claim_context": {split: len(rows) for split, rows in claim_cases.items()},
        }
        claim_fusion_result = {
            "status": "skipped",
            "skip_reason": "claim_context_only skipped",
        }
    else:
        claim_result_full = run_claim_context_experiment(
            claim_cases,
            output_dir=output_dir,
            random_state=random_state,
        )
        claim_result = compact_experiment_result(claim_result_full)
        claim_fusion_result_full = run_probability_fusion_experiment(
            claim_cases,
            first_result=text_result,
            second_result=claim_result_full,
            output_dir=output_dir,
            prediction_filename="claim_context_late_fusion_predictions.jsonl",
            fusion_policy="validation_grid_search_text_claim_context_probability_average",
            first_view_name="text",
            second_view_name="claim_context",
        )
        claim_fusion_result = compact_experiment_result(claim_fusion_result_full)

    image_cases = {
        split: [case for case in rows if image_path_of(case)]
        for split, rows in split_cases.items()
    }
    if any(not rows for rows in image_cases.values()):
        image_result = {
            "status": "skipped",
            "skip_reason": "one or more splits have no aligned local image cases",
            "split_counts_with_images": {split: len(rows) for split, rows in image_cases.items()},
        }
        fusion_result = {
            "status": "skipped",
            "skip_reason": "image_only skipped",
        }
        majority_vote_result = {
            "status": "skipped",
            "skip_reason": "image_only skipped",
        }
        learned_fusion_result = {
            "status": "skipped",
            "skip_reason": "image_only skipped",
        }
    elif any(len({label_of(case) for case in rows}) < 2 for rows in image_cases.values()):
        image_result = {
            "status": "skipped",
            "skip_reason": "image-aligned subset lost a class in one or more splits",
            "split_counts_with_images": {split: len(rows) for split, rows in image_cases.items()},
        }
        fusion_result = {
            "status": "skipped",
            "skip_reason": "image_only skipped",
        }
        majority_vote_result = {
            "status": "skipped",
            "skip_reason": "image_only skipped",
        }
        learned_fusion_result = {
            "status": "skipped",
            "skip_reason": "image_only skipped",
        }
    else:
        image_result_full = run_image_experiment(
            image_cases,
            output_dir=output_dir,
            clip_model_name=clip_model_name,
            hf_cache_dir=hf_cache_dir,
            batch_size=batch_size,
            random_state=random_state,
        )
        image_result = compact_experiment_result(image_result_full)
        if image_result_full.get("status") == "evaluated":
            majority_vote_result_full = run_majority_vote_experiment(
                image_cases,
                text_result=text_result,
                image_result=image_result_full,
                output_dir=output_dir,
            )
            majority_vote_result = compact_experiment_result(majority_vote_result_full)
            fusion_result_full = run_fusion_experiment(
                image_cases,
                text_result=text_result,
                image_result=image_result_full,
                output_dir=output_dir,
            )
            fusion_result = compact_experiment_result(fusion_result_full)
            learned_fusion_result_full = run_learned_fusion_experiment(
                image_cases,
                text_result=text_result,
                image_result=image_result_full,
                output_dir=output_dir,
                random_state=random_state,
            )
            learned_fusion_result = compact_experiment_result(learned_fusion_result_full)
        else:
            majority_vote_result = {
                "status": "skipped",
                "skip_reason": "image_only skipped: " + str(image_result_full.get("skip_reason", "unknown")),
            }
            fusion_result = {
                "status": "skipped",
                "skip_reason": "image_only skipped: " + str(image_result_full.get("skip_reason", "unknown")),
            }
            learned_fusion_result = {
                "status": "skipped",
                "skip_reason": "image_only skipped: " + str(image_result_full.get("skip_reason", "unknown")),
            }

    video_result = {
        "status": "skipped",
        "skip_reason": "dataset does not require a video feature view",
    }
    video_majority_vote_result = {
        "status": "skipped",
        "skip_reason": "video_feature_only skipped",
    }
    video_fusion_result = {
        "status": "skipped",
        "skip_reason": "video_feature_only skipped",
    }
    if dataset == "FakeSV":
        video_cases = build_fakesv_c3d_case_splits(split_cases, fakesv_c3d_zip)
        if video_cases.get("status") == "skipped":
            video_result = video_cases
            video_majority_vote_result = {
                "status": "skipped",
                "skip_reason": "video_feature_only skipped: " + str(video_cases.get("skip_reason", "unknown")),
            }
            video_fusion_result = {
                "status": "skipped",
                "skip_reason": "video_feature_only skipped: " + str(video_cases.get("skip_reason", "unknown")),
            }
        else:
            c3d_split_cases = video_cases["split_cases"]
            video_result_full = run_fakesv_c3d_video_experiment(
                c3d_split_cases,
                output_dir=output_dir,
                c3d_zip=fakesv_c3d_zip,
                random_state=random_state,
            )
            video_result = compact_experiment_result(video_result_full)
            if video_result_full.get("status") == "evaluated":
                video_majority_vote_result_full = run_view_majority_vote_experiment(
                    c3d_split_cases,
                    first_result=text_result,
                    second_result=video_result_full,
                    output_dir=output_dir,
                    prediction_filename="video_text_majority_vote_predictions.jsonl",
                    first_view_name="text",
                    second_view_name="video_feature",
                )
                video_majority_vote_result = compact_experiment_result(video_majority_vote_result_full)
                video_fusion_result_full = run_probability_fusion_experiment(
                    c3d_split_cases,
                    first_result=text_result,
                    second_result=video_result_full,
                    output_dir=output_dir,
                    prediction_filename="video_text_late_fusion_predictions.jsonl",
                    fusion_policy="validation_grid_search_text_video_feature_probability_average",
                    first_view_name="text",
                    second_view_name="video_feature",
                )
                video_fusion_result = compact_experiment_result(video_fusion_result_full)
            else:
                video_majority_vote_result = {
                    "status": "skipped",
                    "skip_reason": "video_feature_only skipped: " + str(video_result_full.get("skip_reason", "unknown")),
                }
                video_fusion_result = {
                    "status": "skipped",
                    "skip_reason": "video_feature_only skipped: " + str(video_result_full.get("skip_reason", "unknown")),
                }

    if dataset == "FakeSV" and video_majority_vote_result.get("status") == "evaluated":
        majority_vote_result = video_majority_vote_result
    if dataset == "FakeSV" and video_fusion_result.get("status") == "evaluated":
        fusion_result = video_fusion_result

    report["experiments"]["image_only"] = image_result
    report["experiments"]["video_feature_only"] = video_result
    report["experiments"]["majority_vote"] = majority_vote_result
    report["experiments"]["late_fusion"] = fusion_result
    report["experiments"]["learned_fusion"] = learned_fusion_result
    report["experiments"]["claim_context_only"] = claim_result
    report["experiments"]["claim_context_late_fusion"] = claim_fusion_result
    report["experiments"]["video_text_majority_vote"] = video_majority_vote_result
    report["experiments"]["video_text_late_fusion"] = video_fusion_result
    report["summary"] = summarize_dataset_experiments(report["experiments"])
    report["validation_coverage"] = build_validation_coverage(dataset, report)
    return report


def build_splits(
    dataset: str,
    cases: list[dict[str, Any]],
    random_state: int,
) -> tuple[dict[str, list[dict[str, Any]]], str]:
    if dataset == "MultiOFF":
        return (
            {
                "train": [case for case in cases if case.get("split") == "train"],
                "validation": [case for case in cases if case.get("split") == "validation"],
                "test": [case for case in cases if case.get("split") == "test"],
            },
            "official_train_validation_test",
        )

    if dataset == "HateXplain":
        return (
            {
                "train": [case for case in cases if case.get("split") == "train"],
                "validation": [case for case in cases if case.get("split") == "val"],
                "test": [case for case in cases if case.get("split") == "test"],
            },
            "official_train_val_test_unassigned_ignored",
        )

    if dataset == "FakeSV":
        return (
            {
                "train": [case for case in cases if case.get("split") == "train"],
                "validation": [case for case in cases if case.get("split") == "validation"],
                "test": [case for case in cases if case.get("split") == "test"],
            },
            "official_temporal_time3_train_validation_test",
        )

    if dataset == "PHEME":
        test_events = {"sydneysiege", "ottawashooting"}
        train_pool = [case for case in cases if case.get("split") not in test_events]
        test = [case for case in cases if case.get("split") in test_events]
        train, validation = stratified_split(train_pool, test_size=0.15, random_state=random_state)
        return (
            {"train": train, "validation": validation, "test": test},
            "event_holdout_test_sydneysiege_ottawashooting_validation_from_train_pool_15pct",
        )

    train_pool, test = stratified_split(cases, test_size=0.2, random_state=random_state)
    train, validation = stratified_split(train_pool, test_size=0.125, random_state=random_state)
    return (
        {"train": train, "validation": validation, "test": test},
        "stratified_random_70_10_20",
    )


def stratified_split(
    cases: list[dict[str, Any]],
    *,
    test_size: float,
    random_state: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    train, test = train_test_split(
        cases,
        test_size=test_size,
        random_state=random_state,
        stratify=[label_of(case) for case in cases],
    )
    return list(train), list(test)


def summarize_view_availability(cases: list[dict[str, Any]]) -> dict[str, Any]:
    image_paths = [image_path_of(case) for case in cases]
    return {
        "tweet_text_cases": sum(1 for case in cases if text_of(case)),
        "image_path_cases": sum(1 for path in image_paths if path),
        "image_path_ratio": round(sum(1 for path in image_paths if path) / len(cases), 4) if cases else 0.0,
        "video_cases": sum(1 for case in cases if ((case.get("views") or {}).get("video") or {}).get("available")),
        "claim_context_cases": sum(1 for case in cases if claim_context_text(case)),
    }


def compact_experiment_result(result: dict[str, Any]) -> dict[str, Any]:
    compact = {
        key: value
        for key, value in result.items()
        if key not in {"validation_probabilities", "test_probabilities"}
    }
    return compact


def run_claim_context_experiment(
    split_cases: dict[str, list[dict[str, Any]]],
    *,
    output_dir: Path,
    random_state: int,
) -> dict[str, Any]:
    model = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    min_df=2,
                    max_features=50000,
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",
                    solver="liblinear",
                    random_state=random_state,
                ),
            ),
        ]
    )
    train = split_cases["train"]
    validation = split_cases["validation"]
    test = split_cases["test"]
    model.fit([claim_context_text(case) for case in train], [label_of(case) for case in train])
    val_proba = positive_probabilities(model, [claim_context_text(case) for case in validation])
    test_proba = positive_probabilities(model, [claim_context_text(case) for case in test])
    val_pred = labels_from_probabilities(val_proba)
    test_pred = labels_from_probabilities(test_proba)
    prediction_path = output_dir / "claim_context_only_predictions.jsonl"
    write_probability_predictions(prediction_path, test, test_proba, test_pred)
    return {
        "status": "evaluated",
        "view": "claim_context",
        "capability_boundary": "dataset_annotation_claim_evidence_metadata_baseline_not_external_rag",
        "train_count": len(train),
        "validation_count": len(validation),
        "test_count": len(test),
        "validation_metrics": compute_metrics([label_of(case) for case in validation], val_pred),
        "test_metrics": compute_metrics([label_of(case) for case in test], test_pred),
        "validation_probabilities": {
            case["case_id"]: float(prob)
            for case, prob in zip(validation, val_proba)
        },
        "test_probabilities": {
            case["case_id"]: float(prob)
            for case, prob in zip(test, test_proba)
        },
        "prediction_path": str(prediction_path),
    }


def run_probability_fusion_experiment(
    split_cases: dict[str, list[dict[str, Any]]],
    *,
    first_result: dict[str, Any],
    second_result: dict[str, Any],
    output_dir: Path,
    prediction_filename: str,
    fusion_policy: str,
    first_view_name: str,
    second_view_name: str,
) -> dict[str, Any]:
    validation = split_cases["validation"]
    test = split_cases["test"]
    first_val = first_result["validation_probabilities"]
    second_val = second_result["validation_probabilities"]
    first_test = first_result["test_probabilities"]
    second_test = second_result["test_probabilities"]
    weights = np.linspace(0.0, 1.0, 21)
    candidates = []
    y_val = [label_of(case) for case in validation]
    for first_weight in weights:
        probs = np.array(
            [
                first_weight * first_val[case["case_id"]]
                + (1.0 - first_weight) * second_val[case["case_id"]]
                for case in validation
            ]
        )
        pred = labels_from_probabilities(probs)
        metrics = compute_metrics(y_val, pred)
        candidates.append(
            {
                f"{first_view_name}_weight": round(float(first_weight), 2),
                f"{second_view_name}_weight": round(float(1.0 - first_weight), 2),
                "macro_f1": metrics["macro_f1"],
                "accuracy": metrics["accuracy"],
            }
        )
    best = sorted(candidates, key=lambda row: (row["macro_f1"], row["accuracy"]), reverse=True)[0]
    first_weight = best[f"{first_view_name}_weight"]
    second_weight = best[f"{second_view_name}_weight"]
    test_probs = np.array(
        [
            first_weight * first_test[case["case_id"]]
            + second_weight * second_test[case["case_id"]]
            for case in test
        ]
    )
    test_pred = labels_from_probabilities(test_probs)
    prediction_path = output_dir / prediction_filename
    write_probability_predictions(prediction_path, test, test_probs, test_pred)
    return {
        "status": "evaluated",
        "fusion_policy": fusion_policy,
        "selected_weights": {
            first_view_name: first_weight,
            second_view_name: second_weight,
        },
        "validation_candidates": candidates,
        "test_metrics": compute_metrics([label_of(case) for case in test], test_pred),
        "prediction_path": str(prediction_path),
    }


def build_fakesv_c3d_case_splits(
    split_cases: dict[str, list[dict[str, Any]]],
    c3d_zip: Path,
) -> dict[str, Any]:
    if not c3d_zip.exists():
        return {
            "status": "skipped",
            "skip_reason": "FakeSV C3D feature zip missing",
            "feature_zip": str(c3d_zip),
        }
    try:
        feature_ids = fakesv_c3d_feature_ids(c3d_zip)
    except Exception as exc:
        return {
            "status": "skipped",
            "skip_reason": f"FakeSV C3D feature zip unreadable: {type(exc).__name__}: {str(exc)[:240]}",
            "feature_zip": str(c3d_zip),
        }

    filtered = {
        split: [
            case
            for case in rows
            if video_id_of(case) in feature_ids
        ]
        for split, rows in split_cases.items()
    }
    missing_counts = {
        split: len(split_cases[split]) - len(filtered[split])
        for split in split_cases
    }
    if any(not rows for rows in filtered.values()):
        return {
            "status": "skipped",
            "skip_reason": "one or more FakeSV splits have no matching C3D feature rows",
            "feature_zip": str(c3d_zip),
            "feature_file_count": len(feature_ids),
            "split_counts_with_c3d": {split: len(rows) for split, rows in filtered.items()},
            "missing_feature_counts": missing_counts,
        }
    if any(len({label_of(case) for case in rows}) < 2 for rows in filtered.values()):
        return {
            "status": "skipped",
            "skip_reason": "C3D feature subset lost a class in one or more splits",
            "feature_zip": str(c3d_zip),
            "feature_file_count": len(feature_ids),
            "split_counts_with_c3d": {split: len(rows) for split, rows in filtered.items()},
            "missing_feature_counts": missing_counts,
        }
    return {
        "status": "prepared",
        "feature_zip": str(c3d_zip),
        "feature_file_count": len(feature_ids),
        "split_cases": filtered,
        "split_counts_with_c3d": {split: len(rows) for split, rows in filtered.items()},
        "missing_feature_counts": missing_counts,
    }


def run_fakesv_c3d_video_experiment(
    split_cases: dict[str, list[dict[str, Any]]],
    *,
    output_dir: Path,
    c3d_zip: Path,
    random_state: int,
) -> dict[str, Any]:
    try:
        embeddings = load_fakesv_c3d_embeddings(
            [case for rows in split_cases.values() for case in rows],
            output_dir=output_dir,
            c3d_zip=c3d_zip,
        )
    except Exception as exc:  # pragma: no cover - environment/data dependent
        return {
            "status": "skipped",
            "skip_reason": f"FakeSV C3D feature loading failed: {type(exc).__name__}: {str(exc)[:240]}",
            "feature_zip": str(c3d_zip),
        }

    train = split_cases["train"]
    validation = split_cases["validation"]
    test = split_cases["test"]
    model = Pipeline(
        [
            ("scale", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",
                    solver="liblinear",
                    random_state=random_state,
                ),
            ),
        ]
    )
    model.fit(stack_embeddings(train, embeddings), [label_of(case) for case in train])
    val_proba = positive_probabilities(model, stack_embeddings(validation, embeddings))
    test_proba = positive_probabilities(model, stack_embeddings(test, embeddings))
    val_pred = labels_from_probabilities(val_proba)
    test_pred = labels_from_probabilities(test_proba)
    prediction_path = output_dir / "video_feature_only_predictions.jsonl"
    write_probability_predictions(prediction_path, test, test_proba, test_pred)
    return {
        "status": "evaluated",
        "view": "video_feature",
        "capability_boundary": "FakeSV public pre-extracted C3D frame features with temporal mean pooling; not raw-video end-to-end encoding",
        "feature_zip": str(c3d_zip),
        "feature_extractor": "C3D pre-extracted features from FakeSV public HuggingFace artifact",
        "pooling": "temporal_mean_then_l2_normalization",
        "embedding_dim": int(next(iter(embeddings.values())).shape[0]) if embeddings else 0,
        "train_count": len(train),
        "validation_count": len(validation),
        "test_count": len(test),
        "validation_metrics": compute_metrics([label_of(case) for case in validation], val_pred),
        "test_metrics": compute_metrics([label_of(case) for case in test], test_pred),
        "validation_probabilities": {
            case["case_id"]: float(prob)
            for case, prob in zip(validation, val_proba)
        },
        "test_probabilities": {
            case["case_id"]: float(prob)
            for case, prob in zip(test, test_proba)
        },
        "prediction_path": str(prediction_path),
    }


def run_view_majority_vote_experiment(
    split_cases: dict[str, list[dict[str, Any]]],
    *,
    first_result: dict[str, Any],
    second_result: dict[str, Any],
    output_dir: Path,
    prediction_filename: str,
    first_view_name: str,
    second_view_name: str,
) -> dict[str, Any]:
    test = split_cases["test"]
    first_test = first_result["test_probabilities"]
    second_test = second_result["test_probabilities"]
    predictions = []
    probabilities = []
    covered_cases = []
    covered_predictions = []
    abstained = []
    for case in test:
        first_label = POSITIVE_LABEL if first_test[case["case_id"]] >= 0.5 else "non_harmful"
        second_label = POSITIVE_LABEL if second_test[case["case_id"]] >= 0.5 else "non_harmful"
        if first_label == second_label:
            prediction = first_label
            probability = 1.0 if prediction == POSITIVE_LABEL else 0.0
            covered_cases.append(case)
            covered_predictions.append(prediction)
        else:
            prediction = "uncertain"
            probability = 0.5
            abstained.append(case)
        predictions.append(prediction)
        probabilities.append(probability)

    prediction_path = output_dir / prediction_filename
    write_probability_predictions(prediction_path, test, np.asarray(probabilities), predictions)
    covered_metrics = (
        compute_metrics([label_of(case) for case in covered_cases], covered_predictions)
        if covered_cases
        else None
    )
    return {
        "status": "evaluated",
        "fusion_policy": f"selective_majority_vote_over_{first_view_name}_{second_view_name}_labels",
        "decision_rule": "emit label only when both view labels agree; otherwise abstain as uncertain",
        "test_count": len(test),
        "covered_count": len(covered_cases),
        "abstained_count": len(abstained),
        "coverage": round(len(covered_cases) / len(test), 6) if test else 0.0,
        "covered_test_metrics": covered_metrics,
        "abstained_case_ids": [case["case_id"] for case in abstained[:50]],
        "prediction_path": str(prediction_path),
    }


def load_fakesv_c3d_embeddings(
    cases: list[dict[str, Any]],
    *,
    output_dir: Path,
    c3d_zip: Path,
) -> dict[str, np.ndarray]:
    cache_path = output_dir / f"fakesv_c3d_mean_embeddings_{hash_fakesv_c3d_cases(cases, c3d_zip)}.npz"
    if cache_path.exists():
        loaded = np.load(cache_path)
        case_ids = [str(value) for value in loaded["case_ids"]]
        matrix = loaded["features"].astype("float32")
        return {case_id: matrix[index] for index, case_id in enumerate(case_ids)}

    case_ids = []
    feature_rows = []
    with zipfile.ZipFile(c3d_zip) as archive:
        for case in cases:
            video_id = video_id_of(case)
            member = f"c3d/{video_id}.hdf5"
            data = archive.read(member)
            feature_rows.append(read_fakesv_c3d_vector(data, video_id))
            case_ids.append(case["case_id"])
    matrix = np.stack(feature_rows).astype("float32")
    np.savez_compressed(
        cache_path,
        case_ids=np.asarray(case_ids, dtype=str),
        features=matrix,
    )
    return {case_id: matrix[index] for index, case_id in enumerate(case_ids)}


def read_fakesv_c3d_vector(data: bytes, video_id: str) -> np.ndarray:
    import h5py

    with h5py.File(io.BytesIO(data), "r") as handle:
        group_key = video_id if video_id in handle else next(iter(handle.keys()))
        group = handle[group_key]
        features = np.asarray(group["c3d_features"][:], dtype="float32")
    vector = features if features.ndim == 1 else np.nanmean(features, axis=0)
    vector = np.nan_to_num(vector, copy=False)
    norm = float(np.linalg.norm(vector))
    if norm > 0:
        vector = vector / norm
    return vector.astype("float32")


def fakesv_c3d_feature_ids(c3d_zip: Path) -> set[str]:
    with zipfile.ZipFile(c3d_zip) as archive:
        return {
            Path(name).stem
            for name in archive.namelist()
            if name.startswith("c3d/") and name.endswith(".hdf5")
        }


def hash_fakesv_c3d_cases(cases: list[dict[str, Any]], c3d_zip: Path) -> str:
    digest = hashlib.sha256()
    stat = c3d_zip.stat()
    digest.update(str(c3d_zip).encode("utf-8"))
    digest.update(str(stat.st_size).encode("utf-8"))
    digest.update(str(int(stat.st_mtime)).encode("utf-8"))
    for case in cases:
        digest.update(str(case.get("case_id", "")).encode("utf-8"))
        digest.update(video_id_of(case).encode("utf-8"))
    return digest.hexdigest()[:16]


def claim_context_text(case: dict[str, Any]) -> str:
    context = case.get("claim_context") or {}
    parts = [
        str(context.get("claim_text", "")).strip(),
        str(context.get("evidence_text", "")).strip(),
    ]
    for link in context.get("evidence_links") or []:
        if not isinstance(link, dict):
            continue
        url = str(link.get("link", "")).strip()
        host = urlparse(url).netloc
        parts.extend(
            [
                str(link.get("position", "")).strip(),
                str(link.get("mediatype", "")).strip(),
                host,
            ]
        )
    return " ".join(part for part in parts if part).strip()


def summarize_dataset_experiments(experiments: dict[str, dict[str, Any]]) -> dict[str, Any]:
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
        macro_f1 = ((result.get("test_metrics") or {}).get("macro_f1"))
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


def build_validation_coverage(dataset: str, report: dict[str, Any]) -> dict[str, Any]:
    experiments = report.get("experiments") or {}
    expected_views = EXPECTED_DATASET_VIEWS.get(dataset, ["tweet"])
    expected = set(expected_views)
    text_evaluated = experiment_evaluated(experiments, "text_only")
    image_evaluated = experiment_evaluated(experiments, "image_only")
    video_evaluated = experiment_evaluated(experiments, "video_feature_only")
    majority_evaluated = experiment_evaluated(experiments, "majority_vote")
    weighted_evaluated = (
        experiment_evaluated(experiments, "late_fusion")
        or experiment_evaluated(experiments, "claim_context_late_fusion")
        or experiment_evaluated(experiments, "video_text_late_fusion")
    )
    learned_evaluated = experiment_evaluated(experiments, "learned_fusion")
    claim_evaluated = experiment_evaluated(experiments, "claim_context_only")
    evidence_evaluated = False
    image_required = bool(expected & {"img", "meme"})
    video_required = "video" in expected
    claim_required = "claim" in expected
    evidence_required = "evidence" in expected
    fusion_required = len(expected & {"tweet", "img", "meme", "video", "claim"}) > 1

    missing = []
    if "tweet" in expected and not text_evaluated:
        missing.append("tweet_text_view_not_evaluated")
    if image_required and not image_evaluated:
        missing.append("image_or_meme_view_not_evaluated")
    if video_required and not video_evaluated:
        missing.append("true_video_view_not_evaluated")
    if claim_required and not claim_evaluated:
        missing.append("claim_view_not_evaluated")
    if evidence_required and not evidence_evaluated:
        missing.append("evidence_view_not_evaluated")
    if fusion_required and not (majority_evaluated or weighted_evaluated or learned_evaluated):
        missing.append("cross_view_fusion_not_evaluated")

    return {
        "expected_views": expected_views,
        "tweet_text_view_evaluated": text_evaluated,
        "image_or_meme_view_required": image_required,
        "image_or_meme_view_evaluated": image_evaluated,
        "video_view_required": video_required,
        "true_video_view_evaluated": video_evaluated,
        "video_metadata_proxy_only": dataset == "FakeSV" and text_evaluated and not video_evaluated,
        "preextracted_video_feature_baseline": dataset == "FakeSV" and video_evaluated,
        "claim_evidence_view_required": claim_required,
        "claim_evidence_view_evaluated": claim_evaluated,
        "claim_view_required": claim_required,
        "claim_view_evaluated": claim_evaluated,
        "evidence_view_required": evidence_required,
        "evidence_view_evaluated": evidence_evaluated,
        "claim_context_metadata_baseline": claim_evaluated,
        "majority_vote_evaluated": majority_evaluated,
        "weighted_fusion_evaluated": weighted_evaluated,
        "learned_fusion_evaluated": learned_evaluated,
        "fusion_required": fusion_required,
        "full_expected_view_coverage": not missing,
        "missing_requirements": missing,
        "note": (
            "Coverage describes what this suite actually validated. It intentionally "
            "does not count URL-only media, video IDs, or claim text proxies as true "
            "image/video/claim-evidence validation. FakeSV C3D counts as a pre-extracted "
            "video feature baseline, not raw-video end-to-end encoding."
        ),
    }


def experiment_evaluated(experiments: dict[str, dict[str, Any]], name: str) -> bool:
    return (experiments.get(name) or {}).get("status") == "evaluated"


def summarize_suite(datasets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    evaluated_datasets = {
        name: result
        for name, result in datasets.items()
        if (result.get("summary") or {}).get("status") == "evaluated"
    }
    skipped_datasets = {
        name: (result.get("summary") or {}).get("skip_reason", "")
        for name, result in datasets.items()
        if (result.get("summary") or {}).get("status") == "skipped"
    }
    best_rows = []
    for dataset, result in evaluated_datasets.items():
        best = (result.get("summary") or {}).get("best_test_macro_f1")
        if best:
            best_rows.append({"dataset": dataset, **best})
    coverage_matrix = {
        dataset: result.get("validation_coverage") or {}
        for dataset, result in datasets.items()
    }
    return {
        "dataset_count": len(datasets),
        "evaluated_datasets": sorted(evaluated_datasets),
        "skipped_datasets": skipped_datasets,
        "best_by_dataset": best_rows,
        "coverage_matrix": coverage_matrix,
        "full_view_covered_datasets": sorted(
            dataset
            for dataset, coverage in coverage_matrix.items()
            if coverage.get("full_expected_view_coverage")
        ),
        "view_coverage_blockers": {
            dataset: coverage.get("missing_requirements", [])
            for dataset, coverage in coverage_matrix.items()
            if coverage and not coverage.get("full_expected_view_coverage")
        },
        "note": (
            "This suite evaluates currently available local review-post-case views. "
            "Datasets without aligned image media are text-only at this stage. FakeSV uses "
            "public video IDs/keywords as a short-video metadata/text proxy for the text lane, "
            "and can additionally evaluate public pre-extracted C3D video features when the "
            "local feature zip is available."
        ),
    }


def video_id_of(case: dict[str, Any]) -> str:
    video_view = (case.get("views") or {}).get("video") or {}
    return str(video_view.get("video_id") or case.get("source_id") or "").strip()


if __name__ == "__main__":
    raise SystemExit(main())
