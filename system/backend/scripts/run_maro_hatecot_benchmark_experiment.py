"""Evaluate the MARO-compatible HateCoT harm Teacher on external benchmarks.

This is a sampled source-to-target transfer study, not an official MARO or
HateCoT reproduction.  HateCoT source labels are used only to optimize rules
on source validation tasks. Target labels stay out of every Agent and Judge
prompt and are read only after prediction for scoring.
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.review.deepseek_provider import build_deepseek_provider, has_deepseek_api_key  # noqa: E402
from app.core.review.experiment_concurrency import ExperimentConcurrency, run_ordered_bounded  # noqa: E402
from app.core.review.hatecot_harm_benchmarks import (  # noqa: E402
    BENCHMARK_LABEL_KEY,
    HATECOT_BENCHMARKS,
    HateCoTBenchmark,
    build_benchmark_target_manifest,
    load_hatecheck_cases,
    load_hatexplain_cases,
    load_latent_hate_cases,
    map_hatecot_source_cases,
    select_benchmark_target_cases,
)
from app.core.review.hatecot_harm_experiment import load_hatecot_cases  # noqa: E402
from app.core.review.maro_harm_benchmark_protocol import (  # noqa: E402
    BenchmarkJudgeTask,
    JudgeTask,
    benchmark_majority_vote,
    build_benchmark_judge_prompt,
    evaluate_benchmark_predictions,
    parse_benchmark_judgment,
)
from app.core.review.maro_harm_protocol import (  # noqa: E402
    has_complete_harm_analysis,
    run_maro_harm_multiagent_analysis,
)
from app.core.review.maro_rule_optimization import (  # noqa: E402
    CrossDomainValidationTask,
    DecisionRule,
    MARORuleOptimizationConfig,
    build_cross_domain_validation_tasks,
    optimize_decision_rules,
)


DEFAULT_HATECOT_CSV = Path(r"G:\CISCN\dataset\HateCoT\hatecot_final_D3.csv")
DEFAULT_HATECHECK_CSV = Path(r"G:\CISCN\dataset\hatecheck-data\test_suite_cases.csv")
DEFAULT_HATEXPLAIN_DIR = Path(r"G:\CISCN\dataset\kt3_public\HateXplain")
DEFAULT_LATENT_HATE_TSV = Path(r"G:\CISCN\.tmp\hatecot_transfer_datasets\implicit_hate_v1_stg1_posts.tsv")
DEFAULT_OUTPUT_DIR = Path(r"G:\CISCN\.tmp\maro_hatecot_benchmark")

PAPER_BOUNDARY = {
    "source_paper": "A Multi-Agent Framework with Automated Decision Rule Optimization for Cross-Domain Misinformation Detection",
    "paper_url": "https://aclanthology.org/2025.emnlp-main.291/",
    "repository": "https://github.com/Brtulien/MARO",
    "transfer": "MARO-compatible interpersonal-harm benchmark transfer, not official MARO misinformation reproduction.",
    "retained_mechanisms": [
        "source-validation-only rule optimization",
        "strict-improvement retention",
        "top-k decision-rule voting",
        "separate analysis and final Judge phases",
    ],
    "replaced_mechanisms": [
        "fact-checking/external retrieval is not used for harmful-language classification",
        "benchmark-specific harm label spaces replace MARO's fake/real labels",
        "comment analysis is omitted because all selected benchmarks are post-only",
    ],
}


class JudgeExecutionError(RuntimeError):
    """Raised when a target or validation Judge cannot return a strict label."""


@dataclass(frozen=True)
class BoundedExperimentProvider:
    """Apply shared non-secret concurrency telemetry to an LLM provider."""

    execution: ExperimentConcurrency
    delegate: Any

    @property
    def last_call_telemetry(self) -> dict[str, Any]:
        telemetry = getattr(self.delegate, "last_call_telemetry", {})
        return dict(telemetry) if isinstance(telemetry, Mapping) else {}

    async def __call__(self, **kwargs: Any) -> str:
        return await self.execution.invoke(
            service="deepseek",
            operation=self.delegate,
            max_retries=0,
            **kwargs,
        )

    async def aclose(self) -> None:
        close = getattr(self.delegate, "aclose", None)
        if close is not None:
            await close()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    hatecot_cases, hatecot_manifest = load_hatecot_cases(args.hatecot_csv)
    benchmarks = resolve_benchmarks(args.benchmarks)
    target_datasets = {
        benchmark.name: load_target_dataset(benchmark, args)
        for benchmark in benchmarks
    }
    if args.dry_run:
        manifest = build_dry_run_manifest(hatecot_cases, hatecot_manifest, benchmarks, target_datasets, args)
        write_json(output_dir / "dry_run_manifest.json", manifest)
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0
    if not has_deepseek_api_key():
        raise SystemExit(
            "DEEPSEEK_API_KEY is missing. Configure it through the ignored local environment; "
            "this runner never accepts or writes API keys."
        )
    report = asyncio.run(
        run_experiment(
            hatecot_cases=hatecot_cases,
            hatecot_manifest=hatecot_manifest,
            benchmarks=benchmarks,
            target_datasets=target_datasets,
            args=args,
            output_dir=output_dir,
        )
    )
    write_json(output_dir / "report.json", report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"wrote {output_dir / 'report.json'}")
    return 0


async def run_experiment(
    *,
    hatecot_cases: list[dict[str, Any]],
    hatecot_manifest: Mapping[str, Any],
    benchmarks: list[HateCoTBenchmark],
    target_datasets: Mapping[str, tuple[list[dict[str, Any]], Mapping[str, Any]]],
    args: argparse.Namespace,
    output_dir: Path,
) -> dict[str, Any]:
    analysis_provider, rule_provider, provider_config, execution = build_experiment_runtime(args)
    cache_path = output_dir / "analysis_cache.jsonl"
    analysis_cache = load_analysis_cache(cache_path, seed_path=args.seed_analysis_cache)
    results: dict[str, Any] = {}
    try:
        for benchmark in benchmarks:
            target_cases, target_manifest = target_datasets[benchmark.name]
            results[benchmark.name] = await run_benchmark(
                hatecot_cases=hatecot_cases,
                benchmark=benchmark,
                available_target_cases=target_cases,
                target_dataset_manifest=target_manifest,
                args=args,
                output_dir=output_dir,
                analysis_provider=analysis_provider,
                rule_provider=rule_provider,
                model=provider_config.model,
                analysis_cache=analysis_cache,
                cache_path=cache_path,
            )
            write_json(
                output_dir / "report.partial.json",
                {
                    "schema": "maro-hatecot-harm-benchmark-report-v1",
                    "paper_boundary": PAPER_BOUNDARY,
                    "source_dataset_manifest": dict(hatecot_manifest),
                    "benchmarks": results,
                    "provider_telemetry": execution.snapshot(),
                },
            )
    finally:
        await analysis_provider.aclose()
        await rule_provider.aclose()
    return {
        "schema": "maro-hatecot-harm-benchmark-report-v1",
        "paper_boundary": PAPER_BOUNDARY,
        "source_dataset_manifest": dict(hatecot_manifest),
        "effective_protocol": effective_protocol(args),
        "execution": {
            "model": provider_config.model,
            "timeout_seconds": provider_config.timeout_seconds,
            "provider_max_retries": 0,
            "external_fact_retrieval_used": False,
            "policy_reference_source": "local_public_governance_reference_library",
            "analysis_cache": str(cache_path),
            "concurrency": {"llm": args.llm_concurrency},
            "provider_telemetry": execution.snapshot(),
        },
        "benchmarks": results,
        "summary": summarize_benchmarks(results),
    }


def build_experiment_runtime(args: argparse.Namespace):
    raw_analysis_provider, config = build_deepseek_provider(temperature=0.0)
    raw_rule_provider, _ = build_deepseek_provider(config, temperature=1.0)
    execution = ExperimentConcurrency(
        llm_concurrency=args.llm_concurrency,
        retrieval_concurrency=1,
        retry_backoff_seconds=1.0,
    )
    return (
        BoundedExperimentProvider(execution=execution, delegate=raw_analysis_provider),
        BoundedExperimentProvider(execution=execution, delegate=raw_rule_provider),
        config,
        execution,
    )


async def run_benchmark(
    *,
    hatecot_cases: list[dict[str, Any]],
    benchmark: HateCoTBenchmark,
    available_target_cases: list[dict[str, Any]],
    target_dataset_manifest: Mapping[str, Any],
    args: argparse.Namespace,
    output_dir: Path,
    analysis_provider: BoundedExperimentProvider,
    rule_provider: BoundedExperimentProvider,
    model: str,
    analysis_cache: dict[str, dict[str, Any]],
    cache_path: Path,
) -> dict[str, Any]:
    benchmark_dir = output_dir / "benchmarks" / safe_name(benchmark.name)
    judge_audit_path = benchmark_dir / "judge_audit.jsonl"
    judge_audit_records: list[dict[str, Any]] = []
    source_cases = map_hatecot_source_cases(hatecot_cases, benchmark=benchmark)
    target_cases = select_benchmark_target_cases(
        available_target_cases,
        benchmark=benchmark,
        cases_per_label=args.target_cases_per_label,
        random_state=args.random_state,
    )
    config = MARORuleOptimizationConfig(
        validation_task_count=args.validation_tasks,
        max_samples_per_source_domain=args.samples_per_source_domain,
        max_iterations=args.max_iterations,
        max_attempts=args.max_attempts,
        returned_rule_count=args.returned_rule_count,
        random_state=args.random_state,
        evaluation_concurrency=args.llm_concurrency,
        label_space=benchmark.label_space,
        demonstration_label_plan=demonstration_label_plan(benchmark.label_space),
        label_key=BENCHMARK_LABEL_KEY,
    )
    validation_tasks = build_cross_domain_validation_tasks(
        source_cases,
        target_domain=benchmark.name.lower(),
        config=config,
    )
    case_index = {str(case["case_id"]): case for case in [*source_cases, *target_cases]}
    needed_ids = {task.query_case_id for task in validation_tasks}
    needed_ids.update(str(case["case_id"]) for case in target_cases)
    await ensure_analysis_reports(
        cases=[case_index[case_id] for case_id in sorted(needed_ids)],
        provider=analysis_provider,
        model=model,
        include_reflection=not args.disable_reflection,
        retries=args.analysis_case_retries,
        cache=analysis_cache,
        cache_path=cache_path,
        concurrency=args.llm_concurrency,
    )

    async def propose_rule(*, trajectory: list[DecisionRule], best_rule: DecisionRule, iteration: int) -> str:
        trajectory_text = "\n".join(
            f"RULE {index}: {item.text}\nVALIDATION_ACCURACY: {item.accuracy:.6f}"
            for index, item in enumerate(trajectory, start=1)
        )
        response = await rule_provider(
            agent_name="MARODecisionRuleOptimizationAgent",
            system_prompt=(
                "You optimize a concise cross-domain rule for interpersonal-harm classification. "
                f"The declared label space is {label_space_text(benchmark.label_space)}. Improve the rule only from "
                "the source-validation trajectory. Keep distinctions tied to observable text and target scope; do not "
                "use policy references as label evidence. Return exactly one line beginning RULE:."
            ),
            user_prompt=json.dumps(
                {
                    "iteration": iteration,
                    "best_rule": best_rule.text,
                    "trajectory": trajectory_text,
                    "source_mapping_note": benchmark.source_mapping_note,
                },
                ensure_ascii=False,
            ),
            input_bundle={"iteration": iteration, "best_rule": best_rule.text, "trajectory": trajectory_text},
            model=model,
        )
        return extract_rule_text(response)

    async def judge_task(*, rule_text: str, task: JudgeTask, phase: str = "validation") -> str:
        analysis = analysis_cache[str(task.query_case_id)]["analysis"]
        return await run_judge_with_retries(
            provider=rule_provider,
            model=model,
            rule_text=rule_text,
            task=task,
            analysis=analysis,
            benchmark=benchmark,
            phase=phase,
            format_retries=args.judge_format_retries,
            audit_path=judge_audit_path,
            audit_records=judge_audit_records,
        )

    optimization = await optimize_decision_rules(
        tasks=validation_tasks,
        initial_rule=initial_rule_for(benchmark),
        propose_rule=propose_rule,
        judge_task=judge_task,
        config=config,
    )
    if len(optimization.returned_rules) % 2 != 1:
        raise RuntimeError("MARO benchmark voting requires an odd number of returned rules")

    gold_by_case_id = {
        str(case["case_id"]): str(case["labels"][BENCHMARK_LABEL_KEY])
        for case in target_cases
    }

    async def predict_target(case: dict[str, Any]) -> dict[str, Any]:
        task = benchmark_target_task(case, benchmark.name)
        votes = [
            await judge_task(rule_text=rule.text, task=task, phase="target")
            for rule in optimization.returned_rules
        ]
        return {
            "case_id": str(case["case_id"]),
            "rule_votes": votes,
            "prediction": benchmark_majority_vote(votes, benchmark.label_space),
            "vote_tie": len(set(votes)) == len(votes),
            "tie_break_rule": "best_returned_rule" if len(set(votes)) == len(votes) else None,
        }

    predictions = await run_ordered_bounded(target_cases, predict_target, concurrency=args.llm_concurrency)
    scored_predictions = [
        {**prediction, "gold_label": gold_by_case_id[str(prediction["case_id"])]}
        for prediction in predictions
    ]
    metrics = evaluate_benchmark_predictions(scored_predictions, label_space=benchmark.label_space)
    sampling_manifest = build_benchmark_target_manifest(
        benchmark=benchmark,
        target_cases=target_cases,
        random_state=args.random_state,
        cases_per_label=args.target_cases_per_label,
    )
    report = {
        "benchmark": benchmark.name,
        "target_dataset_manifest": dict(target_dataset_manifest),
        "label_space": list(benchmark.label_space),
        "source_mapping": {
            "source_label_map": dict(benchmark.source_label_map),
            "is_proxy": benchmark.source_mapping_is_proxy,
            "note": benchmark.source_mapping_note,
        },
        "validation_task_count": len(validation_tasks),
        "source_case_count": len(source_cases),
        "target_case_count": len(target_cases),
        "optimization": optimization_to_json(optimization),
        "metrics": metrics,
        "execution_integrity": summarize_judge_audit(judge_audit_records, expected_rule_votes=len(optimization.returned_rules)),
        "policy_reference_audit": summarize_policy_capsules(target_cases, analysis_cache),
        "target_sampling": sampling_manifest,
    }
    write_json(benchmark_dir / "report.json", report)
    write_json(benchmark_dir / "target_sampling_manifest.json", sampling_manifest)
    write_jsonl(benchmark_dir / "predictions.jsonl", predictions)
    write_jsonl(benchmark_dir / "scored_predictions.jsonl", scored_predictions)
    return report


async def ensure_analysis_reports(
    *,
    cases: list[dict[str, Any]],
    provider: BoundedExperimentProvider,
    model: str,
    include_reflection: bool,
    retries: int,
    cache: dict[str, dict[str, Any]],
    cache_path: Path,
    concurrency: int,
) -> None:
    missing = [case for case in cases if not has_complete_harm_analysis(cache.get(str(case.get("case_id") or "")))]

    async def analyze_case(case: dict[str, Any]) -> dict[str, Any]:
        case_id = str(case["case_id"])
        last_record: dict[str, Any] | None = None
        for attempt in range(retries + 1):
            result = await run_maro_harm_multiagent_analysis(
                case=case,
                provider=provider,
                model=model,
                include_reflection=include_reflection,
            )
            last_record = {
                "case_id": case_id,
                "analysis": result["analysis"],
                "agent_reports": result["agent_reports"],
                "policy_selection": result["policy_selection"],
                "rationale_capsule": result["rationale_capsule"],
                "rationale_capsule_blockers": result["rationale_capsule_blockers"],
                "analysis_summary": result["summary"],
                "audit": result["audit"],
                "protocol": result["schema_version"],
                "analysis_attempt": attempt + 1,
            }
            if has_complete_harm_analysis(last_record):
                return last_record
        assert last_record is not None
        return last_record

    for record in await run_ordered_bounded(missing, analyze_case, concurrency=concurrency):
        if not has_complete_harm_analysis(record):
            raise RuntimeError(f"Incomplete MARO harm analysis for {record.get('case_id')}")
        cache[str(record["case_id"])] = record
        append_jsonl(cache_path, record)


def benchmark_target_task(case: Mapping[str, Any], benchmark: str) -> BenchmarkJudgeTask:
    """Build a target prompt contract that deliberately omits the target label."""

    metadata = case.get("metadata") if isinstance(case.get("metadata"), Mapping) else {}
    return BenchmarkJudgeTask(
        task_id=f"target:{benchmark}:{case.get('case_id')}",
        query_case_id=str(case.get("case_id") or ""),
        query_text=str(case.get("text") or ""),
        query_domain=str(metadata.get("category") or benchmark).lower(),
        target_benchmark=benchmark,
    )


async def run_judge_with_retries(
    *,
    provider: BoundedExperimentProvider,
    model: str,
    rule_text: str,
    task: JudgeTask,
    analysis: str,
    benchmark: HateCoTBenchmark,
    phase: str,
    format_retries: int,
    audit_path: Path,
    audit_records: list[dict[str, Any]],
) -> str:
    """Require strict protocol labels and fail the run on exhausted retries."""

    prompt = build_benchmark_judge_prompt(
        label_space=benchmark.label_space,
        rule_text=rule_text,
        task=task,
        analysis=analysis,
    )
    for attempt in range(1, format_retries + 2):
        record = {
            "phase": phase,
            "task_id": task.task_id,
            "benchmark": benchmark.name,
            "rule_text": rule_text,
            "attempt": attempt,
            "input_bundle": {"task_id": task.task_id, "phase": phase, "gold_label_included": False},
        }
        try:
            response = await provider(
                agent_name="HarmfulnessJudgeAgent",
                system_prompt=(
                    "You are the final MARO-compatible interpersonal-harm Judge. Use the supplied rule, source-domain "
                    "demonstrations, and post-harm analysis. Policy references are advisory and cannot substitute for "
                    "observed text. Do not use external facts or issue enforcement. End with exactly one final line: "
                    f"JUDGMENT: one numeric index from 0 to {len(benchmark.label_space) - 1}."
                ),
                user_prompt=prompt,
                input_bundle=record["input_bundle"],
                model=model,
            )
        except Exception as exc:
            append_judge_audit(record | {"status": "provider_error", "error_class": type(exc).__name__}, audit_path, audit_records)
            continue
        response_text = str(response or "").strip()
        label = parse_benchmark_judgment(response_text, benchmark.label_space)
        if label is None:
            append_judge_audit(record | {"status": "invalid_format", "response_text": response_text}, audit_path, audit_records)
            continue
        append_judge_audit(record | {"status": "completed", "response_text": response_text, "parsed_label": label}, audit_path, audit_records)
        return label
    raise JudgeExecutionError(f"Judge did not produce a strict label for {task.task_id}")


def demonstration_label_plan(label_space: tuple[str, ...]) -> tuple[str, ...]:
    """Use MARO's 2+2 binary demonstrations; make every non-binary plan explicit."""

    if len(label_space) == 2:
        return (label_space[1], label_space[1], label_space[0], label_space[0])
    return label_space


def initial_rule_for(benchmark: HateCoTBenchmark) -> str:
    rules = {
        "HateCheck": (
            "Classify observable harmful language in the post. Choose hateful for direct hostility, dehumanization, "
            "threats, or abusive generalizations targeting a protected identity or group. Choose non_hateful when "
            "there is no such target-directed hostility, including quotation, negation, reporting, or condemnation "
            "without endorsement."
        ),
        "HateXplain": (
            "Classify only observable interpersonal harm. Choose hate for identity- or affiliation-targeted "
            "dehumanization or abuse, offensive for direct person-targeted abuse or derogatory toxic language without "
            "a protected-group target, and normal when the post lacks such attack or clearly negates, quotes, or "
            "condemns it."
        ),
        "Latent_Hate": (
            "Classify implicit-hate presence from observable wording and context. Choose implicit_hate for indirect "
            "demeaning stereotypes, coded hostility, or negative generalizations about an identity or protected group; "
            "choose not_hate for neutral discussion, quotation, negation, reporting, or condemnation without endorsement."
        ),
    }
    return rules[benchmark.name]


def load_target_dataset(benchmark: HateCoTBenchmark, args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if benchmark.name == "HateCheck":
        return load_hatecheck_cases(args.hatecheck_csv)
    if benchmark.name == "HateXplain":
        return load_hatexplain_cases(args.hatexplain_dir)
    if benchmark.name == "Latent_Hate":
        return load_latent_hate_cases(args.latent_hate_tsv)
    raise ValueError(f"Unsupported benchmark: {benchmark.name}")


def resolve_benchmarks(requested: list[str]) -> list[HateCoTBenchmark]:
    names = requested or list(HATECOT_BENCHMARKS)
    unknown = [name for name in names if name not in HATECOT_BENCHMARKS]
    if unknown:
        raise ValueError("Unknown benchmark(s): " + ", ".join(unknown))
    return [HATECOT_BENCHMARKS[name] for name in names]


def build_dry_run_manifest(
    hatecot_cases: list[dict[str, Any]],
    hatecot_manifest: Mapping[str, Any],
    benchmarks: list[HateCoTBenchmark],
    target_datasets: Mapping[str, tuple[list[dict[str, Any]], Mapping[str, Any]]],
    args: argparse.Namespace,
) -> dict[str, Any]:
    records: dict[str, Any] = {}
    for benchmark in benchmarks:
        source_cases = map_hatecot_source_cases(hatecot_cases, benchmark=benchmark)
        target_cases, target_manifest = target_datasets[benchmark.name]
        selected = select_benchmark_target_cases(
            target_cases,
            benchmark=benchmark,
            cases_per_label=args.target_cases_per_label,
            random_state=args.random_state,
        )
        config = MARORuleOptimizationConfig(
            validation_task_count=args.validation_tasks,
            max_samples_per_source_domain=args.samples_per_source_domain,
            max_iterations=args.max_iterations,
            max_attempts=args.max_attempts,
            returned_rule_count=args.returned_rule_count,
            random_state=args.random_state,
            evaluation_concurrency=args.llm_concurrency,
            label_space=benchmark.label_space,
            demonstration_label_plan=demonstration_label_plan(benchmark.label_space),
            label_key=BENCHMARK_LABEL_KEY,
        )
        tasks = build_cross_domain_validation_tasks(source_cases, target_domain=benchmark.name.lower(), config=config)
        records[benchmark.name] = {
            "target_dataset_manifest": dict(target_manifest),
            "label_space": list(benchmark.label_space),
            "source_mapping": {
                "source_label_map": dict(benchmark.source_label_map),
                "is_proxy": benchmark.source_mapping_is_proxy,
                "note": benchmark.source_mapping_note,
            },
            "source_case_count": len(source_cases),
            "validation_task_count": len(tasks),
            "target_case_count": len(selected),
            "target_label_counts": dict(Counter(str(case["labels"][BENCHMARK_LABEL_KEY]) for case in selected)),
            "external_calls": False,
        }
    return {
        "schema": "maro-hatecot-harm-benchmark-dry-run-v1",
        "paper_boundary": PAPER_BOUNDARY,
        "effective_protocol": effective_protocol(args),
        "source_dataset_manifest": dict(hatecot_manifest),
        "benchmarks": records,
        "external_calls": False,
    }


def summarize_policy_capsules(cases: list[Mapping[str, Any]], cache: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    records = [cache[str(case.get("case_id") or "")] for case in cases]
    capsules = [record.get("rationale_capsule") or {} for record in records]
    policies = [record.get("policy_selection") or {} for record in records]
    return {
        "target_analysis_count": len(records),
        "quality_gated_capsule_count": sum(bool(item.get("capsule_quality_gate")) for item in capsules),
        "input_span_available_count": sum(bool(item.get("rationale_span_available")) for item in capsules),
        "policy_clause_match_count": sum(bool(item.get("policy_clause_match")) for item in capsules),
        "policy_reference_bundle_count": sum(len(item.get("bundles") or []) for item in policies),
        "boundary": "Policy references are advisory audit provenance; they are not labels, factual evidence, or enforcement decisions.",
    }


def summarize_judge_audit(records: list[Mapping[str, Any]], *, expected_rule_votes: int) -> dict[str, Any]:
    completed = [record for record in records if record.get("status") == "completed"]
    return {
        "judge_call_attempt_count": len(records),
        "completed_judge_call_count": len(completed),
        "expected_rule_votes_per_target": expected_rule_votes,
        "audit_log": "judge_audit.jsonl",
        "metric_denominator_policy": "Every selected target sample receives one odd-rule majority vote; an exhausted Judge retry fails the run rather than removing a sample from metrics.",
    }


def optimization_to_json(result: Any) -> dict[str, Any]:
    return {
        "initial_rule": rule_to_json(result.initial_rule),
        "best_rule": rule_to_json(result.best_rule),
        "accepted_rules": [rule_to_json(rule) for rule in result.accepted_rules],
        "returned_rules": [rule_to_json(rule) for rule in result.returned_rules],
        "trajectory": [rule_to_json(rule) for rule in result.trajectory],
        "evaluated_task_count": result.evaluated_task_count,
        "iterations_completed": result.iterations_completed,
        "consecutive_non_improvements": result.consecutive_non_improvements,
        "stop_reason": result.stop_reason,
    }


def rule_to_json(rule: DecisionRule) -> dict[str, Any]:
    return {
        "text": rule.text,
        "accuracy": rule.accuracy,
        "iteration": rule.iteration,
        "accepted": rule.accepted,
    }


def summarize_benchmarks(results: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "evaluated_benchmarks": list(results),
        "metric_aggregation": "not aggregated because benchmark label spaces and source-mapping assumptions differ",
        "macro_f1_by_benchmark": {
            name: record["metrics"]["classification_metrics"]["macro_f1"]
            for name, record in results.items()
        },
    }


def effective_protocol(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "task": "interpersonal_harm",
        "validation_task_count": args.validation_tasks,
        "samples_per_source_domain": args.samples_per_source_domain,
        "max_iterations": args.max_iterations,
        "max_attempts": args.max_attempts,
        "returned_rule_count": args.returned_rule_count,
        "target_cases_per_label": args.target_cases_per_label,
        "reflection_enabled": not args.disable_reflection,
        "analysis_case_retries": args.analysis_case_retries,
        "judge_format_retries": args.judge_format_retries,
        "llm_concurrency": args.llm_concurrency,
        "external_fact_retrieval": False,
        "policy_reference_mode": "local_advisory_governance_reference_library",
        "gold_labels_used_only_for": ["source_validation_rule_scoring", "held_out_final_metrics", "fixed_target_sampling"],
        "dataset_explanations_used_by_teacher": False,
    }


def label_space_text(label_space: tuple[str, ...]) -> str:
    return ", ".join(f"{index}={label}" for index, label in enumerate(label_space))


def extract_rule_text(response: str) -> str:
    lines = [line.strip() for line in str(response or "").splitlines() if line.strip()]
    marked = [line.split(":", 1)[1].strip() for line in lines if line.upper().startswith("RULE:")]
    return marked[-1] if marked else " ".join(lines)


def load_analysis_cache(path: Path, *, seed_path: str = "") -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    paths = [Path(seed_path)] if seed_path else []
    paths.append(path)
    for source_path in paths:
        if not source_path.is_file():
            continue
        with source_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if isinstance(record, dict) and str(record.get("case_id") or ""):
                    records[str(record["case_id"])] = record
    return records


def append_judge_audit(record: Mapping[str, Any], path: Path, records: list[dict[str, Any]]) -> None:
    append_jsonl(path, record)
    records.append(dict(record))


def append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def safe_name(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value).strip()).strip("-")
    return normalized or "benchmark"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hatecot-csv", default=str(DEFAULT_HATECOT_CSV))
    parser.add_argument("--hatecheck-csv", default=str(DEFAULT_HATECHECK_CSV))
    parser.add_argument("--hatexplain-dir", default=str(DEFAULT_HATEXPLAIN_DIR))
    parser.add_argument("--latent-hate-tsv", default=str(DEFAULT_LATENT_HATE_TSV))
    parser.add_argument("--benchmarks", nargs="*", default=list(HATECOT_BENCHMARKS))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--validation-tasks", type=int, default=30)
    parser.add_argument("--samples-per-source-domain", type=int, default=100)
    parser.add_argument("--max-iterations", type=int, default=3)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--returned-rule-count", type=int, default=3)
    parser.add_argument("--target-cases-per-label", type=int, default=20)
    parser.add_argument("--seed-analysis-cache", default="")
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--disable-reflection", action="store_true")
    parser.add_argument("--analysis-case-retries", type=int, default=1)
    parser.add_argument("--judge-format-retries", type=int, default=1)
    parser.add_argument("--llm-concurrency", type=int, default=8)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.validation_tasks < 2:
        raise SystemExit("validation-tasks must be >= 2")
    if args.samples_per_source_domain < 2:
        raise SystemExit("samples-per-source-domain must be >= 2")
    if args.max_iterations < 1 or args.max_attempts < 1:
        raise SystemExit("max-iterations and max-attempts must be >= 1")
    if args.returned_rule_count < 1 or args.returned_rule_count % 2 == 0:
        raise SystemExit("returned-rule-count must be a positive odd number")
    if args.target_cases_per_label < 1:
        raise SystemExit("target-cases-per-label must be >= 1")
    if args.analysis_case_retries < 0 or args.judge_format_retries < 0:
        raise SystemExit("retry values must be >= 0")
    if args.llm_concurrency < 1:
        raise SystemExit("llm-concurrency must be >= 1")
    return args


if __name__ == "__main__":
    raise SystemExit(main())
