"""Run a text-only baseline on review-post-case-v1 JSONL files.

This is the first executable evaluation lane for MV-PostGuard. It deliberately
uses only the normalized `text` field, so the result is a tweet/text-only
baseline and not a multimodal validation.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-dir", default=r"G:\CISCN\.tmp\review_post_cases_full")
    parser.add_argument("--output-dir", default=r"G:\CISCN\.tmp\review_post_text_baseline")
    parser.add_argument(
        "--datasets",
        nargs="*",
        default=["MultiOFF", "PHEME", "mcfend"],
        help="Datasets to evaluate. Twitter15/16 is skipped by default because local text is missing.",
    )
    parser.add_argument("--max-features", type=int, default=50000)
    parser.add_argument("--min-df", type=int, default=2)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    case_dir = Path(args.case_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "schema": "review-post-text-baseline-report-v1",
        "model": "tfidf_logistic_regression_text_only",
        "case_dir": str(case_dir),
        "output_dir": str(output_dir),
        "capability_boundary": {
            "text_only": True,
            "uses_image_encoder": False,
            "uses_video_encoder": False,
            "uses_claim_retrieval": False,
            "is_mv_postguard_full_model": False,
            "description": (
                "This baseline uses only review-post-case text and harmfulness labels. "
                "It is a sanity check for the evaluation pipeline, not the final "
                "multiview MV-PostGuard model."
            ),
        },
        "datasets": {},
        "summary": {},
    }

    for dataset in args.datasets:
        path = case_dir / f"{safe_name(dataset)}.jsonl"
        cases = load_cases(path)
        report["datasets"][dataset] = evaluate_dataset(
            dataset,
            cases,
            output_dir,
            max_features=args.max_features,
            min_df=args.min_df,
            random_state=args.random_state,
        )

    report["summary"] = summarize(report["datasets"])
    report_path = output_dir / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"wrote {report_path}")
    return 0


def evaluate_dataset(
    dataset: str,
    cases: list[dict[str, Any]],
    output_dir: Path,
    *,
    max_features: int,
    min_df: int,
    random_state: int,
) -> dict[str, Any]:
    usable = [
        case
        for case in cases
        if case.get("text", "").strip()
        and case.get("labels", {}).get("harmfulness") in {"harmful", "non_harmful"}
    ]
    result: dict[str, Any] = {
        "dataset": dataset,
        "case_count": len(cases),
        "usable_text_cases": len(usable),
        "status": "unknown",
        "split_policy": "",
        "label_distribution": dict(Counter(label_of(case) for case in usable)),
    }
    if len(usable) < 20 or len(set(label_of(case) for case in usable)) < 2:
        result.update(
            {
                "status": "skipped",
                "skip_reason": "not enough text-labelled cases or only one class",
            }
        )
        return result

    train_cases, test_cases, split_policy = split_cases(dataset, usable, random_state)
    if len(set(label_of(case) for case in train_cases)) < 2 or len(set(label_of(case) for case in test_cases)) < 2:
        result.update(
            {
                "status": "skipped",
                "split_policy": split_policy,
                "skip_reason": "train/test split lost a class",
            }
        )
        return result

    model = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    min_df=min_df,
                    max_features=max_features,
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
    x_train = [case["text"] for case in train_cases]
    y_train = [label_of(case) for case in train_cases]
    x_test = [case["text"] for case in test_cases]
    y_test = [label_of(case) for case in test_cases]

    model.fit(x_train, y_train)
    y_pred = model.predict(x_test)
    metrics = compute_metrics(y_test, y_pred)
    prediction_path = output_dir / f"{safe_name(dataset)}_predictions.jsonl"
    write_predictions(prediction_path, test_cases, y_test, list(y_pred))

    result.update(
        {
            "status": "evaluated",
            "split_policy": split_policy,
            "train_count": len(train_cases),
            "test_count": len(test_cases),
            "train_label_distribution": dict(Counter(y_train)),
            "test_label_distribution": dict(Counter(y_test)),
            "metrics": metrics,
            "prediction_path": str(prediction_path),
        }
    )
    return result


def split_cases(
    dataset: str,
    cases: list[dict[str, Any]],
    random_state: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    if dataset == "MultiOFF":
        train_cases = [case for case in cases if case.get("split") in {"train", "validation"}]
        test_cases = [case for case in cases if case.get("split") == "test"]
        return train_cases, test_cases, "official_train_validation_to_test"

    if dataset == "PHEME":
        test_events = {"sydneysiege", "ottawashooting"}
        train_cases = [case for case in cases if case.get("split") not in test_events]
        test_cases = [case for case in cases if case.get("split") in test_events]
        return train_cases, test_cases, "event_holdout_sydneysiege_ottawashooting"

    labels = [label_of(case) for case in cases]
    train, test = train_test_split(
        cases,
        test_size=0.2,
        random_state=random_state,
        stratify=labels,
    )
    return list(train), list(test), "stratified_random_80_20"


def compute_metrics(y_true: list[str], y_pred: list[str]) -> dict[str, Any]:
    labels = ["harmful", "non_harmful"]
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true,
        y_pred,
        labels=labels,
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
            for index, label in enumerate(labels)
        },
    }


def write_predictions(
    path: Path,
    cases: list[dict[str, Any]],
    y_true: list[str],
    y_pred: list[str],
) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for case, truth, pred in zip(cases, y_true, y_pred):
            handle.write(
                json.dumps(
                    {
                        "case_id": case.get("case_id"),
                        "dataset": case.get("dataset"),
                        "split": case.get("split"),
                        "source_id": case.get("source_id"),
                        "y_true": truth,
                        "y_pred": pred,
                        "text_excerpt": case.get("text", "")[:240],
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
            if not line:
                continue
            cases.append(json.loads(line))
    return cases


def label_of(case: dict[str, Any]) -> str:
    return str(case.get("labels", {}).get("harmfulness", "unknown"))


def summarize(datasets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    evaluated = {name: item for name, item in datasets.items() if item.get("status") == "evaluated"}
    skipped = {name: item for name, item in datasets.items() if item.get("status") == "skipped"}
    macro_f1_values = [
        item.get("metrics", {}).get("macro_f1")
        for item in evaluated.values()
        if item.get("metrics", {}).get("macro_f1") is not None
    ]
    return {
        "dataset_count": len(datasets),
        "evaluated": sorted(evaluated),
        "skipped": sorted(skipped),
        "mean_macro_f1": round(float(np.mean(macro_f1_values)), 6) if macro_f1_values else None,
        "note": (
            "Mean macro-F1 is across evaluated text-only datasets and is not a "
            "claim of full multimodal MV-PostGuard validation."
        ),
    }


def safe_name(value: str) -> str:
    return value.replace("/", "_").replace("\\", "_").replace(" ", "_")


if __name__ == "__main__":
    raise SystemExit(main())
