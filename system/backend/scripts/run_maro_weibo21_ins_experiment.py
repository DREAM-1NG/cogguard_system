"""Run the paper-aligned MARO + INS experiment on local Weibo21.

This is an offline research runner. It does not modify the product Review API,
Coordination, or Propagation. A real run requires ``DEEPSEEK_API_KEY`` and the
configured traceable retrieval provider in the current process environment.
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Mapping

from sklearn.metrics import accuracy_score, f1_score, precision_score

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from app.core.review.deepseek_provider import (  # noqa: E402
    build_deepseek_provider,
    has_deepseek_api_key,
)
from app.core.review.experiment_concurrency import (  # noqa: E402
    ExperimentConcurrency,
    run_ordered_bounded,
)
from app.core.review.maro_rule_optimization import (  # noqa: E402
    CrossDomainValidationTask,
    DecisionRule,
    MARORuleOptimizationConfig,
    build_cross_domain_validation_tasks,
    optimize_decision_rules,
)
from app.core.review.maro_protocol import (  # noqa: E402
    run_maro_paper_multi_dimensional_analysis,
)
from app.config import settings  # noqa: E402
from app.tasks.review_tasks import _build_http_retrieval_provider  # noqa: E402


DEFAULT_DATASET_ROOT = Path(r"G:\CISCN\dataset")
DEFAULT_OUTPUT_DIR = Path(r"G:\CISCN\.tmp\maro_weibo21_ins")
DEFAULT_INITIAL_RULE = (
    "Judge whether the news is fake only after combining the linguistic analysis, "
    "comment analysis, and traceable fact-checking evidence. Prefer a fake label "
    "when the claim conflicts with cited evidence, and prefer a real label only "
    "when the claim is supported by cited evidence. Do not infer truth from style "
    "or commenter sentiment alone. Output JUDGMENT: 1 for fake and JUDGMENT: 0 for real."
)
PAPER_PROTOCOL = {
    "paper": "A Multi-Agent Framework with Automated Decision Rule Optimization for Cross-Domain Misinformation Detection",
    "paper_url": "https://arxiv.org/abs/2503.23329",
    "repository": "https://github.com/Brtulien/MARO",
    "repository_commit": "20aea25462c5ee55af5bf777084a0eb8553b8920",
    "dataset": "Weibo21",
    "fold_protocol": (
        "Paper reports 8-fold cross-validation; the local Weibo21 table/snapshot exposes 9 domains, "
        "so this adapter evaluates one held-out fold per available domain."
    ),
    "validation_task_count": 500,
    "samples_per_source_domain": 100,
    "max_iterations": 500,
    "max_attempts": 10,
    "returned_rule_count": 3,
    "rule_temperature": 1.0,
    "judge_temperature": 0.0,
    "inference_aggregation": "majority_vote_top_k_rules",
    "paper_metrics": ["accuracy", "f1"],
}


class JudgeExecutionError(RuntimeError):
    """Raised when a MARO Judge call cannot produce a usable response."""


@dataclass(frozen=True)
class TargetJudgeTask:
    """Unlabelled target-domain input for final MARO inference."""

    task_id: str
    query_case_id: str
    query_text: str
    query_domain: str
    target_domain: str
    demonstrations: tuple[Any, ...] = ()


JudgeTask = CrossDomainValidationTask | TargetJudgeTask


class BoundedExperimentProvider:
    """Apply experiment-wide bounds without exposing provider credentials."""

    def __init__(
        self,
        *,
        execution: ExperimentConcurrency,
        service: str,
        delegate,
        max_retries: int = 0,
    ) -> None:
        self._execution = execution
        self._service = service
        self._delegate = delegate
        self._max_retries = max_retries

    @property
    def last_call_telemetry(self) -> dict[str, Any]:
        telemetry = getattr(self._delegate, "last_call_telemetry", {})
        return dict(telemetry) if isinstance(telemetry, Mapping) else {}

    async def __call__(self, **kwargs: Any):
        return await self._execution.invoke(
            service=self._service,
            operation=self._delegate,
            max_retries=self._max_retries,
            **kwargs,
        )

    async def aclose(self) -> None:
        close = getattr(self._delegate, "aclose", None)
        if close is not None:
            await close()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cases, dataset_manifest = load_or_convert_cases(args, output_dir)
    domains = sorted({case_domain(case) for case in cases if case_domain(case)})
    target_domains = _select_domains(domains, args.target_domains)
    if len(domains) < 9 and not args.allow_local_domain_snapshot:
        raise SystemExit(
            f"Weibo21 local snapshot exposes {len(domains)} domains; expected 9. "
            "Use --allow-local-domain-snapshot only when reporting a local-snapshot protocol."
        )

    if args.dry_run:
        manifest = build_dry_run_manifest(cases, target_domains, args, dataset_manifest)
        write_json(output_dir / "dry_run_manifest.json", manifest)
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0

    if not has_deepseek_api_key():
        raise SystemExit(
            "DEEPSEEK_API_KEY is missing. Configure it in the local ignored .env "
            "or current process environment; this runner never accepts or writes API keys."
        )
    if not args.enable_retrieval:
        raise SystemExit(
            "A MARO performance run requires --enable-retrieval and a configured "
            "traceable retrieval provider. Use --dry-run to inspect the protocol without it."
        )

    if args.calibration_cases:
        report = asyncio.run(run_calibration(cases, target_domains, args, dataset_manifest, output_dir))
        write_json(output_dir / "calibration_report.json", report)
        print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
        print(f"wrote {output_dir / 'calibration_report.json'}")
        return 0

    report = asyncio.run(run_experiment(cases, target_domains, args, dataset_manifest, output_dir))
    write_json(output_dir / "report.json", report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"wrote {output_dir / 'report.json'}")
    return 0


async def run_experiment(
    cases: list[dict[str, Any]],
    target_domains: list[str],
    args: argparse.Namespace,
    dataset_manifest: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    analysis_provider, rule_provider, provider_config, retriever, execution = build_experiment_runtime(args)
    analysis_cache_path = output_dir / "analysis_cache.jsonl"
    analysis_cache, cache_provenance = load_experiment_analysis_cache(
        output_cache_path=analysis_cache_path,
        seed_cache_path=args.seed_analysis_cache,
    )
    try:
        fold_reports: dict[str, Any] = {}
        for target_domain in target_domains:
            fold_reports[target_domain] = await run_fold(
                cases=cases,
                target_domain=target_domain,
                args=args,
                output_dir=output_dir,
                analysis_provider=analysis_provider,
                rule_provider=rule_provider,
                model=provider_config.model,
                retriever=retriever,
                analysis_cache=analysis_cache,
                analysis_cache_path=analysis_cache_path,
            )
            cache_provenance = refresh_analysis_cache_provenance(
                cache_provenance,
                output_cache_path=analysis_cache_path,
            )
            write_json(output_dir / "report.partial.json", {
                "schema": "maro-weibo21-ins-report-v3",
                "protocol": PAPER_PROTOCOL,
                "effective_protocol": effective_protocol(args),
                "dataset_manifest": dataset_manifest,
                "folds": fold_reports,
                "analysis_cache_provenance": cache_provenance,
                "provider_telemetry": execution.snapshot(),
            })
    finally:
        await analysis_provider.aclose()
        await rule_provider.aclose()

    return {
        "schema": "maro-weibo21-ins-report-v3",
        "protocol": PAPER_PROTOCOL,
        "effective_protocol": effective_protocol(args),
        "dataset_manifest": dataset_manifest,
        "execution": {
            "model": provider_config.model,
            "retrieval_enabled": True,
            "max_target_cases_per_domain": resolved_target_case_count(args),
            "analysis_cache": str(analysis_cache_path),
            "analysis_cache_provenance": cache_provenance,
            "concurrency": {
                "llm": args.llm_concurrency,
                "retrieval": args.retrieval_concurrency,
            },
            "provider_telemetry": execution.snapshot(),
        },
        "folds": fold_reports,
        "summary": summarize_folds(fold_reports),
    }


async def run_calibration(
    cases: list[dict[str, Any]],
    target_domains: list[str],
    args: argparse.Namespace,
    dataset_manifest: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    """Measure provider reliability on analysis-only cases without evaluation labels."""

    analysis_provider, rule_provider, provider_config, retriever, execution = build_experiment_runtime(args)
    calibration_cases = select_calibration_cases(
        cases,
        target_domains=target_domains,
        max_cases=args.calibration_cases,
        random_state=args.random_state,
    )
    cache_path = output_dir / "calibration_analysis_cache.jsonl"
    cache = load_analysis_cache(cache_path)
    started = asyncio.get_running_loop().time()
    try:
        await ensure_analysis_reports(
            cases=calibration_cases,
            provider=analysis_provider,
            model=provider_config.model,
            retriever=retriever,
            args=args,
            cache=cache,
            cache_path=cache_path,
        )
    finally:
        await analysis_provider.aclose()
        await rule_provider.aclose()
    elapsed = asyncio.get_running_loop().time() - started
    completed = sum(
        1
        for case in calibration_cases
        if str(case.get("case_id") or "") in cache
    )
    return {
        "schema": "maro-weibo21-provider-calibration-v1",
        "dataset_manifest": dataset_manifest,
        "analysis_cache_provenance": cache_provenance,
        "mode": "analysis_only_no_metrics",
        "selected_case_count": len(calibration_cases),
        "completed_case_count": completed,
        "target_domains": list(target_domains),
        "concurrency": {
            "llm": args.llm_concurrency,
            "retrieval": args.retrieval_concurrency,
        },
        "provider_telemetry": execution.snapshot(),
        "duration_seconds": round(elapsed, 6),
        "summary": {
            "completed_case_count": completed,
            "case_throughput_per_second": round(completed / elapsed, 6) if elapsed > 0 else None,
            "deepseek": execution.snapshot()["deepseek"],
            "exa": execution.snapshot()["exa"],
        },
    }


def build_experiment_runtime(args: argparse.Namespace):
    """Build bounded providers for one run while keeping credentials process-local."""

    raw_analysis_provider, provider_config = build_deepseek_provider(temperature=0.0)
    raw_rule_provider, _ = build_deepseek_provider(provider_config, temperature=1.0)
    raw_retriever = build_environment_retriever()
    if raw_retriever is None:
        raise RuntimeError("No traceable retrieval provider is configured.")
    execution = ExperimentConcurrency(
        llm_concurrency=args.llm_concurrency,
        retrieval_concurrency=args.retrieval_concurrency,
        retry_backoff_seconds=args.retrieval_retry_backoff_seconds,
    )
    return (
        BoundedExperimentProvider(
            execution=execution,
            service="deepseek",
            delegate=raw_analysis_provider,
        ),
        BoundedExperimentProvider(
            execution=execution,
            service="deepseek",
            delegate=raw_rule_provider,
        ),
        provider_config,
        BoundedExperimentProvider(
            execution=execution,
            service="exa",
            delegate=raw_retriever,
            max_retries=args.retrieval_max_retries,
        ),
        execution,
    )


async def run_fold(
    *,
    cases: list[dict[str, Any]],
    target_domain: str,
    args: argparse.Namespace,
    output_dir: Path,
    analysis_provider,
    rule_provider,
    model: str,
    retriever,
    analysis_cache: dict[str, dict[str, Any]],
    analysis_cache_path: Path,
) -> dict[str, Any]:
    fold_dir = output_dir / "folds" / safe_name(target_domain)
    judge_audit_path = fold_dir / "judge_audit.jsonl"
    judge_audit_records: list[dict[str, Any]] = []
    config = MARORuleOptimizationConfig(
        validation_task_count=args.validation_tasks,
        max_samples_per_source_domain=args.samples_per_source_domain,
        max_iterations=args.max_iterations,
        max_attempts=args.max_attempts,
        returned_rule_count=args.returned_rule_count,
        random_state=args.random_state,
        evaluation_concurrency=args.llm_concurrency,
    )
    source_cases = [case for case in cases if case_domain(case) != target_domain]
    target_cases = select_target_cases(
        [case for case in cases if case_domain(case) == target_domain],
        max_cases=resolved_target_case_count(args),
        random_state=args.random_state,
        cases_per_label=resolved_target_cases_per_label(args),
    )
    tasks = build_cross_domain_validation_tasks(source_cases, target_domain=target_domain, config=config)
    required_case_ids = {task.query_case_id for task in tasks}
    required_case_ids.update(str(case.get("case_id") or "") for case in target_cases)
    await ensure_analysis_reports(
        cases=[case for case in cases if str(case.get("case_id") or "") in required_case_ids],
        provider=analysis_provider,
        model=model,
        retriever=retriever,
        args=args,
        cache=analysis_cache,
        cache_path=analysis_cache_path,
    )

    async def propose_rule(*, trajectory: list[DecisionRule], best_rule: DecisionRule, iteration: int) -> str:
        trajectory_text = "\n".join(
            f"RULE {index}: {item.text}\nVALIDATION_ACCURACY: {item.accuracy:.6f}"
            for index, item in enumerate(trajectory, start=1)
        )
        prompt = (
            "You are MARO's Decision Rule Optimization Agent. Improve the decision rule for cross-domain "
            "misinformation detection using the validation trajectory below. Return exactly one concise rule on "
            "one line beginning with RULE:. Do not return a label, score, or commentary.\n\n"
            f"Current best rule:\n{best_rule.text}\n\nTrajectory:\n{trajectory_text}"
        )
        response = await rule_provider(
            agent_name="MARODecisionRuleOptimizationAgent",
            system_prompt=prompt,
            user_prompt=json.dumps({"iteration": iteration, "trajectory": trajectory_text}, ensure_ascii=False),
            input_bundle={"iteration": iteration, "trajectory": trajectory_text},
            model=model,
        )
        return extract_rule_text(response)

    async def judge_task(*, rule_text: str, task: JudgeTask, phase: str = "validation") -> str:
        analysis = analysis_cache.get(task.query_case_id, {}).get("analysis", "")
        return await run_judge_with_retries(
            provider=rule_provider,
            model=model,
            rule_text=rule_text,
            task=task,
            analysis=analysis,
            phase=phase,
            format_retries=args.judge_format_retries,
            audit_path=judge_audit_path,
            audit_records=judge_audit_records,
        )

    optimization = await optimize_decision_rules(
        tasks=tasks,
        initial_rule=args.initial_rule,
        propose_rule=propose_rule,
        judge_task=judge_task,
        config=config,
    )

    gold_by_case_id = {
        str(case.get("case_id") or ""): case_label(case)
        for case in target_cases
    }
    async def predict_target(case: dict[str, Any]) -> dict[str, Any]:
        rule_votes = []
        task = target_task(case, target_domain)
        for rule in optimization.returned_rules:
            rule_votes.append(await judge_task(rule_text=rule.text, task=task, phase="target"))
        return {
            "case_id": str(case.get("case_id") or ""),
            "rule_votes": rule_votes,
            "prediction": majority_vote(rule_votes),
        }

    target_predictions = await run_ordered_bounded(
        target_cases,
        predict_target,
        concurrency=args.llm_concurrency,
    )
    metrics = evaluate_predictions([
        {**row, "gold_label": gold_by_case_id.get(str(row["case_id"]), "")}
        for row in target_predictions
    ])
    execution_integrity = summarize_judge_audit(judge_audit_records)
    sampling_manifest = build_target_sampling_manifest(
        target_domain=target_domain,
        target_cases=target_cases,
        random_state=args.random_state,
        cases_per_label=resolved_target_cases_per_label(args),
    )
    write_json(fold_dir / "target_sampling_manifest.json", sampling_manifest)
    write_json(fold_dir / "report.json", {
        "target_domain": target_domain,
        "effective_protocol": effective_protocol(args),
        "source_domain_count": len({case_domain(case) for case in source_cases}),
        "validation_task_count": len(tasks),
        "target_case_count": len(target_cases),
        "optimization": optimization_to_json(optimization),
        "metrics": metrics,
        "execution_integrity": execution_integrity,
        "target_sampling": sampling_manifest,
    })
    write_jsonl(fold_dir / "predictions.jsonl", target_predictions)
    return {
        "target_domain": target_domain,
        "effective_protocol": effective_protocol(args),
        "source_domains": sorted({case_domain(case) for case in source_cases}),
        "validation_task_count": len(tasks),
        "target_case_count": len(target_cases),
        "optimization": optimization_to_json(optimization),
        "metrics": metrics,
        "execution_integrity": execution_integrity,
        "target_sampling": sampling_manifest,
    }


async def ensure_analysis_reports(*, cases, provider, model, retriever, args, cache, cache_path) -> None:
    missing_cases = []
    for case in cases:
        case_id = str(case.get("case_id") or "")
        if not case_id:
            continue
        cached = find_complete_cached_analysis(case, cache)
        if cached is None:
            missing_cases.append(case)
        else:
            cache[case_id] = cached

    async def analyze_case(case: dict[str, Any]) -> dict[str, Any]:
        case_id = str(case.get("case_id") or "")
        last_record: dict[str, Any] | None = None
        for attempt in range(int(getattr(args, "analysis_case_retries", 0)) + 1):
            result = await run_maro_paper_multi_dimensional_analysis(
                case=case,
                provider=provider,
                model=model,
                active_retriever=retriever,
                external_retrieval_enabled=True,
                retrieval_top_k=args.retrieval_top_k,
                max_agent_calls_per_case=args.max_agent_calls_per_case,
            )
            last_record = {
                "case_id": case_id,
                "case_fingerprint": case_fingerprint(case),
                "analysis": format_analysis_report(result),
                "agent_reports": result.get("agent_reports", []),
                "evidence_bundle": result.get("evidence_bundle", {}),
                "retrieval_audit": (result.get("active_retrieval") or {}).get("audit", {}),
                "analysis_audit": result.get("audit", {}),
                "analysis_summary": result.get("summary", {}),
                "protocol": result.get("schema_version"),
                "analysis_attempt": attempt + 1,
            }
            if has_complete_analysis(last_record):
                return last_record
        assert last_record is not None
        return last_record

    records = await run_ordered_bounded(
        missing_cases,
        analyze_case,
        concurrency=args.llm_concurrency,
    )
    for record in records:
        require_complete_analysis(record)
        cache[str(record["case_id"])] = record
        append_jsonl(cache_path, record)


def build_cross_domain_validation_tasks_for_dry_run(cases, target_domain, args):
    return build_cross_domain_validation_tasks(
        [case for case in cases if case_domain(case) != target_domain],
        target_domain=target_domain,
        config=MARORuleOptimizationConfig(
            validation_task_count=args.validation_tasks,
            max_samples_per_source_domain=args.samples_per_source_domain,
            max_iterations=args.max_iterations,
            max_attempts=args.max_attempts,
            returned_rule_count=args.returned_rule_count,
            random_state=args.random_state,
        ),
    )


def build_dry_run_manifest(cases, target_domains, args, dataset_manifest):
    folds = []
    for domain in target_domains:
        source = [case for case in cases if case_domain(case) != domain]
        target = [case for case in cases if case_domain(case) == domain]
        tasks = build_cross_domain_validation_tasks_for_dry_run(cases, domain, args)
        folds.append({
            "target_domain": domain,
            "source_domains": sorted({case_domain(case) for case in source}),
            "validation_task_count": len(tasks),
            "target_case_count": len(
                select_target_cases(
                    target,
                    max_cases=resolved_target_case_count(args),
                    random_state=args.random_state,
                    cases_per_label=resolved_target_cases_per_label(args),
                )
            ),
            "query_label_counts": dict(Counter(task.query_label for task in tasks)),
            "demonstration_domain_check": all(
                all(item.domain not in {task.query_domain, domain} for item in task.demonstrations)
                for task in tasks
            ),
        })
    return {
        "schema": "maro-weibo21-ins-dry-run-v1",
        "protocol": PAPER_PROTOCOL,
        "effective_protocol": effective_protocol(args),
        "dataset_manifest": dataset_manifest,
        "case_count": len(cases),
        "domains": sorted({case_domain(case) for case in cases}),
        "folds": folds,
        "external_calls": False,
        "concurrency": {
            "llm": args.llm_concurrency,
            "retrieval": args.retrieval_concurrency,
        },
    }


def load_or_convert_cases(args, output_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    case_path = Path(args.case_file) if args.case_file else output_dir / "Weibo21.jsonl"
    if not case_path.is_file():
        script_path = Path(__file__).with_name("build_review_post_cases.py")
        spec = importlib.util.spec_from_file_location("weibo21_case_converter", script_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Cannot load converter: {script_path}")
        converter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(converter)
        dataset_manifest = converter.convert_weibo21(
            Path(args.dataset_root),
            case_path,
            0,
            input_profile=args.input_profile,
        )
    else:
        dataset_manifest = {"status": "existing_case_file", "path": str(case_path)}
    if dataset_manifest.get("status") == "missing":
        raise SystemExit(f"Weibo21 source files are missing: {dataset_manifest.get('missing')}")
    source_cases = load_jsonl(case_path)
    if not source_cases:
        raise SystemExit(f"No cases found in {case_path}")
    cases = normalize_case_instances(source_cases)
    return cases, {
        **dataset_manifest,
        "case_path": str(case_path),
        "source_row_count": len(source_cases),
        "unique_case_instance_count": len(cases),
    }


def build_environment_retriever():
    """Build the experiment retriever without importing dataset training code."""

    api_key = (os.getenv("REVIEW_RETRIEVAL_API_KEY") or settings.REVIEW_RETRIEVAL_API_KEY or "").strip()
    base_url = (os.getenv("REVIEW_RETRIEVAL_BASE_URL") or settings.REVIEW_RETRIEVAL_BASE_URL or "").strip()
    if not api_key or not base_url:
        return None
    return _build_http_retrieval_provider(
        base_url=base_url,
        api_key=api_key,
        search_path=(
            os.getenv("REVIEW_RETRIEVAL_SEARCH_PATH")
            or settings.REVIEW_RETRIEVAL_SEARCH_PATH
            or "/search"
        ).strip()
        or "/search",
        timeout_seconds=float(os.getenv("REVIEW_RETRIEVAL_TIMEOUT_SECONDS") or "20"),
        provider_name=(
            os.getenv("REVIEW_RETRIEVAL_PROVIDER_NAME")
            or settings.REVIEW_RETRIEVAL_PROVIDER_NAME
            or "env_retrieval"
        ).strip()
        or "env_retrieval",
        adapter=(os.getenv("REVIEW_RETRIEVAL_ADAPTER") or settings.REVIEW_RETRIEVAL_ADAPTER or "").strip(),
    )


def target_task(case: Mapping[str, Any], target_domain: str) -> TargetJudgeTask:
    """Build a target inference task without carrying its gold label."""

    return TargetJudgeTask(
        task_id=f"target:{target_domain}:{case.get('case_id')}",
        query_case_id=str(case.get("case_id") or ""),
        query_text=str(case.get("text") or ""),
        query_domain=case_domain(case),
        target_domain=target_domain,
    )


def build_judge_prompt(*, rule_text: str, task: JudgeTask, analysis: str) -> str:
    demonstrations = "\n".join(
        f"DEMO {index}: domain={item.domain}; label={'1' if item.label == 'harmful' else '0'}; news={item.text[:1000]}"
        for index, item in enumerate(task.demonstrations, start=1)
    )
    return (
        f"DECISION RULE:\n{rule_text}\n\n"
        f"DEMONSTRATIONS FROM OTHER DOMAINS:\n{demonstrations}\n\n"
        f"QUERY DOMAIN: {task.query_domain}\nQUERY NEWS:\n{task.query_text[:4000]}\n\n"
        f"MULTI-DIMENSIONAL ANALYSIS REPORT:\n{analysis[:12000]}\n\n"
        "Apply the rule to this query."
    )


def parse_binary_judgment(text: str) -> str:
    """Return MARO's deterministic 0/1 interpretation for a non-empty response."""

    return _parse_binary_judgment_with_method(text)[0]


def _parse_binary_judgment_with_method(text: str) -> tuple[str, str]:
    raw = str(text or "")
    matches = re.findall(
        r"(?:JUDGMENT|LABEL|ANSWER|结论|判断)\s*[:：]\s*([01])\b",
        raw,
        flags=re.IGNORECASE,
    )
    if matches:
        return _binary_label(matches[-1]), "explicit_label"

    last_line = raw.strip().split("\n")[-1] if raw.strip() else ""
    last_line_numbers = re.findall(r"\d+", last_line)
    if last_line_numbers and last_line_numbers[-1] in {"0", "1"}:
        return _binary_label(last_line_numbers[-1]), "last_line_numeric"

    judgment_match = re.search(r"judgment\s*:\s*(.*)", raw, flags=re.IGNORECASE)
    if judgment_match:
        judgment_numbers = re.findall(r"\d+", judgment_match.group(1))
        if judgment_numbers and judgment_numbers[0] in {"0", "1"}:
            return _binary_label(judgment_numbers[0]), "judgment_numeric"

    paragraphs = raw.split("\n\n")
    penultimate = paragraphs[-2] if len(paragraphs) >= 2 else raw
    if re.search(r"\b(?:0|real-news)\b", penultimate, flags=re.IGNORECASE):
        return "non_harmful", "penultimate_paragraph"
    if re.search(r"\b(?:1|fake-news)\b", penultimate, flags=re.IGNORECASE):
        return "harmful", "penultimate_paragraph"

    if SequenceMatcher(None, "fake-news", raw.strip().lower()).ratio() > 0.5:
        return "harmful", "sequence_matcher_fallback"
    return "non_harmful", "sequence_matcher_fallback"


def _binary_label(value: str) -> str:
    return "harmful" if value == "1" else "non_harmful"


async def run_judge_with_retries(
    *,
    provider,
    model: str,
    rule_text: str,
    task: JudgeTask,
    analysis: str,
    phase: str,
    format_retries: int,
    audit_path: Path,
    audit_records: list[dict[str, Any]] | None = None,
) -> str:
    """Call the INS Judge and fail the run if empty/error responses exhaust retries."""

    total_attempts = max(0, int(format_retries)) + 1
    prompt = build_judge_prompt(rule_text=rule_text, task=task, analysis=analysis)
    input_bundle = {
        "rule": rule_text,
        "task_id": task.task_id,
        "analysis": analysis,
        "phase": phase,
    }
    rule_hash = hashlib.sha256(rule_text.encode("utf-8")).hexdigest()
    for attempt in range(1, total_attempts + 1):
        record: dict[str, Any] = {
            "phase": phase,
            "task_id": task.task_id,
            "rule_hash": rule_hash,
            "rule_text": rule_text,
            "attempt": attempt,
            "input_bundle": input_bundle,
        }
        try:
            response = await provider(
                agent_name="HarmfulnessJudgeAgent",
                system_prompt=(
                    "You are MARO's Judge Agent. Apply the supplied rule to the query and its multi-dimensional "
                    "analysis. Demonstration labels use 1=fake and 0=real. Return exactly one final line "
                    "JUDGMENT: 1 or JUDGMENT: 0; do not place another JUDGMENT token in the explanation."
                ),
                user_prompt=prompt,
                input_bundle=input_bundle,
                model=model,
            )
        except Exception as exc:
            telemetry = provider_telemetry_for_audit(provider)
            _append_judge_audit_record(
                record
                | {
                    "status": "provider_error",
                    "error_class": type(exc).__name__,
                    "provider_http_status": telemetry.get("http_status"),
                    "provider_error_class": telemetry.get("error_class"),
                    "provider_attempt_count": telemetry.get("attempt_count"),
                    "provider_retry_count": telemetry.get("retry_count"),
                    "provider_rate_limit_retry_count": telemetry.get("rate_limit_retry_count"),
                },
                audit_path,
                audit_records,
            )
            continue
        response_text = str(response or "").strip()
        if not response_text:
            _append_judge_audit_record(record | {"status": "empty_response"}, audit_path, audit_records)
            continue
        label, parse_method = _parse_binary_judgment_with_method(response_text)
        _append_judge_audit_record(
            record | {
                "status": "completed",
                "response_text": response_text,
                "parse_method": parse_method,
                "parsed_label": label,
            },
            audit_path,
            audit_records,
        )
        return label
    raise JudgeExecutionError(
        f"MARO Judge failed to return a non-empty response after {total_attempts} attempts "
        f"for {phase} task {task.task_id}."
    )


def _append_judge_audit_record(
    record: dict[str, Any],
    audit_path: Path,
    audit_records: list[dict[str, Any]] | None,
) -> None:
    append_jsonl(audit_path, record)
    if audit_records is not None:
        audit_records.append(record)


def majority_vote(votes: list[str]) -> str:
    if not votes or len(votes) % 2 == 0:
        raise ValueError("MARO majority voting requires a non-empty odd number of rule votes.")
    if any(vote not in MARO_LABELS for vote in votes):
        raise ValueError("MARO majority voting requires only binary labels.")
    counts = Counter(votes)
    return "harmful" if counts["harmful"] > len(votes) // 2 else "non_harmful"


def extract_rule_text(response: str) -> str:
    lines = [line.strip() for line in str(response or "").splitlines() if line.strip()]
    marked = [line.split(":", 1)[1].strip() for line in lines if line.upper().startswith("RULE:")]
    return marked[-1] if marked else " ".join(lines)


def evaluate_predictions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise ValueError("MARO evaluation requires at least one submitted target row.")
    for row in rows:
        if row.get("gold_label") not in MARO_LABELS:
            raise ValueError(f"MARO evaluation received an invalid gold label: {row.get('gold_label')!r}")
        if row.get("prediction") not in MARO_LABELS:
            raise ValueError(f"MARO evaluation received a non-binary prediction: {row.get('prediction')!r}")
    gold = [1 if row["gold_label"] == "harmful" else 0 for row in rows]
    predicted = [1 if row["prediction"] == "harmful" else 0 for row in rows]
    return {
        "submitted_count": len(rows),
        "classification_metrics": {
            "accuracy": round(float(accuracy_score(gold, predicted)), 6),
            "macro_f1": round(float(f1_score(gold, predicted, average="macro", zero_division=0)), 6),
            "f1_positive_fake": round(float(f1_score(gold, predicted, zero_division=0)), 6),
            "precision_positive_fake": round(float(precision_score(gold, predicted, zero_division=0)), 6),
        },
    }


def optimization_to_json(result) -> dict[str, Any]:
    return {
        "initial_rule": decision_rule_to_json(result.initial_rule),
        "best_rule": decision_rule_to_json(result.best_rule),
        "accepted_rules": [decision_rule_to_json(item) for item in result.accepted_rules],
        "returned_rules": [decision_rule_to_json(item) for item in result.returned_rules],
        "trajectory": [decision_rule_to_json(item) for item in result.trajectory],
        "evaluated_task_count": result.evaluated_task_count,
        "iterations_completed": result.iterations_completed,
        "consecutive_non_improvements": result.consecutive_non_improvements,
        "stop_reason": result.stop_reason,
    }


def decision_rule_to_json(rule: DecisionRule) -> dict[str, Any]:
    return {
        "text": rule.text,
        "accuracy": rule.accuracy,
        "iteration": rule.iteration,
        "accepted": rule.accepted,
    }


def summarize_folds(folds: Mapping[str, Any]) -> dict[str, Any]:
    reports = [fold["metrics"] for fold in folds.values()]
    metric_rows = [item["classification_metrics"] for item in reports]
    return {
        "fold_count": len(folds),
        "mean_accuracy": round(sum(item["accuracy"] for item in metric_rows) / len(metric_rows), 6) if metric_rows else None,
        "mean_macro_f1": round(sum(item["macro_f1"] for item in metric_rows) / len(metric_rows), 6) if metric_rows else None,
        "claim_boundary": "Weibo21 local leave-one-domain-out adaptation; not official MARO AMTCele reproduction.",
    }


def summarize_judge_audit(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Report execution reliability without changing the evaluation denominator."""

    completed = [record for record in records if record.get("status") == "completed"]
    retried_task_ids = {
        str(record.get("task_id") or "")
        for record in records
        if int(record.get("attempt") or 0) > 1
    }
    return {
        "judge_call_attempt_count": len(records),
        "completed_judge_call_count": len(completed),
        "retried_task_count": len(retried_task_ids),
        "audit_log": "judge_audit.jsonl",
        "metric_denominator_policy": "Every target sample receives one binary majority-vote prediction; audit fields never filter metrics.",
    }


def select_target_cases(
    cases: list[dict[str, Any]],
    *,
    max_cases: int,
    random_state: int,
    cases_per_label: int | None = None,
) -> list[dict[str, Any]]:
    """Select a deterministic, optionally exact label-stratified target sample.

    ``cases_per_label`` is an evaluation-only sampling control. Gold labels are
    used to construct the fixed sample manifest, but are never copied into a
    target Judge task or prompt.
    """

    if max_cases < 0:
        raise ValueError("max_cases must be >= 0")
    cases = _deduplicate_target_cases(cases)
    if cases_per_label is not None:
        if cases_per_label < 1:
            raise ValueError("cases_per_label must be >= 1")
        expected_count = cases_per_label * len(MARO_LABELS)
        if max_cases not in {0, expected_count}:
            raise ValueError(
                "max_cases must be zero or exactly twice cases_per_label when "
                "exact label-stratified sampling is enabled"
            )
        max_cases = expected_count
    if max_cases <= 0:
        return list(cases)
    groups = {
        label: sorted(
            [case for case in cases if case_label(case) == label],
            key=lambda case: hashlib.sha256(
                f"{random_state}:{case.get('case_id') or ''}".encode("utf-8")
            ).hexdigest(),
        )
        for label in MARO_LABELS
    }
    if cases_per_label is not None and any(len(groups[label]) < cases_per_label for label in MARO_LABELS):
        raise ValueError(
            "target domain does not contain enough cases for the requested per-label sample"
        )
    if cases_per_label is None and len(cases) <= max_cases:
        return list(cases)
    selected: list[dict[str, Any]] = []
    for label in MARO_LABELS:
        quota = cases_per_label if cases_per_label is not None else max_cases // 2
        selected.extend(groups[label][:quota])
    remaining = [case for case in cases if case not in selected]
    selected.extend(remaining[: max_cases - len(selected)])
    return selected[:max_cases]


def _deduplicate_target_cases(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep one identical row per case ID and reject ambiguous dataset collisions."""

    unique: dict[str, dict[str, Any]] = {}
    for position, case in enumerate(cases):
        case_id = str(case.get("case_id") or "").strip()
        if not case_id:
            raise ValueError(f"target case at position {position} has no case_id")
        previous = unique.get(case_id)
        if previous is None:
            unique[case_id] = case
            continue
        same_case = (
            case_label(previous) == case_label(case)
            and case_domain(previous) == case_domain(case)
            and str(previous.get("text") or "").strip() == str(case.get("text") or "").strip()
        )
        if not same_case:
            raise ValueError(f"target case_id collision has inconsistent content or labels: {case_id}")
    return list(unique.values())


def resolved_target_cases_per_label(args: argparse.Namespace) -> int | None:
    """Resolve the exact per-label quota while preserving legacy CLI calls."""

    value = getattr(args, "target_cases_per_label", None)
    if value is not None:
        return int(value)
    max_cases = int(getattr(args, "max_target_cases", 0))
    return max_cases // len(MARO_LABELS) if max_cases > 0 and max_cases % 2 == 0 else None


def resolved_target_case_count(args: argparse.Namespace) -> int:
    """Return the effective target count per held-out domain."""

    per_label = resolved_target_cases_per_label(args)
    if per_label is not None:
        return per_label * len(MARO_LABELS)
    return int(getattr(args, "max_target_cases", 0))


def build_target_sampling_manifest(
    *,
    target_domain: str,
    target_cases: list[Mapping[str, Any]],
    random_state: int,
    cases_per_label: int | None,
) -> dict[str, Any]:
    """Describe the fixed evaluation sample without exposing it to the Judge."""

    rows = [
        {
            "case_id": str(case.get("case_id") or ""),
            "source_case_id": source_case_id(case),
            "domain": case_domain(case),
            "gold_label": case_label(case),
        }
        for case in target_cases
    ]
    if len({row["case_id"] for row in rows}) != len(rows):
        raise ValueError("target sampling manifest requires unique case IDs")
    manifest_payload = json.dumps(rows, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return {
        "protocol": "weibo21-stratified-target-sample-v1",
        "target_domain": target_domain,
        "selection_seed": random_state,
        "cases_per_label": cases_per_label,
        "target_case_count": len(rows),
        "label_counts": dict(Counter(row["gold_label"] for row in rows)),
        "evaluation_only": True,
        "target_labels_sent_to_agent": False,
        "sample_manifest_sha256": hashlib.sha256(manifest_payload).hexdigest(),
        "cases": rows,
    }


def has_complete_analysis(record: Mapping[str, Any] | None) -> bool:
    """Return whether a cached MARO analysis completed every required role."""

    if not isinstance(record, Mapping):
        return False
    summary = record.get("analysis_summary") if isinstance(record.get("analysis_summary"), Mapping) else {}
    requested = int(summary.get("requested_agents") or 0)
    completed = int(summary.get("completed") or 0)
    reports = record.get("agent_reports") if isinstance(record.get("agent_reports"), list) else []
    return requested > 0 and completed == requested and all(
        isinstance(report, Mapping) and report.get("status") == "completed"
        for report in reports
    )


def find_complete_cached_analysis(
    case: Mapping[str, Any],
    cache: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    """Resolve a complete cache entry by instance ID, then by input fingerprint."""

    direct = cache.get(str(case.get("case_id") or ""))
    if has_complete_analysis(direct):
        return direct
    fingerprint = case_fingerprint(case)
    for record in cache.values():
        if has_complete_analysis(record) and str(record.get("case_fingerprint") or "") == fingerprint:
            return record
    return None


def require_complete_analysis(record: Mapping[str, Any]) -> None:
    """Prevent partial multi-agent analysis from silently reaching the Judge."""

    if has_complete_analysis(record):
        return
    case_id = str(record.get("case_id") or "")
    raise RuntimeError(f"MARO analysis is incomplete for case_id={case_id}")


def select_calibration_cases(
    cases: list[dict[str, Any]],
    *,
    target_domains: list[str],
    max_cases: int,
    random_state: int,
) -> list[dict[str, Any]]:
    """Select deterministic analysis-only cases without inspecting gold labels."""

    normalized_domains = {str(item).strip().lower() for item in target_domains if str(item).strip()}
    candidates = [
        case
        for case in cases
        if not normalized_domains or case_domain(case) in normalized_domains
    ]
    ordered = sorted(
        candidates,
        key=lambda case: hashlib.sha256(
            f"calibration:{random_state}:{case.get('case_id') or ''}".encode("utf-8")
        ).hexdigest(),
    )
    return ordered if max_cases <= 0 else ordered[:max_cases]


def effective_protocol(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "validation_task_count": args.validation_tasks,
        "samples_per_source_domain": args.samples_per_source_domain,
        "max_iterations": args.max_iterations,
        "max_attempts": args.max_attempts,
        "returned_rule_count": args.returned_rule_count,
        "random_state": args.random_state,
        "max_target_cases_per_domain": resolved_target_case_count(args),
        "target_cases_per_label": resolved_target_cases_per_label(args),
        "target_sampling": "exact_label_stratified_when_target_cases_per_label_is_set",
        "analysis_calls_per_case": args.max_agent_calls_per_case,
        "analysis_case_retries": args.analysis_case_retries,
        "retrieval_top_k": args.retrieval_top_k,
        "judge_format_retries": args.judge_format_retries,
        "llm_concurrency": args.llm_concurrency,
        "retrieval_concurrency": args.retrieval_concurrency,
        "retrieval_max_retries": args.retrieval_max_retries,
        "paper_default_override": {
            "validation_tasks": args.validation_tasks != PAPER_PROTOCOL["validation_task_count"],
            "source_samples": args.samples_per_source_domain != PAPER_PROTOCOL["samples_per_source_domain"],
            "iterations": args.max_iterations != PAPER_PROTOCOL["max_iterations"],
            "attempts": args.max_attempts != PAPER_PROTOCOL["max_attempts"],
            "returned_rules": args.returned_rule_count != PAPER_PROTOCOL["returned_rule_count"],
        },
    }


def format_analysis_report(result: Mapping[str, Any]) -> str:
    sections = []
    for report in result.get("agent_reports") or []:
        text = str(report.get("report_text") or "").strip()
        if text:
            sections.append(f"[{report.get('maro_role') or report.get('agent_name')}]\n{text}")
    return "\n\n".join(sections)


def load_analysis_cache(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    return {
        analysis_cache_record_key(row): row
        for row in load_jsonl(path)
        if str(row.get("case_id") or "")
    }


def analysis_cache_record_key(record: Mapping[str, Any]) -> str:
    """Preserve multiple input variants that share an upstream source-post ID."""

    case_id = str(record.get("case_id") or "")
    fingerprint = str(record.get("case_fingerprint") or "")
    return f"{case_id}::{fingerprint}" if fingerprint else case_id


def load_experiment_analysis_cache(
    *,
    output_cache_path: Path,
    seed_cache_path: str | Path = "",
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Merge an optional read-only seed cache with the current run cache."""

    current = load_analysis_cache(output_cache_path)
    seed_path = Path(seed_cache_path) if str(seed_cache_path or "").strip() else None
    seed = load_analysis_cache(seed_path) if seed_path is not None else {}
    merged = {**seed, **current}
    return merged, {
        "output_cache_path": str(output_cache_path),
        "seed_cache_path": str(seed_path) if seed_path is not None else None,
        "seed_unique_record_count": len(seed),
        "current_unique_record_count": len(current),
        "merged_unique_record_count": len(merged),
    }


def refresh_analysis_cache_provenance(
    provenance: Mapping[str, Any],
    *,
    output_cache_path: Path,
) -> dict[str, Any]:
    """Update cache counts after the current run appends completed analyses."""

    current = load_analysis_cache(output_cache_path)
    seed_path = provenance.get("seed_cache_path")
    seed = load_analysis_cache(Path(str(seed_path))) if seed_path else {}
    refreshed = dict(provenance)
    refreshed["current_unique_record_count"] = len(current)
    refreshed["merged_unique_record_count"] = len({*seed, *current})
    return refreshed


def provider_telemetry_for_audit(provider: Any) -> dict[str, Any]:
    telemetry = getattr(provider, "last_call_telemetry", {})
    return dict(telemetry) if isinstance(telemetry, Mapping) else {}


def case_domain(case: Mapping[str, Any]) -> str:
    metadata = case.get("metadata") if isinstance(case.get("metadata"), Mapping) else {}
    return str(metadata.get("category") or "").strip().lower()


def case_label(case: Mapping[str, Any]) -> str:
    labels = case.get("labels") if isinstance(case.get("labels"), Mapping) else {}
    return str(labels.get("harmfulness") or "").strip().lower()


MARO_LABELS = ("harmful", "non_harmful")


def _select_domains(available: list[str], requested: list[str]) -> list[str]:
    if not requested:
        return available
    values = [str(item).strip().lower() for item in requested if str(item).strip()]
    missing = sorted(set(values) - set(available))
    if missing:
        raise SystemExit(f"Requested target domains are missing from the local snapshot: {missing}")
    return values


def source_case_id(case: Mapping[str, Any]) -> str:
    metadata = case.get("metadata") if isinstance(case.get("metadata"), Mapping) else {}
    return str(metadata.get("source_case_id") or case.get("case_id") or "").strip()


def normalize_case_instances(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Create stable row-instance IDs and remove exact duplicate source rows."""

    normalized: dict[str, dict[str, Any]] = {}
    for position, case in enumerate(cases):
        source_id = str(case.get("case_id") or "").strip()
        if not source_id:
            raise ValueError(f"Weibo21 source row at position {position} has no case_id")
        identity = {
            "source_case_id": source_id,
            "text": case.get("text"),
            "maro_inputs": case.get("maro_inputs"),
            "label": case_label(case),
            "domain": case_domain(case),
        }
        digest = hashlib.sha256(
            json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        instance_id = f"{source_id}::{digest[:16]}"
        if instance_id in normalized:
            continue
        metadata = dict(case.get("metadata") or {}) if isinstance(case.get("metadata"), Mapping) else {}
        metadata["source_case_id"] = source_id
        normalized[instance_id] = {**case, "case_id": instance_id, "metadata": metadata}
    return list(normalized.values())


def case_fingerprint(case: Mapping[str, Any]) -> str:
    payload = json.dumps(
        {
            "case_id": source_case_id(case),
            "text": case.get("text"),
            "maro_inputs": case.get("maro_inputs"),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def safe_name(value: str) -> str:
    text = str(value).strip()
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_")
    if normalized:
        return normalized
    return f"domain-{hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]}"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, default=str) + "\n" for row in rows), encoding="utf-8")


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", default=str(DEFAULT_DATASET_ROOT))
    parser.add_argument("--case-file", default="")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--input-profile", choices=["post_only", "post_and_comments"], default="post_and_comments")
    parser.add_argument("--target-domains", nargs="*", default=[])
    parser.add_argument("--validation-tasks", type=int, default=500)
    parser.add_argument("--samples-per-source-domain", type=int, default=100)
    parser.add_argument("--max-iterations", type=int, default=500)
    parser.add_argument("--max-attempts", type=int, default=10)
    parser.add_argument("--returned-rule-count", type=int, default=3)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument(
        "--max-target-cases",
        type=int,
        default=50,
        help="Maximum target cases per held-out domain; use 0 for all cases.",
    )
    parser.add_argument(
        "--target-cases-per-label",
        type=int,
        default=None,
        help="Exact evaluation-only quota for each binary target label.",
    )
    parser.add_argument("--max-agent-calls-per-case", type=int, default=9)
    parser.add_argument(
        "--analysis-case-retries",
        type=int,
        default=1,
        help="Retries for a case whose MARO role chain returns an incomplete report.",
    )
    parser.add_argument("--retrieval-top-k", type=int, default=3)
    parser.add_argument("--judge-format-retries", type=int, default=1)
    parser.add_argument("--llm-concurrency", type=int, default=1)
    parser.add_argument("--retrieval-concurrency", type=int, default=1)
    parser.add_argument("--retrieval-max-retries", type=int, default=2)
    parser.add_argument("--retrieval-retry-backoff-seconds", type=float, default=1.0)
    parser.add_argument("--calibration-cases", type=int, default=0)
    parser.add_argument(
        "--seed-analysis-cache",
        default="",
        help="Optional completed analysis cache used read-only before this run's cache.",
    )
    parser.add_argument("--initial-rule", default=DEFAULT_INITIAL_RULE)
    parser.add_argument("--enable-retrieval", action="store_true")
    parser.add_argument("--allow-local-domain-snapshot", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.validation_tasks < 1 or args.samples_per_source_domain < 4:
        raise SystemExit("validation tasks must be >=1 and source samples must be >=4")
    if args.max_target_cases < 0 or args.max_agent_calls_per_case < 9:
        raise SystemExit("max-target-cases must be >=0 and paper analysis needs at least 9 calls per case")
    if args.target_cases_per_label is not None:
        if args.target_cases_per_label < 1:
            raise SystemExit("target-cases-per-label must be >=1")
        expected_target_cases = args.target_cases_per_label * len(MARO_LABELS)
        if args.max_target_cases not in {0, expected_target_cases}:
            raise SystemExit(
                "max-target-cases must be zero or exactly twice target-cases-per-label"
            )
    if args.judge_format_retries < 0:
        raise SystemExit("judge-format-retries must be >=0")
    if args.analysis_case_retries < 0:
        raise SystemExit("analysis-case-retries must be >=0")
    if args.llm_concurrency < 1 or args.retrieval_concurrency < 1:
        raise SystemExit("llm-concurrency and retrieval-concurrency must be >=1")
    if args.retrieval_max_retries < 0 or args.retrieval_retry_backoff_seconds < 0:
        raise SystemExit("retrieval retry settings must be non-negative")
    if args.calibration_cases < 0:
        raise SystemExit("calibration-cases must be >=0")
    return args


if __name__ == "__main__":
    raise SystemExit(main())
