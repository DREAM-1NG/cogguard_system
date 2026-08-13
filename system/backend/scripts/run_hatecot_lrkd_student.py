"""Run full HateCoT LRKD rationale-space alignment for Review Student.

This runner is intentionally scoped to HateCoT. It trains an XLM-R text Student
with classification supervision plus dataset-explanation vector alignment, then
evaluates whether projected Student rationale vectors can retrieve similar
HateCoT explanations at inference time.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping

import numpy as np
from sklearn.metrics import accuracy_score, average_precision_score, f1_score
from sklearn.model_selection import train_test_split

# Keep explanation encoding on the PyTorch path. Some local environments have
# TensorFlow + Keras 3 installed, which makes transformers imports fail unless
# TF support is explicitly disabled before sentence-transformers is imported.
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from app.core.review.taxonomy_student import (  # noqa: E402
    INTERPERSONAL_AXIS,
    TextifiedStudentLoss,
    XLMRTextifiedReviewStudent,
    build_textified_student_batch,
    normalize_rationale_projection,
    predict_rationale_projection,
)
from app.core.review.trainable_post import (  # noqa: E402
    encode_text_features,
    expected_calibration_error,
    require_torch,
    resolve_torch_device,
)
from run_review_taxonomy_student import _axis_metrics, select_threshold_by_macro_f1  # noqa: E402


HATECOT_NEGATIVE_LABELS = {"benign", "neutral", "normal", "not hate", "not hate speech", "not offensive"}
DEFAULT_BACKBONE = "FacebookAI/xlm-roberta-base"
DEFAULT_RATIONALE_ENCODER = DEFAULT_BACKBONE


def load_hatecot_csv_full(path: Path) -> list[dict[str, Any]]:
    """Load full HateCoT CSV while preserving explanation metadata."""

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader):
            text = _clean(row.get("post"))
            explanation = _clean(row.get("explanation"))
            raw_label = _clean(row.get("label"))
            if not text or not explanation or not raw_label:
                continue
            binary_label = 0 if raw_label.lower() in HATECOT_NEGATIVE_LABELS else 1
            normalized_label = "normal" if binary_label == 0 else "hate"
            rows.append(
                {
                    "case_id": _clean(row.get("uid") or row.get("id")) or f"hatecot-{index}",
                    "dataset": "HateCoT",
                    "text": text,
                    "explanation": explanation,
                    "domain": _clean(row.get("domain")),
                    "target": _clean(row.get("target")),
                    "source_label": raw_label,
                    "binary_label": binary_label,
                    "labels": {
                        "label": normalized_label,
                        "raw_label": normalized_label,
                        "source_label": raw_label,
                        "target_groups": [_clean(row.get("target"))] if _clean(row.get("target")) else [],
                    },
                }
            )
    return rows


def split_hatecot(
    rows: list[dict[str, Any]],
    *,
    random_state: int = 42,
    max_cases_per_split: int = 0,
) -> dict[str, list[dict[str, Any]]]:
    labels = np.asarray([row["binary_label"] for row in rows], dtype="int64")
    train_rows, heldout_rows, train_y, heldout_y = train_test_split(
        rows,
        labels,
        test_size=0.30,
        random_state=random_state,
        stratify=labels,
    )
    validation_rows, test_rows = train_test_split(
        heldout_rows,
        test_size=0.50,
        random_state=random_state,
        stratify=heldout_y,
    )
    splits = {
        "train": _mark_split(train_rows, "train"),
        "validation": _mark_split(validation_rows, "validation"),
        "test": _mark_split(test_rows, "test"),
    }
    if max_cases_per_split > 0:
        splits = {
            split: _balanced_cap(split_rows, max_cases_per_split)
            for split, split_rows in splits.items()
        }
    _validate_splits(splits)
    return splits


def encode_explanations(rows: list[dict[str, Any]], *, args: argparse.Namespace, cache_path: Path) -> np.ndarray:
    """Encode explanations and cache vectors by case/order fingerprint."""

    cache_meta_path = cache_path.with_suffix(".meta.json")
    fingerprint = _rows_fingerprint(rows, extra={
        "backend": args.rationale_encoder_backend,
        "model": args.rationale_encoder_model,
        "dim": args.rationale_dim,
        "max_length": args.rationale_max_length,
        "pooling": args.rationale_pooling,
    })
    if cache_path.exists() and cache_meta_path.exists():
        try:
            metadata = json.loads(cache_meta_path.read_text(encoding="utf-8"))
            if metadata.get("fingerprint") == fingerprint:
                return np.load(cache_path).astype("float32")
        except Exception:
            pass
    features = _encode_rationale_features([row["explanation"] for row in rows], args=args)
    vectors = _normalize_np(features.matrix.astype("float32"))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(cache_path, vectors)
    cache_meta_path.write_text(
        json.dumps(
            {
                "schema": "hatecot-rationale-vector-cache-v1",
                "fingerprint": fingerprint,
                "row_count": len(rows),
                "shape": list(vectors.shape),
                "feature_backend": features.backend,
                "model_name": features.model_name,
                "capability_boundary": features.capability_boundary,
                "requested_backend": args.rationale_encoder_backend,
                "requested_model": args.rationale_encoder_model,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return vectors


def _encode_rationale_features(texts: list[str], *, args: argparse.Namespace) -> Any:
    try:
        return encode_text_features(
            texts,
            backend=args.rationale_encoder_backend,
            model_name=args.rationale_encoder_model,
            cache_dir=args.hf_cache_dir,
            batch_size=args.rationale_batch_size,
            local_files_only=not args.allow_model_download,
            max_length=args.rationale_max_length,
            pooling=args.rationale_pooling,
            dim=args.rationale_dim,
        )
    except Exception:
        if str(args.rationale_encoder_backend) != "sentence-transformer":
            raise
        # The local MiniLM cache may be metadata-only or TF-only. Fall back to
        # the already-cached XLM-R PyTorch encoder and make that provenance
        # explicit in the vector-cache metadata/report.
        return encode_text_features(
            texts,
            backend="hf-transformer",
            model_name=args.backbone,
            cache_dir=args.hf_cache_dir,
            batch_size=args.rationale_batch_size,
            local_files_only=not args.allow_model_download,
            max_length=args.rationale_max_length,
            pooling=args.rationale_pooling,
            dim=args.rationale_dim,
        )


def build_reason_bank(train_rows: list[dict[str, Any]], vectors: np.ndarray) -> dict[str, Any]:
    if len(train_rows) != int(vectors.shape[0]):
        raise ValueError("train row count must match rationale vector count")
    return {
        "vectors": _normalize_np(vectors.astype("float32")),
        "metadata": [
            {
                "case_id": row["case_id"],
                "split": "train",
                "label": int(row["binary_label"]),
                "source_label": row.get("source_label", ""),
                "domain": row.get("domain", ""),
                "target": row.get("target", ""),
                "explanation": row.get("explanation", ""),
                "text": row.get("text", ""),
            }
            for row in train_rows
        ],
    }


def retrieve_nearest_reasons(
    query_vector: np.ndarray,
    bank: Mapping[str, Any],
    *,
    top_k: int = 3,
    exclude_case_id: str = "",
) -> list[dict[str, Any]]:
    vectors = np.asarray(bank["vectors"], dtype="float32")
    if vectors.size == 0:
        return []
    query = _normalize_np(np.asarray(query_vector, dtype="float32").reshape(1, -1))[0]
    scores = vectors @ query
    metadata = list(bank["metadata"])
    if exclude_case_id:
        for index, row in enumerate(metadata):
            if str(row.get("case_id")) == str(exclude_case_id):
                scores[index] = -np.inf
    order = np.argsort(-scores)[: max(1, top_k)]
    results = []
    for index in order:
        if not np.isfinite(scores[index]):
            continue
        row = dict(metadata[int(index)])
        row["similarity"] = round(float(scores[index]), 6)
        results.append(row)
    return results


def evaluate_reason_retrieval(
    cases: list[dict[str, Any]],
    projected_vectors: np.ndarray,
    bank: Mapping[str, Any],
    *,
    top_k: int = 3,
    max_examples: int = 50,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    top1_label_hits = 0
    topk_majority_hits = 0
    same_domain_total = 0
    same_domain_hits = 0
    target_total = 0
    target_hits = 0
    examples = []
    for case, vector in zip(cases, projected_vectors):
        retrieved = retrieve_nearest_reasons(
            vector,
            bank,
            top_k=top_k,
            exclude_case_id=str(case.get("case_id") or ""),
        )
        if not retrieved:
            continue
        gold_label = int(case["binary_label"])
        if int(retrieved[0].get("label", -1)) == gold_label:
            top1_label_hits += 1
        majority = _majority_label([int(row.get("label", -1)) for row in retrieved])
        if majority == gold_label:
            topk_majority_hits += 1
        domain = str(case.get("domain") or "")
        if domain:
            for row in retrieved:
                same_domain_total += 1
                if str(row.get("domain") or "") == domain:
                    same_domain_hits += 1
        target = str(case.get("target") or "")
        if target:
            for row in retrieved:
                target_total += 1
                if str(row.get("target") or "") == target:
                    target_hits += 1
        if len(examples) < max_examples:
            examples.append(
                {
                    "case_id": case.get("case_id"),
                    "input_text": case.get("text"),
                    "gold_label": gold_label,
                    "source_label": case.get("source_label"),
                    "domain": case.get("domain"),
                    "target": case.get("target"),
                    "gold_explanation": case.get("explanation"),
                    "retrieved_reasons": retrieved,
                }
            )
    support = min(len(cases), int(projected_vectors.shape[0]))
    return (
        {
            "support": support,
            "top_k": top_k,
            "top1_label_consistency": _safe_rate(top1_label_hits, support),
            "topk_majority_label_consistency": _safe_rate(topk_majority_hits, support),
            "topk_same_domain_rate": _safe_rate(same_domain_hits, same_domain_total),
            "topk_target_consistency_when_present": _safe_rate(target_hits, target_total),
            "target_support": target_total,
        },
        examples,
    )


def train_hatecot_lrkd(
    splits: dict[str, list[dict[str, Any]]],
    rationale_vectors: dict[str, np.ndarray],
    *,
    args: argparse.Namespace,
) -> tuple[Any, Any, dict[str, Any]]:
    require_torch()
    import torch
    from transformers import AutoTokenizer

    device = resolve_torch_device(args.device)
    tokenizer = AutoTokenizer.from_pretrained(
        args.backbone,
        cache_dir=args.hf_cache_dir or None,
        local_files_only=not args.allow_model_download,
        use_fast=True,
    )
    model = XLMRTextifiedReviewStudent(
        args.backbone,
        rationale_dim=int(rationale_vectors["train"].shape[1]),
        cache_dir=args.hf_cache_dir or None,
        local_files_only=not args.allow_model_download,
    ).to(device)
    if bool(getattr(args, "gradient_checkpointing", False)):
        model.backbone.gradient_checkpointing_enable()
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    criterion = TextifiedStudentLoss(
        stance_weight=0.0,
        fine_label_weight=0.0,
        lrkd_weight=args.lrkd_weight,
    )
    train_batch = build_textified_student_batch(splits["train"])
    tokenized_train = prepare_tokenized_text_batch(
        splits["train"], tokenizer, max_length=args.max_length
    )
    train_batch["teacher_vector"] = rationale_vectors["train"]
    train_batch["teacher_vector_mask"] = np.ones((len(splits["train"]),), dtype="float32")
    history = []
    train_count = len(splits["train"])
    accumulation_steps = max(1, int(getattr(args, "gradient_accumulation_steps", 1)))
    use_amp = bool(getattr(args, "fp16", False)) and str(device).startswith("cuda")
    scaler = torch.cuda.amp.GradScaler(enabled=use_amp)
    for epoch in range(max(1, args.epochs)):
        model.train()
        # Keep indices on CPU because the pre-tokenized batch is CPU-resident;
        # only the selected mini-batch is transferred to the GPU.
        order = torch.randperm(train_count)
        losses = []
        cls_losses = []
        lrkd_losses = []
        batch_starts = list(range(0, train_count, max(1, args.batch_size)))
        optimizer.zero_grad(set_to_none=True)
        for batch_index, start in enumerate(batch_starts):
            idx_tensor = order[start : start + args.batch_size]
            idx = idx_tensor.detach().cpu().numpy().astype(int).tolist()
            encoded = {
                key: value[idx_tensor].to(device)
                for key, value in tokenized_train.items()
            }
            targets = _hatecot_targets(train_batch, idx, device)
            with torch.cuda.amp.autocast(enabled=use_amp):
                outputs = model(**encoded)
                outputs["rationale_proj"] = normalize_rationale_projection(outputs["rationale_proj"])
                loss_record = criterion(outputs, targets)
                scaled_loss = loss_record["total_loss"] / accumulation_steps
            scaler.scale(scaled_loss).backward()
            if should_step_optimizer(
                batch_index=batch_index,
                batch_count=len(batch_starts),
                gradient_accumulation_steps=accumulation_steps,
            ):
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad(set_to_none=True)
            losses.append(float(loss_record["total_loss"].detach().cpu()))
            cls_losses.append(float(loss_record[INTERPERSONAL_AXIS].detach().cpu()))
            lrkd_losses.append(float(loss_record["lrkd"].detach().cpu()))
        validation = evaluate_classifier(model, tokenizer, splits["validation"], args=args, device=device)
        history.append(
            {
                "epoch": epoch + 1,
                "loss": round(float(np.mean(losses)), 6),
                "classification_loss": round(float(np.mean(cls_losses)), 6),
                "lrkd_loss": round(float(np.mean(lrkd_losses)), 6),
                "validation_macro_f1": validation["classification_metrics"]["metrics"].get("macro_f1"),
            }
        )
        if bool(getattr(args, "save_epoch_checkpoints", False)):
            checkpoint_dir = Path(getattr(args, "output_dir", "."))
            write_epoch_checkpoint(
                checkpoint_dir / f"checkpoint_epoch_{epoch + 1}.pt",
                model_state_dict=model.state_dict(),
                args=args,
                train_info={
                    "history": history,
                    "lrkd_valid_count": train_count,
                    "rationale_dim": int(rationale_vectors["train"].shape[1]),
                    "epoch": epoch + 1,
                },
                threshold=float(validation["threshold"]),
                validation_metrics=validation["classification_metrics"],
            )
    return model, tokenizer, {
        "history": history,
        "lrkd_valid_count": train_count,
        "rationale_dim": int(rationale_vectors["train"].shape[1]),
    }


def evaluate_classifier(model: Any, tokenizer: Any, cases: list[dict[str, Any]], *, args: argparse.Namespace, device: str) -> dict[str, Any]:
    probabilities, labels = predict_probabilities(model, tokenizer, cases, args=args, device=device)
    threshold_record = select_threshold_by_macro_f1(labels, probabilities)
    threshold = float(threshold_record["threshold"])
    return {
        "threshold": threshold,
        "threshold_selection": threshold_record,
        "classification_metrics": _axis_metrics(labels, probabilities, threshold=threshold),
        "probabilities": probabilities,
        "labels": labels,
    }


def predict_probabilities(model: Any, tokenizer: Any, cases: list[dict[str, Any]], *, args: argparse.Namespace, device: str) -> tuple[np.ndarray, np.ndarray]:
    require_torch()
    import torch

    batch = build_textified_student_batch(cases)
    probabilities = []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(cases), max(1, args.batch_size)):
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
    labels = np.asarray([case["binary_label"] for case in cases], dtype="float32")
    return np.asarray(probabilities, dtype="float32"), labels


def evaluate_alignment(projected: np.ndarray, gold_vectors: np.ndarray, labels: np.ndarray) -> dict[str, Any]:
    projected = _normalize_np(projected)
    gold_vectors = _normalize_np(gold_vectors)
    cosine = np.sum(projected * gold_vectors, axis=1) if len(projected) else np.asarray([], dtype="float32")
    label_values = labels.astype(int)
    same_class = []
    diff_class = []
    sample_count = min(len(gold_vectors), 1000)
    for i in range(sample_count):
        row_scores = gold_vectors[:sample_count] @ projected[i]
        for j, score in enumerate(row_scores):
            if i == j:
                continue
            if label_values[i] == label_values[j]:
                same_class.append(float(score))
            else:
                diff_class.append(float(score))
    return {
        "support": int(len(cosine)),
        "mean_gold_cosine": round(float(np.mean(cosine)), 6) if cosine.size else None,
        "median_gold_cosine": round(float(np.median(cosine)), 6) if cosine.size else None,
        "same_class_mean_cosine_sampled": round(float(np.mean(same_class)), 6) if same_class else None,
        "different_class_mean_cosine_sampled": round(float(np.mean(diff_class)), 6) if diff_class else None,
        "sampled_pair_count": int(len(same_class) + len(diff_class)),
    }


def write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":"), default=str) + "\n")


def main() -> int:
    started = perf_counter()
    parser = argparse.ArgumentParser(description="Run full HateCoT LRKD rationale alignment.")
    parser.add_argument("--hatecot-csv", default=r"G:\CISCN\dataset\HateCoT\hatecot_final_D3.csv")
    parser.add_argument("--output-dir", default=r"G:\CISCN\.tmp\hatecot_lrkd_student")
    parser.add_argument("--backbone", default=DEFAULT_BACKBONE)
    parser.add_argument("--hf-cache-dir", default=r"G:\CISCN\hf_models")
    parser.add_argument("--allow-model-download", action="store_true")
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--max-cases-per-split", type=int, default=0)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--lrkd-weight", type=float, default=0.2)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=1)
    parser.add_argument("--fp16", action="store_true")
    parser.add_argument("--gradient-checkpointing", action="store_true")
    parser.add_argument("--save-epoch-checkpoints", action="store_true")
    parser.add_argument("--rationale-encoder-backend", choices=["sentence-transformer", "hf-transformer", "auto"], default="hf-transformer")
    parser.add_argument("--rationale-encoder-model", default=DEFAULT_RATIONALE_ENCODER)
    parser.add_argument("--rationale-dim", type=int, default=768)
    parser.add_argument("--rationale-max-length", type=int, default=256)
    parser.add_argument("--rationale-pooling", choices=["cls", "mean"], default="mean")
    parser.add_argument("--rationale-batch-size", type=int, default=32)
    parser.add_argument("--reason-top-k", type=int, default=3)
    parser.add_argument("--max-reason-examples", type=int, default=50)
    parser.add_argument("--save-checkpoint", action="store_true")
    parser.add_argument("--device", default=None)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    args.output_dir = str(output_dir)
    rows = load_hatecot_csv_full(Path(args.hatecot_csv))
    splits = split_hatecot(rows, random_state=args.random_state, max_cases_per_split=args.max_cases_per_split)
    rationale_vectors = {
        split: encode_explanations(
            split_rows,
            args=args,
            cache_path=output_dir / f"{split}_rationale_vectors.npy",
        )
        for split, split_rows in splits.items()
    }
    model, tokenizer, train_info = train_hatecot_lrkd(splits, rationale_vectors, args=args)
    device = resolve_torch_device(args.device)
    validation_eval = evaluate_classifier(model, tokenizer, splits["validation"], args=args, device=device)
    test_probabilities, test_labels = predict_probabilities(model, tokenizer, splits["test"], args=args, device=device)
    threshold = float(validation_eval["threshold"])
    classification_metrics = _classification_summary(test_labels, test_probabilities, threshold=threshold)
    test_projection = predict_rationale_projection(
        model,
        tokenizer,
        build_textified_student_batch(splits["test"])["texts"],
        batch_size=args.batch_size,
        max_length=args.max_length,
        device=device,
    )
    alignment_metrics = evaluate_alignment(test_projection, rationale_vectors["test"], test_labels)
    reason_bank = build_reason_bank(splits["train"], rationale_vectors["train"])
    retrieval_metrics, reason_examples = evaluate_reason_retrieval(
        splits["test"],
        test_projection,
        reason_bank,
        top_k=args.reason_top_k,
        max_examples=args.max_reason_examples,
    )
    for example in reason_examples:
        case_id = example["case_id"]
        index = next((i for i, row in enumerate(splits["test"]) if row["case_id"] == case_id), None)
        if index is not None:
            example["predicted_probability"] = round(float(test_probabilities[index]), 6)
    test_predictions = [
        {
            "case_id": row["case_id"],
            "gold_label": int(row["binary_label"]),
            "predicted_probability": round(float(probability), 6),
            "predicted_label": int(float(probability) >= threshold),
            "domain": row.get("domain"),
            "target": row.get("target"),
        }
        for row, probability in zip(splits["test"], test_probabilities)
    ]
    write_jsonl(output_dir / "reason_examples.jsonl", reason_examples)
    write_jsonl(output_dir / "test_predictions.jsonl", test_predictions)
    (output_dir / "rationale_bank_meta.json").write_text(
        json.dumps(
            {
                "schema": "hatecot-rationale-bank-meta-v1",
                "source_split": "train",
                "row_count": len(reason_bank["metadata"]),
                "vector_shape": list(reason_bank["vectors"].shape),
                "leakage_policy": "train_split_only_reason_bank",
                "top_k": args.reason_top_k,
                "metadata_preview": reason_bank["metadata"][:3],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    if args.save_checkpoint:
        import torch

        torch.save(
            build_checkpoint_payload(
                args=args,
                model_state_dict=model.state_dict(),
                train_info=train_info,
                threshold=threshold,
                validation_metrics=validation_eval["classification_metrics"],
            ),
            output_dir / "checkpoint.pt",
        )
    report = {
        "schema": "hatecot-lrkd-student-run-v1",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(perf_counter() - started, 6),
        "run_config": vars(args),
        "dataset": {
            "name": "HateCoT",
            "source": str(Path(args.hatecot_csv)),
            "loaded_rows": len(rows),
            "split_counts": {split: len(split_rows) for split, split_rows in splits.items()},
            "label_counts": {
                split: dict(Counter(int(row["binary_label"]) for row in split_rows))
                for split, split_rows in splits.items()
            },
            "explanation_supervision": "dataset-provided/generated explanation supervision, not human gold token rationales",
        },
        "train": train_info,
        "validation": {
            "threshold": threshold,
            "classification_metrics": validation_eval["classification_metrics"],
        },
        "classification_metrics": classification_metrics,
        "alignment_metrics": alignment_metrics,
        "reason_retrieval_metrics": retrieval_metrics,
        "qualitative_reason_examples_path": str(output_dir / "reason_examples.jsonl"),
        "test_predictions_path": str(output_dir / "test_predictions.jsonl"),
        "rationale_bank_meta_path": str(output_dir / "rationale_bank_meta.json"),
    }
    (output_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return 0


def build_checkpoint_payload(
    *,
    args: argparse.Namespace,
    model_state_dict: Mapping[str, Any],
    train_info: Mapping[str, Any],
    threshold: float,
    validation_metrics: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a portable checkpoint payload for downstream transfer evaluation."""

    return {
        "schema": "hatecot-lrkd-student-checkpoint-v1",
        "model_state_dict": model_state_dict,
        "model_config": {
            "backbone": str(args.backbone),
            "hf_cache_dir": str(args.hf_cache_dir or ""),
            "allow_model_download": bool(args.allow_model_download),
            "max_length": int(args.max_length),
            "rationale_dim": int(args.rationale_dim),
        },
        "decision_threshold": round(float(threshold), 6),
        "train_info": dict(train_info),
        "validation_metrics": dict(validation_metrics),
    }


def prepare_tokenized_text_batch(
    cases: list[dict[str, Any]],
    tokenizer: Any,
    *,
    max_length: int,
) -> dict[str, Any]:
    """Tokenize a fixed training split once so every epoch reuses the inputs."""

    require_torch()
    encoded = tokenizer(
        build_textified_student_batch(cases)["texts"],
        padding="max_length",
        truncation=True,
        max_length=max_length,
        return_tensors="pt",
    )
    return {key: value for key, value in encoded.items()}


def write_epoch_checkpoint(
    path: Path,
    *,
    model_state_dict: Mapping[str, Any],
    args: argparse.Namespace,
    train_info: Mapping[str, Any],
    threshold: float,
    validation_metrics: Mapping[str, Any],
) -> None:
    require_torch()
    import torch

    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        build_checkpoint_payload(
            args=args,
            model_state_dict=model_state_dict,
            train_info=train_info,
            threshold=threshold,
            validation_metrics=validation_metrics,
        ),
        path,
    )


def load_checkpoint_payload(path: Path) -> dict[str, Any]:
    require_torch()
    import torch

    return torch.load(path, map_location="cpu")


def should_step_optimizer(*, batch_index: int, batch_count: int, gradient_accumulation_steps: int) -> bool:
    steps = max(1, int(gradient_accumulation_steps))
    return ((int(batch_index) + 1) % steps == 0) or (int(batch_index) + 1 >= int(batch_count))


def _classification_summary(labels: np.ndarray, probabilities: np.ndarray, *, threshold: float) -> dict[str, Any]:
    predicted = (probabilities >= threshold).astype(int)
    labels_int = labels.astype(int)
    try:
        pr_auc = float(average_precision_score(labels_int, probabilities))
    except ValueError:
        pr_auc = 0.0
    return {
        "threshold": round(float(threshold), 6),
        "support": int(labels.size),
        "positive_count": int(labels_int.sum()),
        "accuracy": round(float(accuracy_score(labels_int, predicted)), 6),
        "macro_f1": round(float(f1_score(labels_int, predicted, average="macro", zero_division=0)), 6),
        "pr_auc": round(pr_auc, 6),
        "ece": expected_calibration_error(labels_int, probabilities),
    }


def _hatecot_targets(batch: Mapping[str, Any], idx: list[int], device: str) -> dict[str, Any]:
    import torch

    labels = batch["labels"]
    task_mask = batch["task_mask"]
    return {
        INTERPERSONAL_AXIS: torch.as_tensor(labels[INTERPERSONAL_AXIS][idx], dtype=torch.float32, device=device),
        f"{INTERPERSONAL_AXIS}_mask": torch.as_tensor(task_mask[INTERPERSONAL_AXIS][idx], dtype=torch.float32, device=device),
        "ideological_deception": torch.zeros((len(idx),), dtype=torch.float32, device=device),
        "ideological_deception_mask": torch.zeros((len(idx),), dtype=torch.float32, device=device),
        "stance": torch.zeros((len(idx),), dtype=torch.long, device=device),
        "stance_mask": torch.zeros((len(idx),), dtype=torch.float32, device=device),
        "fine_labels": torch.as_tensor(labels["fine_labels"][idx], dtype=torch.float32, device=device),
        "fine_labels_mask": torch.zeros((len(idx),), dtype=torch.float32, device=device),
        "teacher_vector": torch.as_tensor(batch["teacher_vector"][idx], dtype=torch.float32, device=device),
        "teacher_vector_mask": torch.as_tensor(batch["teacher_vector_mask"][idx], dtype=torch.float32, device=device),
    }


def _mark_split(rows: list[dict[str, Any]], split: str) -> list[dict[str, Any]]:
    return [{**row, "split": split} for row in rows]


def _balanced_cap(rows: list[dict[str, Any]], max_cases: int) -> list[dict[str, Any]]:
    positives = [row for row in rows if int(row["binary_label"]) == 1]
    negatives = [row for row in rows if int(row["binary_label"]) == 0]
    each = max(1, max_cases // 2)
    return (positives[:each] + negatives[:each])[:max_cases]


def _validate_splits(splits: Mapping[str, list[dict[str, Any]]]) -> None:
    for split, rows in splits.items():
        labels = {int(row["binary_label"]) for row in rows}
        if labels != {0, 1}:
            raise ValueError(f"{split} split must contain both binary labels")


def _rows_fingerprint(rows: list[dict[str, Any]], *, extra: Mapping[str, Any]) -> str:
    import hashlib

    payload = {
        "case_ids": [row.get("case_id") for row in rows],
        "explanations": [row.get("explanation") for row in rows],
        "extra": dict(extra),
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _normalize_np(matrix: np.ndarray) -> np.ndarray:
    matrix = np.asarray(matrix, dtype="float32")
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    norm = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.maximum(norm, 1e-12)


def _majority_label(labels: list[int]) -> int:
    valid = [label for label in labels if label in {0, 1}]
    if not valid:
        return -1
    counts = Counter(valid)
    return 1 if counts[1] >= counts[0] else 0


def _safe_rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(float(numerator) / float(denominator), 6)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


if __name__ == "__main__":
    raise SystemExit(main())
