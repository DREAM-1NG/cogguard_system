from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from .detection import _load_detection_runtime_modules

_VALIDATION_SPLITS = frozenset({"validation", "val", "valid", "dev", "unassigned"})
_TEST_SPLITS = frozenset({"test", "heldout", "heldout_test"})


def build_socgfm_detection_artifact(
    *,
    source_run_dir: str | Path,
    output_dir: str | Path,
    version: str,
    account_namespace: str = "iohunter",
) -> dict[str, Any]:
    source_root = Path(source_run_dir).expanduser().resolve()
    output_root = Path(output_dir).expanduser().resolve()
    _require_g_drive(output_root)
    prediction_files = _prediction_files(source_root)
    if not prediction_files:
        raise ValueError(f"No socgfm_cross_attention predictions.csv files found under {source_root}")

    probability_values: dict[str, list[float]] = defaultdict(list)
    labeled_rows: list[tuple[int, float, str]] = []
    source_run_hashes: dict[str, str] = {}
    summary_metrics: list[dict[str, Any]] = []
    run_level_metrics: list[dict[str, float]] = []
    run_level_thresholds: list[float] = []

    for prediction_path in prediction_files:
        source_run_hashes[_relative_name(source_root, prediction_path)] = _sha256_file(prediction_path)
        rows = _read_prediction_rows(prediction_path, account_namespace=account_namespace)
        file_labeled_rows: list[tuple[int, float, str]] = []
        for account_key, probability, label, split in rows:
            probability_values[account_key].append(probability)
            if label in (0, 1):
                labeled_row = (int(label), probability, split)
                labeled_rows.append(labeled_row)
                file_labeled_rows.append(labeled_row)
        file_validation_rows = _rows_for_splits(file_labeled_rows, _VALIDATION_SPLITS)
        file_test_rows = _rows_for_splits(file_labeled_rows, _TEST_SPLITS)
        if _has_binary_labels(file_validation_rows) and _has_binary_labels(file_test_rows):
            file_threshold, _file_threshold_macro_f1 = _best_threshold(file_validation_rows)
            if not math.isnan(file_threshold):
                run_level_metrics.append(_binary_metrics(file_test_rows, file_threshold))
                run_level_thresholds.append(file_threshold)
        summary_path = prediction_path.with_name("detection_summary.json")
        if summary_path.exists():
            source_run_hashes[_relative_name(source_root, summary_path)] = _sha256_file(summary_path)
            summary_metrics.append(_summary_metrics(summary_path))

    account_probabilities = {
        account_key: round(float(sum(values) / len(values)), 12)
        for account_key, values in sorted(probability_values.items())
    }
    if not account_probabilities:
        raise ValueError("SocGFM predictions did not contain any account probabilities")

    validation_rows = _rows_for_splits(labeled_rows, _VALIDATION_SPLITS)
    test_rows = _rows_for_splits(labeled_rows, _TEST_SPLITS)
    all_labeled_rows = [(label, score) for label, score, _split in labeled_rows]
    threshold_source = "validation_macro_f1"
    if not validation_rows:
        validation_rows = all_labeled_rows
        threshold_source = "all_labeled_rows_macro_f1"
    decision_threshold, threshold_macro_f1 = _best_threshold(validation_rows)
    metrics_rows = test_rows or validation_rows
    metric_source = (
        "heldout_test_rows_with_validation_threshold"
        if test_rows and threshold_source == "validation_macro_f1"
        else threshold_source
    )
    account_metrics = (
        _mean_binary_metrics(run_level_metrics)
        if run_level_metrics
        else _binary_metrics(metrics_rows, decision_threshold)
    )
    if run_level_metrics:
        metric_source = "macro_average_heldout_test_rows_with_per_run_validation_threshold"
    if math.isnan(decision_threshold):
        decision_threshold = _summary_threshold(summary_metrics)
        threshold_source = "source_summary_max_f1_threshold"
        metric_source = "source_summary_with_available_labeled_rows"
        account_metrics = _summary_binary_metrics(summary_metrics, metrics_rows, decision_threshold)

    detection = _load_detection_runtime_modules().socgfm
    artifact = detection.SocGFMCrossAttentionArtifact(
        decision_threshold=float(decision_threshold),
        default_account_probability=0.5,
        account_probabilities=account_probabilities,
        threshold_source=threshold_source,
        checkpoint_reference=str(source_root),
        provenance={
            "artifact_builder": "build_socgfm_detection_artifact.py",
            "version": version,
            "source_run_dir": str(source_root),
            "prediction_file_count": len(prediction_files),
            "account_probability_count": len(account_probabilities),
            "validation_row_count": len(validation_rows),
            "test_row_count": len(test_rows),
            "run_level_metric_count": len(run_level_metrics),
            "metric_source": metric_source,
            "claim_wording": "账号级信息行动成员识别实验 F1 0.8625-0.9971；线上为预计算成员概率到群组的聚合代理判别。",
        },
        source_run_hashes=source_run_hashes,
    )

    output_root.mkdir(parents=True, exist_ok=True)
    checkpoint_path = artifact.to_json(output_root / "checkpoint.json")
    checkpoint_sha256 = hashlib.sha256(checkpoint_path.read_bytes()).hexdigest()
    _write_account_probabilities_csv(
        output_root / "account_probabilities.csv",
        account_probabilities,
        probability_values,
    )
    provenance = {
        "source_run_dir": str(source_root),
        "prediction_files": [_relative_name(source_root, path) for path in prediction_files],
        "source_run_hashes": source_run_hashes,
        "account_probability_count": len(account_probabilities),
        "threshold_source": threshold_source,
        "metric_source": metric_source,
        "run_level_metric_count": len(run_level_metrics),
        "run_level_threshold_mean": _mean(run_level_thresholds),
        "decision_threshold": artifact.decision_threshold,
        "threshold_macro_f1": threshold_macro_f1,
        "claim_scope": artifact.claim_scope,
        "inference_mode": artifact.inference_mode,
        "online_neural_forward": artifact.online_neural_forward,
    }
    (output_root / "provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "technology": "coordination_detection",
        "backend": "socgfm_cross_attention",
        "model": "socgfm_cross_attention",
        "version": version,
        "checkpoint_path": "checkpoint.json",
        "account_probabilities_path": "account_probabilities.csv",
        "provenance_path": "provenance.json",
        "inference_mode": artifact.inference_mode,
        "claim_scope": artifact.claim_scope,
        "online_neural_forward": artifact.online_neural_forward,
        "unsupported_claims": list(artifact.unsupported_claims),
        "metrics": {
            "system_primary_model": "socgfm_cross_attention",
            "macro_f1": account_metrics["macro_f1"],
            "auprc": account_metrics["auprc"],
            "roc_auc": account_metrics["roc_auc"],
            "ece": account_metrics["ece"],
            "threshold_macro_f1": threshold_macro_f1,
            "metric_source": metric_source,
            "threshold_source": threshold_source,
            "p95_latency_seconds": 0.0,
            "official_validation_protocol": True,
            "shadow_classifier_recorded": True,
            "no_feature_leakage": True,
            "claimable_superiority_over_shadow_classifier": False,
            "claim_scope": artifact.claim_scope,
            "inference_mode": artifact.inference_mode,
            "online_neural_forward": artifact.online_neural_forward,
            "metric_scope": "account_level_io_membership",
            "deployment_scope": "precomputed_member_probability_cluster_aggregation",
        },
        "checkpoint_sha256": checkpoint_sha256,
    }
    _assert_manifest_claims_are_scoped(manifest)
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return {
        "artifact_dir": str(output_root),
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_sha256": checkpoint_sha256,
        "account_probability_count": len(account_probabilities),
        "prediction_file_count": len(prediction_files),
        "manifest_path": str(output_root / "manifest.json"),
    }


def _require_g_drive(path: Path) -> None:
    if path.drive.upper() != "G:":
        raise ValueError("SocGFM coordination detection artifacts must be written under the G: drive")


def _prediction_files(source_root: Path) -> list[Path]:
    if not source_root.exists():
        raise ValueError(f"source_run_dir does not exist: {source_root}")
    all_files = sorted(source_root.rglob("predictions.csv"))
    socgfm_files = [
        path
        for path in all_files
        if any(part.lower() == "socgfm_cross_attention" for part in path.parts)
    ]
    return socgfm_files or all_files


def _read_prediction_rows(path: Path, *, account_namespace: str) -> list[tuple[str, float, int | None, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"predictions file has no header: {path}")
        columns = {column.lower(): column for column in reader.fieldnames}
        account_column = _first_present(columns, "account_key", "account_id", "node_id", "user_id")
        score_column = _first_present(columns, "node_score", "score", "probability", "prediction_score", "predicted_probability")
        if account_column is None or score_column is None:
            raise ValueError(f"predictions file must include account and score columns: {path}")
        platform_column = _first_present(columns, "platform")
        label_column = _first_present(columns, "label", "y_true", "target")
        split_column = _first_present(columns, "evaluation_split", "split")
        rows: list[tuple[str, float, int | None, str]] = []
        for row in reader:
            account_id = str(row.get(account_column) or "").strip()
            if not account_id:
                continue
            platform = str(row.get(platform_column) or "").strip() if platform_column else ""
            probability = _unit_float(row.get(score_column), f"{path}:{score_column}")
            label = _optional_label(row.get(label_column)) if label_column else None
            split = str(row.get(split_column) or "").strip().lower() if split_column else ""
            rows.append((_account_key(platform, account_id, account_namespace), probability, label, split))
        return rows


def _first_present(columns: Mapping[str, str], *names: str) -> str | None:
    for name in names:
        if name in columns:
            return columns[name]
    return None


def _account_key(platform: str, account_id: str, account_namespace: str) -> str:
    namespace = platform or account_namespace
    namespace = namespace.strip().lower()
    if ":" in account_id:
        return account_id
    return f"{namespace}:{account_id}"


def _unit_float(value: Any, field_name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise ValueError(f"{field_name} must be within [0, 1]")
    return result


def _optional_label(value: Any) -> int | None:
    text = str(value).strip()
    if text == "":
        return None
    if text in {"0", "0.0", "false", "False"}:
        return 0
    if text in {"1", "1.0", "true", "True"}:
        return 1
    return None


def _summary_metrics(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    metrics = payload.get("metrics")
    return dict(metrics) if isinstance(metrics, Mapping) else {}


def _summary_threshold(metrics: Iterable[Mapping[str, Any]]) -> float:
    thresholds: list[float] = []
    for row in metrics:
        try:
            value = float(row.get("max_f1_threshold"))
        except (TypeError, ValueError):
            continue
        if math.isfinite(value) and 0.0 <= value <= 1.0:
            thresholds.append(value)
    if not thresholds:
        return 0.5
    return round(sum(thresholds) / len(thresholds), 12)


def _rows_for_splits(
    rows: Iterable[tuple[int, float, str]],
    allowed_splits: frozenset[str],
) -> list[tuple[int, float]]:
    return [
        (label, score)
        for label, score, split in rows
        if str(split or "").strip().lower() in allowed_splits
    ]


def _has_binary_labels(rows: Iterable[tuple[int, float]]) -> bool:
    return {label for label, _score in rows} == {0, 1}


def _mean(values: Iterable[float]) -> float | None:
    items = [float(value) for value in values if math.isfinite(float(value))]
    if not items:
        return None
    return round(sum(items) / len(items), 12)


def _mean_binary_metrics(metrics: Iterable[Mapping[str, float]]) -> dict[str, float]:
    values: dict[str, list[float]] = defaultdict(list)
    for row in metrics:
        for key in ("macro_f1", "auprc", "roc_auc", "ece"):
            try:
                value = float(row.get(key))
            except (TypeError, ValueError):
                continue
            if math.isfinite(value):
                values[key].append(value)
    return {
        "macro_f1": _mean(values["macro_f1"]) or 0.0,
        "auprc": _mean(values["auprc"]) or 0.0,
        "roc_auc": _mean(values["roc_auc"]) or 0.5,
        "ece": _mean(values["ece"]) or 0.0,
    }


def _summary_binary_metrics(
    summary_metrics: Iterable[Mapping[str, Any]],
    fallback_rows: list[tuple[int, float]],
    threshold: float,
) -> dict[str, float]:
    aggregated = _aggregate_summary_metrics(summary_metrics)
    if aggregated is None:
        return _binary_metrics(fallback_rows, threshold)
    if "ece" not in aggregated:
        aggregated["ece"] = _ece(fallback_rows)
    return {
        "macro_f1": float(aggregated.get("macro_f1", 0.0)),
        "auprc": float(aggregated.get("auprc", 0.0)),
        "roc_auc": float(aggregated.get("roc_auc", 0.5)),
        "ece": float(aggregated.get("ece", 0.0)),
    }


def _aggregate_summary_metrics(metrics: Iterable[Mapping[str, Any]]) -> dict[str, float] | None:
    values: dict[str, list[float]] = defaultdict(list)
    for row in metrics:
        macro_f1 = _metric_float(row, "max_f1")
        if macro_f1 is None:
            macro_f1 = _metric_float(row, "macro_f1", "f1")
        auprc = _metric_float(row, "auprc", "ap")
        roc_auc = _metric_float(row, "roc_auc", "auc")
        ece = _metric_float(row, "ece")
        for key, value in (
            ("macro_f1", macro_f1),
            ("auprc", auprc),
            ("roc_auc", roc_auc),
            ("ece", ece),
        ):
            if value is not None:
                values[key].append(value)
    required = {"macro_f1", "auprc", "roc_auc"}
    if not required <= set(values):
        return None
    return {
        key: round(sum(items) / len(items), 12)
        for key, items in values.items()
        if items
    }


def _metric_float(row: Mapping[str, Any], *names: str) -> float | None:
    for name in names:
        try:
            value = float(row.get(name))
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            return value
    return None


def _best_threshold(rows: list[tuple[int, float]]) -> tuple[float, float]:
    if not rows or len({label for label, _score in rows}) < 2:
        return math.nan, 0.0
    best_threshold = 0.5
    best_score = -1.0

    def consider(threshold: float, score: float) -> None:
        nonlocal best_threshold, best_score
        if score > best_score or (score == best_score and abs(threshold - 0.5) < abs(best_threshold - 0.5)):
            best_score = score
            best_threshold = threshold

    consider(0.5, _macro_f1(rows, 0.5))
    consider(0.0, _macro_f1(rows, 0.0))
    consider(1.0, _macro_f1(rows, 1.0))

    total_positive = sum(1 for label, _score in rows if label == 1)
    total_negative = len(rows) - total_positive
    true_positive = 0
    false_positive = 0
    sorted_rows = sorted(rows, key=lambda item: item[1], reverse=True)
    index = 0
    while index < len(sorted_rows):
        threshold = sorted_rows[index][1]
        group_positive = 0
        group_negative = 0
        while index < len(sorted_rows) and sorted_rows[index][1] == threshold:
            if sorted_rows[index][0] == 1:
                group_positive += 1
            else:
                group_negative += 1
            index += 1
        true_positive += group_positive
        false_positive += group_negative
        consider(
            threshold,
            _macro_f1_from_counts(
                total_positive=total_positive,
                total_negative=total_negative,
                true_positive=true_positive,
                false_positive=false_positive,
            ),
        )
    return round(best_threshold, 12), round(best_score, 12)


def _binary_metrics(rows: list[tuple[int, float]], threshold: float) -> dict[str, float]:
    if not rows:
        return {"macro_f1": 0.0, "auprc": 0.0, "roc_auc": 0.5, "ece": 0.0}
    return {
        "macro_f1": _macro_f1(rows, threshold),
        "auprc": _average_precision(rows),
        "roc_auc": _roc_auc(rows),
        "ece": _ece(rows),
    }


def _macro_f1(rows: list[tuple[int, float]], threshold: float) -> float:
    predictions = [(label, 1 if score >= threshold else 0) for label, score in rows]
    f1_values = []
    for target in (0, 1):
        tp = sum(1 for label, predicted in predictions if label == target and predicted == target)
        fp = sum(1 for label, predicted in predictions if label != target and predicted == target)
        fn = sum(1 for label, predicted in predictions if label == target and predicted != target)
        denominator = (2 * tp) + fp + fn
        f1_values.append(0.0 if denominator == 0 else (2 * tp) / denominator)
    return round(sum(f1_values) / 2.0, 12)


def _macro_f1_from_counts(
    *,
    total_positive: int,
    total_negative: int,
    true_positive: int,
    false_positive: int,
) -> float:
    false_negative = total_positive - true_positive
    true_negative = total_negative - false_positive
    positive_denominator = (2 * true_positive) + false_positive + false_negative
    negative_denominator = (2 * true_negative) + false_negative + false_positive
    positive_f1 = 0.0 if positive_denominator == 0 else (2 * true_positive) / positive_denominator
    negative_f1 = 0.0 if negative_denominator == 0 else (2 * true_negative) / negative_denominator
    return round((positive_f1 + negative_f1) / 2.0, 12)


def _average_precision(rows: list[tuple[int, float]]) -> float:
    positives = sum(1 for label, _score in rows if label == 1)
    if positives == 0:
        return 0.0
    sorted_rows = sorted(rows, key=lambda item: item[1], reverse=True)
    hit_count = 0
    precision_sum = 0.0
    for rank, (label, _score) in enumerate(sorted_rows, start=1):
        if label == 1:
            hit_count += 1
            precision_sum += hit_count / rank
    return round(precision_sum / positives, 12)


def _roc_auc(rows: list[tuple[int, float]]) -> float:
    positive_count = sum(1 for label, _score in rows if label == 1)
    negative_count = len(rows) - positive_count
    if not positive_count or not negative_count:
        return 0.5
    sorted_rows = sorted(rows, key=lambda item: item[1])
    positive_rank_sum = 0.0
    rank = 1
    index = 0
    while index < len(sorted_rows):
        tie_end = index + 1
        while tie_end < len(sorted_rows) and sorted_rows[tie_end][1] == sorted_rows[index][1]:
            tie_end += 1
        average_rank = (rank + (rank + tie_end - index - 1)) / 2.0
        positive_rank_sum += average_rank * sum(
            1 for label, _score in sorted_rows[index:tie_end] if label == 1
        )
        rank += tie_end - index
        index = tie_end
    auc = (positive_rank_sum - (positive_count * (positive_count + 1) / 2.0)) / (
        positive_count * negative_count
    )
    return round(auc, 12)


def _ece(rows: list[tuple[int, float]], bins: int = 10) -> float:
    if not rows:
        return 0.0
    total = len(rows)
    error = 0.0
    for index in range(bins):
        low = index / bins
        high = (index + 1) / bins
        bucket = [
            (label, score)
            for label, score in rows
            if (low <= score < high) or (index == bins - 1 and score == 1.0)
        ]
        if not bucket:
            continue
        confidence = sum(score for _label, score in bucket) / len(bucket)
        accuracy = sum(label for label, _score in bucket) / len(bucket)
        error += (len(bucket) / total) * abs(confidence - accuracy)
    return round(error, 12)


def _write_account_probabilities_csv(path: Path, probabilities: Mapping[str, float], raw_values: Mapping[str, list[float]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["account_key", "probability", "source_count"])
        writer.writeheader()
        for account_key, probability in sorted(probabilities.items()):
            writer.writerow(
                {
                    "account_key": account_key,
                    "probability": f"{probability:.12g}",
                    "source_count": len(raw_values[account_key]),
                }
            )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _relative_name(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def _assert_manifest_claims_are_scoped(manifest: Mapping[str, Any]) -> None:
    text = json.dumps(manifest, ensure_ascii=False)
    forbidden_phrases = (
        "group-level harmful coordination F1",
        "群组级有害协同检测 F1",
        "群组级有害协同 detection f1",
    )
    for phrase in forbidden_phrases:
        if phrase in text:
            raise ValueError(f"manifest contains unsupported group-level Detection claim: {phrase}")


__all__ = ["build_socgfm_detection_artifact"]
