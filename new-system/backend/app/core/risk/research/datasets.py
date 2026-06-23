"""统一数据集加载与标签映射。"""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from app.core.risk.research.types import ResearchSample, RiskSplit, RiskTask


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _normalize_label(value: Any) -> str:
    return _normalize_text(value).lower()


def _canonical_harmful_label(value: Any) -> str:
    normalized = _normalize_label(value)
    aliases = {
        "harmful": {"harmful", "toxic", "hate", "abusive", "1", "true", "yes"},
        "borderline": {"borderline", "uncertain", "mixed", "2"},
        "safe": {"safe", "benign", "normal", "neutral", "0", "false", "no"},
    }
    for canonical, values in aliases.items():
        if normalized in values:
            return canonical
    if normalized.isdigit() and int(normalized) > 1:
        return "borderline"
    return normalized or "safe"


def _canonical_stance_label(value: Any) -> str:
    normalized = _normalize_label(value)
    aliases = {
        "support": {"support", "favor", "favour", "pro", "agree", "for", "positive", "1"},
        "deny": {"deny", "against", "oppose", "disagree", "con", "negative", "-1"},
        "query": {"query", "question", "ask", "inquiry", "0.5", "q"},
        "comment": {"comment", "neutral", "none", "unrelated", "observing", "0", "other"},
    }
    for canonical, values in aliases.items():
        if normalized in values:
            return canonical
    return normalized or "comment"


@dataclass
class DatasetAdapter:
    name: str
    task: RiskTask
    text_fields: tuple[str, ...]
    label_fields: tuple[str, ...]
    target_fields: tuple[str, ...] = ()
    id_fields: tuple[str, ...] = ()
    split_fields: tuple[str, ...] = ("split",)
    canonicalize_label: callable = lambda value: _normalize_label(value)
    supported_suffixes: tuple[str, ...] = (".jsonl", ".json", ".csv", ".tsv")
    metadata_fields: tuple[str, ...] = field(default_factory=tuple)


DATASET_REGISTRY: dict[str, DatasetAdapter] = {
    "cold": DatasetAdapter(
        name="cold",
        task=RiskTask.HARMFUL,
        text_fields=("text", "content", "comment", "tweet", "post"),
        label_fields=("label", "gold_label", "toxicity", "category", "class"),
        id_fields=("id", "uid", "sample_id"),
        split_fields=("split", "set"),
        canonicalize_label=_canonical_harmful_label,
        metadata_fields=("language", "source"),
    ),
    "nlpcc2016": DatasetAdapter(
        name="nlpcc2016",
        task=RiskTask.STANCE,
        text_fields=("text", "content", "tweet", "weibo"),
        label_fields=("label", "stance", "gold_label"),
        target_fields=("target", "topic", "claim"),
        id_fields=("id", "sample_id", "uid"),
        split_fields=("split", "set"),
        canonicalize_label=_canonical_stance_label,
        metadata_fields=("language", "source"),
    ),
    "cstance": DatasetAdapter(
        name="cstance",
        task=RiskTask.STANCE,
        text_fields=("text", "content", "comment", "post"),
        label_fields=("label", "stance", "gold_label"),
        target_fields=("target", "topic", "claim"),
        id_fields=("id", "sample_id", "uid"),
        split_fields=("split", "set"),
        canonicalize_label=_canonical_stance_label,
        metadata_fields=("language", "source", "subtask"),
    ),
}


def _infer_split(path: Path, explicit_value: Any) -> RiskSplit:
    normalized = _normalize_label(explicit_value)
    if normalized in {"train", "training"}:
        return RiskSplit.TRAIN
    if normalized in {"dev", "valid", "validation", "val"}:
        return RiskSplit.DEV
    if normalized in {"test", "testing"}:
        return RiskSplit.TEST

    path_name = path.as_posix().lower()
    if "train" in path_name:
        return RiskSplit.TRAIN
    if any(token in path_name for token in ("dev", "valid", "validation", "val")):
        return RiskSplit.DEV
    if "test" in path_name:
        return RiskSplit.TEST
    return RiskSplit.UNSPECIFIED


def _first_non_empty(record: dict[str, Any], fields: Iterable[str]) -> Any:
    for field in fields:
        if field in record and record[field] not in (None, ""):
            return record[field]
    return None


def _load_json_records(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("data", "records", "items", "examples"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise ValueError(f"无法识别 JSON 数据集结构: {path}")


def _load_jsonl_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if isinstance(row, dict):
            records.append(row)
    return records


def _load_delimited_records(path: Path, delimiter: str) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter=delimiter)
        return [dict(row) for row in reader]


def _load_records(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return _load_jsonl_records(path)
    if suffix == ".json":
        return _load_json_records(path)
    if suffix == ".csv":
        return _load_delimited_records(path, ",")
    if suffix == ".tsv":
        return _load_delimited_records(path, "\t")
    raise ValueError(f"不支持的数据集文件格式: {path.suffix}")


def _record_to_sample(path: Path, record: dict[str, Any], adapter: DatasetAdapter) -> ResearchSample:
    text = _normalize_text(_first_non_empty(record, adapter.text_fields))
    if not text:
        raise ValueError(f"样本缺少 text 字段，适配器={adapter.name}, record={record}")

    raw_label = _first_non_empty(record, adapter.label_fields)
    if raw_label in (None, ""):
        raise ValueError(f"样本缺少 label 字段，适配器={adapter.name}, record={record}")

    target_value = _first_non_empty(record, adapter.target_fields)
    sample_id = _first_non_empty(record, adapter.id_fields)
    split_value = _first_non_empty(record, adapter.split_fields)
    split = _infer_split(path, split_value)
    meta = {field: record[field] for field in adapter.metadata_fields if field in record and record[field] not in (None, "")}

    return ResearchSample(
        dataset=adapter.name,
        task=adapter.task,
        text=text,
        label=adapter.canonicalize_label(raw_label),
        target=_normalize_text(target_value) or None,
        split=split,
        sample_id=str(sample_id) if sample_id not in (None, "") else None,
        meta=meta,
    )


def load_dataset_file(path: str | Path, dataset_name: str) -> list[ResearchSample]:
    adapter = DATASET_REGISTRY[dataset_name.lower()]
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(file_path)
    if file_path.suffix.lower() not in adapter.supported_suffixes:
        raise ValueError(f"{adapter.name} 不支持文件格式 {file_path.suffix}")

    samples: list[ResearchSample] = []
    for record in _load_records(file_path):
        samples.append(_record_to_sample(file_path, record, adapter))
    return samples


def summarize_samples(samples: Iterable[ResearchSample]) -> dict[str, Any]:
    samples = list(samples)
    label_counter = Counter(sample.label for sample in samples)
    split_counter = Counter(sample.split.value for sample in samples)
    target_counter = Counter(sample.target for sample in samples if sample.target)
    return {
        "count": len(samples),
        "labels": dict(label_counter),
        "splits": dict(split_counter),
        "targets": dict(target_counter),
    }
