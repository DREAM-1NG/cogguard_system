"""Run MultiOFF text/image/fusion ablations for KT3 post-level MV-PostGuard.

This script is the first executable multimodal validation lane for the
tweet/meme/img part of MV-PostGuard. It follows the literature pattern used by
MultiOFF and Hateful Memes: evaluate unimodal text, unimodal image, and late
fusion rather than claiming that concatenated metadata is a multimodal model.

The image lane uses a frozen CLIP image encoder when available. If CLIP weights
cannot be loaded, image and fusion experiments are reported as skipped instead
of falling back to shallow image metadata.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageFile
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support
from sklearn.pipeline import Pipeline

ImageFile.LOAD_TRUNCATED_IMAGES = True

LABELS = ["harmful", "non_harmful"]
POSITIVE_LABEL = "harmful"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-dir", default=r"G:\CISCN\.tmp\kt3_post_cases_full")
    parser.add_argument("--output-dir", default=r"G:\CISCN\.tmp\kt3_multioff_multiview_ablation")
    parser.add_argument("--dataset", default="MultiOFF")
    parser.add_argument("--clip-model", default="openai/clip-vit-base-patch32")
    parser.add_argument("--hf-cache-dir", default=r"G:\CISCN\.cache\huggingface")
    parser.add_argument(
        "--hf-endpoint",
        default="",
        help="Optional HuggingFace endpoint override, e.g. https://huggingface.co.",
    )
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--max-cases", type=int, default=0, help="Optional smoke-test limit; 0 means full dataset.")
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    os.environ.setdefault("HF_HOME", args.hf_cache_dir)
    os.environ.setdefault("TRANSFORMERS_CACHE", args.hf_cache_dir)
    if args.hf_endpoint:
        os.environ["HF_ENDPOINT"] = args.hf_endpoint

    case_path = Path(args.case_dir) / f"{safe_name(args.dataset)}.jsonl"
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cases = load_cases(case_path)
    if args.max_cases > 0:
        cases = cases[: args.max_cases]
    report = evaluate_multioff(
        cases,
        output_dir=output_dir,
        dataset=args.dataset,
        clip_model_name=args.clip_model,
        hf_cache_dir=Path(args.hf_cache_dir),
        hf_endpoint=os.environ.get("HF_ENDPOINT", ""),
        batch_size=args.batch_size,
        random_state=args.random_state,
    )
    report_path = output_dir / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"wrote {report_path}")
    return 0


def evaluate_multioff(
    cases: list[dict[str, Any]],
    *,
    output_dir: Path,
    dataset: str,
    clip_model_name: str,
    hf_cache_dir: Path,
    hf_endpoint: str,
    batch_size: int,
    random_state: int,
) -> dict[str, Any]:
    usable = [
        case
        for case in cases
        if text_of(case)
        and label_of(case) in set(LABELS)
        and case.get("split") in {"train", "validation", "test"}
    ]
    split_cases = {
        split: [case for case in usable if case.get("split") == split]
        for split in ("train", "validation", "test")
    }
    report: dict[str, Any] = {
        "schema": "kt3-multioff-multiview-ablation-report-v1",
        "dataset": dataset,
        "case_count": len(cases),
        "usable_case_count": len(usable),
        "split_counts": {split: len(rows) for split, rows in split_cases.items()},
        "label_distribution": dict(Counter(label_of(case) for case in usable)),
        "method": {
            "text_view": "TF-IDF char n-gram + Logistic Regression",
            "image_view": "Frozen CLIP image encoder + Logistic Regression",
        "fusion": "Validation-tuned late fusion and learned Logistic Regression fusion over text/image harmful probabilities",
            "split_policy": "official train -> validation tune -> test",
            "hf_endpoint": hf_endpoint,
        },
        "literature_alignment": [
            {
                "paper": "MultiOFF, TRAC 2020",
                "transfer": "Report text-only, image-only, and fusion ablations on offensive meme detection.",
            },
            {
                "paper": "Hateful Memes, NeurIPS 2020",
                "transfer": "Keep unimodal and multimodal results separate to expose shortcut reliance.",
            },
            {
                "paper": "CLIP, ICML 2021",
                "transfer": "Use frozen vision-language representations for the image view before task-specific fine-tuning.",
            },
        ],
        "capability_boundary": {
            "dataset_scope": "MultiOFF only",
            "views_evaluated": ["tweet", "img", "meme_late_fusion"],
            "video_view": False,
            "claim_conditioned": False,
            "trained_end_to_end_multimodal_transformer": False,
            "uses_shallow_image_metadata_fallback": False,
        },
        "experiments": {},
        "summary": {},
    }

    missing_splits = [split for split, rows in split_cases.items() if not rows]
    if missing_splits:
        report["summary"] = {
            "status": "skipped",
            "skip_reason": "missing official splits: " + ",".join(missing_splits),
        }
        return report

    text_result = run_text_experiment(split_cases, output_dir, random_state)
    report["experiments"]["text_only"] = text_result

    image_cases = {
        split: [case for case in rows if image_path_of(case)]
        for split, rows in split_cases.items()
    }
    if any(not rows for rows in image_cases.values()):
        image_result = {
            "status": "skipped",
            "skip_reason": "one or more official splits have no aligned image cases",
            "split_counts_with_images": {split: len(rows) for split, rows in image_cases.items()},
        }
        fusion_result = {
            "status": "skipped",
            "skip_reason": "image_only skipped",
        }
    else:
        image_result = run_image_experiment(
            image_cases,
            output_dir=output_dir,
            clip_model_name=clip_model_name,
            hf_cache_dir=hf_cache_dir,
            batch_size=batch_size,
            random_state=random_state,
        )
        if image_result.get("status") == "evaluated":
            majority_vote_result = run_majority_vote_experiment(
                image_cases,
                text_result=text_result,
                image_result=image_result,
                output_dir=output_dir,
            )
            fusion_result = run_fusion_experiment(
                image_cases,
                text_result=text_result,
                image_result=image_result,
                output_dir=output_dir,
            )
            learned_fusion_result = run_learned_fusion_experiment(
                image_cases,
                text_result=text_result,
                image_result=image_result,
                output_dir=output_dir,
                random_state=random_state,
            )
        else:
            majority_vote_result = {
                "status": "skipped",
                "skip_reason": "image_only skipped: " + str(image_result.get("skip_reason", "unknown")),
            }
            fusion_result = {
                "status": "skipped",
                "skip_reason": "image_only skipped: " + str(image_result.get("skip_reason", "unknown")),
            }
            learned_fusion_result = {
                "status": "skipped",
                "skip_reason": "image_only skipped: " + str(image_result.get("skip_reason", "unknown")),
            }
    report["experiments"]["image_only"] = image_result
    report["experiments"]["majority_vote"] = majority_vote_result
    report["experiments"]["late_fusion"] = fusion_result
    report["experiments"]["learned_fusion"] = learned_fusion_result
    report["summary"] = summarize(report["experiments"])
    return report


def run_text_experiment(
    split_cases: dict[str, list[dict[str, Any]]],
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
    model.fit([text_of(case) for case in train], [label_of(case) for case in train])
    val_proba = positive_probabilities(model, [text_of(case) for case in validation])
    test_proba = positive_probabilities(model, [text_of(case) for case in test])
    val_pred = labels_from_probabilities(val_proba)
    test_pred = labels_from_probabilities(test_proba)
    prediction_path = output_dir / "text_only_predictions.jsonl"
    write_probability_predictions(prediction_path, test, test_proba, test_pred)
    return {
        "status": "evaluated",
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


def run_image_experiment(
    split_cases: dict[str, list[dict[str, Any]]],
    *,
    output_dir: Path,
    clip_model_name: str,
    hf_cache_dir: Path,
    batch_size: int,
    random_state: int,
) -> dict[str, Any]:
    try:
        embeddings = encode_clip_images(
            [case for rows in split_cases.values() for case in rows],
            output_dir=output_dir,
            clip_model_name=clip_model_name,
            hf_cache_dir=hf_cache_dir,
            batch_size=batch_size,
        )
    except Exception as exc:  # pragma: no cover - environment dependent
        return {
            "status": "skipped",
            "skip_reason": f"CLIP image encoder unavailable: {type(exc).__name__}: {str(exc)[:240]}",
            "clip_model": clip_model_name,
        }

    train = split_cases["train"]
    validation = split_cases["validation"]
    test = split_cases["test"]
    model = LogisticRegression(
        max_iter=1000,
        class_weight="balanced",
        solver="liblinear",
        random_state=random_state,
    )
    model.fit(stack_embeddings(train, embeddings), [label_of(case) for case in train])
    val_proba = positive_probabilities(model, stack_embeddings(validation, embeddings))
    test_proba = positive_probabilities(model, stack_embeddings(test, embeddings))
    val_pred = labels_from_probabilities(val_proba)
    test_pred = labels_from_probabilities(test_proba)
    prediction_path = output_dir / "image_only_predictions.jsonl"
    write_probability_predictions(prediction_path, test, test_proba, test_pred)
    return {
        "status": "evaluated",
        "clip_model": clip_model_name,
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


def run_fusion_experiment(
    split_cases: dict[str, list[dict[str, Any]]],
    *,
    text_result: dict[str, Any],
    image_result: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    validation = split_cases["validation"]
    test = split_cases["test"]
    text_val = text_result["validation_probabilities"]
    image_val = image_result["validation_probabilities"]
    text_test = text_result["test_probabilities"]
    image_test = image_result["test_probabilities"]
    weights = np.linspace(0.0, 1.0, 21)
    candidates = []
    y_val = [label_of(case) for case in validation]
    for text_weight in weights:
        probs = np.array(
            [
                text_weight * text_val[case["case_id"]]
                + (1.0 - text_weight) * image_val[case["case_id"]]
                for case in validation
            ]
        )
        pred = labels_from_probabilities(probs)
        metrics = compute_metrics(y_val, pred)
        candidates.append(
            {
                "text_weight": round(float(text_weight), 2),
                "image_weight": round(float(1.0 - text_weight), 2),
                "macro_f1": metrics["macro_f1"],
                "accuracy": metrics["accuracy"],
            }
        )
    best = sorted(candidates, key=lambda row: (row["macro_f1"], row["accuracy"]), reverse=True)[0]
    test_probs = np.array(
        [
            best["text_weight"] * text_test[case["case_id"]]
            + best["image_weight"] * image_test[case["case_id"]]
            for case in test
        ]
    )
    test_pred = labels_from_probabilities(test_probs)
    prediction_path = output_dir / "late_fusion_predictions.jsonl"
    write_probability_predictions(prediction_path, test, test_probs, test_pred)
    return {
        "status": "evaluated",
        "fusion_policy": "validation_grid_search_weighted_probability_average",
        "selected_weights": {
            "text": best["text_weight"],
            "image": best["image_weight"],
        },
        "validation_candidates": candidates,
        "test_metrics": compute_metrics([label_of(case) for case in test], test_pred),
        "prediction_path": str(prediction_path),
    }


def run_majority_vote_experiment(
    split_cases: dict[str, list[dict[str, Any]]],
    *,
    text_result: dict[str, Any],
    image_result: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    test = split_cases["test"]
    text_test = text_result["test_probabilities"]
    image_test = image_result["test_probabilities"]
    predictions = []
    probabilities = []
    covered_cases = []
    covered_predictions = []
    abstained = []
    for case in test:
        text_label = POSITIVE_LABEL if text_test[case["case_id"]] >= 0.5 else "non_harmful"
        image_label = POSITIVE_LABEL if image_test[case["case_id"]] >= 0.5 else "non_harmful"
        if text_label == image_label:
            prediction = text_label
            probability = 1.0 if prediction == POSITIVE_LABEL else 0.0
            covered_cases.append(case)
            covered_predictions.append(prediction)
        else:
            prediction = "uncertain"
            probability = 0.5
            abstained.append(case)
        predictions.append(prediction)
        probabilities.append(probability)

    prediction_path = output_dir / "majority_vote_predictions.jsonl"
    write_probability_predictions(prediction_path, test, np.asarray(probabilities), predictions)
    covered_metrics = (
        compute_metrics([label_of(case) for case in covered_cases], covered_predictions)
        if covered_cases
        else None
    )
    return {
        "status": "evaluated",
        "fusion_policy": "selective_majority_vote_over_text_image_labels",
        "decision_rule": "emit label only when text and image view labels agree; otherwise abstain as uncertain",
        "test_count": len(test),
        "covered_count": len(covered_cases),
        "abstained_count": len(abstained),
        "coverage": round(len(covered_cases) / len(test), 6) if test else 0.0,
        "covered_test_metrics": covered_metrics,
        "abstained_case_ids": [case["case_id"] for case in abstained[:50]],
        "prediction_path": str(prediction_path),
    }


def run_learned_fusion_experiment(
    split_cases: dict[str, list[dict[str, Any]]],
    *,
    text_result: dict[str, Any],
    image_result: dict[str, Any],
    output_dir: Path,
    random_state: int,
) -> dict[str, Any]:
    """Train a small calibration head over view probabilities.

    This is intentionally lightweight: the view detectors stay unchanged, and the
    learned layer only sees calibrated text/image harmful probabilities plus
    simple agreement features. It moves the runner beyond fixed grid weights
    without pretending to be an end-to-end multimodal transformer.
    """
    validation = split_cases["validation"]
    test = split_cases["test"]
    text_val = text_result["validation_probabilities"]
    image_val = image_result["validation_probabilities"]
    text_test = text_result["test_probabilities"]
    image_test = image_result["test_probabilities"]

    model = LogisticRegression(
        max_iter=1000,
        class_weight="balanced",
        solver="liblinear",
        random_state=random_state,
    )
    model.fit(
        fusion_features(validation, text_val, image_val),
        [label_of(case) for case in validation],
    )
    val_proba = positive_probabilities(model, fusion_features(validation, text_val, image_val))
    test_proba = positive_probabilities(model, fusion_features(test, text_test, image_test))
    val_pred = labels_from_probabilities(val_proba)
    test_pred = labels_from_probabilities(test_proba)
    prediction_path = output_dir / "learned_fusion_predictions.jsonl"
    write_probability_predictions(prediction_path, test, test_proba, test_pred)
    return {
        "status": "evaluated",
        "fusion_policy": "logistic_regression_over_view_probabilities",
        "calibration_split": "validation",
        "feature_names": ["text_prob", "image_prob", "prob_mean", "prob_abs_diff", "prob_product"],
        "calibration_count": len(validation),
        "calibration_metrics": compute_metrics([label_of(case) for case in validation], val_pred),
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


def encode_clip_images(
    cases: list[dict[str, Any]],
    *,
    output_dir: Path,
    clip_model_name: str,
    hf_cache_dir: Path,
    batch_size: int,
) -> dict[str, np.ndarray]:
    from transformers import CLIPModel, CLIPProcessor
    import torch

    cache_path = output_dir / f"clip_image_embeddings_{hash_cases(cases, clip_model_name)}.npz"
    if cache_path.exists():
        loaded = np.load(cache_path)
        return {key: loaded[key] for key in loaded.files}

    processor = CLIPProcessor.from_pretrained(clip_model_name, cache_dir=str(hf_cache_dir))
    model = CLIPModel.from_pretrained(
        clip_model_name,
        cache_dir=str(hf_cache_dir),
        use_safetensors=True,
    )
    model.eval()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)

    embeddings: dict[str, np.ndarray] = {}
    for start in range(0, len(cases), batch_size):
        batch_cases = cases[start : start + batch_size]
        images = [load_image(image_path_of(case)) for case in batch_cases]
        inputs = processor(images=images, return_tensors="pt")
        inputs = {key: value.to(device) for key, value in inputs.items()}
        with torch.no_grad():
            features = model.get_image_features(**inputs)
            features = features / features.norm(dim=-1, keepdim=True)
        array = features.detach().cpu().numpy().astype("float32")
        for case, vector in zip(batch_cases, array):
            embeddings[case["case_id"]] = vector
    np.savez_compressed(cache_path, **embeddings)
    return embeddings


def stack_embeddings(cases: list[dict[str, Any]], embeddings: dict[str, np.ndarray]) -> np.ndarray:
    return np.stack([embeddings[case["case_id"]] for case in cases])


def fusion_features(
    cases: list[dict[str, Any]],
    text_probabilities: dict[str, float],
    image_probabilities: dict[str, float],
) -> np.ndarray:
    rows = []
    for case in cases:
        case_id = case["case_id"]
        text_prob = float(text_probabilities[case_id])
        image_prob = float(image_probabilities[case_id])
        rows.append(
            [
                text_prob,
                image_prob,
                (text_prob + image_prob) / 2.0,
                abs(text_prob - image_prob),
                text_prob * image_prob,
            ]
        )
    return np.asarray(rows, dtype=float)


def positive_probabilities(model: Any, x_values: Any) -> np.ndarray:
    classes = list(model.classes_)
    positive_index = classes.index(POSITIVE_LABEL)
    return model.predict_proba(x_values)[:, positive_index]


def labels_from_probabilities(probabilities: np.ndarray) -> list[str]:
    return [POSITIVE_LABEL if float(prob) >= 0.5 else "non_harmful" for prob in probabilities]


def compute_metrics(y_true: list[str], y_pred: list[str]) -> dict[str, Any]:
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true,
        y_pred,
        labels=LABELS,
        zero_division=0,
    )
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 6),
        "macro_f1": round(float(f1_score(y_true, y_pred, average="macro", zero_division=0)), 6),
        "weighted_f1": round(float(f1_score(y_true, y_pred, average="weighted", zero_division=0)), 6),
        "per_class": {
            label: {
                "precision": round(float(precision[index]), 6),
                "recall": round(float(recall[index]), 6),
                "f1": round(float(f1[index]), 6),
                "support": int(support[index]),
            }
            for index, label in enumerate(LABELS)
        },
    }


def summarize(experiments: dict[str, dict[str, Any]]) -> dict[str, Any]:
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
    best_name = None
    best_macro_f1 = None
    for name, result in evaluated.items():
        metrics = result.get("test_metrics") or {}
        macro_f1 = metrics.get("macro_f1")
        if macro_f1 is None:
            continue
        if best_macro_f1 is None or macro_f1 > best_macro_f1:
            best_name = name
            best_macro_f1 = macro_f1
    return {
        "status": "evaluated" if evaluated else "skipped",
        "evaluated": sorted(evaluated),
        "skipped": skipped,
        "best_test_macro_f1_experiment": best_name,
        "best_test_macro_f1": best_macro_f1,
        "note": (
            "This is a MultiOFF-only tweet/img/meme late-fusion ablation. It is "
            "not full MV-PostGuard validation across all KT3 datasets and views."
        ),
    }


def write_probability_predictions(
    path: Path,
    cases: list[dict[str, Any]],
    probabilities: np.ndarray,
    predictions: list[str],
) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for case, probability, prediction in zip(cases, probabilities, predictions):
            handle.write(
                json.dumps(
                    {
                        "case_id": case.get("case_id"),
                        "dataset": case.get("dataset"),
                        "split": case.get("split"),
                        "source_id": case.get("source_id"),
                        "y_true": label_of(case),
                        "y_pred": prediction,
                        "harmful_probability": round(float(probability), 6),
                        "text_excerpt": text_of(case)[:240],
                        "image_path": image_path_of(case),
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
            )


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


def load_image(path: str) -> Image.Image:
    with Image.open(path) as image:
        return image.convert("RGB")


def hash_cases(cases: list[dict[str, Any]], clip_model_name: str) -> str:
    digest = hashlib.sha256()
    digest.update(clip_model_name.encode("utf-8"))
    for case in cases:
        digest.update(str(case.get("case_id", "")).encode("utf-8"))
        digest.update(str(image_path_of(case)).encode("utf-8"))
    return digest.hexdigest()[:16]


def text_of(case: dict[str, Any]) -> str:
    return " ".join(str(case.get("text") or "").split()).strip()


def image_path_of(case: dict[str, Any]) -> str:
    path = str(((case.get("views") or {}).get("img") or {}).get("media_path") or "").strip()
    return path if path and Path(path).exists() else ""


def label_of(case: dict[str, Any]) -> str:
    return str((case.get("labels") or {}).get("harmfulness") or "unknown")


def safe_name(value: str) -> str:
    return value.replace("/", "_").replace("\\", "_").replace(" ", "_")


if __name__ == "__main__":
    raise SystemExit(main())
