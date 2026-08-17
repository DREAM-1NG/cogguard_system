"""Evaluate a HateCoT-trained Review Student on HateCOT paper transfer sets.

The runner is deliberately inference-only: it loads a saved HateCoT LRKD
checkpoint and evaluates it on downstream offensive-speech datasets. Data
sources are loaded from local files first, then optional HuggingFace direct
downloads. Missing datasets are recorded as skipped instead of being replaced
with unrelated corpora.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.request
from collections import Counter
from pathlib import Path
from time import perf_counter
from typing import Any, Iterable, Mapping

import numpy as np
from sklearn.metrics import accuracy_score, average_precision_score, f1_score

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from app.core.review.taxonomy_student import (  # noqa: E402
    INTERPERSONAL_AXIS,
    XLMRTextifiedReviewStudent,
    build_textified_student_batch,
)
from app.core.review.trainable_post import (  # noqa: E402
    expected_calibration_error,
    require_torch,
    resolve_torch_device,
)
from run_hatecot_lrkd_student import _classification_summary  # noqa: E402
from run_review_taxonomy_student import select_threshold_by_macro_f1  # noqa: E402


HF_URLS = {
    "HateCheck": "https://huggingface.co/datasets/Paul/hatecheck/resolve/main/test.csv",
    "Latent_Hate": "https://huggingface.co/datasets/tasksource/implicit-hate-stg1/resolve/main/implicit_hate_v1_stg1_posts.tsv",
    "Implicit_Hate": "https://huggingface.co/datasets/SALT-NLP/ImplicitHate/resolve/main/implicit_hate.csv",
}
NEGATIVE_LABELS = {
    "normal",
    "neutral",
    "non-hateful",
    "non_hateful",
    "not hate",
    "not_hate",
    "none",
    "no",
}


def load_hatecheck_csv(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader):
            text = _first_text(row, ("test_case", "text", "post", "comment"))
            raw_label = _clean(row.get("label_gold") or row.get("label") or row.get("gold_label"))
            if not text or not raw_label:
                continue
            binary = _binary_label(raw_label)
            rows.append(_case(
                dataset="HateCheck",
                case_id=_clean(row.get("case_id") or row.get("id")) or f"hatecheck-{index}",
                text=text,
                binary_label=binary,
                raw_label=raw_label,
                split="test",
                metadata={"functionality": _clean(row.get("functionality"))},
            ))
    return rows


def load_hatexplain_official(root: Path, *, split: str | None = None) -> list[dict[str, Any]]:
    data_dir = root / "Data" if (root / "Data").exists() else root
    dataset_path = data_dir / "dataset.json"
    splits_path = data_dir / "post_id_divisions.json"
    if not dataset_path.exists() or not splits_path.exists():
        return []
    records = json.loads(dataset_path.read_text(encoding="utf-8"))
    split_ids = json.loads(splits_path.read_text(encoding="utf-8"))
    rows = []
    split_names = {"train": "train", "val": "validation", "validation": "validation", "test": "test"}
    requested_split = split
    for raw_split, ids in split_ids.items():
        current_split = split_names.get(str(raw_split), str(raw_split))
        if requested_split is not None and requested_split != current_split:
            continue
        for case_id in ids:
            record = records.get(str(case_id))
            if not isinstance(record, Mapping):
                continue
            label = _hatexplain_majority_label(record.get("annotators") or [])
            text = _clean(record.get("post") or " ".join(record.get("post_tokens") or []))
            if not text or not label:
                continue
            rows.append(_case(
                dataset="HateXplain",
                case_id=str(case_id),
                text=text,
                binary_label=0 if label == "normal" else 1,
                raw_label=label,
                split=current_split,
                metadata={"source": "official_hatexplain_split"},
            ))
    return rows


def load_implicit_hate_csv(path: Path, *, dataset_name: str, implicit_only: bool) -> list[dict[str, Any]]:
    rows = []
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        for index, row in enumerate(reader):
            text = _first_text(row, ("post", "text", "tweet", "sentence", "content"))
            raw_label = _clean(
                row.get("label")
                or row.get("class")
                or row.get("gold_label")
                or row.get("stg1_label")
                or row.get("implicit_class")
            )
            implicit_class = _clean(row.get("implicit_class") or row.get("stg2_label") or row.get("target_class"))
            if not text:
                continue
            if implicit_only and not _is_implicit(raw_label, implicit_class):
                continue
            binary = 1 if implicit_only else _binary_label(raw_label or implicit_class)
            if raw_label or implicit_class:
                rows.append(_case(
                    dataset=dataset_name,
                    case_id=_clean(row.get("id") or row.get("post_id")) or f"{dataset_name.lower()}-{index}",
                    text=text,
                    binary_label=binary,
                    raw_label=raw_label or implicit_class,
                    split=_clean(row.get("split")) or "test",
                    metadata={"implicit_class": implicit_class},
                ))
    return rows


def load_transfer_dataset(dataset: str, args: argparse.Namespace) -> tuple[list[dict[str, Any]], str]:
    if dataset == "HateXplain":
        rows = load_hatexplain_official(Path(args.hatexplain_dir), split="test")
        return rows, str(Path(args.hatexplain_dir))
    if dataset == "HateCheck":
        local_path = Path(args.hatecheck_dir) / "test_suite_cases.csv"
        if local_path.exists():
            return load_hatecheck_csv(local_path), str(local_path)
        path = _materialize_dataset_file(dataset, args)
        return (load_hatecheck_csv(path), str(path)) if path else ([], "HuggingFace Paul/hatecheck test.csv unavailable")
    if dataset == "Latent_Hate":
        local_path = Path(args.implicit_hate_dir) / "implicit_hate_v1_stg1_posts.tsv"
        if local_path.exists():
            return (
                load_implicit_hate_csv(local_path, dataset_name="Latent_Hate", implicit_only=False),
                str(local_path),
            )
        path = _materialize_dataset_file(dataset, args)
        return (
            load_implicit_hate_csv(path, dataset_name="Latent_Hate", implicit_only=False),
            str(path),
        ) if path else ([], "HuggingFace tasksource/implicit-hate-stg1 unavailable")
    if dataset == "Implicit_Hate":
        local_path = Path(args.implicit_hate_dir) / "implicit_hate_v1_stg2_posts.tsv"
        if local_path.exists():
            return (
                load_implicit_hate_csv(local_path, dataset_name="Implicit_Hate", implicit_only=True),
                str(local_path),
            )
        path = _materialize_dataset_file(dataset, args)
        return (
            load_implicit_hate_csv(path, dataset_name="Implicit_Hate", implicit_only=True),
            str(path),
        ) if path else ([], "HuggingFace SALT-NLP/ImplicitHate unavailable")
    return [], f"unsupported dataset: {dataset}"


def load_checkpoint(path: Path, *, device: str) -> tuple[Any, Any, dict[str, Any]]:
    require_torch()
    import torch
    from transformers import AutoTokenizer

    payload = torch.load(path, map_location=device, weights_only=False)
    config = payload.get("model_config") or payload.get("run_config") or {}
    backbone = str(config.get("backbone") or "FacebookAI/xlm-roberta-base")
    cache_dir = str(config.get("hf_cache_dir") or "")
    local_files_only = not bool(config.get("allow_model_download", False))
    rationale_dim = int(config.get("rationale_dim") or 768)
    tokenizer = AutoTokenizer.from_pretrained(
        backbone,
        cache_dir=cache_dir or None,
        local_files_only=local_files_only,
        use_fast=True,
    )
    model = XLMRTextifiedReviewStudent(
        backbone,
        rationale_dim=rationale_dim,
        cache_dir=cache_dir or None,
        local_files_only=local_files_only,
    ).to(device)
    # Protocol heads were added after the original HateCoT LRKD checkpoint
    # schema. They are irrelevant to this legacy binary transfer runner.
    model.load_state_dict(payload["model_state_dict"], strict=False)
    model.eval()
    return model, tokenizer, payload


def predict_probabilities(model: Any, tokenizer: Any, rows: list[dict[str, Any]], *, args: argparse.Namespace, device: str) -> np.ndarray:
    require_torch()
    import torch

    batch = build_textified_student_batch(rows)
    probabilities = []
    with torch.no_grad():
        for start in range(0, len(rows), max(1, args.batch_size)):
            encoded = tokenizer(
                batch["texts"][start : start + args.batch_size],
                padding=True,
                truncation=True,
                max_length=args.max_length,
                return_tensors="pt",
            )
            encoded = {key: value.to(device) for key, value in encoded.items()}
            outputs = model(**encoded)
            probabilities.extend(torch.sigmoid(outputs[INTERPERSONAL_AXIS]).detach().cpu().numpy().tolist())
    return np.asarray(probabilities, dtype="float32")


def evaluate_rows(rows: list[dict[str, Any]], probabilities: np.ndarray, *, threshold: float | None) -> dict[str, Any]:
    labels = np.asarray([row["binary_label"] for row in rows], dtype="float32")
    if labels.size == 0:
        return {"status": "skipped", "skip_reason": "no labelled rows"}
    if np.unique(labels.astype(int)).size < 2:
        return {
            "status": "skipped",
            "skip_reason": "only one binary class after normalization",
            "support": int(labels.size),
            "positive_count": int(labels.sum()),
        }
    resolved_threshold = float(threshold) if threshold is not None else float(select_threshold_by_macro_f1(labels, probabilities)["threshold"])
    metrics = _classification_summary(labels, probabilities, threshold=resolved_threshold)
    predicted = (probabilities >= resolved_threshold).astype(int)
    metrics["status"] = "evaluated"
    metrics["label_distribution"] = dict(Counter(int(value) for value in labels.astype(int).tolist()))
    metrics["confusion"] = _confusion(labels.astype(int), predicted)
    return metrics


def main() -> int:
    started = perf_counter()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--output-dir", default=r"G:\CISCN\.tmp\hatecot_transfer_student")
    parser.add_argument("--datasets", nargs="*", default=["HateCheck", "HateXplain", "Latent_Hate", "Implicit_Hate"])
    parser.add_argument("--hatexplain-dir", default=r"G:\CISCN\dataset\kt3_public\HateXplain")
    parser.add_argument("--hatecheck-dir", default=r"G:\CISCN\dataset\hatecheck-data")
    parser.add_argument("--implicit-hate-dir", default=r"G:\CISCN\dataset\implicit-hate-corpus")
    parser.add_argument("--download-dir", default=r"G:\CISCN\.tmp\hatecot_transfer_datasets")
    parser.add_argument("--allow-download", action="store_true")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--max-cases-per-dataset", type=int, default=0)
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--use-checkpoint-threshold", action="store_true")
    parser.add_argument("--device", default=None)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    device = resolve_torch_device(args.device)
    model, tokenizer, checkpoint = load_checkpoint(Path(args.checkpoint), device=device)
    checkpoint_threshold = checkpoint.get("decision_threshold")
    threshold = args.threshold
    if threshold is None and args.use_checkpoint_threshold and checkpoint_threshold is not None:
        threshold = float(checkpoint_threshold)

    report: dict[str, Any] = {
        "schema": "hatecot-transfer-student-eval-v1",
        "checkpoint": str(Path(args.checkpoint)),
        "checkpoint_schema": checkpoint.get("schema"),
        "threshold_policy": "cli_or_checkpoint" if threshold is not None else "per_dataset_oracle_macro_f1",
        "threshold": threshold,
        "datasets_requested": args.datasets,
        "datasets": {},
        "duration_seconds": None,
    }
    for dataset in args.datasets:
        rows, source = load_transfer_dataset(dataset, args)
        if args.max_cases_per_dataset > 0:
            rows = _balanced_cap(rows, args.max_cases_per_dataset)
        record: dict[str, Any] = {
            "dataset": dataset,
            "source": source,
            "case_count": len(rows),
            "split_counts": dict(Counter(str(row.get("split") or "test") for row in rows)),
        }
        if not rows:
            record.update({"status": "skipped", "skip_reason": "dataset unavailable or empty"})
            report["datasets"][dataset] = record
            continue
        probabilities = predict_probabilities(model, tokenizer, rows, args=args, device=device)
        record.update(evaluate_rows(rows, probabilities, threshold=threshold))
        report["datasets"][dataset] = record
        _write_predictions(output_dir / f"{_safe_name(dataset)}_predictions.jsonl", rows, probabilities, threshold=record.get("threshold", threshold or 0.5))
    report["summary"] = summarize(report["datasets"])
    report["duration_seconds"] = round(perf_counter() - started, 6)
    (output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"wrote {output_dir / 'report.json'}")
    return 0


def summarize(datasets: Mapping[str, Any]) -> dict[str, Any]:
    evaluated = [name for name, record in datasets.items() if record.get("status") == "evaluated"]
    skipped = {name: record.get("skip_reason") for name, record in datasets.items() if record.get("status") != "evaluated"}
    return {"evaluated_count": len(evaluated), "evaluated": evaluated, "skipped": skipped}


def _materialize_dataset_file(dataset: str, args: argparse.Namespace) -> Path | None:
    download_dir = Path(args.download_dir)
    candidates = {
        "HateCheck": download_dir / "hatecheck_test.csv",
        "Latent_Hate": download_dir / "implicit_hate_v1_stg1_posts.tsv",
        "Implicit_Hate": download_dir / "implicit_hate.csv",
    }
    path = candidates[dataset]
    if path.exists():
        return path
    if not args.allow_download:
        return None
    url = HF_URLS[dataset]
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        urllib.request.urlretrieve(url, path)
    except Exception:
        return None
    return path if path.exists() else None


def _case(*, dataset: str, case_id: str, text: str, binary_label: int, raw_label: str, split: str, metadata: Mapping[str, Any]) -> dict[str, Any]:
    normalized = "hate" if int(binary_label) == 1 else "normal"
    return {
        "case_id": str(case_id),
        "dataset": dataset,
        "split": split,
        "text": text,
        "binary_label": int(binary_label),
        "labels": {"raw_label": normalized, "label": normalized, "source_label": raw_label},
        "metadata": dict(metadata),
    }


def _hatexplain_majority_label(annotators: Iterable[Mapping[str, Any]]) -> str:
    labels = [_clean(row.get("label")).lower() for row in annotators if _clean(row.get("label"))]
    if not labels:
        return ""
    counts = Counter(labels)
    return counts.most_common(1)[0][0]


def _binary_label(raw_label: str) -> int:
    label = _clean(raw_label).lower().replace("-", "_")
    return 0 if label in {item.replace("-", "_") for item in NEGATIVE_LABELS} else 1


def _is_implicit(raw_label: str, implicit_class: str) -> bool:
    label = _clean(raw_label).lower()
    fine = _clean(implicit_class).lower()
    return "implicit" in label or bool(fine and fine not in {"none", "nan", "not_hate", "not hate"})


def _first_text(row: Mapping[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        text = _clean(row.get(key))
        if text:
            return text
    return ""


def _balanced_cap(rows: list[dict[str, Any]], max_cases: int) -> list[dict[str, Any]]:
    if max_cases <= 0:
        return rows
    positives = [row for row in rows if int(row["binary_label"]) == 1]
    negatives = [row for row in rows if int(row["binary_label"]) == 0]
    each = max(1, max_cases // 2)
    return (positives[:each] + negatives[:each])[:max_cases]


def _write_predictions(path: Path, rows: list[dict[str, Any]], probabilities: np.ndarray, *, threshold: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row, probability in zip(rows, probabilities):
            handle.write(json.dumps({
                "case_id": row.get("case_id"),
                "dataset": row.get("dataset"),
                "gold_label": int(row["binary_label"]),
                "predicted_probability": round(float(probability), 6),
                "predicted_label": int(float(probability) >= float(threshold)),
                "split": row.get("split"),
            }, ensure_ascii=False, separators=(",", ":")) + "\n")


def _confusion(labels: np.ndarray, predicted: np.ndarray) -> dict[str, int]:
    return {
        "tn": int(((labels == 0) & (predicted == 0)).sum()),
        "fp": int(((labels == 0) & (predicted == 1)).sum()),
        "fn": int(((labels == 1) & (predicted == 0)).sum()),
        "tp": int(((labels == 1) & (predicted == 1)).sum()),
    }


def _safe_name(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


if __name__ == "__main__":
    raise SystemExit(main())
