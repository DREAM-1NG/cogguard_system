"""Target-benchmark protocols for MARO-compatible HateCoT harm evaluation.

The helpers deliberately keep benchmark labels out of the Agent-visible input
contract.  They only prepare source-only rule-optimization data and frozen
target manifests; the experiment runner owns the final metric calculation.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import csv
import hashlib
import json
from pathlib import Path
from random import Random
from typing import Any, Callable, Mapping


BENCHMARK_LABEL_KEY = "benchmark_label"

__all__ = [
    "BENCHMARK_LABEL_KEY",
    "HATECOT_BENCHMARKS",
    "HateCoTBenchmark",
    "build_benchmark_target_manifest",
    "load_hatecheck_cases",
    "load_hatexplain_cases",
    "load_latent_hate_cases",
    "map_hatecot_source_cases",
    "select_benchmark_target_cases",
]


@dataclass(frozen=True)
class HateCoTBenchmark:
    """Declared target task and audited HateCoT-source mapping."""

    name: str
    label_space: tuple[str, ...]
    source_label_map: Mapping[str, str]
    source_mapping_is_proxy: bool
    source_mapping_note: str


HATECOT_BENCHMARKS = {
    "HateCheck": HateCoTBenchmark(
        name="HateCheck",
        label_space=("non_hateful", "hateful"),
        source_label_map={
            "non_harmful": "non_hateful",
            "offensive": "hateful",
            "hate": "hateful",
        },
        source_mapping_is_proxy=False,
        source_mapping_note=(
            "The binary protocol intentionally treats every HateCoT harmful class as a positive source example; "
            "it is a task-specific collapse, not an official HateCheck training protocol."
        ),
    ),
    "HateXplain": HateCoTBenchmark(
        name="HateXplain",
        label_space=("normal", "offensive", "hate"),
        source_label_map={
            "non_harmful": "normal",
            "offensive": "offensive",
            "hate": "hate",
        },
        source_mapping_is_proxy=False,
        source_mapping_note="The source and target both expose an audited three-way content-harm label space.",
    ),
    "Latent_Hate": HateCoTBenchmark(
        name="Latent_Hate",
        label_space=("not_hate", "implicit_hate"),
        source_label_map={
            "non_harmful": "not_hate",
            "offensive": "implicit_hate",
            "hate": "implicit_hate",
        },
        source_mapping_is_proxy=True,
        source_mapping_note=(
            "Latent Hate stage-one labels concern implicit-hate presence. HateCoT does not annotate that construct, "
            "so its harmful source classes are an explicit proxy and the result is not label-equivalent."
        ),
    ),
}


def load_hatecheck_cases(path: str | Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load the official HateCheck suite using its native binary labels."""

    source_path = _require_file(path)
    cases: list[dict[str, Any]] = []
    with source_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for index, row in enumerate(csv.DictReader(handle)):
            text = _clean(row.get("test_case") or row.get("text"))
            label = _hatecheck_label(row.get("label_gold") or row.get("label"))
            case_id = _clean(row.get("case_id") or row.get("id")) or f"hatecheck-{index}"
            if not text or label is None:
                continue
            cases.append(_target_case(
                benchmark="HateCheck",
                case_id=case_id,
                text=text,
                label=label,
                metadata={"functionality": _clean(row.get("functionality")), "source_label": _clean(row.get("label_gold") or row.get("label"))},
            ))
    return cases, _target_manifest("HateCheck", source_path, cases, split="test", label_semantics="native_hateful_binary")


def load_hatexplain_cases(root: str | Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load only HateXplain's official test partition and majority labels."""

    root_path = Path(root)
    data_dir = root_path / "Data" if (root_path / "Data").is_dir() else root_path
    dataset_path = _require_file(data_dir / "dataset.json")
    divisions_path = _require_file(data_dir / "post_id_divisions.json")
    records = json.loads(dataset_path.read_text(encoding="utf-8"))
    divisions = json.loads(divisions_path.read_text(encoding="utf-8"))
    test_ids = {str(value) for value in divisions.get("test") or []}
    cases: list[dict[str, Any]] = []
    for case_id in sorted(test_ids):
        record = records.get(case_id)
        if not isinstance(record, Mapping):
            continue
        text = _clean(record.get("post") or " ".join(str(token) for token in record.get("post_tokens") or []))
        label = _hatexplain_majority_label(record.get("annotators") or [])
        if not text or label is None:
            continue
        cases.append(_target_case(
            benchmark="HateXplain",
            case_id=case_id,
            text=text,
            label=label,
            metadata={"source_label": label, "official_split": "test"},
        ))
    return cases, _target_manifest("HateXplain", dataset_path, cases, split="test", label_semantics="official_majority_three_way")


def load_latent_hate_cases(path: str | Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load Latent Hate's stage-one binary labels without fabricating subtype labels."""

    source_path = _require_file(path)
    cases: list[dict[str, Any]] = []
    with source_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for index, row in enumerate(csv.DictReader(handle, delimiter="\t")):
            text = _clean(row.get("post") or row.get("text") or row.get("tweet"))
            label = _latent_hate_label(row.get("class") or row.get("label") or row.get("stg1_label"))
            if not text or label is None:
                continue
            case_id = _clean(row.get("post_id") or row.get("id")) or f"latent-hate-{index}"
            cases.append(_target_case(
                benchmark="Latent_Hate",
                case_id=case_id,
                text=text,
                label=label,
                metadata={"source_label": _clean(row.get("class") or row.get("label") or row.get("stg1_label"))},
            ))
    return cases, _target_manifest("Latent_Hate", source_path, cases, split="stage_one", label_semantics="stage_one_binary_hate_presence")


def map_hatecot_source_cases(
    cases: list[Mapping[str, Any]],
    *,
    benchmark: HateCoTBenchmark,
) -> list[dict[str, Any]]:
    """Map the audited HateCoT source labels to one declared benchmark task."""

    mapped: list[dict[str, Any]] = []
    for case in cases:
        labels = case.get("labels") if isinstance(case.get("labels"), Mapping) else {}
        source_label = _clean(labels.get("interpersonal_harm")).lower()
        target_label = benchmark.source_label_map.get(source_label)
        text = _clean(case.get("text"))
        if not target_label or not text:
            continue
        metadata = dict(case.get("metadata") or {})
        metadata["source_interpersonal_harm"] = source_label
        mapped.append({
            "case_id": str(case.get("case_id") or ""),
            "text": text,
            "labels": {BENCHMARK_LABEL_KEY: target_label},
            "metadata": metadata,
        })
    if not mapped:
        raise ValueError(f"No HateCoT source cases map to benchmark {benchmark.name!r}")
    return mapped


def select_benchmark_target_cases(
    cases: list[Mapping[str, Any]],
    *,
    benchmark: HateCoTBenchmark,
    cases_per_label: int,
    random_state: int,
) -> list[dict[str, Any]]:
    """Freeze an exact balanced target sample before any Teacher invocation."""

    if cases_per_label < 1:
        raise ValueError("cases_per_label must be >= 1")
    grouped: dict[str, list[Mapping[str, Any]]] = {label: [] for label in benchmark.label_space}
    seen_ids: set[str] = set()
    for case in cases:
        case_id = _clean(case.get("case_id"))
        labels = case.get("labels") if isinstance(case.get("labels"), Mapping) else {}
        label = _clean(labels.get(BENCHMARK_LABEL_KEY)).lower()
        if not case_id or label not in grouped:
            continue
        if case_id in seen_ids:
            raise ValueError(f"Duplicate benchmark target case_id: {case_id}")
        seen_ids.add(case_id)
        grouped[label].append(case)
    selected: list[dict[str, Any]] = []
    for label in benchmark.label_space:
        candidates = sorted(
            grouped[label],
            key=lambda case: hashlib.sha256(f"{random_state}:{case['case_id']}".encode("utf-8")).hexdigest(),
        )
        if len(candidates) < cases_per_label:
            raise ValueError(
                f"{benchmark.name} has {len(candidates)} target cases for {label!r}; needs {cases_per_label}."
            )
        selected.extend(dict(case) for case in candidates[:cases_per_label])
    Random(random_state).shuffle(selected)
    return selected


def build_benchmark_target_manifest(
    *,
    benchmark: HateCoTBenchmark,
    target_cases: list[Mapping[str, Any]],
    random_state: int,
    cases_per_label: int,
) -> dict[str, Any]:
    """Persist the frozen target sample and its label-isolation boundary."""

    rows = []
    for case in target_cases:
        labels = case.get("labels") if isinstance(case.get("labels"), Mapping) else {}
        rows.append({
            "case_id": _clean(case.get("case_id")),
            "gold_label": _clean(labels.get(BENCHMARK_LABEL_KEY)).lower(),
        })
    if len({row["case_id"] for row in rows}) != len(rows):
        raise ValueError("Benchmark target manifest contains duplicate case IDs")
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return {
        "protocol": "hatecot-maro-benchmark-target-sample-v1",
        "benchmark": benchmark.name,
        "selection_seed": random_state,
        "cases_per_label": cases_per_label,
        "target_case_count": len(rows),
        "label_space": list(benchmark.label_space),
        "label_counts": dict(Counter(row["gold_label"] for row in rows)),
        "evaluation_only": True,
        "target_labels_sent_to_agent": False,
        "sample_manifest_sha256": hashlib.sha256(payload).hexdigest(),
        "cases": rows,
    }


def _target_case(*, benchmark: str, case_id: str, text: str, label: str, metadata: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "case_id": f"{benchmark.lower()}::{case_id}",
        "text": text,
        "labels": {BENCHMARK_LABEL_KEY: label},
        "metadata": {"category": benchmark.lower(), **dict(metadata)},
    }


def _target_manifest(
    benchmark: str,
    source_path: Path,
    cases: list[Mapping[str, Any]],
    *,
    split: str,
    label_semantics: str,
) -> dict[str, Any]:
    labels = [str((case.get("labels") or {}).get(BENCHMARK_LABEL_KEY) or "") for case in cases]
    return {
        "benchmark": benchmark,
        "source_path": str(source_path),
        "case_count": len(cases),
        "label_counts": dict(Counter(labels)),
        "split": split,
        "label_semantics": label_semantics,
        "target_labels_sent_to_agent": False,
    }


def _hatecheck_label(value: Any) -> str | None:
    normalized = _clean(value).casefold().replace("_", "-")
    return {"hateful": "hateful", "non-hateful": "non_hateful"}.get(normalized)


def _hatexplain_majority_label(annotators: Any) -> str | None:
    labels = []
    for item in annotators if isinstance(annotators, list) else []:
        if not isinstance(item, Mapping):
            continue
        value = _clean(item.get("label")).casefold()
        mapped = {"normal": "normal", "offensive": "offensive", "hatespeech": "hate", "hate speech": "hate"}.get(value)
        if mapped:
            labels.append(mapped)
    if not labels:
        return None
    counts = Counter(labels)
    # The official data has three annotators. Resolve rare ties deterministically
    # instead of leaving a platform-dependent dict-order decision.
    return max(HATECOT_BENCHMARKS["HateXplain"].label_space, key=lambda label: (counts[label], -HATECOT_BENCHMARKS["HateXplain"].label_space.index(label)))


def _latent_hate_label(value: Any) -> str | None:
    normalized = _clean(value).casefold().replace(" ", "_").replace("-", "_")
    return {"not_hate": "not_hate", "implicit_hate": "implicit_hate"}.get(normalized)


def _require_file(path: str | Path) -> Path:
    resolved = Path(path)
    if not resolved.is_file():
        raise FileNotFoundError(f"Benchmark source does not exist: {resolved}")
    return resolved


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()
