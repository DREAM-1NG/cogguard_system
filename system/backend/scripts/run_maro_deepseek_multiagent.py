"""Run a Weibo21 MARO reference-protocol MultiAgent claim-review experiment.

The runner evaluates local Weibo21 cases with MARO's implemented
content-analysis -> comment-analysis -> fact-questioning -> retrieval ->
fact-summary -> fact-checking -> Judgment chain. It is a CogGuard protocol,
not an official MARO dataset reproduction. No
production Review API, Student model, Coordination, or Propagation runtime is
modified or invoked by this runner.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from app.core.review.deepseek_provider import build_deepseek_provider  # noqa: E402
from app.core.review.maro_experiment_evaluation import evaluate_claim_decisions  # noqa: E402
from app.core.review.maro_experiment_evaluation import evaluate_maro_reference_binary_metrics  # noqa: E402
from run_review_agent_dataset_experiment import (  # noqa: E402
    build_env_retriever,
    evaluate_dataset,
    load_case_manifest,
    load_json_object,
    summarize_suite,
)


DEFAULT_CASE_DIR = Path(r"G:\CISCN\.tmp\review_post_cases_weibo21")
DEFAULT_DATASETS = ("Weibo21",)


def main() -> int:
    args = parse_args()
    if args.profile != "maro_reference":
        raise SystemExit("--profile must be maro_reference")
    if tuple(args.datasets) != DEFAULT_DATASETS:
        raise SystemExit("This runner is scoped to the local Weibo21 protocol; use --datasets Weibo21.")
    if not os.getenv("DEEPSEEK_API_KEY", "").strip():
        raise SystemExit(
            "DEEPSEEK_API_KEY is missing. The runner never accepts API keys as "
            "arguments or writes them to experiment artifacts."
        )

    case_dir = Path(args.case_dir)
    output_dir = Path(args.output_dir) / args.profile
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = load_case_manifest(Path(args.case_manifest), population_role="evaluation") if args.case_manifest else None
    policy = load_json_object(args.active_policy_path, "active policy")
    error_memory = load_json_object(args.error_memory_path, "error memory")
    provider, provider_config = build_deepseek_provider()
    evidence_retrieval_enabled = bool(args.enable_active_retrieval or args.enable_external_retrieval)
    active_retriever = build_env_retriever() if evidence_retrieval_enabled else None

    report: dict[str, Any] = {
        "schema": "cogguard-maro-deepseek-experiment-v1",
        "dataset_protocol": "weibo21_maro_reference_adapter_v1",
        "protocol_boundary": {
            "source_dataset": "Weibo21",
            "task": "binary Chinese fake-news claim review",
            "input_scope": "case-selected MARO input profile; comments remain a separate role-scoped view",
            "maro_relation": "official MARO role sequence adapted to Weibo21, not official MARO dataset reproduction",
        },
        "case_dir": str(case_dir),
        "output_dir": str(output_dir),
        "profile": args.profile,
        "datasets_requested": list(args.datasets),
        "agent_chain": {
            "official_role_sequence": "ContentAnalysis -> CommentAnalysis -> FactQuestioning -> EvidenceRAG -> FactSummarizer -> FactChecking -> Judgment",
            "comment_boundary": "CommentAnalysis reports unavailable when a case uses post_only; comments never become fact evidence.",
            "ins_rule_optimization": "not reproduced: the official repository leaves its dataset-specific prompts, model endpoint, and rule inputs as placeholders.",
            "countermeasure": "disabled",
            "multimodal": "disabled",
            "propagation": "not part of this MARO misinformation experiment",
        },
        "llm": {
            "provider": "deepseek",
            "base_url": provider_config.base_url,
            "model": provider_config.model,
            "wire_api": "chat_completions",
            "api_key_configured": True,
        },
        "execution": {
            "max_cases_per_dataset": args.max_cases_per_dataset,
            "case_timeout_seconds": args.case_timeout_seconds,
            "dataset_concurrency": args.dataset_concurrency,
            "max_agent_calls_per_case": args.max_agent_calls_per_case,
            "evidence_retrieval_enabled": evidence_retrieval_enabled,
        },
        "datasets": {},
    }

    async def run() -> None:
        try:
            for dataset in args.datasets:
                result = await evaluate_dataset(
                    dataset=dataset,
                    case_dir=case_dir,
                    output_dir=output_dir / _safe_name(dataset),
                    max_cases=args.max_cases_per_dataset,
                    prefer_embeddings=False,
                    provider=provider,
                    model=provider_config.model,
                    agent_names=[],
                    include_media_base64=False,
                    require_vision=False,
                    enable_active_retrieval=evidence_retrieval_enabled,
                    enable_external_retrieval=evidence_retrieval_enabled,
                    enable_light_debate=False,
                    enable_full_debate=False,
                    enable_deep_judge=False,
                    enable_countermeasure=False,
                    runtime_mode="maro_reference",
                    experiment_profile=args.profile,
                    debate_max_rounds=0,
                    retrieval_top_k=args.retrieval_top_k,
                    case_timeout_seconds=args.case_timeout_seconds,
                    dataset_concurrency=args.dataset_concurrency,
                    flush_every_case=True,
                    verbose_progress=args.verbose_progress,
                    active_retriever=active_retriever,
                    policy=policy,
                    error_memory_summary=error_memory,
                    max_agent_calls_per_case=args.max_agent_calls_per_case,
                    case_manifest=manifest,
                    resume=args.resume,
                    include_propagation_agent=False,
                    maro_reference_protocol=True,
                )
                report["datasets"][dataset] = result
                _write_json(output_dir / "report.partial.json", report)
        finally:
            await provider.aclose()

    asyncio.run(run())
    report["summary"] = summarize_suite(report["datasets"])
    prediction_rows = _load_prediction_rows(report["datasets"])
    selected_identities = {
        (str(row.get("dataset") or "").lower(), str(row.get("case_id") or ""))
        for row in prediction_rows
        if str(row.get("case_id") or "")
    }
    source_cases = _load_source_cases(
        case_dir,
        args.datasets,
        selected_identities=selected_identities,
    )
    report["decision_evaluation"] = evaluate_claim_decisions(source_cases, prediction_rows)
    report["maro_reference_binary_metrics"] = evaluate_maro_reference_binary_metrics(source_cases, prediction_rows)
    _write_json(output_dir / "report.json", report)
    _write_json(
        output_dir / "experiment_manifest.json",
        {
            "schema": "cogguard-maro-deepseek-experiment-manifest-v1",
            "dataset_protocol": report["dataset_protocol"],
            "profile": args.profile,
            "datasets": list(args.datasets),
            "case_dir": str(case_dir),
            "output_dir": str(output_dir),
            "api_key": "[process_env_only]",
        },
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"wrote {output_dir / 'report.json'}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-dir", default=str(DEFAULT_CASE_DIR))
    parser.add_argument("--output-dir", default=r"G:\CISCN\.tmp\maro_deepseek_experiments")
    parser.add_argument("--datasets", nargs="*", default=list(DEFAULT_DATASETS))
    parser.add_argument("--profile", choices=["maro_reference"], required=True)
    parser.add_argument("--max-cases-per-dataset", type=int, default=0)
    parser.add_argument("--case-manifest", default="")
    parser.add_argument("--active-policy-path", default="")
    parser.add_argument("--error-memory-path", default="")
    parser.add_argument(
        "--enable-active-retrieval",
        action="store_true",
        help="Enable the configured traceable EvidenceRAG provider for MARO fact questions.",
    )
    parser.add_argument(
        "--enable-external-retrieval",
        action="store_true",
        help="Compatibility alias for --enable-active-retrieval.",
    )
    parser.add_argument("--retrieval-top-k", type=int, default=3)
    parser.add_argument("--dataset-concurrency", type=int, default=1)
    parser.add_argument("--max-agent-calls-per-case", type=int, default=8)
    parser.add_argument("--case-timeout-seconds", type=float, default=900.0)
    parser.add_argument("--verbose-progress", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.max_cases_per_dataset < 0 or args.dataset_concurrency < 1:
        raise SystemExit("max cases must be >= 0 and dataset concurrency must be >= 1")
    if args.max_agent_calls_per_case < 1:
        raise SystemExit("--max-agent-calls-per-case must be >= 1")
    if args.retrieval_top_k < 1:
        raise SystemExit("--retrieval-top-k must be >= 1")
    return args


def _safe_name(value: str) -> str:
    return str(value).replace("/", "_").replace("\\", "_").replace(" ", "_")


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _load_source_cases(
    case_dir: Path,
    datasets: list[str],
    *,
    selected_identities: set[tuple[str, str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for dataset in datasets:
        path = case_dir / f"{_safe_name(dataset)}.jsonl"
        if not path.is_file():
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    row = json.loads(line)
                    identity = (str(row.get("dataset") or "").lower(), str(row.get("case_id") or ""))
                    if identity in selected_identities:
                        rows.append(row)
    return rows


def _load_prediction_rows(datasets: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in datasets.values():
        path_value = str(item.get("prediction_path") or "")
        path = Path(path_value)
        if not path.is_file():
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return rows


if __name__ == "__main__":
    raise SystemExit(main())
