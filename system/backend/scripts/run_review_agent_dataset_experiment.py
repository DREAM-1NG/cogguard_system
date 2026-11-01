"""Run GPT-based Review MARO-style agent experiments over local review-post-case-v1 datasets.

This script is for offline dataset experiments, not the live system API flow.
It converts normalized post cases into minimal risk-report contexts, runs the
existing MARO-style agent layer directly, and writes machine-readable reports.
It also exports `review-teacher-silver-v1` rows for offline student distillation.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.review.agent_provider import OpenAICompatibleAgentProvider  # noqa: E402
from app.core.review.agent_provider import OpenAICompatibleConfig  # noqa: E402
from app.core.review.agent_review import run_manual_agent_review  # noqa: E402
from app.core.review.propagation_context import build_propagation_context_for_case  # noqa: E402
from app.core.review.post_semantics import assess_post_semantics  # noqa: E402
from app.core.review.trainable_post import build_teacher_silver_record  # noqa: E402
from app.config import settings  # noqa: E402
from app.tasks.review_tasks import _build_http_retrieval_provider  # noqa: E402


DEFAULT_DATASETS = ["HateXplain", "MultiOFF", "PHEME", "mcfend", "FakeSV"]
DEFAULT_AGENTS = [
    "PostHarmAgent",
    "MultimodalConsistencyAgent",
    "ClaimEvidenceAgent",
    "QuestionReflectionAgent",
    "HarmfulnessJudgeAgent",
    "CountermeasureAgent",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-dir", default=r"G:\CISCN\tmp\review_offline_validation_20260703\cases")
    parser.add_argument("--output-dir", default=r"G:\CISCN\tmp\review_agent_dataset_experiment")
    parser.add_argument("--datasets", nargs="*", default=DEFAULT_DATASETS)
    parser.add_argument("--agents", nargs="*", default=DEFAULT_AGENTS)
    parser.add_argument("--max-cases-per-dataset", type=int, default=10)
    parser.add_argument("--prefer-embeddings", action="store_true")
    parser.add_argument("--include-media-base64", action="store_true")
    parser.add_argument("--require-vision", action="store_true")
    parser.add_argument("--enable-active-retrieval", action="store_true")
    parser.add_argument("--enable-external-retrieval", action="store_true")
    parser.add_argument("--enable-light-debate", action="store_true")
    parser.add_argument("--enable-full-debate", action="store_true")
    parser.add_argument("--debate-max-rounds", type=int, default=3)
    parser.add_argument("--retrieval-top-k", type=int, default=3)
    parser.add_argument("--api-key", default=(os.getenv("LLM_API_KEY") or settings.LLM_API_KEY or ""))
    parser.add_argument("--base-url", default=(os.getenv("LLM_API_BASE") or settings.LLM_API_BASE or "https://api.openai.com/v1"))
    parser.add_argument("--model", default=(os.getenv("LLM_MODEL") or settings.LLM_MODEL or "gpt-5.4"))
    parser.add_argument("--wire-api", default=(os.getenv("LLM_API_WIRE") or settings.LLM_API_WIRE or "responses"))
    parser.add_argument("--timeout-seconds", type=float, default=float(os.getenv("LLM_TIMEOUT_SECONDS") or settings.LLM_TIMEOUT_SECONDS or "180"))
    parser.add_argument("--case-timeout-seconds", type=float, default=float(os.getenv("Review_AGENT_CASE_TIMEOUT_SECONDS") or "600"))
    parser.add_argument("--flush-every-case", action="store_true")
    parser.add_argument("--verbose-progress", action="store_true")
    args = parser.parse_args()

    if not args.api_key.strip():
        raise SystemExit("Missing API key. Pass --api-key or set LLM_API_KEY.")

    case_dir = Path(args.case_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    provider = OpenAICompatibleAgentProvider(
        OpenAICompatibleConfig(
            api_key=args.api_key.strip(),
            base_url=args.base_url.strip(),
            model=args.model.strip(),
            wire_api=args.wire_api.strip(),
            timeout_seconds=float(args.timeout_seconds),
            include_media_base64=bool(args.include_media_base64),
            require_vision=bool(args.require_vision),
        )
    )
    active_retriever = build_env_retriever() if args.enable_external_retrieval else None

    report: dict[str, Any] = {
        "schema": "review-agent-dataset-experiment-v1",
        "case_dir": str(case_dir),
        "output_dir": str(output_dir),
        "datasets_requested": args.datasets,
        "agents": args.agents,
        "llm": {
            "base_url": args.base_url,
            "model": args.model,
            "wire_api": args.wire_api,
            "include_media_base64": bool(args.include_media_base64),
            "require_vision": bool(args.require_vision),
            "api_key_configured": True,
        },
        "method": {
            "runner": "offline_dataset_to_maro_agent_review",
            "online_llm_agent": True,
            "system_api_required": False,
            "external_retrieval_enabled": bool(args.enable_external_retrieval),
            "teacher_silver_schema": "review-teacher-silver-v1",
            "teacher_silver_mode": "structured_supervision_with_full_traces_for_hard_cases",
        },
        "datasets": {},
    }

    for dataset in args.datasets:
        dataset_result = asyncio.run(
            evaluate_dataset(
                dataset=dataset,
                case_dir=case_dir,
                output_dir=output_dir / safe_name(dataset),
                max_cases=args.max_cases_per_dataset,
                prefer_embeddings=bool(args.prefer_embeddings),
                provider=provider,
                model=args.model,
                agent_names=list(args.agents),
                include_media_base64=bool(args.include_media_base64),
                require_vision=bool(args.require_vision),
                enable_active_retrieval=bool(args.enable_active_retrieval),
                enable_external_retrieval=bool(args.enable_external_retrieval),
                enable_light_debate=bool(args.enable_light_debate),
                enable_full_debate=bool(args.enable_full_debate),
                debate_max_rounds=int(args.debate_max_rounds),
                retrieval_top_k=int(args.retrieval_top_k),
                case_timeout_seconds=float(args.case_timeout_seconds),
                flush_every_case=bool(args.flush_every_case),
                verbose_progress=bool(args.verbose_progress),
                active_retriever=active_retriever,
            )
        )
        report["datasets"][dataset] = dataset_result

    report["summary"] = summarize_suite(report["datasets"])
    report_path = output_dir / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"wrote {report_path}")
    return 0


async def evaluate_dataset(
    *,
    dataset: str,
    case_dir: Path,
    output_dir: Path,
    max_cases: int,
    prefer_embeddings: bool,
    provider: OpenAICompatibleAgentProvider,
    model: str,
    agent_names: list[str],
    include_media_base64: bool,
    require_vision: bool,
    enable_active_retrieval: bool,
    enable_external_retrieval: bool,
    enable_light_debate: bool,
    enable_full_debate: bool,
    debate_max_rounds: int,
    retrieval_top_k: int,
    case_timeout_seconds: float,
    flush_every_case: bool,
    verbose_progress: bool,
    active_retriever,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    case_path = case_dir / f"{safe_name(dataset)}.jsonl"
    cases = load_cases(case_path)
    if max_cases > 0:
        cases = cases[:max_cases]
    if not cases:
        return {"dataset": dataset, "status": "skipped", "reason": f"missing or empty case file: {case_path}"}

    prediction_path = output_dir / "agent_predictions.jsonl"
    teacher_silver_path = output_dir / "teacher_silver.jsonl"
    rows = []
    teacher_rows = []
    total = len(cases)
    for index, case in enumerate(cases, start=1):
        case_id = str(case.get("case_id") or f"{dataset}:{index}")
        if verbose_progress:
            print(f"[dataset:{dataset}] case {index}/{total} start {case_id}", flush=True)
        started_at = time.time()
        try:
            row = await asyncio.wait_for(
                evaluate_case(
                    case=case,
                    provider=provider,
                    model=model,
                    agent_names=agent_names,
                    prefer_embeddings=prefer_embeddings,
                    include_media_base64=include_media_base64,
                    require_vision=require_vision,
                    enable_active_retrieval=enable_active_retrieval,
                    enable_external_retrieval=enable_external_retrieval,
                    enable_light_debate=enable_light_debate,
                    enable_full_debate=enable_full_debate,
                    debate_max_rounds=debate_max_rounds,
                    retrieval_top_k=retrieval_top_k,
                    active_retriever=active_retriever,
                ),
                timeout=case_timeout_seconds,
            )
        except asyncio.TimeoutError:
            row = timeout_row(case=case, dataset=dataset, timeout_seconds=case_timeout_seconds)
        elapsed_seconds = round(time.time() - started_at, 3)
        row["elapsed_seconds"] = elapsed_seconds
        rows.append(row)
        teacher_rows.append(row.get("teacher_silver") or {})
        if flush_every_case:
            write_jsonl(prediction_path, rows)
            write_jsonl(teacher_silver_path, [item for item in teacher_rows if item])
        if verbose_progress:
            print(
                f"[dataset:{dataset}] case {index}/{total} done {case_id} "
                f"judge={row.get('judge_status')} elapsed={elapsed_seconds}s",
                flush=True,
            )

    write_jsonl(prediction_path, rows)
    write_jsonl(teacher_silver_path, [item for item in teacher_rows if item])
    return {
        "dataset": dataset,
        "status": "evaluated",
        "case_count": len(rows),
        "prediction_path": str(prediction_path),
        "teacher_silver_path": str(teacher_silver_path),
        "teacher_silver_count": len([item for item in teacher_rows if item]),
        "metrics": compute_metrics(rows),
    }


async def evaluate_case(
    *,
    case: dict[str, Any],
    provider: OpenAICompatibleAgentProvider,
    model: str,
    agent_names: list[str],
    prefer_embeddings: bool,
    include_media_base64: bool,
    require_vision: bool,
    enable_active_retrieval: bool,
    enable_external_retrieval: bool,
    enable_light_debate: bool,
    enable_full_debate: bool,
    debate_max_rounds: int,
    retrieval_top_k: int,
    active_retriever,
) -> dict[str, Any]:
    report = build_minimal_report(case, prefer_embeddings=prefer_embeddings)
    selected_post_ids = [item.get("post_id") for item in (report.get("post_semantics") or {}).get("posts") or [] if item.get("post_id")]
    selected_tree_ids = tree_ids_of(case)
    effective_agent_names = agent_names_for_case(agent_names, has_tree=bool(selected_tree_ids))
    agent_result = await run_manual_agent_review(
        report=report,
        agent_names=effective_agent_names,
        case_id=str(case.get("case_id") or ""),
        selected_post_ids=[str(item) for item in selected_post_ids[:1]],
        selected_tree_ids=selected_tree_ids,
        human_triggered_by="offline_dataset_experiment",
        provider=provider,
        model=model,
        provider_name="offline_llm_experiment",
        include_media_base64=include_media_base64,
        require_vision=require_vision,
        enable_active_retrieval=enable_active_retrieval,
        enable_light_debate=enable_light_debate,
        enable_full_debate=enable_full_debate,
        debate_max_rounds=debate_max_rounds,
        retrieval_top_k=retrieval_top_k,
        active_retriever=active_retriever,
        external_retrieval_enabled=enable_external_retrieval,
        policy={},
        error_memory_summary={},
    )
    judge_report = next(
        (item for item in agent_result["agent_reports"] if item.get("report_role") == "judge_final"),
        next((item for item in agent_result["agent_reports"] if item.get("agent_name") == "HarmfulnessJudgeAgent"), {}),
    )
    return {
        "case_id": case.get("case_id"),
        "dataset": case.get("dataset"),
        "split": case.get("split"),
        "source_id": case.get("source_id"),
        "gold_harmfulness": ((case.get("labels") or {}).get("harmfulness") or "unknown"),
        "agent_summary": agent_result.get("summary") or {},
        "judge_status": judge_report.get("status"),
        "judge_report_text": judge_report.get("report_text"),
        "judge_sidecar": judge_report.get("structured_sidecar") or {},
        "teacher_silver": build_teacher_silver_record(case, agent_result),
        "all_agent_reports": [
            {
                "agent_name": item.get("agent_name"),
                "report_role": item.get("report_role"),
                "status": item.get("status"),
                "report_text": item.get("report_text"),
            }
            for item in agent_result.get("agent_reports") or []
        ],
    }


def timeout_row(*, case: dict[str, Any], dataset: str, timeout_seconds: float) -> dict[str, Any]:
    return {
        "case_id": case.get("case_id"),
        "dataset": case.get("dataset") or dataset,
        "split": case.get("split"),
        "source_id": case.get("source_id"),
        "gold_harmfulness": ((case.get("labels") or {}).get("harmfulness") or "unknown"),
        "agent_summary": {
            "requested_agents": 0,
            "completed": 0,
            "failed": 1,
            "timeout_seconds": timeout_seconds,
        },
        "judge_status": "timeout",
        "judge_report_text": None,
        "judge_sidecar": {
            "schema_version": "review-agent-sidecar-v1",
            "timeout_seconds": timeout_seconds,
            "review_required": True,
        },
        "all_agent_reports": [],
        "error": f"case_timeout_after_{timeout_seconds}_seconds",
    }


def build_minimal_report(case: dict[str, Any], *, prefer_embeddings: bool) -> dict[str, Any]:
    post = {
        "post_id": str(case.get("source_id") or case.get("case_id") or ""),
        "author_id": str((case.get("metadata") or {}).get("author_id") or ""),
        "author_name": str((case.get("metadata") or {}).get("author_name") or ""),
        "platform": str((case.get("metadata") or {}).get("platform") or case.get("dataset") or ""),
        "event_id": str(case.get("split") or case.get("dataset") or ""),
        "content": text_of(case),
        "hashtags": hashtags_of(case),
        "media_urls": media_refs_of(case),
        "raw_data": raw_data_of(case),
    }
    claim_context = case.get("claim_context") or {}
    claim_id = str(claim_context.get("claim_id") or case.get("source_id") or case.get("case_id") or "claim-1")
    claim_text = str(claim_context.get("claim_text") or text_of(case)[:200] or "unknown claim").strip()
    prop_data = {
        "global_summary": {
            "claim_rank": [
                {
                    "claim_id": claim_id,
                    "claim_text": claim_text,
                    "share_count": 1,
                    "account_count": 1,
                }
            ]
        }
    }
    post_semantics = assess_post_semantics([post], prop_data, prefer_embeddings=prefer_embeddings, max_output_posts=1)
    harmful_label = ((case.get("labels") or {}).get("harmfulness") or "unknown")
    propagation_context = build_propagation_context_for_case(
        case,
        claim_rank=prop_data["global_summary"]["claim_rank"],
        graph_summary=(case.get("thread_context") or {}).get("summary") or {},
        post_semantics_summary=post_semantics.get("summary") or {},
    )
    thread_metrics = propagation_context.get("tree_metrics") or {}
    return {
        "report_id": f"offline::{case.get('dataset')}::{case.get('case_id')}",
        "event_id": str(case.get("dataset") or ""),
        "platform": str((case.get("metadata") or {}).get("platform") or case.get("dataset") or ""),
        "scores": {"risk_level": "high" if harmful_label == "harmful" else "low"},
        "post_semantics": post_semantics,
        "review_harmfulness": {
            "global_summary": {
                "review_harm_risk_level": "high" if harmful_label == "harmful" else "low",
                "claim_rank": prop_data["global_summary"]["claim_rank"],
            },
            "review_queue": {
                "retrieval_tasks": [{"query": claim_text}] if claim_text else [],
                "review_items": [{"post_id": post["post_id"], "reason": "offline_dataset_case"}],
            },
            "review_execution": {"retrieval_results": []},
            "propagation_context": propagation_context,
            "graph_export": {
                "summary": {
                    "node_count": int(thread_metrics.get("node_count", 1) or 1),
                    "edge_count": int(thread_metrics.get("edge_count", 0) or 0),
                    "graph_native_ready": bool(propagation_context.get("has_thread_context")),
                    "source": "review-propagation-context-v1",
                }
            },
        },
        "disarm_analysis": {},
    }


def compute_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    judge_completed = sum(1 for row in rows if row.get("judge_status") == "completed")
    failed = sum(1 for row in rows if row.get("judge_status") != "completed")
    agent_completed = sum((row.get("agent_summary") or {}).get("completed", 0) for row in rows)
    agent_failed = sum((row.get("agent_summary") or {}).get("failed", 0) for row in rows)
    return {
        "cases": len(rows),
        "judge_completed": judge_completed,
        "judge_failed": failed,
        "judge_completion_rate": round(judge_completed / len(rows), 6),
        "agent_completed_reports": agent_completed,
        "agent_failed_reports": agent_failed,
        "gold_distribution": dict(Counter(row.get("gold_harmfulness") for row in rows)),
    }


def summarize_suite(datasets: dict[str, Any]) -> dict[str, Any]:
    totals = defaultdict(int)
    evaluated = []
    for dataset, item in datasets.items():
        if item.get("status") != "evaluated":
            continue
        evaluated.append(dataset)
        metrics = item.get("metrics") or {}
        totals["cases"] += int(metrics.get("cases", 0))
        totals["judge_completed"] += int(metrics.get("judge_completed", 0))
        totals["judge_failed"] += int(metrics.get("judge_failed", 0))
        totals["agent_completed_reports"] += int(metrics.get("agent_completed_reports", 0))
        totals["agent_failed_reports"] += int(metrics.get("agent_failed_reports", 0))
    totals["evaluated_datasets"] = evaluated
    if totals["cases"]:
        totals["judge_completion_rate"] = round(totals["judge_completed"] / totals["cases"], 6)
    else:
        totals["judge_completion_rate"] = 0.0
    return dict(totals)


def load_cases(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=str))
            handle.write("\n")


def build_env_retriever():
    api_key = (os.getenv("Review_RETRIEVAL_API_KEY") or settings.Review_RETRIEVAL_API_KEY or "").strip()
    base_url = (os.getenv("Review_RETRIEVAL_BASE_URL") or settings.Review_RETRIEVAL_BASE_URL or "").strip()
    if not api_key or not base_url:
        return None
    return _build_http_retrieval_provider(
        base_url=base_url,
        api_key=api_key,
        search_path=(os.getenv("Review_RETRIEVAL_SEARCH_PATH") or settings.Review_RETRIEVAL_SEARCH_PATH or "/search").strip() or "/search",
        timeout_seconds=float(os.getenv("Review_RETRIEVAL_TIMEOUT_SECONDS") or "20"),
        provider_name=(os.getenv("Review_RETRIEVAL_PROVIDER_NAME") or settings.Review_RETRIEVAL_PROVIDER_NAME or "").strip() or "env_retrieval",
        adapter=(os.getenv("Review_RETRIEVAL_ADAPTER") or settings.Review_RETRIEVAL_ADAPTER or "").strip(),
    )


def safe_name(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")


def text_of(case: dict[str, Any]) -> str:
    return str(case.get("text") or "").strip()


def hashtags_of(case: dict[str, Any]) -> list[str]:
    raw = (case.get("metadata") or {}).get("hashtag") or (case.get("metadata") or {}).get("hashtags") or []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    if isinstance(raw, str):
        return [part.strip() for part in raw.replace(",", " ").split() if part.strip()]
    return []


def media_refs_of(case: dict[str, Any]) -> list[str]:
    views = case.get("views") or {}
    refs = []
    for key in ("img", "video", "meme"):
        view = views.get(key) or {}
        for field in ("media_path", "media_url"):
            value = str(view.get(field) or "").strip()
            if value:
                refs.append(value)
    return refs


def tree_ids_of(case: dict[str, Any]) -> list[str]:
    thread_context = case.get("thread_context") if isinstance(case.get("thread_context"), dict) else {}
    tree_id = str(thread_context.get("tree_id") or "").strip()
    return [tree_id] if tree_id else []


def agent_names_for_case(agent_names: list[str], *, has_tree: bool) -> list[str]:
    names = list(agent_names)
    if not has_tree or "PropagationTreeAgent" in names:
        return names
    try:
        insert_at = names.index("QuestionReflectionAgent")
    except ValueError:
        insert_at = len(names)
    return [*names[:insert_at], "PropagationTreeAgent", *names[insert_at:]]


def raw_data_of(case: dict[str, Any]) -> dict[str, Any]:
    claim_context = case.get("claim_context") or {}
    metadata = case.get("metadata") or {}
    return {
        "ocr_text": str(metadata.get("ocr_text") or ""),
        "asr_text": str(metadata.get("asr_text") or ""),
        "caption": str(metadata.get("caption") or metadata.get("title") or ""),
        "claim_text": str(claim_context.get("claim_text") or ""),
        "evidence_text": str(claim_context.get("evidence_text") or ""),
    }


if __name__ == "__main__":
    raise SystemExit(main())
