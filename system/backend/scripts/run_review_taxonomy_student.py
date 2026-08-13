"""Run taxonomy-first textified Review Student SFT.

Stage 1 intentionally uses text evidence only:
``[TEXT] [HASHTAGS] [OCR] [ASR] [CAPTION] [CLAIM_CONTEXT]``.
It does not consume raw images/videos and does not use Teacher distillation.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from app.core.review.taxonomy_student import (  # noqa: E402
    DECEPTION_AXIS,
    FINE_LABEL_ORDER,
    INTERPERSONAL_AXIS,
    MAIN_AXIS_ORDER,
    STANCE_AXIS,
    TextifiedStudentLoss,
    XLMRTextifiedReviewStudent,
    build_textified_student_batch,
    dataset_supports_axis,
)
from app.core.review.trainable_post import (  # noqa: E402
    FeedForwardBinaryClassifier,
    binary_classification_metrics,
    binary_pr_auc,
    encode_text_features,
    expected_calibration_error,
    require_torch,
    resolve_torch_device,
    train_binary_torch_model,
    write_jsonl,
)
from run_review_post_multiview_ablation import build_splits  # noqa: E402
from run_review_trainable_post import load_cases  # noqa: E402


DEFAULT_DATASETS = ["HateXplain", "HateCoT", "MultiOFF", "PHEME", "mcfend", "FakeSV", "Weibo21"]
BACKBONE_MODELS = {
    "xlm-r-base": "FacebookAI/xlm-roberta-base",
    "chinese-roberta-wwm-ext": "hfl/chinese-roberta-wwm-ext",
}
HATECOT_NEGATIVE_LABELS = {"benign", "neutral", "normal", "not hate", "not hate speech", "not offensive"}


def _masked_rows(split_cases: list[dict[str, Any]], axis: str) -> tuple[list[dict[str, Any]], np.ndarray]:
    batch = build_textified_student_batch(split_cases)
    mask = np.asarray(batch["task_mask"][axis], dtype="float32") > 0.5
    labels = np.asarray(batch["labels"][axis], dtype="float32")[mask]
    rows = [case for case, keep in zip(split_cases, mask) if bool(keep)]
    return rows, labels


def _axis_label_names(labels: np.ndarray) -> list[str]:
    return ["harmful" if int(value) == 1 else "non_harmful" for value in labels.astype(int).tolist()]


def _axis_metrics(labels: np.ndarray, probabilities: np.ndarray, *, threshold: float = 0.5) -> dict[str, Any]:
    if labels.size == 0:
        return {"status": "skipped", "skip_reason": "no masked labels for axis"}
    if np.unique(labels.astype(int)).size < 2:
        return {
            "status": "skipped",
            "skip_reason": "masked axis labels contain one class",
            "support": int(labels.size),
            "positive_count": int(labels.sum()),
        }
    label_names = _axis_label_names(labels)
    return {
        "status": "evaluated",
        "threshold": round(float(threshold), 6),
        "support": int(labels.size),
        "positive_count": int(labels.sum()),
        "metrics": binary_classification_metrics(label_names, probabilities, threshold=threshold),
        "pr_auc": binary_pr_auc(label_names, probabilities),
        "ece": expected_calibration_error(labels.astype(int), probabilities),
    }


def select_threshold_by_macro_f1(labels: np.ndarray, probabilities: np.ndarray) -> dict[str, Any]:
    if labels.size == 0 or np.unique(labels.astype(int)).size < 2:
        return {"threshold": 0.5, "metrics": {}}
    candidates = sorted({0.5, *[float(value) for value in probabilities.tolist()]})
    best_threshold = 0.5
    best_metrics: dict[str, Any] = {}
    best_score = -1.0
    label_names = _axis_label_names(labels)
    for threshold in candidates:
        metrics = binary_classification_metrics(label_names, probabilities, threshold=threshold)
        score = float(metrics.get("macro_f1") or 0.0)
        if score > best_score or (score == best_score and abs(threshold - 0.5) < abs(best_threshold - 0.5)):
            best_score = score
            best_threshold = threshold
            best_metrics = metrics
    return {"threshold": round(float(best_threshold), 6), "metrics": best_metrics}


def load_hatecot_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader):
            raw_label = str(row.get("label") or "").strip()
            if not raw_label:
                continue
            normalized = raw_label.lower()
            label = "normal" if normalized in HATECOT_NEGATIVE_LABELS else "hate"
            rows.append(
                {
                    "case_id": str(row.get("uid") or row.get("id") or f"hatecot-{index}"),
                    "dataset": "HateCoT",
                    "split": str(row.get("domain") or "all"),
                    "text": str(row.get("post") or ""),
                    "explanation": str(row.get("explanation") or ""),
                    "labels": {
                        "label": label,
                        "raw_label": label,
                        "source_label": raw_label,
                        "target_groups": [str(row.get("target"))] if str(row.get("target") or "").strip() else [],
                    },
                    "metadata": {"domain": str(row.get("domain") or ""), "source_id": str(row.get("id") or "")},
                }
            )
    return rows


def load_weibo21_jsonl(root: Path) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    rows: list[dict[str, Any]] = []
    sources = [
        (root / "fake_release_all.json", "fake"),
        (root / "real_release_all.json", "real"),
    ]
    for path, kind in sources:
        if not path.exists():
            continue
        raw_label = "fake" if kind == "fake" else "real"
        with path.open("r", encoding="utf-8") as handle:
            for index, line in enumerate(handle):
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                comments = row.get("comments")
                piclists = row.get("piclists")
                pic_count = len(piclists) if isinstance(piclists, list) else 0
                rows.append(
                    {
                        "case_id": str(row.get("id") or f"weibo21-{kind}-{index}"),
                        "dataset": "Weibo21",
                        "split": str(row.get("category") or "all"),
                        "text": str(row.get("content") or ""),
                        "hashtags": [],
                        "claim_context": {
                            "claim_text": str(row.get("content") or ""),
                            "evidence_text": str(comments or "")[:2000],
                        },
                        "labels": {
                            "raw_label": raw_label,
                            "veracity": "false" if kind == "fake" else "true",
                            "category": str(row.get("category") or ""),
                        },
                        "metadata": {
                            "timestamp": str(row.get("timestamp") or ""),
                            "pic_count": pic_count,
                            "source_file": str(path),
                        },
                    }
                )
    return rows


def load_dataset_cases(dataset: str, case_dir: Path, args: argparse.Namespace) -> tuple[list[dict[str, Any]], str]:
    case_path = case_dir / f"{dataset}.jsonl"
    cases = load_cases(case_path)
    if cases:
        return cases, str(case_path)
    if dataset.lower() == "hatecot":
        cases = load_hatecot_csv(Path(args.hatecot_csv))
        if cases:
            return cases, str(args.hatecot_csv)
    if dataset.lower() == "weibo21":
        cases = load_weibo21_jsonl(Path(args.weibo21_dir))
        if cases:
            return cases, str(args.weibo21_dir)
    return [], str(case_path)


def taxonomy_label_of(case: Mapping[str, Any], dataset: str) -> str:
    axis = INTERPERSONAL_AXIS if dataset_supports_axis(dataset, INTERPERSONAL_AXIS) else DECEPTION_AXIS
    batch = build_textified_student_batch([case])
    return "harmful" if float(batch["labels"][axis][0]) >= 0.5 else "non_harmful"


def validate_taxonomy_splits(split_cases: dict[str, list[dict[str, Any]]], dataset: str) -> str:
    axis = INTERPERSONAL_AXIS if dataset_supports_axis(dataset, INTERPERSONAL_AXIS) else DECEPTION_AXIS
    for split in ("train", "validation", "test"):
        rows = split_cases.get(split) or []
        if not rows:
            return f"{split} split empty"
        batch = build_textified_student_batch(rows)
        mask = np.asarray(batch["task_mask"][axis], dtype="float32") > 0.5
        labels = np.asarray(batch["labels"][axis], dtype="float32")[mask]
        if labels.size == 0:
            return f"{split} split has no {axis} labels"
        if np.unique(labels.astype(int)).size < 2:
            return f"{split} split lost a class for {axis}"
    return ""


def cap_taxonomy_splits(
    split_cases: dict[str, list[dict[str, Any]]],
    max_cases: int,
    dataset: str,
) -> dict[str, list[dict[str, Any]]]:
    if max_cases <= 0:
        return split_cases
    capped = {}
    for split, rows in split_cases.items():
        positives = [case for case in rows if taxonomy_label_of(case, dataset) == "harmful"]
        negatives = [case for case in rows if taxonomy_label_of(case, dataset) != "harmful"]
        each = max(1, max_cases // 2)
        capped[split] = (positives[:each] + negatives[:each])[:max_cases]
    return capped


def train_hash_axis(
    axis: str,
    train_cases: list[dict[str, Any]],
    validation_cases: list[dict[str, Any]],
    test_cases: list[dict[str, Any]],
    *,
    args: argparse.Namespace,
) -> dict[str, Any]:
    train_rows, train_y = _masked_rows(train_cases, axis)
    validation_rows, validation_y = _masked_rows(validation_cases, axis)
    test_rows, test_y = _masked_rows(test_cases, axis)
    if not train_rows or np.unique(train_y.astype(int)).size < 2:
        return {
            "status": "skipped",
            "axis": axis,
            "skip_reason": "train split has no masked rows or one class",
            "train_support": int(train_y.size),
            "train_positive_count": int(train_y.sum()) if train_y.size else 0,
        }
    texts = build_textified_student_batch(train_rows + validation_rows + test_rows)["texts"]
    features = encode_text_features(
        texts,
        backend="hash",
        dim=args.hash_dim,
        batch_size=args.batch_size,
    ).matrix
    train_x = features[: len(train_rows)]
    validation_x = features[len(train_rows) : len(train_rows) + len(validation_rows)]
    test_x = features[len(train_rows) + len(validation_rows) :]
    model = FeedForwardBinaryClassifier(input_dim=train_x.shape[1], hidden_dim=args.hidden_dim)
    train_info = train_binary_torch_model(
        model,
        train_x,
        train_y,
        epochs=args.epochs,
        lr=args.lr,
        batch_size=args.batch_size,
        device=args.device,
    )
    validation_prob = _predict_binary_model(model, validation_x, batch_size=args.batch_size, device=args.device)
    test_prob = _predict_binary_model(model, test_x, batch_size=args.batch_size, device=args.device)
    return {
        "status": "evaluated",
        "axis": axis,
        "backend": "hash-smoke",
        "train": {
            "support": int(train_y.size),
            "positive_count": int(train_y.sum()),
            "train_info": train_info,
        },
        "validation": _axis_metrics(validation_y, validation_prob),
        "test": _axis_metrics(test_y, test_prob),
        "test_predictions": [
            {
                "case_id": case.get("case_id"),
                "dataset": case.get("dataset"),
                "axis": axis,
                "probability": round(float(prob), 6),
                "label": int(label),
            }
            for case, prob, label in zip(test_rows, test_prob, test_y)
        ],
    }


def _predict_binary_model(model: Any, features: np.ndarray, *, batch_size: int, device: str | None) -> np.ndarray:
    require_torch()
    import torch

    resolved_device = resolve_torch_device(device)
    model.to(resolved_device)
    model.eval()
    x_tensor = torch.as_tensor(features, dtype=torch.float32, device=resolved_device)
    rows = []
    with torch.no_grad():
        for start in range(0, int(x_tensor.shape[0]), max(1, batch_size)):
            logits = model(x_tensor[start : start + batch_size])
            rows.append(torch.sigmoid(logits).detach().cpu().numpy())
    return np.concatenate(rows).astype("float32") if rows else np.zeros((0,), dtype="float32")


def _as_torch_targets(batch: Mapping[str, Any], device: str) -> dict[str, Any]:
    import torch

    labels = batch["labels"]
    task_mask = batch["task_mask"]
    targets = {
        INTERPERSONAL_AXIS: torch.as_tensor(labels[INTERPERSONAL_AXIS], dtype=torch.float32, device=device),
        f"{INTERPERSONAL_AXIS}_mask": torch.as_tensor(task_mask[INTERPERSONAL_AXIS], dtype=torch.float32, device=device),
        DECEPTION_AXIS: torch.as_tensor(labels[DECEPTION_AXIS], dtype=torch.float32, device=device),
        f"{DECEPTION_AXIS}_mask": torch.as_tensor(task_mask[DECEPTION_AXIS], dtype=torch.float32, device=device),
        STANCE_AXIS: torch.as_tensor(labels[STANCE_AXIS], dtype=torch.long, device=device),
        f"{STANCE_AXIS}_mask": torch.as_tensor(task_mask[STANCE_AXIS], dtype=torch.float32, device=device),
        "fine_labels": torch.as_tensor(labels["fine_labels"], dtype=torch.float32, device=device),
        "fine_labels_mask": torch.as_tensor(task_mask["fine_labels"], dtype=torch.float32, device=device),
    }
    if "teacher_vector" in batch:
        targets["teacher_vector"] = torch.as_tensor(batch["teacher_vector"], dtype=torch.float32, device=device)
        targets["teacher_vector_mask"] = torch.as_tensor(batch["teacher_vector_mask"], dtype=torch.float32, device=device)
    return targets


def encode_rationale_vectors(texts: list[str], *, args: argparse.Namespace) -> np.ndarray:
    features = encode_text_features(
        texts,
        backend=args.rationale_encoder_backend,
        model_name=args.rationale_encoder_model,
        cache_dir=args.hf_cache_dir,
        batch_size=args.batch_size,
        local_files_only=not args.allow_model_download,
        max_length=args.rationale_max_length,
        pooling=args.rationale_pooling,
        dim=args.rationale_dim,
    )
    return features.matrix.astype("float32")


def add_lrkd_targets(batch: dict[str, Any], *, args: argparse.Namespace) -> dict[str, Any]:
    if not args.enable_lrkd:
        return batch
    rationale_texts = list(batch.get("rationale_texts") or [])
    mask = np.asarray(batch["task_mask"].get("rationale"), dtype="float32")
    vectors = np.zeros((len(rationale_texts), args.rationale_dim), dtype="float32")
    valid_indices = [index for index, (text, keep) in enumerate(zip(rationale_texts, mask)) if text and keep > 0.5]
    if valid_indices:
        encoded = encode_rationale_vectors([rationale_texts[index] for index in valid_indices], args=args)
        if encoded.shape[1] != args.rationale_dim:
            raise ValueError(
                f"rationale encoder dim {encoded.shape[1]} does not match --rationale-dim {args.rationale_dim}"
            )
        for index, vector in zip(valid_indices, encoded):
            vectors[index] = vector
    batch["teacher_vector"] = vectors
    batch["teacher_vector_mask"] = mask
    batch["lrkd_valid_count"] = int(mask.sum())
    return batch


def lrkd_scope_status(enable_lrkd: bool, valid_count: int) -> str:
    if not enable_lrkd:
        return "disabled"
    if valid_count:
        return "dataset_explanation_vectors_used"
    return "enabled_but_no_dataset_explanations"


def train_xlmr_joint(
    train_cases: list[dict[str, Any]],
    validation_cases: list[dict[str, Any]],
    test_cases: list[dict[str, Any]],
    *,
    args: argparse.Namespace,
) -> dict[str, Any]:
    require_torch()
    import torch
    from transformers import AutoTokenizer

    model_name = BACKBONE_MODELS.get(args.backbone, args.backbone)
    device = resolve_torch_device(args.device)
    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        cache_dir=args.hf_cache_dir or None,
        local_files_only=not args.allow_model_download,
        use_fast=True,
    )
    model = XLMRTextifiedReviewStudent(
        model_name,
        rationale_dim=args.rationale_dim,
        cache_dir=args.hf_cache_dir or None,
        local_files_only=not args.allow_model_download,
    ).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    criterion = TextifiedStudentLoss(
        stance_weight=args.stance_weight,
        fine_label_weight=args.fine_label_weight,
        lrkd_weight=args.lrkd_weight if args.enable_lrkd else 0.0,
    )
    train_batch = add_lrkd_targets(build_textified_student_batch(train_cases), args=args)
    history = []
    model.train()
    for epoch in range(max(1, args.epochs)):
        order = torch.randperm(len(train_cases), device=device)
        losses = []
        for start in range(0, len(train_cases), max(1, args.batch_size)):
            idx_tensor = order[start : start + args.batch_size]
            idx = idx_tensor.detach().cpu().numpy().astype(int).tolist()
            texts = [train_batch["texts"][row] for row in idx]
            encoded = tokenizer(
                texts,
                padding=True,
                truncation=True,
                max_length=args.max_length,
                return_tensors="pt",
            )
            encoded = {key: value.to(device) for key, value in encoded.items()}
            mini_batch = {
                "labels": {key: value[idx] for key, value in train_batch["labels"].items()},
                "task_mask": {key: value[idx] for key, value in train_batch["task_mask"].items()},
            }
            if args.enable_lrkd:
                mini_batch["teacher_vector"] = train_batch["teacher_vector"][idx]
                mini_batch["teacher_vector_mask"] = train_batch["teacher_vector_mask"][idx]
            targets = _as_torch_targets(mini_batch, device)
            optimizer.zero_grad()
            outputs = model(**encoded)
            loss_record = criterion(outputs, targets)
            loss_record["total_loss"].backward()
            optimizer.step()
            losses.append(float(loss_record["total_loss"].detach().cpu()))
        history.append({"epoch": epoch + 1, "loss": round(float(np.mean(losses)), 6)})
    evaluation = evaluate_xlmr_validation_test_axes(
        model,
        tokenizer,
        validation_cases,
        test_cases,
        args=args,
        device=device,
    )
    lrkd_valid_count = int(train_batch.get("lrkd_valid_count", 0))
    return {
        "status": "evaluated",
        "backend": "xlm-r-end-to-end",
        "model_name": model_name,
        "train": {
            "support": len(train_cases),
            "history": history,
            "lrkd_enabled": bool(args.enable_lrkd),
            "lrkd_valid_count": lrkd_valid_count,
            "lrkd_scope_status": lrkd_scope_status(bool(args.enable_lrkd), lrkd_valid_count),
        },
        "validation": evaluation["validation"],
        "test": evaluation["test"],
    }


def predict_xlmr_probabilities(
    model: Any,
    tokenizer: Any,
    cases: list[dict[str, Any]],
    *,
    args: argparse.Namespace,
    device: str,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    import torch

    batch = build_textified_student_batch(cases)
    probabilities = {axis: [] for axis in MAIN_AXIS_ORDER}
    model.eval()
    with torch.no_grad():
        for start in range(0, len(cases), max(1, args.batch_size)):
            texts = batch["texts"][start : start + args.batch_size]
            encoded = tokenizer(
                texts,
                padding=True,
                truncation=True,
                max_length=args.max_length,
                return_tensors="pt",
            )
            encoded = {key: value.to(device) for key, value in encoded.items()}
            outputs = model(**encoded)
            for axis in MAIN_AXIS_ORDER:
                probabilities[axis].extend(torch.sigmoid(outputs[axis]).detach().cpu().numpy().tolist())
    return {axis: np.asarray(values, dtype="float32") for axis, values in probabilities.items()}, batch


def predict_xlmr_axes(model: Any, tokenizer: Any, cases: list[dict[str, Any]], *, args: argparse.Namespace, device: str) -> dict[str, Any]:
    probabilities, batch = predict_xlmr_probabilities(model, tokenizer, cases, args=args, device=device)
    axis_reports = {}
    for axis in MAIN_AXIS_ORDER:
        mask = np.asarray(batch["task_mask"][axis], dtype="float32") > 0.5
        labels = np.asarray(batch["labels"][axis], dtype="float32")[mask]
        probs = probabilities[axis][mask]
        axis_reports[axis] = _axis_metrics(labels, probs)
    return axis_reports


def evaluate_xlmr_validation_test_axes(
    model: Any,
    tokenizer: Any,
    validation_cases: list[dict[str, Any]],
    test_cases: list[dict[str, Any]],
    *,
    args: argparse.Namespace,
    device: str,
) -> dict[str, dict[str, Any]]:
    validation_probabilities, validation_batch = predict_xlmr_probabilities(
        model,
        tokenizer,
        validation_cases,
        args=args,
        device=device,
    )
    test_probabilities, test_batch = predict_xlmr_probabilities(
        model,
        tokenizer,
        test_cases,
        args=args,
        device=device,
    )
    validation_reports: dict[str, Any] = {}
    test_reports: dict[str, Any] = {}
    for axis in MAIN_AXIS_ORDER:
        validation_mask = np.asarray(validation_batch["task_mask"][axis], dtype="float32") > 0.5
        validation_labels = np.asarray(validation_batch["labels"][axis], dtype="float32")[validation_mask]
        validation_probs = validation_probabilities[axis][validation_mask]
        threshold_record = select_threshold_by_macro_f1(validation_labels, validation_probs)
        threshold = float(threshold_record["threshold"])
        validation_record = _axis_metrics(validation_labels, validation_probs, threshold=threshold)
        validation_record["threshold_selection"] = threshold_record
        validation_reports[axis] = validation_record

        test_mask = np.asarray(test_batch["task_mask"][axis], dtype="float32") > 0.5
        test_labels = np.asarray(test_batch["labels"][axis], dtype="float32")[test_mask]
        test_probs = test_probabilities[axis][test_mask]
        test_record = _axis_metrics(test_labels, test_probs, threshold=threshold)
        test_record["threshold_source"] = "validation_macro_f1"
        test_reports[axis] = test_record
    return {"validation": validation_reports, "test": test_reports}


def train_joint_xlmr_all_datasets(
    dataset_splits: Mapping[str, dict[str, list[dict[str, Any]]]],
    *,
    args: argparse.Namespace,
) -> dict[str, Any]:
    require_torch()
    import torch
    from transformers import AutoTokenizer

    model_name = BACKBONE_MODELS.get(args.backbone, args.backbone)
    device = resolve_torch_device(args.device)
    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        cache_dir=args.hf_cache_dir or None,
        local_files_only=not args.allow_model_download,
        use_fast=True,
    )
    model = XLMRTextifiedReviewStudent(
        model_name,
        rationale_dim=args.rationale_dim,
        cache_dir=args.hf_cache_dir or None,
        local_files_only=not args.allow_model_download,
    ).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    criterion = TextifiedStudentLoss(
        stance_weight=args.stance_weight,
        fine_label_weight=args.fine_label_weight,
        lrkd_weight=args.lrkd_weight if args.enable_lrkd else 0.0,
    )
    train_cases = [
        case
        for dataset in dataset_splits.values()
        for case in dataset["train"]
    ]
    train_batch = add_lrkd_targets(build_textified_student_batch(train_cases), args=args)
    history = []
    model.train()
    for epoch in range(max(1, args.epochs)):
        order = torch.randperm(len(train_cases), device=device)
        losses = []
        for start in range(0, len(train_cases), max(1, args.batch_size)):
            idx_tensor = order[start : start + args.batch_size]
            idx = idx_tensor.detach().cpu().numpy().astype(int).tolist()
            encoded = tokenizer(
                [train_batch["texts"][row] for row in idx],
                padding=True,
                truncation=True,
                max_length=args.max_length,
                return_tensors="pt",
            )
            encoded = {key: value.to(device) for key, value in encoded.items()}
            mini_batch = {
                "labels": {key: value[idx] for key, value in train_batch["labels"].items()},
                "task_mask": {key: value[idx] for key, value in train_batch["task_mask"].items()},
            }
            if args.enable_lrkd:
                mini_batch["teacher_vector"] = train_batch["teacher_vector"][idx]
                mini_batch["teacher_vector_mask"] = train_batch["teacher_vector_mask"][idx]
            targets = _as_torch_targets(mini_batch, device)
            optimizer.zero_grad()
            loss_record = criterion(model(**encoded), targets)
            loss_record["total_loss"].backward()
            optimizer.step()
            losses.append(float(loss_record["total_loss"].detach().cpu()))
        history.append({"epoch": epoch + 1, "loss": round(float(np.mean(losses)), 6)})

    lrkd_valid_count = int(train_batch.get("lrkd_valid_count", 0))
    dataset_reports = {}
    for dataset, splits in dataset_splits.items():
        dataset_reports[dataset] = {
            "status": "evaluated",
            "split_counts": {split: len(rows) for split, rows in splits.items()},
        }
        dataset_reports[dataset].update(
            evaluate_xlmr_validation_test_axes(
                model,
                tokenizer,
                splits["validation"],
                splits["test"],
                args=args,
                device=device,
            )
        )
    return {
        "status": "evaluated",
        "backend": "xlm-r-end-to-end",
        "model_name": model_name,
        "training_scope": "joint",
        "train": {
            "support": len(train_cases),
            "history": history,
            "lrkd_enabled": bool(args.enable_lrkd),
            "lrkd_valid_count": lrkd_valid_count,
            "lrkd_scope_status": lrkd_scope_status(bool(args.enable_lrkd), lrkd_valid_count),
        },
        "datasets": dataset_reports,
    }


def prepare_dataset_splits(dataset: str, *, case_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    cases, source_path = load_dataset_cases(dataset, case_dir, args)
    if not cases:
        return {
            "dataset": dataset,
            "status": "skipped",
            "skip_reason": f"case source missing or empty: {source_path}",
        }
    split_cases, split_policy = build_splits(dataset, cases, args.random_state)
    split_cases = cap_taxonomy_splits(split_cases, args.max_cases_per_split, dataset)
    split_status = validate_taxonomy_splits(split_cases, dataset)
    if split_status:
        return {"dataset": dataset, "status": "skipped", "skip_reason": split_status, "split_policy": split_policy}
    return {
        "dataset": dataset,
        "status": "prepared",
        "source_path": source_path,
        "split_policy": split_policy,
        "split_counts": {split: len(rows) for split, rows in split_cases.items()},
        "splits": split_cases,
    }


def evaluate_joint_training(*, case_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    prepared = {
        dataset: prepare_dataset_splits(dataset, case_dir=case_dir, args=args)
        for dataset in args.datasets
    }
    dataset_splits = {
        dataset: record["splits"]
        for dataset, record in prepared.items()
        if record.get("status") == "prepared"
    }
    result: dict[str, Any] = {
        "status": "evaluated" if dataset_splits else "skipped",
        "training_scope": "joint",
        "prepared": {
            dataset: {key: value for key, value in record.items() if key != "splits"}
            for dataset, record in prepared.items()
        },
    }
    if not dataset_splits:
        result["skip_reason"] = "no dataset prepared for joint training"
        return result
    if args.encoder_backend != "xlm-r":
        result["skip_reason"] = "joint training currently requires --encoder-backend xlm-r"
        result["status"] = "skipped"
        return result
    result["joint_model"] = train_joint_xlmr_all_datasets(dataset_splits, args=args)
    return result


def summarize_axis_metrics(datasets: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for dataset, record in datasets.items():
        if not isinstance(record, Mapping):
            continue
        for split in ("validation", "test"):
            split_record = record.get(split) or {}
            if not isinstance(split_record, Mapping):
                continue
            for axis, axis_record in split_record.items():
                if not isinstance(axis_record, Mapping) or axis_record.get("status") != "evaluated":
                    continue
                metrics = axis_record.get("metrics") or {}
                rows.append(
                    {
                        "dataset": dataset,
                        "split": split,
                        "axis": axis,
                        "support": axis_record.get("support"),
                        "positive_count": axis_record.get("positive_count"),
                        "accuracy": metrics.get("accuracy"),
                        "macro_f1": metrics.get("macro_f1"),
                        "pr_auc": axis_record.get("pr_auc"),
                        "ece": axis_record.get("ece"),
                    }
                )
    return rows


def evaluate_dataset(dataset: str, *, case_dir: Path, output_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    cases, source_path = load_dataset_cases(dataset, case_dir, args)
    if not cases:
        return {
            "dataset": dataset,
            "status": "skipped",
            "skip_reason": f"case source missing or empty: {source_path}",
        }
    split_cases, split_policy = build_splits(dataset, cases, args.random_state)
    split_cases = cap_taxonomy_splits(split_cases, args.max_cases_per_split, dataset)
    split_status = validate_taxonomy_splits(split_cases, dataset)
    if split_status:
        return {"dataset": dataset, "status": "skipped", "skip_reason": split_status, "split_policy": split_policy}
    train = split_cases["train"]
    validation = split_cases["validation"]
    test = split_cases["test"]
    result: dict[str, Any] = {
        "dataset": dataset,
        "status": "evaluated",
        "source_path": source_path,
        "split_policy": split_policy,
        "split_counts": {split: len(rows) for split, rows in split_cases.items()},
        "taxonomy": {
            "main_axes": list(MAIN_AXIS_ORDER),
            "fine_labels": list(FINE_LABEL_ORDER),
            "stance_aux": STANCE_AXIS,
        },
    }
    if args.encoder_backend == "xlm-r":
        result["joint_model"] = train_xlmr_joint(train, validation, test, args=args)
        return result
    axis_results = {
        axis: train_hash_axis(axis, train, validation, test, args=args)
        for axis in MAIN_AXIS_ORDER
    }
    result["axis_models"] = axis_results
    prediction_rows = []
    for axis_result in axis_results.values():
        prediction_rows.extend(axis_result.get("test_predictions") or [])
    prediction_path = output_dir / f"{dataset}_taxonomy_student_predictions.jsonl"
    write_jsonl(prediction_path, prediction_rows)
    result["prediction_path"] = str(prediction_path)
    return result


def main() -> int:
    started = perf_counter()
    parser = argparse.ArgumentParser(description="Run taxonomy-first textified Review Student SFT.")
    parser.add_argument("--case-dir", default=r"G:\CISCN\.tmp\kt3_post_cases_full")
    parser.add_argument("--output-dir", default=r"G:\CISCN\.tmp\review_taxonomy_student")
    parser.add_argument("--datasets", nargs="*", default=DEFAULT_DATASETS)
    parser.add_argument("--encoder-backend", choices=["hash", "xlm-r"], default="hash")
    parser.add_argument("--training-scope", choices=["per-dataset", "joint"], default="per-dataset")
    parser.add_argument("--backbone", default="xlm-r-base")
    parser.add_argument("--hf-cache-dir", default=r"G:\CISCN\hf_models")
    parser.add_argument("--hatecot-csv", default=r"G:\CISCN\dataset\HateCoT\hatecot_final_D3.csv")
    parser.add_argument("--weibo21-dir", default=r"G:\CISCN\dataset\weibo21")
    parser.add_argument("--allow-model-download", action="store_true")
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--max-cases-per-split", type=int, default=80)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--hidden-dim", type=int, default=128)
    parser.add_argument("--hash-dim", type=int, default=512)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--stance-weight", type=float, default=0.1)
    parser.add_argument("--fine-label-weight", type=float, default=0.2)
    parser.add_argument("--enable-lrkd", action="store_true")
    parser.add_argument("--lrkd-weight", type=float, default=0.2)
    parser.add_argument(
        "--rationale-encoder-backend",
        choices=["hash", "hf-transformer", "sentence-transformer", "auto"],
        default="hash",
    )
    parser.add_argument("--rationale-encoder-model", default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    parser.add_argument("--rationale-dim", type=int, default=768)
    parser.add_argument("--rationale-max-length", type=int, default=256)
    parser.add_argument("--rationale-pooling", choices=["cls", "mean"], default="mean")
    parser.add_argument("--device", default=None)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "schema": "review-taxonomy-student-run-v1",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "method": {
            "task_definition": "taxonomy-first textified Student SFT",
            "input_fields": ["TEXT", "HASHTAGS", "OCR", "ASR", "CAPTION", "CLAIM_CONTEXT"],
            "scope": "interpersonal/aggression and ideological/deception axes",
            "excluded": ["raw image/video encoder", "hard-case mining", "Teacher distillation", "defer learning"],
            "lrkd_scope": "optional dataset-explanation LRKD for HateCoT-style samples only",
        },
        "parameters": vars(args),
        "datasets": {},
    }
    if args.training_scope == "joint":
        try:
            joint_result = evaluate_joint_training(case_dir=Path(args.case_dir), args=args)
            report["joint_training"] = joint_result
            report["datasets"] = (joint_result.get("joint_model") or {}).get("datasets") or {}
            for dataset, prepared in (joint_result.get("prepared") or {}).items():
                if dataset not in report["datasets"]:
                    report["datasets"][dataset] = prepared
        except Exception as error:  # pragma: no cover - report operational failures
            report["joint_training"] = {
                "status": "failed",
                "error_class": error.__class__.__name__,
                "error": str(error),
            }
    else:
        for dataset in args.datasets:
            try:
                report["datasets"][dataset] = evaluate_dataset(
                    dataset,
                    case_dir=Path(args.case_dir),
                    output_dir=output_dir,
                    args=args,
                )
            except Exception as error:  # pragma: no cover - report operational failures
                report["datasets"][dataset] = {
                    "dataset": dataset,
                    "status": "failed",
                    "error_class": error.__class__.__name__,
                    "error": str(error),
                }
    report["completed_at"] = datetime.now(timezone.utc).isoformat()
    report["duration_seconds"] = round(perf_counter() - started, 6)
    report["summary"] = {
        "evaluated": sorted(
            dataset
            for dataset, result in report["datasets"].items()
            if isinstance(result, Mapping) and result.get("status") == "evaluated"
        ),
        "skipped_or_failed": {
            dataset: result.get("skip_reason") or result.get("error") or result.get("status")
            for dataset, result in report["datasets"].items()
            if not (isinstance(result, Mapping) and result.get("status") == "evaluated")
        },
        "axis_metrics": summarize_axis_metrics(report["datasets"]),
    }
    (output_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return 0 if report["summary"]["evaluated"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
