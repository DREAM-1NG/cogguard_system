"""Run offline Review evidence-validation over review-post-case-v1 datasets.

This runner calls the deployed post semantic scaffold directly. It does not
train models, call online LLM agents, use web search, or mutate source datasets.
The output is a compact metric report plus JSONL predictions for later manual
reporting.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.review.post_semantics import assess_post_semantics  # noqa: E402


DEFAULT_DATASETS = [
    "MultiOFF",
    "HateXplain",
    "PHEME",
    "mcfend",
    "FakeSV",
    "Twitter15_16_dataset",
]

HARM_TYPE_MAP = {
    "abusive": "hate_harassment",
    "fake": "misinformation",
    "false": "misinformation",
    "hate": "hate_harassment",
    "hate_speech": "hate_harassment",
    "hatespeech": "hate_harassment",
    "misinformation": "misinformation",
    "misogynous": "hate_harassment",
    "offensive": "hate_harassment",
    "rumor": "misinformation",
    "rumour": "misinformation",
    "targeted_smear": "targeted_smear",
    "toxic": "hate_harassment",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-dir", default=r"G:\CISCN\tmp\review_offline_validation_20260703\cases")
    parser.add_argument("--output-dir", default=r"G:\CISCN\tmp\review_offline_validation_20260703\evidence_validation")
    parser.add_argument("--datasets", nargs="*", default=DEFAULT_DATASETS)
    parser.add_argument("--max-cases-per-dataset", type=int, default=0, help="0 means every converted case.")
    parser.add_argument("--prefer-embeddings", action="store_true", help="Use sentence-transformer embeddings if locally available.")
    args = parser.parse_args()

    case_dir = Path(args.case_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {
        "schema": "review-offline-evidence-validation-v1",
        "case_dir": str(case_dir),
        "output_dir": str(output_dir),
        "datasets_requested": args.datasets,
        "method": {
            "runner": "offline_direct_post_semantics",
            "scorer": "assess_post_semantics",
            "online_llm_agent": False,
            "external_web_or_rag": False,
            "gold_used_for_training": False,
            "twitter1516_policy": "coverage_audit_only_when_source_text_missing",
        },
        "datasets": {},
    }

    combined_rows: list[dict[str, Any]] = []
    for dataset in args.datasets:
        dataset_result, prediction_rows = evaluate_dataset(
            dataset,
            case_dir=case_dir,
            output_dir=output_dir / safe_name(dataset),
            max_cases=args.max_cases_per_dataset,
            prefer_embeddings=args.prefer_embeddings,
        )
        report["datasets"][dataset] = dataset_result
        combined_rows.extend(prediction_rows)

    report["summary"] = summarize_suite(report["datasets"])
    combined_path = output_dir / "evidence_validation_predictions.jsonl"
    write_jsonl(combined_path, combined_rows)
    report["combined_prediction_path"] = str(combined_path)
    report["combined_prediction_count"] = len(combined_rows)

    report_path = output_dir / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"wrote {report_path}")
    return 0


def evaluate_dataset(
    dataset: str,
    *,
    case_dir: Path,
    output_dir: Path,
    max_cases: int,
    prefer_embeddings: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    case_path = case_dir / f"{safe_name(dataset)}.jsonl"
    all_cases = load_cases(case_path)
    if max_cases > 0:
        all_cases = all_cases[:max_cases]
    if not all_cases:
        return (
            {
                "dataset": dataset,
                "status": "skipped",
                "skip_reason": f"case jsonl missing or empty: {case_path}",
                "case_path": str(case_path),
            },
            [],
        )

    usable_cases = [case for case in all_cases if text_of(case)]
    coverage = {
        "case_count": len(all_cases),
        "usable_text_cases": len(usable_cases),
        "text_missing": len(all_cases) - len(usable_cases),
        "view_available_counts": view_available_counts(all_cases),
        "claim_context_cases": sum(1 for case in all_cases if claim_context_text(case)),
    }
    if not usable_cases:
        return (
            {
                "dataset": dataset,
                "status": "coverage_only",
                "skip_reason": "no source text available for post semantic evidence validation",
                "case_path": str(case_path),
                "coverage": coverage,
                "metrics": {},
            },
            [],
        )

    prediction_rows = []
    failure_samples = []
    for case in usable_cases:
        row = evaluate_case(case, prefer_embeddings=prefer_embeddings)
        prediction_rows.append(row)
        if not row["passed"] and len(failure_samples) < 50:
            failure_samples.append(
                {
                    "case_id": row["case_id"],
                    "source_id": row["source_id"],
                    "split": row["split"],
                    "failure_reasons": row["failure_reasons"],
                    "gold_harmfulness": row["gold_harmfulness"],
                    "predicted_harmfulness": row["predicted_harmfulness"],
                    "text_excerpt": row["text_excerpt"],
                }
            )

    prediction_path = output_dir / "evidence_validation_predictions.jsonl"
    write_jsonl(prediction_path, prediction_rows)
    result = {
        "dataset": dataset,
        "status": "evaluated",
        "case_path": str(case_path),
        "prediction_path": str(prediction_path),
        "coverage": coverage,
        "metrics": compute_metrics(prediction_rows),
        "failure_samples": failure_samples,
    }
    return result, prediction_rows


def evaluate_case(case: dict[str, Any], *, prefer_embeddings: bool) -> dict[str, Any]:
    post_id = str(case.get("source_id") or case.get("case_id") or "")
    claim_id, claim_text = claim_identity(case)
    post = {
        "post_id": post_id,
        "author_id": str(case.get("metadata", {}).get("author_id") or ""),
        "author_name": str(case.get("metadata", {}).get("author_name") or ""),
        "platform": str(case.get("metadata", {}).get("platform") or case.get("dataset") or ""),
        "event_id": str(case.get("split") or ""),
        "content": text_of(case),
        "hashtags": hashtags_of(case),
        "media_urls": media_refs_of(case),
        "raw_data": raw_data_of(case),
    }
    prop_data = propagation_for_claim(claim_id, claim_text, post["content"])
    scored = assess_post_semantics(
        [post],
        prop_data,
        prefer_embeddings=prefer_embeddings,
        max_output_posts=1,
    )
    predictions = scored.get("aggregation_posts") or []
    prediction = predictions[0] if predictions else {}
    pred = prediction_view(prediction)
    gold_harm = normalized_harmfulness(case)
    gold_types = normalized_harm_types(case)
    expected_claim = claim_id or "NIL"
    failure_reasons = failure_reasons_for(
        pred,
        gold_harm=gold_harm,
        gold_types=gold_types,
        expected_claim=expected_claim,
    )
    return {
        "case_id": case.get("case_id"),
        "dataset": case.get("dataset"),
        "split": case.get("split"),
        "source_id": case.get("source_id"),
        "passed": not failure_reasons,
        "failure_reasons": failure_reasons,
        "gold_harmfulness": gold_harm,
        "predicted_harmfulness": pred["harm_label"],
        "gold_harm_types": gold_types,
        "predicted_harm_types": pred["harm_types"],
        "expected_claim_id": expected_claim,
        "predicted_claim_id": pred["claim_id"],
        "stance_label": pred["stance"],
        "claim_linked": pred["claim_id"] != "NIL",
        "stance_available": pred["stance"] in {"support", "deny", "query", "neutral"},
        "abstained": pred["abstained"],
        "has_evidence": pred["has_evidence"],
        "scores": pred["scores"],
        "modalities": pred["modalities"],
        "text_excerpt": text_of(case)[:240],
    }


def prediction_view(prediction: dict[str, Any]) -> dict[str, Any]:
    primary_claim = prediction.get("primary_claim") or {}
    stance = prediction.get("stance") or {}
    harmfulness = prediction.get("harmfulness") or {}
    evidence = prediction.get("evidence") or {}
    return {
        "claim_id": text(primary_claim.get("claim_id")) or "NIL",
        "stance": text(stance.get("label")) or "missing",
        "harm_label": text(harmfulness.get("label")) or "missing",
        "harm_types": [map_harm_type(item) for item in as_list(harmfulness.get("types"))],
        "modalities": as_list(prediction.get("modalities")),
        "has_evidence": any(text(value) for value in evidence.values()),
        "abstained": bool(stance.get("abstain")) or bool(harmfulness.get("abstain")),
        "scores": {
            "claim": safe_float(primary_claim.get("score")),
            "stance": safe_float(stance.get("confidence")),
            "harm": safe_float(harmfulness.get("score")),
        },
    }


def failure_reasons_for(
    pred: dict[str, Any],
    *,
    gold_harm: str,
    gold_types: list[str],
    expected_claim: str,
) -> list[str]:
    reasons = []
    if pred["harm_label"] != gold_harm:
        reasons.append("harm_label_mismatch")
    if gold_types and not set(gold_types).issubset(set(pred["harm_types"])):
        reasons.append("harm_type_mismatch")
    if expected_claim != pred["claim_id"]:
        reasons.append("claim_link_mismatch")
    if not pred["has_evidence"]:
        reasons.append("missing_evidence")
    if pred["abstained"]:
        reasons.append("model_abstained")
    return reasons


def compute_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    total = len(rows)
    label_correct = sum(1 for row in rows if row["gold_harmfulness"] == row["predicted_harmfulness"])
    claim_correct = sum(1 for row in rows if row["expected_claim_id"] == row["predicted_claim_id"])
    evidence_count = sum(1 for row in rows if row["has_evidence"])
    abstain_count = sum(1 for row in rows if row["abstained"])
    stance_available_count = sum(1 for row in rows if row["stance_available"])
    claim_linked_count = sum(1 for row in rows if row["claim_linked"])
    type_tp = type_fp = type_fn = 0
    for row in rows:
        gold = set(row["gold_harm_types"])
        pred = set(row["predicted_harm_types"])
        type_tp += len(gold & pred)
        type_fp += len(pred - gold)
        type_fn += len(gold - pred)
    precision = type_tp / (type_tp + type_fp) if (type_tp + type_fp) else 0.0
    recall = type_tp / (type_tp + type_fn) if (type_tp + type_fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "evaluated_posts": total,
        "passed_posts": sum(1 for row in rows if row["passed"]),
        "failed_posts": sum(1 for row in rows if not row["passed"]),
        "harm_label_accuracy": round(label_correct / total, 6),
        "claim_link_accuracy": round(claim_correct / total, 6),
        "harm_type_micro_precision": round(precision, 6),
        "harm_type_micro_recall": round(recall, 6),
        "harm_type_micro_f1": round(f1, 6),
        "evidence_presence_rate": round(evidence_count / total, 6),
        "abstain_rate": round(abstain_count / total, 6),
        "claim_linked_rate": round(claim_linked_count / total, 6),
        "stance_available_rate": round(stance_available_count / total, 6),
        "gold_distribution": dict(Counter(row["gold_harmfulness"] for row in rows)),
        "prediction_distribution": dict(Counter(row["predicted_harmfulness"] for row in rows)),
        "stance_distribution": dict(Counter(row["stance_label"] for row in rows)),
        "failure_reason_counts": dict(Counter(reason for row in rows for reason in row["failure_reasons"])),
    }


def summarize_suite(datasets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    evaluated = {
        name: result
        for name, result in datasets.items()
        if result.get("status") == "evaluated"
    }
    coverage_only = {
        name: result.get("skip_reason", "")
        for name, result in datasets.items()
        if result.get("status") == "coverage_only"
    }
    skipped = {
        name: result.get("skip_reason", "")
        for name, result in datasets.items()
        if result.get("status") == "skipped"
    }
    return {
        "dataset_count": len(datasets),
        "evaluated_datasets": sorted(evaluated),
        "coverage_only_datasets": coverage_only,
        "skipped_datasets": skipped,
        "evaluated_posts": sum(int((result.get("metrics") or {}).get("evaluated_posts", 0)) for result in evaluated.values()),
        "online_llm_agent": False,
        "external_web_or_rag": False,
        "claim": "offline_evidence_validation_complete" if evaluated else "no_dataset_evaluated",
    }


def claim_identity(case: dict[str, Any]) -> tuple[str, str]:
    context = case.get("claim_context") or {}
    claim_text = claim_context_text(case)
    if not claim_text:
        return "", ""
    claim_id = "claim::" + str(case.get("case_id") or case.get("source_id") or "").strip()
    return claim_id, claim_text


def propagation_for_claim(claim_id: str, claim_text: str, post_text: str) -> dict[str, Any]:
    if not claim_id or not claim_text:
        return {}
    return {
        "claims": [
            {
                "object_id": claim_id,
                "share_count": 1,
                "account_count": 1,
            }
        ],
        "evidence_chains": [
            {
                "claim_id": claim_id,
                "supporting_posts": [
                    {"content": claim_text},
                    {"content": post_text},
                ],
            }
        ],
    }


def raw_data_of(case: dict[str, Any]) -> dict[str, Any]:
    context = case.get("claim_context") or {}
    views = case.get("views") or {}
    raw = {
        "caption": text(context.get("claim_text")),
        "summary": text(context.get("evidence_text")),
    }
    image = views.get("img") or {}
    video = views.get("video") or {}
    if image.get("media_path"):
        raw["image_path"] = image.get("media_path")
    if image.get("media_url"):
        raw["image_url"] = image.get("media_url")
    if video.get("video_id"):
        raw["video_id"] = video.get("video_id")
    return raw


def media_refs_of(case: dict[str, Any]) -> list[str]:
    refs = []
    views = case.get("views") or {}
    for view_name in ("img", "video"):
        view = views.get(view_name) or {}
        for key in ("media_path", "media_url", "video_url"):
            value = text(view.get(key))
            if value:
                refs.append(value)
    return refs


def hashtags_of(case: dict[str, Any]) -> list[str]:
    raw = text((case.get("metadata") or {}).get("hashtag"))
    if not raw:
        return []
    return [item.strip("# ") for item in raw.replace(",", " ").split() if item.strip("# ")]


def view_available_counts(cases: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter()
    for case in cases:
        for view, payload in (case.get("views") or {}).items():
            if isinstance(payload, dict) and payload.get("available"):
                counts[view] += 1
    return dict(counts)


def normalized_harmfulness(case: dict[str, Any]) -> str:
    value = text((case.get("labels") or {}).get("harmfulness")).lower()
    if value in {"harmful", "non_harmful"}:
        return value
    return "harmful" if value in {"positive", "fake", "rumor", "rumour"} else "non_harmful"


def normalized_harm_types(case: dict[str, Any]) -> list[str]:
    labels = case.get("labels") or {}
    values = as_list(labels.get("harm_type"))
    if not values and normalized_harmfulness(case) == "harmful":
        raw = text(labels.get("raw_label"))
        values = [raw] if raw else []
    mapped = [map_harm_type(value) for value in values]
    return sorted({value for value in mapped if value})


def map_harm_type(value: Any) -> str:
    key = text(value).lower()
    return HARM_TYPE_MAP.get(key, key)


def claim_context_text(case: dict[str, Any]) -> str:
    context = case.get("claim_context") or {}
    parts = [
        text(context.get("claim_text")),
        text(context.get("evidence_text")),
    ]
    for link in as_list(context.get("evidence_links")):
        if isinstance(link, dict):
            parts.extend([text(link.get("position")), text(link.get("mediatype")), text(link.get("link"))])
        else:
            parts.append(text(link))
    return " ".join(part for part in parts if part).strip()


def text_of(case: dict[str, Any]) -> str:
    return text(case.get("text"))


def load_cases(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    cases = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                cases.append(item)
    return cases


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def safe_name(value: str) -> str:
    return value.replace("/", "_").replace("\\", "_").replace(" ", "_")


if __name__ == "__main__":
    raise SystemExit(main())
