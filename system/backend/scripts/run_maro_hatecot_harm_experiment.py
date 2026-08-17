"""Run a MARO-compatible, cross-domain interpersonal-harm study on HateCoT.

This is not a reproduction of MARO's binary misinformation experiment. It
retains the paper's validation-only decision-rule optimization and independent
Judge, while replacing fact-checking roles with text harm analysis, local
public-policy references, and bounded reflection. HateCoT labels and provided
explanations are never exposed to an Agent prompt.
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from dataclasses import dataclass
import hashlib
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
from app.core.review.hatecot_harm_experiment import (  # noqa: E402
    HATECOT_EVALUATION_LABELS,
    HATECOT_LABEL_MAPPING_VERSION,
    build_source_split_manifest,
    build_target_sampling_manifest,
    case_domain,
    case_label,
    eligible_target_domains,
    evaluate_predictions,
    load_hatecot_cases,
    select_target_cases,
    split_source_cases,
)
from app.core.review.maro_harm_protocol import (  # noqa: E402
    MARO_HARM_PROTOCOL_VERSION,
    has_complete_harm_analysis,
    run_maro_harm_multiagent_analysis,
)
from app.core.review.maro_rule_optimization import (  # noqa: E402
    MARO_HARM_3WAY_LABELS,
    CrossDomainValidationTask,
    DecisionRule,
    MARORuleOptimizationConfig,
    build_cross_domain_validation_tasks,
    optimize_decision_rules,
)


DEFAULT_HATECOT_CSV = Path(r"G:\CISCN\dataset\HateCoT\hatecot_final_D3.csv")
DEFAULT_OUTPUT_DIR = Path(r"G:\CISCN\.tmp\maro_hatecot_harm")
DEFAULT_INITIAL_RULE = (
    "Classify only observable interpersonal harm in the post. Choose hate for identity- or affiliation-targeted "
    "dehumanization or abuse, offensive for direct person-targeted abuse or derogatory toxic language without a "
    "protected-group target, and non_harmful when the post lacks such an attack or clearly negates, quotes, or "
    "condemns it. Treat advisory policy references as vocabulary guidance, not as a label source."
)
PAPER_BOUNDARY = {
    "source_paper": "A Multi-Agent Framework with Automated Decision Rule Optimization for Cross-Domain Misinformation Detection",
    "paper_url": "https://arxiv.org/abs/2503.23329",
    "repository": "https://github.com/Brtulien/MARO",
    "repository_commit": "20aea25462c5ee55af5bf777084a0eb8553b8920",
    "transfer": "MARO-compatible harm adaptation, not official MARO misinformation reproduction.",
    "retained_mechanisms": [
        "source-validation-only rule optimization",
        "strict-improvement retention",
        "top-k decision-rule voting",
        "separate analysis and final Judge phases",
    ],
    "replaced_mechanisms": [
        "fact-checking/external retrieval replaced by PostHarmAgent plus local advisory policy references",
        "binary fake/real labels replaced by audited three-way interpersonal-harm labels",
        "comment analysis omitted because HateCoT supplies a post-only input",
    ],
    "strict_adaptation_protocol": "source-train candidate generation, source-dev rule selection, held-out target-test",
    "policy_context_boundary": "policy-off is the primary result; local_advisory is an ablation, not semantic PolicyRAG domain adaptation",
}


class JudgeExecutionError(RuntimeError):
    """Raised when a target or validation Judge cannot return a strict label."""


@dataclass(frozen=True)
class HarmTargetJudgeTask:
    """Unlabelled target-domain input for final harm inference."""

    task_id: str
    query_case_id: str
    query_text: str
    query_domain: str
    target_domain: str
    demonstrations: tuple[Any, ...] = ()


JudgeTask = CrossDomainValidationTask | HarmTargetJudgeTask


class BoundedExperimentProvider:
    """Apply shared concurrency telemetry without retaining a credential."""

    def __init__(self, *, execution: ExperimentConcurrency, delegate, temperature_role: str) -> None:
        self._execution = execution
        self._delegate = delegate
        self._temperature_role = temperature_role

    @property
    def last_call_telemetry(self) -> dict[str, Any]:
        telemetry = getattr(self._delegate, "last_call_telemetry", {})
        return dict(telemetry) if isinstance(telemetry, Mapping) else {}

    async def __call__(self, **kwargs: Any):
        return await self._execution.invoke(
            service="deepseek",
            operation=self._delegate,
            max_retries=0,
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
    if not args.dry_run and not args.resume:
        reject_existing_experiment_state(output_dir)
    cases, dataset_manifest = load_hatecot_cases(args.hatecot_csv)
    available_domains = eligible_target_domains(cases)
    target_domains = select_domains(available_domains, args.target_domains)
    if args.dry_run:
        manifest = build_dry_run_manifest(cases, target_domains, args, dataset_manifest)
        write_json(output_dir / "dry_run_manifest.json", manifest)
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0
    if not has_deepseek_api_key():
        raise SystemExit(
            "DEEPSEEK_API_KEY is missing. Configure it through the ignored local environment; "
            "this runner never accepts or writes API keys."
        )

    report = asyncio.run(run_experiment(cases, target_domains, args, dataset_manifest, output_dir))
    write_json(output_dir / "report.json", report)
    write_json(output_dir / "comparison.json", report.get("comparison") or {})
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
    analysis_provider, rule_provider, provider_config, execution = build_experiment_runtime(args)
    policy_modes = resolve_policy_modes(args.policy_context_mode)
    folds: dict[str, dict[str, Any]] = {mode: {} for mode in policy_modes}
    protocol_folds: list[dict[str, Any]] = []
    (output_dir / "folds").mkdir(parents=True, exist_ok=True)
    (output_dir / "analysis_cache").mkdir(parents=True, exist_ok=True)
    try:
        for target_domain in target_domains:
            target_cases = select_target_cases(
                [case for case in cases if case_domain(case) == target_domain],
                cases_per_label=args.target_cases_per_label,
                random_state=args.random_state,
            )
            source_train, source_dev, source_split = split_source_cases(
                cases,
                target_domain=target_domain,
                train_fraction=args.source_train_fraction,
                random_state=args.random_state,
            )
            target_manifest = build_target_sampling_manifest(
                target_domain=target_domain,
                target_cases=target_cases,
                random_state=args.random_state,
                cases_per_label=args.target_cases_per_label,
            )
            split_manifest = {
                "schema": "maro-hatecot-harm-split-manifest-v1",
                "target_domain": target_domain,
                "source": source_split,
                "target": target_manifest,
                "case_id_disjoint": _split_case_ids_are_disjoint(source_split, target_manifest),
            }
            if not split_manifest["case_id_disjoint"]:
                raise RuntimeError(f"HateCoT fold {target_domain} has overlapping split case IDs")
            fold_root = output_dir / "folds" / safe_name(target_domain)
            write_json(fold_root / "split_manifest.json", split_manifest)
            protocol_folds.append(split_manifest)
            candidate_rule_texts: list[str] | None = None
            for policy_mode in policy_modes:
                cache_path = output_dir / "analysis_cache" / f"{safe_name(policy_mode)}.jsonl"
                analysis_cache = load_analysis_cache(
                    cache_path,
                    seed_path=args.seed_analysis_cache,
                    include_current_cache=args.resume,
                )
                fold_root = output_dir / "folds" / safe_name(target_domain) / safe_name(policy_mode)
                reusable = load_resumable_fold_report(
                    fold_root / "report.json",
                    split_manifest=split_manifest,
                    args=args,
                    policy_context_mode=policy_mode,
                )
                if reusable is not None:
                    folds[policy_mode][target_domain] = reusable
                    if candidate_rule_texts is None:
                        candidate_rule_texts = list(reusable.get("candidate_rule_pool") or [])
                    continue
                fold_report = await run_fold(
                    cases=cases,
                    target_domain=target_domain,
                    args=args,
                    output_dir=output_dir,
                    analysis_provider=analysis_provider,
                    rule_provider=rule_provider,
                    model=provider_config.model,
                    analysis_cache=analysis_cache,
                    cache_path=cache_path,
                    policy_context_mode=policy_mode,
                    source_train=source_train,
                    source_dev=source_dev,
                    target_cases=target_cases,
                    split_manifest=split_manifest,
                    candidate_rule_texts=candidate_rule_texts,
                )
                if candidate_rule_texts is None:
                    candidate_rule_texts = list(fold_report["candidate_rule_pool"])
                folds[policy_mode][target_domain] = fold_report
                write_json(
                    output_dir / "report.partial.json",
                    {
                        "schema": "maro-hatecot-harm-report-v2",
                        "paper_boundary": PAPER_BOUNDARY,
                        "effective_protocol": effective_protocol(args),
                        "dataset_manifest": dataset_manifest,
                        "folds": folds,
                        "protocol_folds": protocol_folds,
                        "provider_telemetry": execution.snapshot(),
                    },
                )
        protocol_manifest = {
            "schema": "maro-hatecot-harm-protocol-manifest-v2",
            "paper_boundary": PAPER_BOUNDARY,
            "effective_protocol": effective_protocol(args),
            "dataset_manifest": dataset_manifest,
            "target_domains": target_domains,
            "policy_context_arms": policy_modes,
            "folds": protocol_folds,
            "fold_protocol_hashes": {
                mode: {
                    item["target_domain"]: build_protocol_hash(
                        args=args,
                        split_manifest=item,
                        policy_context_mode=mode,
                    )
                    for item in protocol_folds
                }
                for mode in policy_modes
            },
            "external_calls": True,
            "external_fact_retrieval": False,
        }
        write_json(output_dir / "protocol_manifest.json", protocol_manifest)
    finally:
        await analysis_provider.aclose()
        await rule_provider.aclose()
    comparison = build_comparison(folds)
    return {
        "schema": "maro-hatecot-harm-report-v2",
        "paper_boundary": PAPER_BOUNDARY,
        "effective_protocol": effective_protocol(args),
        "dataset_manifest": dataset_manifest,
        "execution": {
            "model": provider_config.model,
            "timeout_seconds": provider_config.timeout_seconds,
            "provider_max_retries": provider_config.max_retries,
            "external_fact_retrieval_used": False,
            "policy_reference_source": "local_public_governance_reference_library",
            "analysis_cache": str(output_dir / "analysis_cache"),
            "concurrency": {"llm": args.llm_concurrency},
            "provider_telemetry": execution.snapshot(),
        },
        "folds": folds,
        "comparison": comparison,
        "summary": summarize_arms(folds),
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
        BoundedExperimentProvider(
            execution=execution,
            delegate=raw_analysis_provider,
            temperature_role="analysis",
        ),
        BoundedExperimentProvider(
            execution=execution,
            delegate=raw_rule_provider,
            temperature_role="rule_and_judge",
        ),
        config,
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
    analysis_cache: dict[str, dict[str, Any]],
    cache_path: Path,
    policy_context_mode: str,
    source_train: list[dict[str, Any]],
    source_dev: list[dict[str, Any]],
    target_cases: list[dict[str, Any]],
    split_manifest: dict[str, Any],
    candidate_rule_texts: list[str] | None,
) -> dict[str, Any]:
    fold_dir = output_dir / "folds" / safe_name(target_domain) / safe_name(policy_context_mode)
    fold_dir.mkdir(parents=True, exist_ok=True)
    judge_audit_path = fold_dir / "judge_audit.jsonl"
    judge_audit_records: list[dict[str, Any]] = []
    train_config = build_rule_config(args, task_count=args.source_train_tasks, random_state=args.random_state)
    dev_config = build_rule_config(args, task_count=args.source_dev_tasks, random_state=args.random_state + 1)
    source_train_tasks = build_cross_domain_validation_tasks(
        source_train,
        target_domain=target_domain,
        config=train_config,
    )
    source_dev_tasks = build_cross_domain_validation_tasks(
        source_dev,
        target_domain=target_domain,
        config=dev_config,
    )
    needed_ids = {task.query_case_id for task in source_train_tasks}
    needed_ids.update(task.query_case_id for task in source_dev_tasks)
    needed_ids.update(str(case.get("case_id") or "") for case in target_cases)
    analysis_cache_stats = await ensure_analysis_reports(
        cases=[case for case in cases if str(case.get("case_id") or "") in needed_ids],
        provider=analysis_provider,
        model=model,
        include_reflection=not args.disable_reflection,
        retries=args.analysis_case_retries,
        cache=analysis_cache,
        cache_path=cache_path,
        concurrency=args.llm_concurrency,
        policy_context_mode=policy_context_mode,
    )

    async def propose_rule(*, trajectory: list[DecisionRule], best_rule: DecisionRule, iteration: int) -> str:
        trajectory_text = "\n".join(
            f"RULE {index}: {item.text}\nSOURCE_TRAIN_ACCURACY: {item.accuracy:.6f}"
            for index, item in enumerate(trajectory, start=1)
        )
        response = await rule_provider(
            agent_name="MARODecisionRuleOptimizationAgent",
            system_prompt=(
                "You optimize a concise cross-domain rule for three-way interpersonal-harm classification. "
                "The class mapping is 0=non_harmful, 1=offensive, 2=hate. Improve the rule only from the source "
                "source-train trajectory. Keep distinctions tied to observable text and identity/affiliation targeting; "
                "do not use policy references as label evidence. Return exactly one line beginning RULE:."
            ),
            user_prompt=json.dumps(
                {"iteration": iteration, "best_rule": best_rule.text, "trajectory": trajectory_text},
                ensure_ascii=False,
            ),
            input_bundle={"iteration": iteration, "best_rule": best_rule.text, "trajectory": trajectory_text},
            model=model,
        )
        return extract_rule_text(response)

    async def judge_task(*, rule_text: str, task: JudgeTask, phase: str = "source_train") -> str:
        analysis = analysis_cache[str(task.query_case_id)]["analysis"]
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
            policy_context_mode=policy_context_mode,
        )

    optimization = None
    if candidate_rule_texts is None:
        optimization = await optimize_decision_rules(
            tasks=source_train_tasks,
            initial_rule=args.initial_rule,
            propose_rule=propose_rule,
            judge_task=lambda *, rule_text, task: judge_task(
                rule_text=rule_text,
                task=task,
                phase="source_train",
            ),
            config=train_config,
        )
        candidate_rule_texts = candidate_rules_from_optimization(optimization)
    if candidate_rule_texts is None or len(candidate_rule_texts) < args.returned_rule_count:
        raise RuntimeError(
            f"Need at least {args.returned_rule_count} distinct candidate rules; "
            f"got {len(candidate_rule_texts or [])}"
        )

    source_dev_rule_scores = await evaluate_rule_pool(
        candidate_rule_texts=candidate_rule_texts,
        tasks=source_dev_tasks,
        judge_task=judge_task,
        concurrency=args.llm_concurrency,
    )
    selected_rules = select_dev_rules(source_dev_rule_scores, args.returned_rule_count)
    if len(selected_rules) % 2 != 1:
        raise RuntimeError("MARO harm voting requires an odd number of returned rules")

    async def predict_target(case: dict[str, Any]) -> dict[str, Any]:
        task = target_task(case, target_domain)
        votes = [
            await judge_task(rule_text=rule, task=task, phase="target")
            for rule in selected_rules
        ]
        return {
            "case_id": str(case["case_id"]),
            "rule_votes": votes,
            "prediction": majority_vote(votes),
            "vote_tie": len(set(votes)) == len(votes),
            "tie_break_rule": "best_returned_rule" if len(set(votes)) == len(votes) else None,
        }

    target_predictions = await run_ordered_bounded(
        target_cases,
        predict_target,
        concurrency=args.llm_concurrency,
    )
    gold_by_case_id = {str(case["case_id"]): case_label(case) for case in target_cases}
    scored_predictions = [
        {**prediction, "gold_label": gold_by_case_id[str(prediction["case_id"])]}
        for prediction in target_predictions
    ]
    metrics = evaluate_predictions(scored_predictions)
    target_manifest = build_target_sampling_manifest(
        target_domain=target_domain,
        target_cases=target_cases,
        random_state=args.random_state,
        cases_per_label=args.target_cases_per_label,
    )
    policy_audit = summarize_policy_capsules(
        target_cases,
        analysis_cache,
        policy_context_mode=policy_context_mode,
    )
    execution_integrity = summarize_judge_audit(judge_audit_records, expected_rule_votes=len(selected_rules))
    fold_report = {
        "target_domain": target_domain,
        "policy_context_mode": policy_context_mode,
        "protocol_hash": build_protocol_hash(
            args=args,
            split_manifest=split_manifest,
            policy_context_mode=policy_context_mode,
        ),
        "source_domains": sorted({case_domain(case) for case in source_train + source_dev}),
        "effective_protocol": effective_protocol(args),
        "label_mapping_version": HATECOT_LABEL_MAPPING_VERSION,
        "source_domain_count": len({case_domain(case) for case in source_train + source_dev}),
        "source_train_task_count": len(source_train_tasks),
        "source_dev_task_count": len(source_dev_tasks),
        "analysis_cache": analysis_cache_stats,
        "source_split": split_manifest["source"],
        "target_case_count": len(target_cases),
        "optimization": optimization_to_json(optimization) if optimization else None,
        "candidate_rule_pool": candidate_rule_texts,
        "selected_rules": selected_rules,
        "source_dev_rule_scores": source_dev_rule_scores,
        "metrics": metrics,
        "execution_integrity": execution_integrity,
        "policy_reference_audit": policy_audit,
        "target_sampling": target_manifest,
    }
    write_json(fold_dir / "report.json", fold_report)
    write_json(
        fold_dir / "source_train_rule_trajectory.json",
        optimization_to_json(optimization) if optimization else {"candidate_rule_pool": candidate_rule_texts},
    )
    write_json(
        fold_dir / "source_dev_rule_scores.json",
        {"scores": source_dev_rule_scores, "selected_rules": selected_rules},
    )
    write_json(fold_dir / "confusion_matrix.json", metrics["confusion_matrix"])
    write_json(fold_dir / "target_sampling_manifest.json", target_manifest)
    write_jsonl(fold_dir / "predictions.jsonl", target_predictions)
    write_jsonl(fold_dir / "scored_predictions.jsonl", scored_predictions)
    if judge_audit_path.exists():
        judge_audit_path.replace(fold_dir / "audit.jsonl")
    return fold_report


async def ensure_analysis_reports(
    *,
    cases: list[dict[str, Any]],
    provider,
    model: str,
    include_reflection: bool,
    retries: int,
    cache: dict[str, dict[str, Any]],
    cache_path: Path,
    concurrency: int,
    policy_context_mode: str,
) -> dict[str, int]:
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
                include_policy_context=policy_context_mode == "local_advisory",
            )
            last_record = {
                "case_id": case_id,
                "case_fingerprint": case_fingerprint(case),
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

    records = await run_ordered_bounded(missing, analyze_case, concurrency=concurrency)
    for record in records:
        if not has_complete_harm_analysis(record):
            raise RuntimeError(f"Incomplete MARO harm analysis for {record.get('case_id')}")
        cache[str(record["case_id"])] = record
        append_jsonl(cache_path, record)
    return {
        "requested_case_count": len(cases),
        "cache_hit_count": len(cases) - len(missing),
        "new_analysis_count": len(records),
    }


def build_rule_config(
    args: argparse.Namespace,
    *,
    task_count: int,
    random_state: int,
) -> MARORuleOptimizationConfig:
    return MARORuleOptimizationConfig(
        validation_task_count=task_count,
        max_samples_per_source_domain=args.samples_per_source_domain,
        max_iterations=args.max_iterations,
        max_attempts=args.max_attempts,
        returned_rule_count=args.returned_rule_count,
        random_state=random_state,
        evaluation_concurrency=args.llm_concurrency,
        label_space=MARO_HARM_3WAY_LABELS,
        demonstration_label_plan=MARO_HARM_3WAY_LABELS,
        label_key="interpersonal_harm",
    )


def unique_rule_texts(trajectory: list[DecisionRule] | tuple[DecisionRule, ...]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for rule in trajectory:
        text = str(rule.text or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def candidate_rules_from_optimization(result) -> list[str]:
    """Return only rules retained by strict source-train improvement."""

    return unique_rule_texts(result.accepted_rules)


async def evaluate_rule_pool(
    *,
    candidate_rule_texts: list[str],
    tasks: list[CrossDomainValidationTask],
    judge_task,
    concurrency: int,
) -> list[dict[str, Any]]:
    """Score a fixed candidate pool on source-dev without rule feedback."""

    scores: list[dict[str, Any]] = []
    for rule_index, rule_text in enumerate(candidate_rule_texts):
        predictions = await run_ordered_bounded(
            tasks,
            lambda task: judge_task(rule_text=rule_text, task=task, phase="source_dev"),
            concurrency=concurrency,
        )
        rows = [
            {"prediction": prediction, "gold_label": task.query_label}
            for task, prediction in zip(tasks, predictions, strict=True)
        ]
        metrics = evaluate_predictions(rows)
        scores.append(
            {
                "rule_index": rule_index,
                "rule_text": rule_text,
                "metrics": metrics,
            }
        )
    return scores


def select_dev_rules(scores: list[dict[str, Any]], count: int) -> list[str]:
    if count < 1 or count % 2 == 0:
        raise ValueError("Rule selection count must be a positive odd number")
    ranked = sorted(
        scores,
        key=lambda item: (
            float(item["metrics"]["classification_metrics"]["macro_f1"]),
            float(item["metrics"]["classification_metrics"]["accuracy"]),
            -int(item["rule_index"]),
        ),
        reverse=True,
    )
    selected = [str(item["rule_text"]) for item in ranked[:count]]
    if len(selected) != count:
        raise ValueError(f"Source-dev rule pool contains only {len(selected)} rules; needs {count}")
    return selected


def build_dry_run_manifest(
    cases: list[dict[str, Any]],
    target_domains: list[str],
    args: argparse.Namespace,
    dataset_manifest: dict[str, Any],
) -> dict[str, Any]:
    folds = []
    for target_domain in target_domains:
        source_train, source_dev, source_split = split_source_cases(
            cases,
            target_domain=target_domain,
            train_fraction=args.source_train_fraction,
            random_state=args.random_state,
        )
        train_config = build_rule_config(
            args,
            task_count=args.source_train_tasks,
            random_state=args.random_state,
        )
        dev_config = build_rule_config(
            args,
            task_count=args.source_dev_tasks,
            random_state=args.random_state + 1,
        )
        train_tasks = build_cross_domain_validation_tasks(
            source_train,
            target_domain=target_domain,
            config=train_config,
        )
        dev_tasks = build_cross_domain_validation_tasks(
            source_dev,
            target_domain=target_domain,
            config=dev_config,
        )
        target_cases = select_target_cases(
            [case for case in cases if case_domain(case) == target_domain],
            cases_per_label=args.target_cases_per_label,
            random_state=args.random_state,
        )
        target_manifest = build_target_sampling_manifest(
            target_domain=target_domain,
            target_cases=target_cases,
            random_state=args.random_state,
            cases_per_label=args.target_cases_per_label,
        )
        case_id_disjoint = _split_case_ids_are_disjoint(source_split, target_manifest)
        if not case_id_disjoint:
            raise RuntimeError(f"HateCoT dry-run fold {target_domain} has overlapping split case IDs")
        folds.append({
            "target_domain": target_domain,
            "source_domains": sorted({case_domain(case) for case in source_train + source_dev}),
            "source_train_case_count": len(source_train),
            "source_dev_case_count": len(source_dev),
            "source_train_task_count": len(train_tasks),
            "source_dev_task_count": len(dev_tasks),
            "target_case_count": len(target_cases),
            "target_label_counts": dict(Counter(case_label(case) for case in target_cases)),
            "source_split": source_split,
            "target_manifest": target_manifest,
            "case_id_disjoint": case_id_disjoint,
        })
    return {
        "schema": "maro-hatecot-harm-dry-run-v2",
        "paper_boundary": PAPER_BOUNDARY,
        "effective_protocol": effective_protocol(args),
        "dataset_manifest": dataset_manifest,
        "folds": folds,
        "policy_context_arms": resolve_policy_modes(args.policy_context_mode),
        "external_calls": False,
    }


def target_task(case: Mapping[str, Any], target_domain: str) -> HarmTargetJudgeTask:
    """Build a target prompt contract that intentionally has no gold label."""

    return HarmTargetJudgeTask(
        task_id=f"target:{target_domain}:{case.get('case_id')}",
        query_case_id=str(case.get("case_id") or ""),
        query_text=str(case.get("text") or ""),
        query_domain=case_domain(case),
        target_domain=target_domain,
    )


def build_judge_prompt(
    *,
    rule_text: str,
    task: JudgeTask,
    analysis: str,
    policy_context_mode: str = "off",
) -> str:
    demonstrations = "\n".join(
        "DEMO {}: domain={}; label={}; text={}".format(
            index,
            item.domain,
            label_to_number(item.label),
            item.text[:1000],
        )
        for index, item in enumerate(task.demonstrations, start=1)
    )
    analysis_heading = (
        "POST-HARM ANALYSIS AND LOCAL POLICY CONTEXT"
        if policy_context_mode == "local_advisory"
        else "POST-HARM ANALYSIS"
    )
    return (
        f"DECISION RULE:\n{rule_text}\n\n"
        "LABEL SPACE: 0=non_harmful, 1=offensive, 2=hate.\n"
        "The demonstrations are source-domain validation examples, not facts about the query.\n\n"
        f"DEMONSTRATIONS FROM OTHER DOMAINS:\n{demonstrations}\n\n"
        f"QUERY DOMAIN: {task.query_domain}\nQUERY TEXT:\n{task.query_text[:4000]}\n\n"
        f"{analysis_heading}:\n{analysis[:12000]}\n\n"
        "Apply the rule to this query."
    )


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
    audit_records: list[dict[str, Any]],
    policy_context_mode: str = "off",
) -> str:
    """Require an explicit three-way output; never invent a fallback label."""

    prompt = build_judge_prompt(
        rule_text=rule_text,
        task=task,
        analysis=analysis,
        policy_context_mode=policy_context_mode,
    )
    rule_hash = hashlib.sha256(rule_text.encode("utf-8")).hexdigest()
    total_attempts = format_retries + 1
    for attempt in range(1, total_attempts + 1):
        record: dict[str, Any] = {
            "phase": phase,
            "task_id": task.task_id,
            "rule_hash": rule_hash,
            "rule_text": rule_text,
            "attempt": attempt,
            "input_bundle": {
                "task_id": task.task_id,
                "phase": phase,
                "gold_label_included": False,
            },
        }
        try:
            response = await provider(
                agent_name="HarmfulnessJudgeAgent",
                system_prompt=(
                    "You are the final MARO-compatible interpersonal-harm Judge. Use the supplied rule, source-domain "
                    "demonstrations, and post-harm analysis. The policy references are advisory and cannot substitute for "
                    "observed text. Do not use external facts or issue enforcement. End with exactly one final line: "
                    "JUDGMENT: 0, JUDGMENT: 1, or JUDGMENT: 2."
                ),
                user_prompt=prompt,
                input_bundle=record["input_bundle"],
                model=model,
            )
        except Exception as exc:
            append_judge_audit(record | {"status": "provider_error", "error_class": type(exc).__name__}, audit_path, audit_records)
            continue
        response_text = str(response or "").strip()
        label = parse_harm_judgment(response_text)
        if label is None:
            append_judge_audit(record | {"status": "invalid_format", "response_text": response_text}, audit_path, audit_records)
            continue
        append_judge_audit(
            record | {"status": "completed", "response_text": response_text, "parsed_label": label},
            audit_path,
            audit_records,
        )
        return label
    raise JudgeExecutionError(f"Judge did not produce a strict label for {task.task_id}")


def parse_harm_judgment(text: str) -> str | None:
    """Accept only the explicit final 0/1/2 decision required by this protocol."""

    matches = re.findall(r"(?:JUDGMENT|LABEL|ANSWER)\s*[:：]\s*([012])\b", str(text or ""), flags=re.IGNORECASE)
    return number_to_label(matches[-1]) if matches else None


def label_to_number(label: str) -> int:
    return list(HATECOT_EVALUATION_LABELS).index(label)


def number_to_label(value: str) -> str | None:
    try:
        return HATECOT_EVALUATION_LABELS[int(value)]
    except (ValueError, IndexError):
        return None


def majority_vote(votes: list[str]) -> str:
    if not votes or len(votes) % 2 == 0:
        raise ValueError("MARO harm voting requires a non-empty odd number of rule votes")
    if any(vote not in HATECOT_EVALUATION_LABELS for vote in votes):
        raise ValueError("MARO harm voting requires only declared harm labels")
    counts = Counter(votes)
    best_count = max(counts.values())
    winners = [label for label in HATECOT_EVALUATION_LABELS if counts[label] == best_count]
    if len(winners) == 1:
        return winners[0]
    # MARO's odd-vote no-tie guarantee is binary-only. For this explicit
    # three-way adaptation, returned rules are ranked by validation accuracy;
    # the first rule is the auditable deterministic tie-break.
    if votes[0] not in winners:
        raise RuntimeError("Best returned rule is missing from the tied vote set")
    return votes[0]


def extract_rule_text(response: str) -> str:
    lines = [line.strip() for line in str(response or "").splitlines() if line.strip()]
    marked = [line.split(":", 1)[1].strip() for line in lines if line.upper().startswith("RULE:")]
    return marked[-1] if marked else " ".join(lines)


def summarize_policy_capsules(
    cases: list[Mapping[str, Any]],
    cache: Mapping[str, Mapping[str, Any]],
    *,
    policy_context_mode: str,
) -> dict[str, Any]:
    """Report capsule quality without treating it as a classification metric."""

    records = [cache[str(case.get("case_id") or "")] for case in cases]
    capsules = [record.get("rationale_capsule") or {} for record in records]
    policies = [record.get("policy_selection") or {} for record in records]
    return {
        "target_analysis_count": len(records),
        "quality_gated_capsule_count": sum(bool(item.get("capsule_quality_gate")) for item in capsules),
        "input_span_available_count": sum(bool(item.get("rationale_span_available")) for item in capsules),
        "policy_clause_match_count": sum(bool(item.get("policy_clause_match")) for item in capsules),
        "policy_reference_bundle_count": sum(len(item.get("bundles") or []) for item in policies),
        "policy_context_mode": policy_context_mode,
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


def optimization_to_json(result) -> dict[str, Any]:
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


def summarize_arms(folds: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    arms: dict[str, Any] = {}
    for mode, mode_folds in folds.items():
        metrics = [fold["metrics"]["classification_metrics"] for fold in mode_folds.values()]
        arms[mode] = {
            "fold_count": len(mode_folds),
            "mean_accuracy": round(sum(float(item["accuracy"]) for item in metrics) / len(metrics), 6) if metrics else None,
            "mean_macro_f1": round(sum(float(item["macro_f1"]) for item in metrics) / len(metrics), 6) if metrics else None,
        }
    return {
        "arms": arms,
        "claim_boundary": "HateCoT MARO-compatible interpersonal-harm adaptation; not an official MARO misinformation reproduction and not a Student distillation result.",
    }


def build_comparison(folds: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Compare policy arms using the same target split and candidate rules."""

    comparison: dict[str, Any] = {"arms": {}, "metric": "target_macro_f1"}
    for mode, mode_folds in folds.items():
        comparison["arms"][mode] = {
            domain: {
                "accuracy": fold["metrics"]["classification_metrics"]["accuracy"],
                "macro_f1": fold["metrics"]["classification_metrics"]["macro_f1"],
            }
            for domain, fold in mode_folds.items()
        }
    if "off" in folds and "local_advisory" in folds:
        comparison["delta_local_advisory_minus_off"] = {
            domain: round(
                float(folds["local_advisory"][domain]["metrics"]["classification_metrics"]["macro_f1"])
                - float(folds["off"][domain]["metrics"]["classification_metrics"]["macro_f1"]),
                6,
            )
            for domain in folds["off"]
            if domain in folds["local_advisory"]
        }
    comparison["interpretation_boundary"] = (
        "local_advisory is a local governance-context ablation, not evidence of general PolicyRAG domain adaptation"
    )
    return comparison


def effective_protocol(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "task": "interpersonal_harm",
        "label_space": {"0": "non_harmful", "1": "offensive", "2": "hate"},
        "label_mapping_version": HATECOT_LABEL_MAPPING_VERSION,
        "source_train_tasks": args.source_train_tasks,
        "source_dev_tasks": args.source_dev_tasks,
        "source_train_fraction": args.source_train_fraction,
        "samples_per_source_domain": args.samples_per_source_domain,
        "max_iterations": args.max_iterations,
        "max_attempts": args.max_attempts,
        "returned_rule_count": args.returned_rule_count,
        "target_cases_per_label": args.target_cases_per_label,
        "reflection_enabled": not args.disable_reflection,
        "analysis_case_retries": args.analysis_case_retries,
        "judge_format_retries": args.judge_format_retries,
        "llm_concurrency": args.llm_concurrency,
        "policy_context_mode": args.policy_context_mode,
        "external_fact_retrieval": False,
        "policy_reference_mode": "local_advisory_governance_reference_library_ablation_only",
        "gold_labels_used_only_for": ["source_train_rule_scoring", "source_dev_rule_selection", "held_out_final_metrics", "fixed_target_sampling"],
        "dataset_explanations_used_by_teacher": False,
    }


def select_domains(available_domains: list[str], requested_domains: list[str]) -> list[str]:
    requested = [str(item).strip().lower() for item in requested_domains if str(item).strip()]
    if not requested:
        return available_domains
    unknown = sorted(set(requested) - set(available_domains))
    if unknown:
        raise ValueError(
            "Requested target domains must independently cover all three labels; invalid: " + ", ".join(unknown)
        )
    return requested


def resolve_policy_modes(value: str) -> list[str]:
    normalized = str(value or "off").strip().lower()
    if normalized == "both":
        return ["off", "local_advisory"]
    if normalized in {"off", "local_advisory"}:
        return [normalized]
    raise ValueError("policy-context-mode must be off, local_advisory, or both")


def _split_case_ids_are_disjoint(source_split: Mapping[str, Any], target_manifest: Mapping[str, Any]) -> bool:
    train_ids = set(str(item) for item in source_split.get("source_train_case_ids") or [])
    dev_ids = set(str(item) for item in source_split.get("source_dev_case_ids") or [])
    target_ids = {str(item.get("case_id") or "") for item in target_manifest.get("cases") or []}
    return not (train_ids & dev_ids or train_ids & target_ids or dev_ids & target_ids)


def load_analysis_cache(
    path: Path,
    *,
    seed_path: str = "",
    include_current_cache: bool = False,
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    paths = [Path(seed_path)] if seed_path else []
    if include_current_cache:
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


def build_protocol_hash(
    *,
    args: argparse.Namespace,
    split_manifest: Mapping[str, Any],
    policy_context_mode: str,
) -> str:
    """Hash the exact fold protocol used to authorize a resume."""

    payload = {
        "harm_protocol": MARO_HARM_PROTOCOL_VERSION,
        "label_mapping_version": HATECOT_LABEL_MAPPING_VERSION,
        "effective_protocol": {
            **effective_protocol(args),
            "policy_context_mode": policy_context_mode,
        },
        "source_split_manifest_sha256": split_manifest["source"]["split_manifest_sha256"],
        "target_sample_manifest_sha256": split_manifest["target"]["sample_manifest_sha256"],
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def load_resumable_fold_report(
    path: Path,
    *,
    split_manifest: Mapping[str, Any],
    args: argparse.Namespace,
    policy_context_mode: str,
) -> dict[str, Any] | None:
    """Load a fold only when its stored protocol hash matches this run."""

    if not args.resume or not path.is_file():
        return None
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot resume from invalid fold report: {path}") from exc
    expected_hash = build_protocol_hash(
        args=args,
        split_manifest=split_manifest,
        policy_context_mode=policy_context_mode,
    )
    if report.get("protocol_hash") != expected_hash:
        raise RuntimeError(
            f"Refusing stale MARO HateCoT fold report {path}; protocol hash does not match."
        )
    if report.get("policy_context_mode") != policy_context_mode:
        raise RuntimeError(f"Refusing fold report with the wrong policy mode: {path}")
    return report


def case_fingerprint(case: Mapping[str, Any]) -> str:
    payload = {
        "case_id": case.get("case_id"),
        "text": case.get("text"),
        "domain": case_domain(case),
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def append_judge_audit(record: Mapping[str, Any], path: Path, records: list[dict[str, Any]]) -> None:
    append_jsonl(path, record)
    records.append(dict(record))


def append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def reject_existing_experiment_state(output_dir: Path) -> None:
    """Require an explicit resume before appending to a prior live run."""

    stale_paths = [
        output_dir / "report.json",
        output_dir / "report.partial.json",
        output_dir / "protocol_manifest.json",
    ]
    cache_dir = output_dir / "analysis_cache"
    if cache_dir.is_dir():
        stale_paths.extend(cache_dir.glob("*.jsonl"))
    fold_dir = output_dir / "folds"
    if fold_dir.is_dir():
        stale_paths.extend(fold_dir.glob("**/report.json"))
    existing = [path for path in stale_paths if path.exists()]
    if existing:
        raise SystemExit(
            "Output directory already contains experiment state. Use --resume "
            "only when the protocol hash is unchanged: "
            + str(existing[0])
        )


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
    return normalized or "domain-" + hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hatecot-csv", default=str(DEFAULT_HATECOT_CSV))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--target-domains", nargs="*", default=[])
    parser.add_argument("--validation-tasks", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--source-train-tasks", type=int, default=120)
    parser.add_argument("--source-dev-tasks", type=int, default=120)
    parser.add_argument("--source-train-fraction", type=float, default=0.8)
    parser.add_argument("--samples-per-source-domain", type=int, default=200)
    parser.add_argument("--max-iterations", type=int, default=10)
    parser.add_argument("--max-attempts", type=int, default=5)
    parser.add_argument("--returned-rule-count", type=int, default=3)
    parser.add_argument("--target-cases-per-label", type=int, default=100)
    parser.add_argument(
        "--policy-context-mode",
        choices=("off", "local_advisory", "both"),
        default="off",
    )
    parser.add_argument(
        "--seed-analysis-cache",
        default="",
        help="Optional completed harm-analysis cache used read-only before the current output cache.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse only fold reports and analysis caches with an exact protocol hash.",
    )
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--disable-reflection", action="store_true")
    parser.add_argument("--analysis-case-retries", type=int, default=1)
    parser.add_argument("--judge-format-retries", type=int, default=1)
    parser.add_argument("--llm-concurrency", type=int, default=8)
    parser.add_argument("--initial-rule", default=DEFAULT_INITIAL_RULE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.validation_tasks is not None:
        if args.validation_tasks < len(HATECOT_EVALUATION_LABELS):
            raise SystemExit("validation-tasks must cover every three-way label at least once")
        args.source_train_tasks = args.validation_tasks
        args.source_dev_tasks = args.validation_tasks
    if args.source_train_tasks < len(HATECOT_EVALUATION_LABELS):
        raise SystemExit("source-train-tasks must cover every three-way label at least once")
    if args.source_dev_tasks < len(HATECOT_EVALUATION_LABELS):
        raise SystemExit("source-dev-tasks must cover every three-way label at least once")
    if args.source_train_tasks % len(HATECOT_EVALUATION_LABELS):
        raise SystemExit("source-train-tasks must be divisible by the three-way label count")
    if args.source_dev_tasks % len(HATECOT_EVALUATION_LABELS):
        raise SystemExit("source-dev-tasks must be divisible by the three-way label count")
    if not 0.0 < args.source_train_fraction < 1.0:
        raise SystemExit("source-train-fraction must be between 0 and 1")
    if args.samples_per_source_domain < 3:
        raise SystemExit("samples-per-source-domain must be >= 3")
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
