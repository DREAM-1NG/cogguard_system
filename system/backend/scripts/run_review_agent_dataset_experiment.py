"""Run GPT-based Review MARO-style agent experiments over local review-post-case-v1 datasets.

This script is for offline dataset experiments, not the live system API flow.
It converts normalized post cases into minimal risk-report contexts, runs the
existing MARO-style agent layer directly, and writes machine-readable reports.
It also exports `review-teacher-silver-v1` rows for offline student distillation.
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
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
DEFAULT_RETRIEVAL_DATASETS = ["PHEME", "mcfend", "FakeSV"]
CLAIM_REVIEW_DATASETS = {item.lower() for item in DEFAULT_RETRIEVAL_DATASETS}
DEFAULT_AGENTS = [
    "PostHarmAgent",
    "MultimodalConsistencyAgent",
    "ClaimEvidenceAgent",
    "PropagationTreeAgent",
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
    parser.add_argument(
        "--case-manifest",
        "--pilot-manifest",
        dest="case_manifest",
        default="",
        help="Optional gold-free JSONL used to select the exact experiment population.",
    )
    parser.add_argument(
        "--population-role",
        choices=["evaluation", "teacher_silver"],
        default="evaluation",
        help="Evaluation accepts test cases; teacher_silver rejects test cases to prevent leakage.",
    )
    parser.add_argument("--prefer-embeddings", action="store_true")
    parser.add_argument("--include-media-base64", action="store_true")
    parser.add_argument("--require-vision", action="store_true")
    parser.add_argument("--enable-active-retrieval", action="store_true")
    parser.add_argument("--enable-external-retrieval", action="store_true")
    parser.add_argument("--enable-light-debate", action="store_true")
    parser.add_argument("--enable-full-debate", action="store_true")
    parser.add_argument("--enable-deep-judge", action="store_true")
    parser.add_argument(
        "--experiment-profile",
        choices=["maro_fixed", "maro_routed"],
        default="",
        help="MARO benchmark profile: fixed complex chain or auto-routed chain.",
    )
    parser.add_argument(
        "--retrieval-datasets",
        nargs="*",
        default=DEFAULT_RETRIEVAL_DATASETS,
        help="Datasets allowed to call the external retrieval provider.",
    )
    parser.add_argument(
        "--enable-countermeasure",
        action="store_true",
        help="Enable post-Judge CountermeasureAgent for non-MARO product-compatible runs.",
    )
    parser.add_argument(
        "--disable-llm-cache",
        action="store_true",
        help="Bypass replay/record cache for real latency and cost measurements.",
    )
    parser.add_argument("--runtime-mode", default="auto")
    parser.add_argument("--debate-max-rounds", type=int, default=3)
    parser.add_argument("--retrieval-top-k", type=int, default=3)
    parser.add_argument("--dataset-concurrency", type=int, default=2)
    parser.add_argument("--max-agent-calls-per-case", type=int, default=0)
    parser.add_argument("--active-policy-path", default="")
    parser.add_argument("--error-memory-path", default="")
    parser.add_argument("--api-key", default=(os.getenv("LLM_API_KEY") or settings.LLM_API_KEY or ""))
    parser.add_argument("--base-url", default=(os.getenv("LLM_API_BASE") or settings.LLM_API_BASE or "https://api.openai.com/v1"))
    parser.add_argument("--model", default=(os.getenv("LLM_MODEL") or settings.LLM_MODEL or "gpt-5.4"))
    parser.add_argument("--wire-api", default=(os.getenv("LLM_API_WIRE") or settings.LLM_API_WIRE or "responses"))
    parser.add_argument("--timeout-seconds", type=float, default=float(os.getenv("LLM_TIMEOUT_SECONDS") or settings.LLM_TIMEOUT_SECONDS or "180"))
    parser.add_argument("--case-timeout-seconds", type=float, default=float(os.getenv("Review_AGENT_CASE_TIMEOUT_SECONDS") or "900"))
    parser.add_argument("--flush-every-case", action="store_true")
    parser.add_argument("--verbose-progress", action="store_true")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse case rows already written under output-dir and evaluate only missing case IDs.",
    )
    args = parser.parse_args()

    profile = str(args.experiment_profile or "").strip().lower()
    effective_runtime_mode = (
        "complex" if profile == "maro_fixed" else "auto" if profile == "maro_routed" else str(args.runtime_mode)
    )
    profile_is_maro = profile in {"maro_fixed", "maro_routed"}
    effective_enable_deep_judge = False if profile_is_maro else bool(args.enable_deep_judge)
    effective_enable_light_debate = False if profile_is_maro else bool(args.enable_light_debate)
    effective_enable_full_debate = False if profile_is_maro else bool(args.enable_full_debate)
    effective_enable_countermeasure = False if profile_is_maro else bool(args.enable_countermeasure)
    effective_max_agent_calls = int(args.max_agent_calls_per_case or 0) or (8 if profile_is_maro else 0)
    retrieval_dataset_names = {str(item).strip().lower() for item in args.retrieval_datasets if str(item).strip()}

    if not args.api_key.strip():
        raise SystemExit("Missing API key. Pass --api-key or set LLM_API_KEY.")

    case_dir = Path(args.case_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if args.dataset_concurrency < 1:
        raise SystemExit("--dataset-concurrency must be at least 1.")
    if args.max_agent_calls_per_case < 0:
        raise SystemExit("--max-agent-calls-per-case cannot be negative.")
    active_policy = load_json_object(args.active_policy_path, "active policy")
    error_memory_summary = load_json_object(args.error_memory_path, "error memory")
    case_manifest = (
        load_case_manifest(Path(args.case_manifest), population_role=str(args.population_role))
        if str(args.case_manifest).strip()
        else None
    )

    provider = OpenAICompatibleAgentProvider(
        OpenAICompatibleConfig(
            api_key=args.api_key.strip(),
            base_url=args.base_url.strip(),
            model=args.model.strip(),
            wire_api=args.wire_api.strip(),
            timeout_seconds=float(args.timeout_seconds),
            include_media_base64=bool(args.include_media_base64),
            require_vision=bool(args.require_vision),
            cache_enabled=False if args.disable_llm_cache else None,
        )
    )
    active_retriever = build_env_retriever() if args.enable_external_retrieval else None

    report: dict[str, Any] = {
        "schema": "review-agent-dataset-experiment-v1",
        "case_dir": str(case_dir),
        "output_dir": str(output_dir),
        "datasets_requested": args.datasets,
        "agents": args.agents,
        "experiment_profile": profile or "custom",
        "retrieval_datasets": sorted(retrieval_dataset_names),
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
            "external_retrieval_dataset_filter": sorted(retrieval_dataset_names),
            "llm_cache_disabled": bool(args.disable_llm_cache),
            "teacher_silver_schema": "review-teacher-silver-v1",
            "teacher_silver_mode": "structured_supervision_with_full_traces_for_hard_cases",
        },
        "execution_budget": {
            "provider_timeout_seconds": float(args.timeout_seconds),
            "case_timeout_seconds": float(args.case_timeout_seconds),
            "dataset_concurrency": int(args.dataset_concurrency),
            "max_agent_calls_per_case": effective_max_agent_calls,
        },
        "case_manifest": {
            "enabled": case_manifest is not None,
            "path": str(args.case_manifest or ""),
            "population_role": str(args.population_role),
            "row_count": sum(len(rows) for rows in (case_manifest or {}).values()),
        },
        "datasets": {},
    }

    async def evaluate_suite() -> None:
        try:
            for dataset in args.datasets:
                retrieval_allowed = str(dataset).strip().lower() in retrieval_dataset_names
                dataset_result = await evaluate_dataset(
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
                    enable_active_retrieval=bool(args.enable_active_retrieval and retrieval_allowed),
                    enable_external_retrieval=bool(args.enable_external_retrieval and retrieval_allowed),
                    enable_light_debate=effective_enable_light_debate,
                    enable_full_debate=effective_enable_full_debate,
                    enable_deep_judge=effective_enable_deep_judge,
                    enable_countermeasure=effective_enable_countermeasure,
                    runtime_mode=effective_runtime_mode,
                    experiment_profile=profile or "custom",
                    debate_max_rounds=int(args.debate_max_rounds),
                    retrieval_top_k=int(args.retrieval_top_k),
                    case_timeout_seconds=float(args.case_timeout_seconds),
                    dataset_concurrency=int(args.dataset_concurrency),
                    max_agent_calls_per_case=effective_max_agent_calls,
                    flush_every_case=bool(args.flush_every_case),
                    verbose_progress=bool(args.verbose_progress),
                    active_retriever=active_retriever if retrieval_allowed else None,
                    policy=active_policy,
                    error_memory_summary=error_memory_summary,
                    case_manifest=case_manifest,
                    resume=bool(args.resume),
                )
                report["datasets"][dataset] = dataset_result
                (output_dir / "report.partial.json").write_text(
                    json.dumps(report, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
        finally:
            if hasattr(provider, "aclose"):
                await provider.aclose()

    asyncio.run(evaluate_suite())

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
    enable_deep_judge: bool,
    enable_countermeasure: bool = False,
    runtime_mode: str = "auto",
    experiment_profile: str = "custom",
    debate_max_rounds: int,
    retrieval_top_k: int,
    case_timeout_seconds: float,
    dataset_concurrency: int,
    flush_every_case: bool,
    verbose_progress: bool,
    active_retriever,
    policy: dict[str, Any] | None = None,
    error_memory_summary: dict[str, Any] | None = None,
    max_agent_calls_per_case: int = 0,
    case_manifest: dict[str, list[dict[str, str]]] | None = None,
    resume: bool = False,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_started_at = time.perf_counter()
    case_path = case_dir / f"{safe_name(dataset)}.jsonl"
    cases = load_cases(case_path)
    cases, manifest_audit = select_manifest_cases(cases, dataset, case_manifest)
    if max_cases > 0:
        cases = cases[:max_cases]
    if not cases:
        return {
            "dataset": dataset,
            "status": "skipped",
            "reason": f"missing, empty, or not selected by case manifest: {case_path}",
            "case_manifest_audit": manifest_audit,
        }

    prediction_path = output_dir / "agent_predictions.jsonl"
    teacher_silver_path = output_dir / "teacher_silver.jsonl"
    total = len(cases)
    semaphore = asyncio.Semaphore(dataset_concurrency)

    existing_rows_by_id: dict[str, dict[str, Any]] = {}
    if resume and prediction_path.exists():
        for item in load_cases(prediction_path):
            case_id = str(item.get("case_id") or "").strip()
            # Completed rows are reusable; failed rows must be retried when a
            # resumed run has corrected credentials or provider settings.
            if case_id and item.get("judge_status") == "completed":
                existing_rows_by_id[case_id] = item
    pending_cases = [
        (index, case)
        for index, case in enumerate(cases, start=1)
        if str(case.get("case_id") or f"{dataset}:{index}") not in existing_rows_by_id
    ]

    async def evaluate_bounded(index: int, case: dict[str, Any]) -> dict[str, Any]:
        case_id = str(case.get("case_id") or f"{dataset}:{index}")
        if verbose_progress:
            print(f"[dataset:{dataset}] case {index}/{total} start {case_id}", flush=True)
        started_at = time.time()
        try:
            async with semaphore:
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
                        enable_deep_judge=enable_deep_judge,
                        enable_countermeasure=enable_countermeasure,
                        runtime_mode=runtime_mode,
                        experiment_profile=experiment_profile,
                        debate_max_rounds=debate_max_rounds,
                        retrieval_top_k=retrieval_top_k,
                        max_agent_calls_per_case=max_agent_calls_per_case,
                        active_retriever=active_retriever,
                        policy=policy,
                        error_memory_summary=error_memory_summary,
                    ),
                    timeout=case_timeout_seconds,
                )
        except asyncio.TimeoutError:
            row = timeout_row(case=case, dataset=dataset, timeout_seconds=case_timeout_seconds)
        except Exception as exc:  # Keep one malformed/provider-failed case from aborting the suite.
            row = exception_row(case=case, dataset=dataset, exc=exc)
        elapsed_seconds = round(time.time() - started_at, 3)
        row["elapsed_seconds"] = elapsed_seconds
        if verbose_progress:
            print(
                f"[dataset:{dataset}] case {index}/{total} done {case_id} "
                f"judge={row.get('judge_status')} elapsed={elapsed_seconds}s",
                flush=True,
            )
        return row

    rows_by_id = dict(existing_rows_by_id)
    tasks = [asyncio.create_task(evaluate_bounded(index, case)) for index, case in pending_cases]
    for task in tasks:
        row = await task
        rows_by_id[str(row.get("case_id") or "")] = row
        if flush_every_case:
            ordered_rows = [
                rows_by_id[case_id]
                for case in cases
                if (case_id := str(case.get("case_id") or "")) in rows_by_id
            ]
            write_jsonl(prediction_path, ordered_rows)
            write_jsonl(
                teacher_silver_path,
                [item.get("teacher_silver") or {} for item in ordered_rows if item.get("teacher_silver")],
            )

    rows = [rows_by_id[str(case.get("case_id") or "")] for case in cases]
    write_jsonl(prediction_path, rows)
    write_jsonl(
        teacher_silver_path,
        [item.get("teacher_silver") or {} for item in rows if item.get("teacher_silver")],
    )
    return {
        "dataset": dataset,
        "status": "evaluated",
        "case_count": len(rows),
        "prediction_path": str(prediction_path),
        "teacher_silver_path": str(teacher_silver_path),
        "teacher_silver_count": len([item for item in rows if item.get("teacher_silver")]),
        "case_manifest_audit": manifest_audit,
        "wall_elapsed_seconds": round(time.perf_counter() - dataset_started_at, 3),
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
    enable_deep_judge: bool,
    enable_countermeasure: bool = False,
    runtime_mode: str = "auto",
    experiment_profile: str = "custom",
    debate_max_rounds: int,
    retrieval_top_k: int,
    max_agent_calls_per_case: int,
    active_retriever,
    policy: dict[str, Any] | None = None,
    error_memory_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report = build_minimal_report(case, prefer_embeddings=prefer_embeddings)
    selected_post_ids = [item.get("post_id") for item in (report.get("post_semantics") or {}).get("posts") or [] if item.get("post_id")]
    selected_tree_ids = tree_ids_of(case)
    effective_agent_names = agent_names_for_case(agent_names, has_tree=bool(selected_tree_ids))
    review_kwargs: dict[str, Any] = {
        "report": report,
        "agent_names": effective_agent_names,
        "case_id": str(case.get("case_id") or ""),
        "selected_post_ids": [str(item) for item in selected_post_ids[:1]],
        "selected_tree_ids": selected_tree_ids,
        "human_triggered_by": "offline_dataset_experiment",
        "provider": provider,
        "model": model,
        "provider_name": "offline_llm_experiment",
        "include_media_base64": include_media_base64,
        "require_vision": require_vision,
        "enable_active_retrieval": enable_active_retrieval,
        "enable_light_debate": enable_light_debate,
        "enable_full_debate": enable_full_debate,
        "enable_deep_judge": enable_deep_judge,
        "enable_countermeasure": enable_countermeasure,
        "runtime_mode": runtime_mode,
        "debate_max_rounds": debate_max_rounds,
        "retrieval_top_k": retrieval_top_k,
        "active_retriever": active_retriever,
        "external_retrieval_enabled": enable_external_retrieval,
        "policy": policy or {},
        "error_memory_summary": error_memory_summary or {},
    }
    if max_agent_calls_per_case > 0 and supports_max_agent_calls(run_manual_agent_review):
        review_kwargs["max_agent_calls_per_case"] = max_agent_calls_per_case
    agent_result = await run_manual_agent_review(**review_kwargs)
    judge_report = next(
        (item for item in agent_result["agent_reports"] if item.get("report_role") == "judge_final"),
        next((item for item in agent_result["agent_reports"] if item.get("agent_name") == "HarmfulnessJudgeAgent"), {}),
    )
    return {
        "case_id": case.get("case_id"),
        "dataset": case.get("dataset"),
        "split": case.get("split"),
        "source_id": case.get("source_id"),
        "agent_summary": agent_result.get("summary") or {},
        "judge_status": judge_report.get("status"),
        "judge_report_text": judge_report.get("report_text"),
        "judge_sidecar": judge_report.get("structured_sidecar") or {},
        "runtime_profile": experiment_profile,
        "runtime_audit": agent_result.get("audit") or {},
        "llm_call_audit": (agent_result.get("audit") or {}).get("llm_call_audit") or [],
        "retrieval_audit": ((agent_result.get("active_retrieval") or {}).get("audit") or {}),
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


def exception_row(*, case: dict[str, Any], dataset: str, exc: Exception) -> dict[str, Any]:
    error_class = type(exc).__name__
    message = str(exc).strip().replace("\x00", " ")
    return {
        "case_id": case.get("case_id"),
        "dataset": case.get("dataset") or dataset,
        "split": case.get("split"),
        "source_id": case.get("source_id"),
        "agent_summary": {
            "requested_agents": 0,
            "completed": 0,
            "failed": 1,
        },
        "judge_status": "failed",
        "judge_report_text": None,
        "judge_sidecar": {
            "schema_version": "review-agent-sidecar-v1",
            "review_required": True,
        },
        "all_agent_reports": [],
        "error": {
            "stage": "case",
            "error_class": error_class,
            "message": message[:1000],
        },
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
    claim_context = case.get("claim_context") if isinstance(case.get("claim_context"), dict) else {}
    dataset_name = str(case.get("dataset") or "").strip().lower()
    explicit_claim = bool(claim_context.get("claim_id") or claim_context.get("claim_text"))
    claim_enabled = explicit_claim or dataset_name in CLAIM_REVIEW_DATASETS
    claim_id = str(claim_context.get("claim_id") or case.get("source_id") or case.get("case_id") or "claim-1")
    claim_text = str(claim_context.get("claim_text") or text_of(case)[:200] or "unknown claim").strip() if claim_enabled else ""
    prop_data = {
        "global_summary": {
            "claim_rank": [
                {
                    "claim_id": claim_id,
                    "claim_text": claim_text,
                    "share_count": 1,
                    "account_count": 1,
                }
            ] if claim_enabled else []
        }
    }
    post_semantics = assess_post_semantics([post], prop_data, prefer_embeddings=prefer_embeddings, max_output_posts=1)
    propagation_context = build_propagation_context_for_case(
        {key: value for key, value in case.items() if key != "labels"},
        claim_rank=prop_data["global_summary"]["claim_rank"],
        graph_summary=(case.get("thread_context") or {}).get("summary") or {},
        post_semantics_summary=post_semantics.get("summary") or {},
    )
    thread_metrics = propagation_context.get("tree_metrics") or {}
    return {
        "report_id": f"offline::{case.get('dataset')}::{case.get('case_id')}",
        "event_id": str(case.get("dataset") or ""),
        "platform": str((case.get("metadata") or {}).get("platform") or case.get("dataset") or ""),
        "scores": {"risk_level": "unknown"},
        "post_semantics": post_semantics,
        "review_harmfulness": {
            "global_summary": {
                "review_harm_risk_level": "unknown",
                "claim_rank": prop_data["global_summary"]["claim_rank"],
            },
            "review_queue": {
                "retrieval_tasks": [{"query": claim_text}] if claim_enabled and claim_text else [],
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
    case_latencies = [float(row.get("elapsed_seconds") or 0.0) for row in rows]
    call_audits = [
        item
        for row in rows
        for item in (row.get("llm_call_audit") or [])
        if isinstance(item, dict)
    ]
    stage_latencies: dict[str, list[float]] = defaultdict(list)
    for item in call_audits:
        stage = str(item.get("stage") or "unknown")
        duration = item.get("provider_duration_ms", item.get("duration_ms"))
        try:
            stage_latencies[stage].append(float(duration or 0.0))
        except (TypeError, ValueError):
            continue
    usage_rows = [
        item
        for item in call_audits
        if item.get("total_tokens") is not None
    ]
    total_tokens = sum(float(item.get("total_tokens") or 0.0) for item in usage_rows)
    retry_count = sum(int(item.get("retry_count") or 0) for item in call_audits)
    retrieval_audits = [row.get("retrieval_audit") or {} for row in rows]
    external_attempted = sum(1 for item in retrieval_audits if item.get("manual_review_default_external_attempted"))
    external_failed = sum(len(item.get("failures") or []) for item in retrieval_audits)
    external_succeeded = sum(
        int(item.get("external_calls") or 0) - len(item.get("failures") or [])
        for item in retrieval_audits
        if item.get("manual_review_default_external_attempted")
    )
    runtime_audits = [row.get("runtime_audit") or {} for row in rows]
    simple_cases = sum(1 for item in runtime_audits if item.get("effective_runtime_mode") == "simple")
    complex_cases = sum(1 for item in runtime_audits if item.get("effective_runtime_mode") == "complex")
    actual_calls = [int((row.get("agent_summary") or {}).get("actual_llm_call_count") or 0) for row in rows]
    planned_calls = [int((row.get("agent_summary") or {}).get("planned_llm_call_count") or 0) for row in rows]
    return {
        "cases": len(rows),
        "judge_completed": judge_completed,
        "judge_failed": failed,
        "judge_completion_rate": round(judge_completed / len(rows), 6),
        "agent_completed_reports": agent_completed,
        "agent_failed_reports": agent_failed,
        "runtime": {
            "simple_cases": simple_cases,
            "complex_cases": complex_cases,
            "simple_rate": round(simple_cases / len(rows), 6),
            "complex_rate": round(complex_cases / len(rows), 6),
        },
        "latency": {
            "case_seconds": percentile_summary(case_latencies),
            "stages_ms": {stage: percentile_summary(values) for stage, values in stage_latencies.items()},
        },
        "calls": {
            "planned_total": sum(planned_calls),
            "actual_total": sum(actual_calls),
            "calls_per_case": round(sum(actual_calls) / len(rows), 6),
            "planned_calls_per_case": round(sum(planned_calls) / len(rows), 6),
            "retry_count": retry_count,
            "retry_rate": round(retry_count / len(call_audits), 6) if call_audits else 0.0,
        },
        "tokens": {
            "available_call_count": len(usage_rows),
            "availability_rate": round(len(usage_rows) / len(call_audits), 6) if call_audits else 0.0,
            "total": round(total_tokens, 3) if usage_rows else None,
            "per_case": round(total_tokens / len(rows), 3) if usage_rows else None,
        },
        "failures": {
            "case_failure_rate": round(failed / len(rows), 6),
            "provider_call_failure_count": sum(1 for item in call_audits if item.get("status") == "failed"),
            "http_error_classes": dict(Counter(str(item.get("error_class") or "unknown") for item in call_audits if item.get("status") == "failed")),
        },
        "external_retrieval": {
            "attempted_case_count": external_attempted,
            "succeeded_call_count": max(0, external_succeeded),
            "failed_call_count": external_failed,
            "attempt_rate": round(external_attempted / len(rows), 6),
        },
        "teacher_silver_eligible": sum(
            1
            for row in rows
            if (row.get("teacher_silver") or {}).get("distillation_eligible") is True
        ),
    }


def percentile_summary(values: list[float]) -> dict[str, Any]:
    clean = sorted(float(value) for value in values if value >= 0)
    if not clean:
        return {"count": 0, "p50": 0.0, "p95": 0.0, "mean": 0.0}
    def quantile(q: float) -> float:
        index = (len(clean) - 1) * q
        lower = int(index)
        upper = min(len(clean) - 1, lower + 1)
        fraction = index - lower
        return clean[lower] + (clean[upper] - clean[lower]) * fraction
    return {
        "count": len(clean),
        "p50": round(quantile(0.50), 3),
        "p95": round(quantile(0.95), 3),
        "mean": round(sum(clean) / len(clean), 3),
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


def load_case_manifest(
    path: Path,
    *,
    population_role: str = "evaluation",
) -> dict[str, list[dict[str, str]]]:
    if not path.is_file():
        raise SystemExit(f"Case manifest JSONL missing: {path}")
    manifest: dict[str, list[dict[str, str]]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    for row in load_cases(path):
        case_id = str(row.get("case_id") or "").strip()
        dataset = str(row.get("dataset") or "").strip()
        split = str(row.get("split") or "").strip()
        protocol_split = str(row.get("protocol_split") or "").strip()
        if not case_id or not dataset:
            continue
        key = (dataset.lower(), case_id)
        if key in seen:
            raise SystemExit(f"Duplicate case manifest entry: {dataset}/{case_id}")
        if population_role == "teacher_silver" and protocol_split != "train":
            raise SystemExit("Teacher Silver population cannot contain test cases.")
        if population_role == "evaluation" and protocol_split and protocol_split != "test":
            raise SystemExit("evaluation population must declare protocol_split=test.")
        seen.add(key)
        manifest[dataset.lower()].append(
            {
                "case_id": case_id,
                "dataset": dataset,
                "split": split,
                "protocol_split": protocol_split,
            }
        )
    return dict(manifest)


def select_manifest_cases(
    cases: list[dict[str, Any]],
    dataset: str,
    manifest: dict[str, list[dict[str, str]]] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if manifest is None:
        return cases, {
            "manifest_enabled": False,
            "requested_case_count": len(cases),
            "selected_case_count": len(cases),
            "missing_case_ids": [],
        }
    requested = manifest.get(dataset.lower(), [])
    case_index = {str(case.get("case_id") or ""): case for case in cases}
    selected: list[dict[str, Any]] = []
    missing: list[str] = []
    for item in requested:
        case_id = item["case_id"]
        case = case_index.get(case_id)
        if case is None or (item.get("split") and str(case.get("split") or "") != item["split"]):
            missing.append(case_id)
            continue
        selected.append(case)
    return selected, {
        "manifest_enabled": True,
        "requested_case_count": len(requested),
        "selected_case_count": len(selected),
        "missing_case_ids": missing,
    }


def load_json_object(path_value: str, label: str) -> dict[str, Any]:
    if not path_value:
        return {}
    path = Path(path_value)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Unable to load {label} JSON from {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"{label.capitalize()} JSON must contain an object: {path}")
    return payload


def supports_max_agent_calls(review_runner: Any) -> bool:
    try:
        parameters = inspect.signature(review_runner).parameters.values()
    except (TypeError, ValueError):
        return False
    return any(
        parameter.name == "max_agent_calls_per_case" or parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in parameters
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=str))
            handle.write("\n")


def build_env_retriever():
    api_key = (os.getenv("Review_RETRIEVAL_API_KEY") or settings.REVIEW_RETRIEVAL_API_KEY or "").strip()
    base_url = (os.getenv("Review_RETRIEVAL_BASE_URL") or settings.REVIEW_RETRIEVAL_BASE_URL or "").strip()
    if not api_key or not base_url:
        return None
    return _build_http_retrieval_provider(
        base_url=base_url,
        api_key=api_key,
        search_path=(os.getenv("Review_RETRIEVAL_SEARCH_PATH") or settings.REVIEW_RETRIEVAL_SEARCH_PATH or "/search").strip() or "/search",
        timeout_seconds=float(os.getenv("Review_RETRIEVAL_TIMEOUT_SECONDS") or "20"),
        provider_name=(os.getenv("Review_RETRIEVAL_PROVIDER_NAME") or settings.REVIEW_RETRIEVAL_PROVIDER_NAME or "").strip() or "env_retrieval",
        adapter=(os.getenv("Review_RETRIEVAL_ADAPTER") or settings.REVIEW_RETRIEVAL_ADAPTER or "").strip(),
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
