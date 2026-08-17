"""Run HateCoT-aligned three-class transfer and target adaptation experiments.

This runner keeps the published HateCoT protocol distinct from CogGuard's
production binary heads.  The XLM-R source model is an encoder transfer
baseline; it is not the prompt-based LLaMA zero-shot method from the paper.
"""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import random
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Iterable, Mapping

import numpy as np
from sklearn.metrics import accuracy_score, average_precision_score, confusion_matrix, f1_score

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from app.core.review.taxonomy_student import (  # noqa: E402
    INTERPERSONAL_AXIS,
    PROTOCOL_HEAD_DIMS,
    XLMRTextifiedReviewStudent,
    build_textified_input,
    require_torch,
)
from app.core.review.trainable_post import resolve_torch_device  # noqa: E402


PROTOCOL_SCHEMA = "hatecot-official-transfer-student-v1"
SOURCE_LABEL_MAPPING_VERSION = "hatecot-source-3way-v1"
TARGET_LABEL_MAPPING_VERSION = "hatecot-target-labels-v1"
TARGET_SPECS = {
    "HateCheck": {
        "classes": 2,
        "class_names": ["Non-hateful", "Hateful"],
        "head": "hatecheck_binary",
        "source_transfer": "hatecheck_binary",
    },
    "HateXplain": {
        "classes": 3,
        "class_names": ["Normal", "Offensive", "Hate"],
        "head": "hatexplain_3way",
        "source_transfer": "hatecot_universal_3way",
    },
    "Latent_Hate": {
        "classes": 3,
        "class_names": ["Not Hate", "Explicit Hate", "Implicit Hate"],
        "head": "latent_hate_3way",
        "source_transfer": "latent_hate_3way",
    },
}
DEFAULT_LATENT_HATE_PATH = (
    r"G:\CISCN\dataset\implicit-hate-corpus\implicit_hate_v1_stg1_posts.tsv"
    if Path(r"G:\CISCN\dataset\implicit-hate-corpus\implicit_hate_v1_stg1_posts.tsv").exists()
    else r"G:\CISCN\.tmp\hatecot_transfer_datasets\implicit_hate_v1_stg1_posts.tsv"
)

_SOURCE_LABELS = {
    "normal": 0,
    "benign": 0,
    "neutral": 0,
    "not hate": 0,
    "not hate speech": 0,
    "not offensive": 0,
    "offensive": 1,
    "toxic": 1,
    "derogation": 1,
    "person directed abuse": 1,
    "hate": 2,
    "hateful": 2,
    "hate speech": 2,
    "identity directed abuse": 2,
    "affiliation directed abuse": 2,
    "dehumanization": 2,
}
_AMBIGUOUS_SOURCE_LABELS = {"animosity", "threatening", "support"}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normal_label(value: Any) -> str:
    return _clean(value).lower().replace("-", " ").replace("_", " ")


def map_hatecot_protocol_label(label: Any) -> int | None:
    """Map only source labels whose semantics are stable in HateCoT's 3-way space."""

    normalized = _normal_label(label)
    if normalized in _AMBIGUOUS_SOURCE_LABELS:
        return None
    return _SOURCE_LABELS.get(normalized)


def map_target_label(dataset: str, label: Any) -> int | None:
    normalized = _normal_label(label)
    if dataset == "HateCheck":
        return {"non hateful": 0, "hateful": 1}.get(normalized)
    if dataset == "HateXplain":
        return {
            "normal": 0,
            "offensive": 1,
            "hate speech": 2,
            "hatespeech": 2,
            "hate": 2,
        }.get(normalized)
    if dataset == "Latent_Hate":
        return {
            "not hate": 0,
            "explicit hate": 1,
            "implicit hate": 2,
            "not hate speech": 0,
        }.get(normalized)
    raise ValueError(f"unsupported target dataset: {dataset}")


def source_to_latent_hate_proxy_label(source_label: int) -> int:
    """Map the universal source ontology to the Latent_Hate evaluation order.

    Source ``Offensive`` is only a harm-level proxy for ``Implicit Hate``. The
    report therefore identifies this as ontology-proxy transfer rather than
    direct latent-hate supervision.
    """

    return {0: 0, 1: 2, 2: 1}[int(source_label)]


def protocol_learning_rate(args: argparse.Namespace, *, phase: str) -> float:
    """Return the explicitly configured optimizer rate for a protocol phase."""

    if phase == "source":
        return float(args.source_lr)
    if phase == "target":
        return float(args.target_lr)
    raise ValueError(f"unsupported protocol phase: {phase}")


def seed_experiment(seed: int) -> None:
    """Seed all local RNGs before a paired protocol training run."""

    random.seed(seed)
    np.random.seed(seed)
    require_torch()
    import torch

    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def amp_enabled(args: argparse.Namespace, *, device: str) -> bool:
    """Use float16 autocast only when the caller explicitly targets CUDA."""

    return bool(getattr(args, "amp", False)) and str(device).startswith("cuda")


def paired_trial_seed(random_state: int, dataset: str, trial: str | int) -> int:
    """Derive a stable seed shared by the pretrained and base trial arms."""

    payload = f"{int(random_state)}:{dataset}:{trial}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], byteorder="big")


def reset_protocol_head(model: Any, *, head: str, seed: int) -> None:
    """Give paired target adaptations an identical fresh protocol head."""

    require_torch()
    import torch

    layer = model.protocol_heads[head]
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    layer.reset_parameters()


def source_protocol_checkpoint_path(args: argparse.Namespace) -> Path | None:
    """Return a validated prior source-protocol checkpoint when supplied."""

    raw_path = str(getattr(args, "source_protocol_checkpoint", "") or "").strip()
    if not raw_path:
        return None
    checkpoint = Path(raw_path)
    if not checkpoint.is_file():
        raise ValueError(f"source protocol checkpoint does not exist: {checkpoint}")
    return checkpoint


def save_target_checkpoints(args: argparse.Namespace) -> bool:
    """Allow metric-only runs to avoid serializing each large target model."""

    return bool(getattr(args, "save_target_checkpoints", True))


def target_adamw_kwargs() -> dict[str, bool]:
    """Avoid temporary AdamW buffers on the shared 8 GB GPU."""

    return {"foreach": False, "fused": True}


def release_runtime_memory() -> None:
    """Release completed trial objects before loading another XLM-R copy."""

    gc.collect()
    require_torch()
    import torch

    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def checkpoint_load_kwargs() -> dict[str, Any]:
    """Load local zip checkpoints without materializing a duplicate state dict."""

    return {"map_location": "cpu", "weights_only": False, "mmap": True}


def build_protocol_support_test(
    rows: list[dict[str, Any]],
    *,
    classes: int,
    support_per_class: int,
    test_per_class: int,
    random_state: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rng = np.random.default_rng(random_state)
    support: list[dict[str, Any]] = []
    test: list[dict[str, Any]] = []
    for label in range(classes):
        group = [row for row in rows if int(row["protocol_label"]) == label]
        if len(group) < support_per_class + test_per_class:
            raise ValueError(
                f"class {label} has {len(group)} rows; "
                f"requires {support_per_class + test_per_class}"
            )
        order = rng.permutation(len(group))
        shuffled = [group[int(index)] for index in order]
        support.extend(shuffled[:support_per_class])
        test.extend(shuffled[support_per_class : support_per_class + test_per_class])
    _assert_disjoint(support, test)
    return support, test


def build_protocol_support_from_pool(
    support_pool: list[dict[str, Any]],
    test_pool: list[dict[str, Any]],
    *,
    classes: int,
    support_per_class: int,
    test_per_class: int,
    random_state: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Sample support and test independently when the dataset has official splits."""

    rng = np.random.default_rng(random_state)
    support: list[dict[str, Any]] = []
    test: list[dict[str, Any]] = []
    for label in range(classes):
        support_group = [row for row in support_pool if int(row["protocol_label"]) == label]
        test_group = [row for row in test_pool if int(row["protocol_label"]) == label]
        if len(support_group) < support_per_class or len(test_group) < test_per_class:
            raise ValueError(
                f"class {label} has support/test {len(support_group)}/{len(test_group)}; "
                f"requires {support_per_class}/{test_per_class}"
            )
        support_order = rng.permutation(len(support_group))
        test_order = rng.permutation(len(test_group))
        support.extend(support_group[int(index)] for index in support_order[:support_per_class])
        test.extend(test_group[int(index)] for index in test_order[:test_per_class])
    _assert_disjoint(support, test)
    return support, test


def select_k_shot(
    support: list[dict[str, Any]], *, k: int, classes: int, random_state: int
) -> list[dict[str, Any]]:
    rng = np.random.default_rng(random_state)
    selected: list[dict[str, Any]] = []
    for label in range(classes):
        group = [row for row in support if int(row["protocol_label"]) == label]
        if len(group) < k:
            raise ValueError(f"class {label} has {len(group)} support rows; requires {k}")
        order = rng.permutation(len(group))
        selected.extend(group[int(index)] for index in order[:k])
    return selected


def multiclass_metrics(
    labels: np.ndarray,
    predictions: np.ndarray,
    *,
    class_names: list[str],
    probabilities: np.ndarray | None = None,
) -> dict[str, Any]:
    labels = np.asarray(labels, dtype="int64")
    predictions = np.asarray(predictions, dtype="int64")
    class_ids = list(range(len(class_names)))
    matrix = confusion_matrix(labels, predictions, labels=class_ids).tolist()
    per_class = f1_score(
        labels, predictions, labels=class_ids, average=None, zero_division=0
    )
    macro_pr_auc = None
    if probabilities is not None and probabilities.shape == (len(labels), len(class_names)):
        one_hot = np.eye(len(class_names), dtype="int64")[labels]
        macro_pr_auc = round(float(average_precision_score(one_hot, probabilities, average="macro")), 6)
    return {
        "support": int(labels.size),
        "accuracy": round(float(accuracy_score(labels, predictions)), 6),
        "macro_f1": round(float(f1_score(labels, predictions, average="macro", zero_division=0)), 6),
        "macro_pr_auc": macro_pr_auc,
        "per_class_f1": {
            name: round(float(score), 6) for name, score in zip(class_names, per_class)
        },
        "confusion_matrix": matrix,
        "class_names": class_names,
        "label_distribution": dict(Counter(int(value) for value in labels.tolist())),
    }


def load_hatecot_protocol_rows(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()
    with path.open("r", encoding="utf-8", newline="") as handle:
        for index, raw in enumerate(csv.DictReader(handle)):
            label = map_hatecot_protocol_label(raw.get("label"))
            if label is None:
                skipped[_normal_label(raw.get("label")) or "missing"] += 1
                continue
            rows.append({
                "case_id": _clean(raw.get("uid") or raw.get("id")) or f"hatecot-{index}",
                "dataset": "HateCoT",
                "text": _clean(raw.get("post")),
                "explanation": _clean(raw.get("explanation")),
                "source_label": _clean(raw.get("label")),
                "protocol_label": label,
                "domain": _clean(raw.get("domain")),
                "target": _clean(raw.get("target")),
            })
    return rows, {
        "source": str(path),
        "mapping_version": SOURCE_LABEL_MAPPING_VERSION,
        "loaded_rows": len(rows),
        "skipped_ambiguous_or_unknown": dict(skipped),
    }


def load_hatecheck_protocol_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for index, raw in enumerate(csv.DictReader(handle)):
            label = map_target_label("HateCheck", raw.get("label_gold"))
            text = _clean(raw.get("test_case"))
            if label is None or not text:
                continue
            rows.append({
                "case_id": _clean(raw.get("case_id")) or f"hatecheck-{index}",
                "dataset": "HateCheck",
                "text": text,
                "source_label": _clean(raw.get("label_gold")),
                "protocol_label": label,
                "functionality": _clean(raw.get("functionality")),
            })
    return rows


def _hatexplain_majority(annotators: Iterable[Mapping[str, Any]]) -> str:
    labels = [_clean(row.get("label")) for row in annotators if _clean(row.get("label"))]
    return Counter(labels).most_common(1)[0][0] if labels else ""


def load_hatexplain_protocol_rows(root: Path) -> list[dict[str, Any]]:
    data_dir = root / "Data" if (root / "Data").exists() else root
    dataset_path = data_dir / "dataset.json"
    division_path = data_dir / "post_id_divisions.json"
    if not dataset_path.exists() or not division_path.exists():
        return []
    records = json.loads(dataset_path.read_text(encoding="utf-8"))
    divisions = json.loads(division_path.read_text(encoding="utf-8"))
    rows = []
    split_aliases = {"val": "validation", "valid": "validation"}
    for raw_split, case_ids in divisions.items():
        split = split_aliases.get(str(raw_split), str(raw_split))
        for case_id in case_ids:
            record = records.get(str(case_id))
            if not isinstance(record, Mapping):
                continue
            source_label = _hatexplain_majority(record.get("annotators") or [])
            protocol_label = map_target_label("HateXplain", source_label)
            text = _clean(record.get("post") or " ".join(record.get("post_tokens") or []))
            if protocol_label is None or not text:
                continue
            rows.append({
                "case_id": str(case_id),
                "dataset": "HateXplain",
                "text": text,
                "source_label": source_label,
                "protocol_label": protocol_label,
                "split": split,
            })
    return rows


def load_latent_hate_protocol_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    rows = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for index, raw in enumerate(csv.DictReader(handle, delimiter=delimiter)):
            source_label = _clean(
                raw.get("label") or raw.get("class") or raw.get("gold_label")
            )
            protocol_label = map_target_label("Latent_Hate", source_label)
            text = _clean(raw.get("post") or raw.get("text") or raw.get("tweet"))
            if protocol_label is None or not text:
                continue
            rows.append({
                "case_id": _clean(raw.get("id") or raw.get("post_id")) or f"latent-{index}",
                "dataset": "Latent_Hate",
                "text": text,
                "source_label": source_label,
                "protocol_label": protocol_label,
            })
    return rows


def _assert_disjoint(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> None:
    overlap = {str(row["case_id"]) for row in left} & {str(row["case_id"]) for row in right}
    if overlap:
        raise ValueError(f"support/test case overlap: {sorted(overlap)[:3]}")


def _dataset_hash(rows: list[dict[str, Any]]) -> str:
    payload = "\n".join(
        f"{row.get('case_id')}\t{row.get('protocol_label')}\t{row.get('text')}"
        for row in rows
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _file_hash(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _label_mapping_payload() -> dict[str, Any]:
    return {
        "source_mapping_version": SOURCE_LABEL_MAPPING_VERSION,
        "target_mapping_version": TARGET_LABEL_MAPPING_VERSION,
        "hatecot_universal_3way": {
            "0": ["Normal", "Benign", "Neutral", "Not Hate", "Not Hate Speech", "Not Offensive"],
            "1": ["Offensive", "Toxic", "Derogation", "Person Directed Abuse"],
            "2": ["Hate", "Hateful", "Hate Speech", "Identity Directed Abuse", "Affiliation Directed Abuse", "Dehumanization"],
            "excluded_ambiguous": sorted(_AMBIGUOUS_SOURCE_LABELS),
        },
        "target_label_spaces": {
            name: {
                "labels": spec["class_names"],
                "head": spec["head"],
            }
            for name, spec in TARGET_SPECS.items()
        },
        "latent_hate_source_proxy": {
            "Normal": "Not Hate",
            "Hate": "Explicit Hate",
            "Offensive": "Implicit Hate",
            "boundary": "Offensive to Implicit Hate is a source-ontology proxy, not target-label equivalence.",
        },
    }


def _case_to_model_input(row: Mapping[str, Any]) -> str:
    return build_textified_input({"text": row.get("text", "")})


def _load_model_and_tokenizer(args: argparse.Namespace, checkpoint_path: Path | None = None):
    require_torch()
    import torch
    from transformers import AutoTokenizer

    payload: dict[str, Any] = {}
    model_name = args.backbone
    cache_dir = args.hf_cache_dir or None
    if checkpoint_path and checkpoint_path.exists():
        payload = torch.load(checkpoint_path, **checkpoint_load_kwargs())
        config = payload.get("model_config") or {}
        model_name = str(config.get("backbone") or model_name)
        cache_dir = str(config.get("hf_cache_dir") or cache_dir or "") or None
        rationale_dim = int(config.get("rationale_dim") or args.rationale_dim)
    else:
        rationale_dim = int(args.rationale_dim)
    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        cache_dir=cache_dir,
        local_files_only=not args.allow_model_download,
        use_fast=True,
    )
    model = XLMRTextifiedReviewStudent(
        model_name,
        rationale_dim=rationale_dim,
        cache_dir=cache_dir,
        local_files_only=not args.allow_model_download,
    )
    missing = unexpected = []
    if payload.get("model_state_dict"):
        result = model.load_state_dict(payload["model_state_dict"], strict=False)
        missing, unexpected = list(result.missing_keys), list(result.unexpected_keys)
    return model, tokenizer, {"missing_keys": missing, "unexpected_keys": unexpected}


def _encode_source_explanations(rows: list[dict[str, Any]], args: argparse.Namespace) -> np.ndarray:
    """Build detached explanation targets for source CE + LRKD training."""

    from app.core.review.trainable_post import encode_text_features

    features = encode_text_features(
        [str(row.get("explanation") or "") for row in rows],
        backend=args.rationale_encoder_backend,
        model_name=args.rationale_encoder_model or args.backbone,
        cache_dir=args.hf_cache_dir or None,
        batch_size=args.rationale_batch_size,
        local_files_only=not args.allow_model_download,
        max_length=args.rationale_max_length,
        pooling=args.rationale_pooling,
        dim=args.rationale_dim,
    ).matrix.astype("float32")
    if features.shape[1] != int(args.rationale_dim):
        raise ValueError("source rationale vector dimension does not match --rationale-dim")
    norms = np.linalg.norm(features, axis=1, keepdims=True)
    return features / np.clip(norms, 1e-12, None)


def _source_subset(rows: list[dict[str, Any]], max_cases: int) -> list[dict[str, Any]]:
    if max_cases <= 0 or len(rows) <= max_cases:
        return rows
    per_class = max(1, max_cases // 3)
    selected: list[dict[str, Any]] = []
    for label in range(3):
        selected.extend([row for row in rows if int(row["protocol_label"]) == label][:per_class])
    return selected[:max_cases]


def _train_source_protocol(
    model: Any,
    tokenizer: Any,
    source_rows: list[dict[str, Any]],
    *,
    args: argparse.Namespace,
    device: str,
) -> dict[str, Any]:
    """Train universal 3-way and HateCheck-compatible heads on HateCoT.

    The universal head receives all unambiguous source labels. The HateCheck
    head receives only unambiguous Normal/Hate source rows, avoiding a claim
    that the paper's broader offensive category is equivalent to protected-
    group hate under HateCheck.
    """

    require_torch()
    import torch
    import torch.nn.functional as functional

    rows = _source_subset(source_rows, int(args.source_max_cases))
    if not rows:
        raise ValueError("no source rows available for protocol training")
    model.to(device)
    model.train()
    use_amp = amp_enabled(args, device=device)
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=protocol_learning_rate(args, phase="source")
    )
    universal_labels = torch.as_tensor([int(row["protocol_label"]) for row in rows], dtype=torch.long)
    binary_mask = torch.as_tensor([int(row["protocol_label"]) in {0, 2} for row in rows], dtype=torch.bool)
    binary_labels = torch.as_tensor([int(row["protocol_label"]) == 2 for row in rows], dtype=torch.long)
    latent_proxy_labels = torch.as_tensor(
        [source_to_latent_hate_proxy_label(int(row["protocol_label"])) for row in rows],
        dtype=torch.long,
    )
    vectors = None
    if args.source_lrkd_weight > 0.0:
        vectors = torch.as_tensor(_encode_source_explanations(rows, args), dtype=torch.float32)
    tokenized = tokenizer(
        [_case_to_model_input(row) for row in rows],
        padding="max_length",
        truncation=True,
        max_length=args.max_length,
        return_tensors="pt",
    )
    history = []
    for epoch in range(max(1, args.epochs)):
        order = torch.randperm(len(rows))
        losses = []
        universal_losses = []
        binary_losses = []
        latent_proxy_losses = []
        lrkd_losses = []
        for start in range(0, len(rows), max(1, args.batch_size)):
            index = order[start : start + args.batch_size]
            encoded = {key: value[index].to(device) for key, value in tokenized.items()}
            with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=use_amp):
                output = model(**encoded)
                universal_loss = functional.cross_entropy(
                    output["protocol_logits"]["hatecot_universal_3way"],
                    universal_labels[index].to(device),
                )
                local_binary_mask = binary_mask[index].to(device)
                binary_loss = torch.zeros((), device=device)
                if bool(local_binary_mask.any()):
                    binary_loss = functional.cross_entropy(
                        output["protocol_logits"]["hatecheck_binary"][local_binary_mask],
                        binary_labels[index].to(device)[local_binary_mask],
                    )
                latent_proxy_loss = functional.cross_entropy(
                    output["protocol_logits"]["latent_hate_3way"],
                    latent_proxy_labels[index].to(device),
                )
                lrkd_loss = torch.zeros((), device=device)
                if vectors is not None:
                    lrkd_loss = (1.0 - functional.cosine_similarity(
                        output["rationale_proj"], vectors[index].to(device), dim=-1
                    )).mean()
                loss = universal_loss + binary_loss + latent_proxy_loss + float(args.source_lrkd_weight) * lrkd_loss
            optimizer.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            losses.append(float(loss.detach().cpu()))
            universal_losses.append(float(universal_loss.detach().cpu()))
            binary_losses.append(float(binary_loss.detach().cpu()))
            latent_proxy_losses.append(float(latent_proxy_loss.detach().cpu()))
            lrkd_losses.append(float(lrkd_loss.detach().cpu()))
        history.append({
            "epoch": epoch + 1,
            "loss": round(float(np.mean(losses)), 6),
            "universal_ce": round(float(np.mean(universal_losses)), 6),
            "hatecheck_ce": round(float(np.mean(binary_losses)), 6),
            "latent_hate_proxy_ce": round(float(np.mean(latent_proxy_losses)), 6),
            "lrkd": round(float(np.mean(lrkd_losses)), 6),
        })
    return {
        "history": history,
        "source_train_support": len(rows),
        "source_binary_support": int(binary_mask.sum()),
        "source_lr": protocol_learning_rate(args, phase="source"),
        "amp": use_amp,
        "source_lrkd_weight": float(args.source_lrkd_weight),
    }


def _save_checkpoint(path: Path, model: Any, args: argparse.Namespace, metadata: Mapping[str, Any]) -> None:
    require_torch()
    import torch

    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "schema": "hatecot-official-transfer-student-checkpoint-v1",
            "model_state_dict": model.state_dict(),
            "model_config": {
                "backbone": args.backbone,
                "hf_cache_dir": args.hf_cache_dir,
                "allow_model_download": bool(args.allow_model_download),
                "rationale_dim": int(args.rationale_dim),
            },
            "protocol_head_dims": PROTOCOL_HEAD_DIMS,
            "metadata": dict(metadata),
        },
        path,
    )


def _save_experiment_outputs(
    dataset_dir: Path,
    experiment_name: str,
    record: Mapping[str, Any],
) -> dict[str, str]:
    predictions = list(record.get("predictions") or [])
    predictions_path = dataset_dir / f"{experiment_name}_predictions.jsonl"
    with predictions_path.open("w", encoding="utf-8") as handle:
        for row in predictions:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    metrics = record.get("metrics") or {}
    confusion_path = dataset_dir / f"{experiment_name}_confusion_matrix.json"
    confusion_path.write_text(
        json.dumps(
            {
                "class_names": metrics.get("class_names"),
                "confusion_matrix": metrics.get("confusion_matrix"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "predictions_path": str(predictions_path),
        "confusion_matrix_path": str(confusion_path),
    }


def _finalize_experiment_record(
    dataset_dir: Path,
    experiment_name: str,
    record: dict[str, Any],
) -> dict[str, Any]:
    record.update(_save_experiment_outputs(dataset_dir, experiment_name, record))
    record.pop("predictions", None)
    return record


def _predict_model(model: Any, tokenizer: Any, rows: list[dict[str, Any]], *, head: str, args: argparse.Namespace, device: str):
    require_torch()
    import torch

    model.to(device)
    logits = []
    model.eval()
    use_amp = amp_enabled(args, device=device)
    with torch.no_grad():
        for start in range(0, len(rows), max(1, args.batch_size)):
            texts = [_case_to_model_input(row) for row in rows[start : start + args.batch_size]]
            encoded = tokenizer(
                texts,
                padding=True,
                truncation=True,
                max_length=args.max_length,
                return_tensors="pt",
            )
            encoded = {key: value.to(device) for key, value in encoded.items()}
            with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=use_amp):
                output = model(**encoded)
            if head == INTERPERSONAL_AXIS:
                batch_logits = torch.stack([-output[head], output[head]], dim=-1)
            else:
                batch_logits = output["protocol_logits"][head]
            logits.append(batch_logits.detach().cpu())
    return torch.cat(logits).numpy() if logits else np.zeros((0, PROTOCOL_HEAD_DIMS.get(head, 2)), dtype="float32")


def _train_head(model: Any, tokenizer: Any, rows: list[dict[str, Any]], *, head: str, args: argparse.Namespace, device: str) -> list[dict[str, Any]]:
    require_torch()
    import torch

    if not rows:
        raise ValueError("cannot train protocol head on empty rows")
    model.to(device)
    model.train()
    use_amp = amp_enabled(args, device=device)
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    if args.freeze_backbone:
        for parameter in model.backbone.parameters():
            parameter.requires_grad = False
    optimizer = torch.optim.AdamW(
        [parameter for parameter in model.parameters() if parameter.requires_grad],
        lr=protocol_learning_rate(args, phase="target"),
        **target_adamw_kwargs(),
    )
    criterion = torch.nn.CrossEntropyLoss()
    tokenized = tokenizer(
        [_case_to_model_input(row) for row in rows],
        padding="max_length",
        truncation=True,
        max_length=args.max_length,
        return_tensors="pt",
    )
    labels = torch.as_tensor([int(row["protocol_label"]) for row in rows], dtype=torch.long)
    history = []
    for epoch in range(max(1, args.epochs)):
        order = torch.randperm(len(rows))
        losses = []
        for start in range(0, len(rows), max(1, args.batch_size)):
            index = order[start : start + args.batch_size]
            encoded = {key: value[index].to(device) for key, value in tokenized.items()}
            with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=use_amp):
                output = model(**encoded)
                logits = output["protocol_logits"][head]
                target = labels[index].to(device)
                loss = criterion(logits, target)
            optimizer.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            losses.append(float(loss.detach().cpu()))
        history.append({"epoch": epoch + 1, "loss": round(float(np.mean(losses)), 6)})
    return history


def _evaluate(model: Any, tokenizer: Any, rows: list[dict[str, Any]], *, head: str, spec: Mapping[str, Any], args: argparse.Namespace, device: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    logits = _predict_model(model, tokenizer, rows, head=head, args=args, device=device)
    predictions = logits.argmax(axis=1) if len(logits) else np.zeros((0,), dtype="int64")
    labels = np.asarray([int(row["protocol_label"]) for row in rows], dtype="int64")
    shifted_logits = logits - logits.max(axis=1, keepdims=True)
    probabilities = np.exp(shifted_logits)
    probabilities /= probabilities.sum(axis=1, keepdims=True)
    metrics = multiclass_metrics(
        labels,
        predictions,
        class_names=list(spec["class_names"]),
        probabilities=probabilities,
    )
    predictions_out = [
        {
            "case_id": row["case_id"],
            "gold_label": int(label),
            "predicted_label": int(prediction),
            "probabilities": [round(float(value), 6) for value in probability],
            "source_label": row.get("source_label"),
        }
        for row, label, prediction, probability in zip(rows, labels, predictions, probabilities)
    ]
    return metrics, predictions_out


def _record_protocol_data(
    name: str,
    rows: list[dict[str, Any]],
    development_support: list[dict[str, Any]],
    kshot_pool: list[dict[str, Any]],
    test: list[dict[str, Any]],
    spec: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "dataset": name,
        "dataset_hash": _dataset_hash(rows),
        "mapping_version": TARGET_LABEL_MAPPING_VERSION,
        "label_space": list(spec["class_names"]),
        "total_rows": len(rows),
        "development_support_rows": len(development_support),
        "kshot_pool_rows": len(kshot_pool),
        "test_rows": len(test),
        "development_support_case_ids": [row["case_id"] for row in development_support],
        "kshot_pool_case_ids": [row["case_id"] for row in kshot_pool],
        "test_case_ids": [row["case_id"] for row in test],
        "split_policy": "fixed class-balanced development/test samples; K-shot pool is 256/class from non-test target rows",
        "snapshot_note": (
            "HateXplain uses its local official train/validation/test division. "
            "HateCheck and Latent_Hate are local snapshot protocol reproductions because this runner has no native target train split for them."
        ),
    }


def run_target_experiment(
    name: str,
    rows: list[dict[str, Any]],
    source_checkpoint: Path | None,
    args: argparse.Namespace,
    output_dir: Path,
) -> dict[str, Any]:
    spec = TARGET_SPECS[name]
    classes = int(spec["classes"])
    if len({int(row["protocol_label"]) for row in rows}) != classes:
        return {
            "status": "skipped",
            "dataset": name,
            "skip_reason": "local snapshot does not contain all official classes",
            "observed_labels": sorted({int(row["protocol_label"]) for row in rows}),
            "expected_classes": classes,
        }
    if name == "HateCheck":
        support_n, test_n = 300, 500
        support_source, test_source = rows, rows
    else:
        support_n, test_n = 200, 400
        if name == "HateXplain":
            support_source = [row for row in rows if row.get("split") in {"train", "validation"}]
            test_source = [row for row in rows if row.get("split") == "test"]
        else:
            support_source, test_source = rows, rows
    try:
        if test_source is not rows:
            development_support, test = build_protocol_support_from_pool(
                support_source,
                test_source,
                classes=classes,
                support_per_class=support_n,
                test_per_class=test_n,
                random_state=args.random_state,
            )
        else:
            development_support, test = build_protocol_support_test(
                rows,
                classes=classes,
                support_per_class=support_n,
                test_per_class=test_n,
                random_state=args.random_state,
            )
    except ValueError:
        return {"status": "skipped", "dataset": name, "skip_reason": "insufficient per-class local rows"}
    _assert_disjoint(development_support, test)
    if test_source is not rows:
        # Keep all official test-split cases out of target adaptation, including
        # test rows not selected into the class-balanced evaluation sample.
        full_support = list(support_source)
    else:
        full_support = [row for row in rows if str(row["case_id"]) not in {str(item["case_id"]) for item in test}]
    try:
        kshot_pool = select_k_shot(
            full_support,
            k=256,
            classes=classes,
            random_state=args.random_state + 256,
        )
    except ValueError:
        return {"status": "skipped", "dataset": name, "skip_reason": "insufficient non-test rows for official K=256 pool"}
    _assert_disjoint(kshot_pool, test)
    data_record = _record_protocol_data(
        name, rows, development_support, kshot_pool, test, spec
    )
    data_record["full_data_support_rows"] = len(full_support)
    dataset_dir = output_dir / name
    dataset_dir.mkdir(parents=True, exist_ok=True)
    (dataset_dir / "split_manifest.json").write_text(json.dumps(data_record, ensure_ascii=False, indent=2), encoding="utf-8")
    (dataset_dir / "label_mapping.json").write_text(
        json.dumps(_label_mapping_payload(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    results: dict[str, Any] = {"status": "evaluated", "dataset": name, "protocol_data": data_record, "experiments": {}}
    device = resolve_torch_device(args.device)
    checkpoint = source_checkpoint if source_checkpoint and source_checkpoint.exists() else None

    if args.experiment in {"source_3way_transfer", "all"}:
        source_head = spec.get("source_transfer")
        if source_head:
            model, tokenizer, load_info = _load_model_and_tokenizer(args, checkpoint)
            metrics, predictions = _evaluate(model, tokenizer, test, head=source_head, spec=spec, args=args, device=device)
            record = {
                "status": "evaluated",
                "adaptation_mode": "hatecot_only_source_transfer",
                "head": source_head,
                "source_checkpoint": str(checkpoint) if checkpoint else None,
                "source_label_alignment": (
                    "ontology_proxy_normal_offensive_hate_to_not_hate_implicit_hate_explicit_hate"
                    if name == "Latent_Hate" else "label_space_aligned"
                ),
                "metrics": metrics,
                "load_info": load_info,
                "predictions": predictions,
            }
            results["experiments"]["source_3way_transfer"] = record
            _finalize_experiment_record(dataset_dir, "source_3way_transfer", record)
            del model, tokenizer
            release_runtime_memory()

    if args.experiment in {"kshot", "all", "full_data"}:
        k_values = args.k_values if args.experiment != "full_data" else []
        for k in k_values:
            selected = select_k_shot(kshot_pool, k=k, classes=classes, random_state=args.random_state + k)
            trial_seed = paired_trial_seed(args.random_state, name, f"kshot-{k}")
            seed_experiment(trial_seed)
            model, tokenizer, load_info = _load_model_and_tokenizer(args, checkpoint)
            reset_protocol_head(model, head=str(spec["head"]), seed=trial_seed)
            history = _train_head(model, tokenizer, selected, head=str(spec["head"]), args=args, device=device)
            metrics, predictions = _evaluate(model, tokenizer, test, head=str(spec["head"]), spec=spec, args=args, device=device)
            record = {
                "status": "evaluated",
                "adaptation_mode": "hatecot_pretrained_target_k_shot",
                "k_shot_per_class": k,
                "train_support": len(selected),
                "seed": trial_seed,
                "target_lr": protocol_learning_rate(args, phase="target"),
                "head": spec["head"],
                "history": history,
                "metrics": metrics,
                "load_info": load_info,
                "predictions": predictions,
            }
            results["experiments"][f"kshot_{k}"] = record
            _finalize_experiment_record(dataset_dir, f"kshot_{k}", record)
            if save_target_checkpoints(args):
                _save_checkpoint(
                    dataset_dir / f"kshot_{k}_checkpoint.pt",
                    model,
                    args,
                    {"dataset": name, "experiment": f"kshot_{k}", "train_support": len(selected)},
                )
            del model, tokenizer
            release_runtime_memory()
            seed_experiment(trial_seed)
            base_model, base_tokenizer, base_load_info = _load_model_and_tokenizer(args, None)
            reset_protocol_head(base_model, head=str(spec["head"]), seed=trial_seed)
            base_history = _train_head(base_model, base_tokenizer, selected, head=str(spec["head"]), args=args, device=device)
            base_metrics, base_predictions = _evaluate(base_model, base_tokenizer, test, head=str(spec["head"]), spec=spec, args=args, device=device)
            base_record = {
                "status": "evaluated",
                "adaptation_mode": "base_target_k_shot",
                "k_shot_per_class": k,
                "train_support": len(selected),
                "seed": trial_seed,
                "target_lr": protocol_learning_rate(args, phase="target"),
                "head": spec["head"],
                "history": base_history,
                "metrics": base_metrics,
                "load_info": base_load_info,
                "predictions": base_predictions,
            }
            results["experiments"][f"kshot_{k}_base"] = base_record
            _finalize_experiment_record(dataset_dir, f"kshot_{k}_base", base_record)
            if save_target_checkpoints(args):
                _save_checkpoint(
                    dataset_dir / f"kshot_{k}_base_checkpoint.pt",
                    base_model,
                    args,
                    {"dataset": name, "experiment": f"kshot_{k}_base", "train_support": len(selected)},
                )
            del base_model, base_tokenizer
            release_runtime_memory()
        if args.experiment in {"full_data", "all"}:
            trial_seed = paired_trial_seed(args.random_state, name, "full-data")
            seed_experiment(trial_seed)
            model, tokenizer, load_info = _load_model_and_tokenizer(args, None)
            reset_protocol_head(model, head=str(spec["head"]), seed=trial_seed)
            history = _train_head(model, tokenizer, full_support, head=str(spec["head"]), args=args, device=device)
            metrics, predictions = _evaluate(model, tokenizer, test, head=str(spec["head"]), spec=spec, args=args, device=device)
            record = {
                "status": "evaluated",
                "adaptation_mode": "target_full_support_no_explanation",
                "train_support": len(full_support),
                "seed": trial_seed,
                "target_lr": protocol_learning_rate(args, phase="target"),
                "head": spec["head"],
                "history": history,
                "metrics": metrics,
                "load_info": load_info,
                "predictions": predictions,
            }
            results["experiments"]["full_data"] = record
            _finalize_experiment_record(dataset_dir, "full_data", record)
            if save_target_checkpoints(args):
                _save_checkpoint(
                    dataset_dir / "full_data_checkpoint.pt",
                    model,
                    args,
                    {"dataset": name, "experiment": "full_data", "train_support": len(full_support)},
                )
            del model, tokenizer
            release_runtime_memory()
    return results


def main() -> int:
    started = perf_counter()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hatecot-csv", default=r"G:\CISCN\dataset\HateCoT\hatecot_final_D3.csv")
    parser.add_argument("--hatexplain-dir", default=r"G:\CISCN\dataset\kt3_public\HateXplain")
    parser.add_argument("--hatecheck-csv", default=r"G:\CISCN\dataset\hatecheck-data\test_suite_cases.csv")
    parser.add_argument("--latent-hate-path", default=DEFAULT_LATENT_HATE_PATH)
    parser.add_argument("--checkpoint", default="")
    parser.add_argument("--source-protocol-checkpoint", default="")
    parser.add_argument("--output-dir", default=r"G:\CISCN\.tmp\hatecot_official_transfer_student")
    parser.add_argument("--datasets", nargs="*", default=list(TARGET_SPECS))
    parser.add_argument("--experiment", choices=["source_3way_transfer", "kshot", "full_data", "all"], default="all")
    parser.add_argument("--k-values", nargs="*", type=int, default=[32, 64, 128, 256])
    parser.add_argument("--backbone", default="FacebookAI/xlm-roberta-base")
    parser.add_argument("--hf-cache-dir", default=r"G:\CISCN\hf_models")
    parser.add_argument("--allow-model-download", action="store_true")
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--source-lr", type=float, default=2e-5)
    parser.add_argument("--target-lr", type=float, default=1e-4)
    parser.add_argument("--amp", dest="amp", action="store_true", default=True)
    parser.add_argument("--no-amp", dest="amp", action="store_false")
    parser.add_argument("--save-target-checkpoints", dest="save_target_checkpoints", action="store_true", default=True)
    parser.add_argument("--no-save-target-checkpoints", dest="save_target_checkpoints", action="store_false")
    parser.add_argument("--source-max-cases", type=int, default=0)
    parser.add_argument("--source-lrkd-weight", type=float, default=0.2)
    parser.add_argument("--rationale-encoder-backend", choices=["hf-transformer", "sentence-transformer", "auto"], default="hf-transformer")
    parser.add_argument("--rationale-encoder-model", default="")
    parser.add_argument("--rationale-dim", type=int, default=768)
    parser.add_argument("--rationale-max-length", type=int, default=256)
    parser.add_argument("--rationale-pooling", choices=["cls", "mean"], default="mean")
    parser.add_argument("--rationale-batch-size", type=int, default=32)
    parser.add_argument("--freeze-backbone", action="store_true", default=False)
    parser.add_argument("--device", default=None)
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "label_mapping.json").write_text(
        json.dumps(_label_mapping_payload(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    source_rows, source_meta = load_hatecot_protocol_rows(Path(args.hatecot_csv))
    source_meta["file_sha256"] = _file_hash(Path(args.hatecot_csv))
    datasets: dict[str, list[dict[str, Any]]] = {}
    if "HateCheck" in args.datasets and Path(args.hatecheck_csv).exists():
        datasets["HateCheck"] = load_hatecheck_protocol_rows(Path(args.hatecheck_csv))
    if "HateXplain" in args.datasets:
        datasets["HateXplain"] = load_hatexplain_protocol_rows(Path(args.hatexplain_dir))
    if "Latent_Hate" in args.datasets and Path(args.latent_hate_path).exists():
        datasets["Latent_Hate"] = load_latent_hate_protocol_rows(Path(args.latent_hate_path))
    report: dict[str, Any] = {
        "schema": PROTOCOL_SCHEMA,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "run_config": vars(args),
        "source": source_meta,
        "official_reference": {
            "paper": "HateCoT: An Explanation-Enhanced Dataset for Generalizable Offensive Speech Detection via Large Language Models",
            "paper_url": "https://arxiv.org/abs/2403.11456",
            "repository": "https://github.com/hnghiem-nlp/hatecot",
            "comparability": "official reference is prompt-based LLaMA; this report is XLM-R encoder transfer/adaptation",
        },
        "datasets": {},
        "duration_seconds": None,
    }
    source_checkpoint: Path | None = Path(args.checkpoint) if args.checkpoint else None
    reused_source_checkpoint = source_protocol_checkpoint_path(args)
    if args.experiment in {"source_3way_transfer", "kshot", "all"}:
        if reused_source_checkpoint is not None:
            source_checkpoint = reused_source_checkpoint
            report["source_training"] = {
                "status": "reused",
                "checkpoint": str(source_checkpoint),
                "checkpoint_sha256": _file_hash(source_checkpoint),
                "reused_from": "--source-protocol-checkpoint",
            }
        else:
            device = resolve_torch_device(args.device)
            seed_experiment(args.random_state)
            source_model, source_tokenizer, source_load = _load_model_and_tokenizer(args, source_checkpoint)
            source_training = _train_source_protocol(
                source_model, source_tokenizer, source_rows, args=args, device=device
            )
            source_checkpoint = output_dir / "hatecot_source_protocol_checkpoint.pt"
            _save_checkpoint(
                source_checkpoint,
                source_model,
                args,
                {"experiment": "hatecot_source_protocol", **source_training, "load_info": source_load},
            )
            report["source_training"] = {
                **source_training,
                "seed": int(args.random_state),
                "checkpoint": str(source_checkpoint),
                "load_info": source_load,
            }
            del source_model, source_tokenizer
            release_runtime_memory()
    for name in args.datasets:
        rows = datasets.get(name, [])
        if not rows:
            report["datasets"][name] = {"status": "skipped", "dataset": name, "skip_reason": "dataset unavailable or empty"}
            continue
        report["datasets"][name] = run_target_experiment(name, rows, source_checkpoint, args, output_dir)
    report["source_rows_used_for_protocol_training"] = len(source_rows)
    report["comparability_notes"] = [
        "XLM-R source_3way_transfer is not the official LLaMA prompt zero-shot setting.",
        "K-shot follows HateCoT Section 4.2: a 256-per-class target training pool, then K={32,64,128,256} sub-samples.",
        "Table 1 K val support counts are retained as development samples; they do not limit the Section 4.2 K=256 pool.",
        "Support, K-shot pool, and test manifests are written per dataset and are disjoint by case_id where required.",
    ]
    report["duration_seconds"] = round(perf_counter() - started, 6)
    (output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({name: record.get("status") for name, record in report["datasets"].items()}, ensure_ascii=False, indent=2))
    print(f"wrote {output_dir / 'report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
