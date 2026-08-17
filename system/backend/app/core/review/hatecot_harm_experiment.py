"""Dataset protocol helpers for the MARO-compatible HateCoT harm experiment.

The functions in this module keep raw HateCoT labels, their normalized
three-way evaluation labels, and Agent-visible inputs separate. In particular,
the dataset-provided explanation is never included in a Teacher prompt.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
from random import Random
from typing import Any, Mapping

from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

from app.core.review.maro_rule_optimization import MARO_HARM_3WAY_LABELS


HATECOT_LABEL_MAPPING_VERSION = "hatecot-interpersonal-harm-3way-v1"
HATECOT_EVALUATION_LABELS = MARO_HARM_3WAY_LABELS
_RAW_LABEL_MAPPING = {
    "benign": "non_harmful",
    "neutral": "non_harmful",
    "normal": "non_harmful",
    "not hate": "non_harmful",
    "not hate speech": "non_harmful",
    "not offensive": "non_harmful",
    "offensive": "offensive",
    "toxic": "offensive",
    "derogation": "offensive",
    "person directed abuse": "offensive",
    "hate": "hate",
    "hate speech": "hate",
    "hateful": "hate",
    "identity directed abuse": "hate",
    "affiliation directed abuse": "hate",
    "dehumanization": "hate",
}
_AMBIGUOUS_RAW_LABELS = {"animosity"}

__all__ = [
    "HATECOT_EVALUATION_LABELS",
    "HATECOT_LABEL_MAPPING_VERSION",
    "build_target_sampling_manifest",
    "build_source_split_manifest",
    "case_domain",
    "case_label",
    "eligible_target_domains",
    "evaluate_predictions",
    "load_hatecot_cases",
    "map_hatecot_label",
    "select_target_cases",
    "split_source_cases",
]


def load_hatecot_cases(path: str | Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load only Agent-eligible fields and record excluded source labels."""

    source_path = Path(path)
    if not source_path.is_file():
        raise FileNotFoundError(f"HateCoT CSV does not exist: {source_path}")
    cases_by_id: dict[str, dict[str, Any]] = {}
    raw_labels: Counter[str] = Counter()
    excluded_labels: Counter[str] = Counter()
    domains: Counter[str] = Counter()
    mappable_row_count = 0
    duplicate_eligible_row_count = 0
    explanation_available = 0
    with source_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row_number, row in enumerate(csv.DictReader(handle), start=2):
            raw_label = str(row.get("label") or "").strip()
            raw_labels[raw_label] += 1
            normalized = map_hatecot_label(raw_label)
            if normalized is None:
                excluded_labels[raw_label] += 1
                continue
            text = str(row.get("post") or "").strip()
            domain = str(row.get("domain") or "").strip().lower()
            source_id = str(row.get("id") or "").strip()
            if not text or not domain or not source_id:
                excluded_labels["missing_required_field"] += 1
                continue
            mappable_row_count += 1
            candidate = {
                "case_id": f"hatecot::{domain}::{source_id}",
                "source_id": source_id,
                "dataset": "HateCoT",
                "text": text,
                "labels": {"interpersonal_harm": normalized},
                "metadata": {
                    "category": domain,
                    "raw_label": raw_label,
                    "target": str(row.get("target") or "").strip(),
                },
            }
            existing = cases_by_id.get(candidate["case_id"])
            if existing is not None:
                if _same_agent_visible_case(existing, candidate):
                    duplicate_eligible_row_count += 1
                    continue
                raise ValueError(
                    "Conflicting HateCoT duplicate case ID at CSV row "
                    f"{row_number}: {candidate['case_id']}"
                )
            cases_by_id[candidate["case_id"]] = candidate
            explanation_available += int(bool(str(row.get("explanation") or "").strip()))
            domains[domain] += 1
    cases = list(cases_by_id.values())
    if not cases:
        raise ValueError("No mappable HateCoT cases were loaded")
    return cases, {
        "dataset": "HateCoT",
        "source_path": str(source_path),
        "source_row_count": sum(raw_labels.values()),
        "mappable_source_row_count": mappable_row_count,
        "eligible_row_count": len(cases),
        "duplicate_eligible_row_count": duplicate_eligible_row_count,
        "excluded_row_count": sum(excluded_labels.values()),
        "label_mapping_version": HATECOT_LABEL_MAPPING_VERSION,
        "raw_label_counts": dict(sorted(raw_labels.items())),
        "excluded_label_counts": dict(sorted(excluded_labels.items())),
        "ambiguous_raw_labels_excluded": sorted(_AMBIGUOUS_RAW_LABELS),
        "domain_counts": dict(sorted(domains.items())),
        "dataset_explanation_available_count": explanation_available,
        "agent_input_boundary": {
            "gold_label_sent_to_agent": False,
            "dataset_explanation_sent_to_agent": False,
            "raw_text_only": True,
        },
    }


def map_hatecot_label(raw_label: str) -> str | None:
    """Map an audited HateCoT source label or explicitly exclude ambiguity."""

    normalized = str(raw_label or "").strip().casefold()
    if normalized in _AMBIGUOUS_RAW_LABELS:
        return None
    return _RAW_LABEL_MAPPING.get(normalized)


def _same_agent_visible_case(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    """Permit only exact repeated source rows; reject silent label collisions."""

    return (
        str(left.get("text") or "") == str(right.get("text") or "")
        and case_label(left) == case_label(right)
        and case_domain(left) == case_domain(right)
        and str((left.get("metadata") or {}).get("raw_label") or "")
        == str((right.get("metadata") or {}).get("raw_label") or "")
        and str((left.get("metadata") or {}).get("target") or "")
        == str((right.get("metadata") or {}).get("target") or "")
    )


def eligible_target_domains(cases: list[Mapping[str, Any]]) -> list[str]:
    """Return domains that independently contain all declared evaluation classes."""

    labels_by_domain: dict[str, set[str]] = defaultdict(set)
    for case in cases:
        labels_by_domain[case_domain(case)].add(case_label(case))
    return sorted(
        domain
        for domain, labels in labels_by_domain.items()
        if domain and set(HATECOT_EVALUATION_LABELS).issubset(labels)
    )


def select_target_cases(
    cases: list[Mapping[str, Any]],
    *,
    cases_per_label: int,
    random_state: int,
) -> list[dict[str, Any]]:
    """Create a fixed exact-stratified evaluation sample without Agent labels."""

    if cases_per_label < 1:
        raise ValueError("cases_per_label must be >= 1")
    unique: dict[str, Mapping[str, Any]] = {}
    for case in cases:
        case_id = str(case.get("case_id") or "").strip()
        if not case_id:
            raise ValueError("Target case is missing case_id")
        existing = unique.get(case_id)
        if existing is not None and (
            case_label(existing) != case_label(case)
            or case_domain(existing) != case_domain(case)
            or str(existing.get("text") or "") != str(case.get("text") or "")
        ):
            raise ValueError(f"Conflicting HateCoT case_id collision: {case_id}")
        unique[case_id] = case

    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for case in unique.values():
        grouped[case_label(case)].append(case)
    selected: list[dict[str, Any]] = []
    for label in HATECOT_EVALUATION_LABELS:
        candidates = sorted(
            grouped[label],
            key=lambda case: hashlib.sha256(
                f"{random_state}:{case.get('case_id') or ''}".encode("utf-8")
            ).hexdigest(),
        )
        if len(candidates) < cases_per_label:
            raise ValueError(
                f"Target domain has {len(candidates)} {label!r} cases; needs {cases_per_label}."
            )
        selected.extend(dict(case) for case in candidates[:cases_per_label])
    random = Random(random_state)
    random.shuffle(selected)
    return selected


def build_target_sampling_manifest(
    *,
    target_domain: str,
    target_cases: list[Mapping[str, Any]],
    random_state: int,
    cases_per_label: int,
) -> dict[str, Any]:
    """Persist the fixed held-out sample while excluding its labels from prompts."""

    rows = [
        {
            "case_id": str(case.get("case_id") or ""),
            "source_id": str(case.get("source_id") or ""),
            "domain": case_domain(case),
            "gold_label": case_label(case),
        }
        for case in target_cases
    ]
    if len({row["case_id"] for row in rows}) != len(rows):
        raise ValueError("HateCoT target sampling manifest has duplicate case IDs")
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return {
        "protocol": "hatecot-harm-stratified-target-sample-v1",
        "target_domain": target_domain,
        "selection_seed": random_state,
        "cases_per_label": cases_per_label,
        "target_case_count": len(rows),
        "label_space": list(HATECOT_EVALUATION_LABELS),
        "label_counts": dict(Counter(row["gold_label"] for row in rows)),
        "evaluation_only": True,
        "target_labels_sent_to_agent": False,
        "sample_manifest_sha256": hashlib.sha256(payload).hexdigest(),
        "cases": rows,
    }


def split_source_cases(
    cases: list[Mapping[str, Any]],
    *,
    target_domain: str,
    train_fraction: float = 0.8,
    random_state: int = 42,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Split non-target cases by domain and mapped label without leakage."""

    if not 0.0 < train_fraction < 1.0:
        raise ValueError("train_fraction must be between 0 and 1")
    normalized_target = str(target_domain or "").strip().lower()
    source_cases = [
        dict(case)
        for case in cases
        if case_domain(case) != normalized_target
    ]
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for case in source_cases:
        case_id = str(case.get("case_id") or "").strip()
        if not case_id:
            raise ValueError("Source case is missing case_id")
        grouped[(case_domain(case), case_label(case))].append(case)

    train: list[dict[str, Any]] = []
    dev: list[dict[str, Any]] = []
    for (domain, label), rows in sorted(grouped.items()):
        ordered = sorted(
            rows,
            key=lambda case: hashlib.sha256(
                f"{random_state}:{normalized_target}:{domain}:{label}:{case['case_id']}".encode("utf-8")
            ).hexdigest(),
        )
        if len(ordered) < 2:
            raise ValueError(
                f"Source stratum {domain}/{label} needs at least two cases for train/dev split"
            )
        train_count = int(len(ordered) * train_fraction)
        train_count = min(max(train_count, 1), len(ordered) - 1)
        train.extend(ordered[:train_count])
        dev.extend(ordered[train_count:])

    train_ids = {str(case["case_id"]) for case in train}
    dev_ids = {str(case["case_id"]) for case in dev}
    if train_ids & dev_ids:
        raise AssertionError("Source train/dev split has overlapping case IDs")
    manifest = build_source_split_manifest(
        target_domain=normalized_target,
        source_train=train,
        source_dev=dev,
        train_fraction=train_fraction,
        random_state=random_state,
    )
    return train, dev, manifest


def build_source_split_manifest(
    *,
    target_domain: str,
    source_train: list[Mapping[str, Any]],
    source_dev: list[Mapping[str, Any]],
    train_fraction: float,
    random_state: int,
) -> dict[str, Any]:
    """Build an auditable source split manifest from case IDs and labels."""

    def rows(cases: list[Mapping[str, Any]]) -> list[dict[str, str]]:
        return [
            {
                "case_id": str(case.get("case_id") or ""),
                "domain": case_domain(case),
                "label": case_label(case),
            }
            for case in sorted(cases, key=lambda item: str(item.get("case_id") or ""))
        ]

    train_rows = rows(source_train)
    dev_rows = rows(source_dev)
    train_ids = {row["case_id"] for row in train_rows}
    dev_ids = {row["case_id"] for row in dev_rows}
    if not train_ids or not dev_ids:
        raise ValueError("Source split manifest requires non-empty train and dev pools")
    if train_ids & dev_ids:
        raise ValueError("Source split manifest contains overlapping train/dev case IDs")
    payload = {
        "target_domain": str(target_domain or "").strip().lower(),
        "train_fraction": train_fraction,
        "random_state": random_state,
        "source_train": train_rows,
        "source_dev": dev_rows,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return {
        "protocol": "hatecot-harm-source-train-dev-v1",
        "target_domain": payload["target_domain"],
        "train_fraction": train_fraction,
        "random_state": random_state,
        "source_train_case_count": len(train_rows),
        "source_dev_case_count": len(dev_rows),
        "source_train_label_counts": dict(Counter(row["label"] for row in train_rows)),
        "source_dev_label_counts": dict(Counter(row["label"] for row in dev_rows)),
        "source_train_case_ids": [row["case_id"] for row in train_rows],
        "source_dev_case_ids": [row["case_id"] for row in dev_rows],
        "split_manifest_sha256": hashlib.sha256(encoded).hexdigest(),
        "target_labels_sent_to_agent": False,
    }


def evaluate_predictions(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Compute multiclass metrics over every submitted held-out target item."""

    if not rows:
        raise ValueError("HateCoT evaluation requires at least one target prediction")
    for row in rows:
        if row.get("gold_label") not in HATECOT_EVALUATION_LABELS:
            raise ValueError(f"Invalid HateCoT gold label: {row.get('gold_label')!r}")
        if row.get("prediction") not in HATECOT_EVALUATION_LABELS:
            raise ValueError(f"Invalid HateCoT prediction: {row.get('prediction')!r}")
    labels = list(HATECOT_EVALUATION_LABELS)
    gold = [str(row["gold_label"]) for row in rows]
    predicted = [str(row["prediction"]) for row in rows]
    per_class = f1_score(gold, predicted, labels=labels, average=None, zero_division=0)
    return {
        "submitted_count": len(rows),
        "classification_metrics": {
            "accuracy": round(float(accuracy_score(gold, predicted)), 6),
            "macro_f1": round(float(f1_score(gold, predicted, labels=labels, average="macro", zero_division=0)), 6),
            "per_class_f1": {
                label: round(float(score), 6)
                for label, score in zip(labels, per_class, strict=True)
            },
        },
        "confusion_matrix": {
            "label_order": labels,
            "rows_gold_columns_prediction": confusion_matrix(gold, predicted, labels=labels).tolist(),
        },
    }


def case_domain(case: Mapping[str, Any]) -> str:
    metadata = case.get("metadata") if isinstance(case.get("metadata"), Mapping) else {}
    return str(metadata.get("category") or "").strip().lower()


def case_label(case: Mapping[str, Any]) -> str:
    labels = case.get("labels") if isinstance(case.get("labels"), Mapping) else {}
    return str(labels.get("interpersonal_harm") or "").strip().lower()
