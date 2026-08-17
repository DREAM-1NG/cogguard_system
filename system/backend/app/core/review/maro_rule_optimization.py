"""Offline MARO decision-rule optimization protocol primitives.

This module implements the paper's cross-domain validation task construction
and strict-improvement rule search.  It deliberately has no dependency on the
production Review runtime, a specific LLM provider, or a dataset adapter.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from random import Random
from typing import Any, Awaitable, Callable, Mapping

from app.core.review.experiment_concurrency import run_ordered_bounded


MARO_BINARY_LABELS = ("harmful", "non_harmful")
MARO_HARM_3WAY_LABELS = ("non_harmful", "offensive", "hate")
_BINARY_DEMONSTRATION_LABEL_PLAN = ("harmful", "harmful", "non_harmful", "non_harmful")

__all__ = [
    "CrossDomainDemonstration",
    "CrossDomainValidationTask",
    "DecisionRule",
    "MARO_BINARY_LABELS",
    "MARO_HARM_3WAY_LABELS",
    "MARORuleOptimizationConfig",
    "RuleOptimizationResult",
    "build_cross_domain_validation_tasks",
    "optimize_decision_rules",
]


@dataclass(frozen=True)
class MARORuleOptimizationConfig:
    """Paper-aligned defaults for one leave-one-domain-out MARO fold."""

    validation_task_count: int = 500
    max_samples_per_source_domain: int = 100
    max_iterations: int = 500
    max_attempts: int = 10
    returned_rule_count: int = 3
    random_state: int = 42
    evaluation_concurrency: int = 1
    # MARO's released misinformation protocol is binary and uses two examples
    # per class. Other task adapters must explicitly declare their label space
    # and demonstration plan rather than silently collapsing labels.
    label_space: tuple[str, ...] = MARO_BINARY_LABELS
    demonstration_label_plan: tuple[str, ...] = _BINARY_DEMONSTRATION_LABEL_PLAN
    label_key: str = "harmfulness"


@dataclass(frozen=True)
class CrossDomainDemonstration:
    case_id: str
    text: str
    label: str
    domain: str


@dataclass(frozen=True)
class CrossDomainValidationTask:
    task_id: str
    query_case_id: str
    query_text: str
    query_label: str
    query_domain: str
    target_domain: str
    demonstrations: tuple[CrossDomainDemonstration, ...]


@dataclass(frozen=True)
class DecisionRule:
    text: str
    accuracy: float
    iteration: int
    accepted: bool


@dataclass(frozen=True)
class RuleOptimizationResult:
    initial_rule: DecisionRule
    best_rule: DecisionRule
    accepted_rules: tuple[DecisionRule, ...]
    returned_rules: tuple[DecisionRule, ...]
    trajectory: tuple[DecisionRule, ...]
    evaluated_task_count: int
    iterations_completed: int
    consecutive_non_improvements: int
    stop_reason: str


RuleProposer = Callable[..., Awaitable[str]]
TaskJudge = Callable[..., Awaitable[str]]


def build_cross_domain_validation_tasks(
    cases: list[Mapping[str, Any]],
    *,
    target_domain: str,
    config: MARORuleOptimizationConfig,
) -> list[CrossDomainValidationTask]:
    """Create label-balanced ICL tasks without using the held-out domain.

    With the default configuration, each task follows MARO's released
    ``get_sample_example`` behavior: one source-domain query and four
    demonstrations from four *other* source domains, two labelled fake and two
    labelled real. A non-binary task is an explicit MARO-compatible adaptation:
    it declares both its label space and demonstration-label plan. It is not a
    claim of the original binary misinformation protocol.
    """

    _validate_config(config)
    normalized_target = _normalize_domain(target_domain)
    grouped: dict[str, dict[str, list[_CaseView]]] = defaultdict(lambda: defaultdict(list))
    for position, case in enumerate(cases):
        view = _case_view(
            case,
            position,
            label_space=config.label_space,
            label_key=config.label_key,
        )
        if view is None or view.domain == normalized_target:
            continue
        grouped[view.domain][view.label].append(view)

    random = Random(config.random_state)
    binary_protocol = (
        config.label_space == MARO_BINARY_LABELS
        and config.demonstration_label_plan == _BINARY_DEMONSTRATION_LABEL_PLAN
    )
    source_domains = sorted(
        domain
        for domain, labels in grouped.items()
        if all(labels.get(label) for label in config.label_space)
    ) if binary_protocol else sorted(
        domain
        for domain, labels in grouped.items()
        if any(labels.get(label) for label in config.label_space)
    )
    minimum_domains = len(config.demonstration_label_plan) + 1
    if len(source_domains) < minimum_domains:
        raise ValueError(
            "MARO cross-domain validation needs at least "
            f"{minimum_domains} eligible source domains for the configured demonstration plan."
        )

    capped: dict[str, dict[str, list[_CaseView]]] = {}
    for domain in source_domains:
        all_rows = [row for label in config.label_space for row in grouped[domain][label]]
        random.shuffle(all_rows)
        selected: list[_CaseView] = []
        for label in config.label_space:
            if grouped[domain][label]:
                selected.append(random.choice(grouped[domain][label]))
        selected_ids = {row.case_id for row in selected}
        selected.extend(
            row
            for row in all_rows
            if row.case_id not in selected_ids
        )
        selected = selected[: config.max_samples_per_source_domain]
        capped[domain] = {
            label: [row for row in selected if row.label == label]
            for label in config.label_space
        }

    tasks: list[CrossDomainValidationTask] = []
    query_offsets: dict[tuple[str, str], int] = defaultdict(int)
    for task_index in range(config.validation_task_count):
        if binary_protocol:
            # Preserve MARO's released binary task rotation exactly.
            query_domain = source_domains[task_index % len(source_domains)]
            query_label = MARO_BINARY_LABELS[
                (task_index // len(source_domains)) % len(MARO_BINARY_LABELS)
            ]
        else:
            query_label = config.label_space[task_index % len(config.label_space)]
            eligible_query_domains = [
                domain for domain in source_domains if capped[domain][query_label]
            ]
            if not eligible_query_domains:
                raise ValueError(f"No source-domain queries are available for label {query_label!r}.")
            query_domain = eligible_query_domains[
                (task_index // len(config.label_space)) % len(eligible_query_domains)
            ]
        query_pool = capped[query_domain][query_label]
        if not query_pool:
            raise ValueError(f"No {query_label} queries available for source domain {query_domain!r}.")
        offset_key = (query_domain, query_label)
        query = query_pool[query_offsets[offset_key] % len(query_pool)]
        query_offsets[offset_key] += 1

        selected_demo_domains = _select_demo_domains(
            capped,
            query_domain=query_domain,
            label_plan=config.demonstration_label_plan,
            random=random,
        )
        demonstrations = tuple(
            _sample_demonstration(capped, domain, label, random)
            for domain, label in zip(
                selected_demo_domains,
                config.demonstration_label_plan,
                strict=True,
            )
        )
        tasks.append(
            CrossDomainValidationTask(
                task_id=f"{normalized_target}:{task_index:04d}",
                query_case_id=query.case_id,
                query_text=query.text,
                query_label=query.label,
                query_domain=query.domain,
                target_domain=normalized_target,
                demonstrations=demonstrations,
            )
        )
    return tasks


async def optimize_decision_rules(
    *,
    tasks: list[CrossDomainValidationTask],
    initial_rule: str,
    propose_rule: RuleProposer,
    judge_task: TaskJudge,
    config: MARORuleOptimizationConfig,
) -> RuleOptimizationResult:
    """Execute Algorithm 1 using strict validation-only improvement retention."""

    _validate_config(config)
    if not tasks:
        raise ValueError("MARO rule optimization requires at least one validation task.")
    initial_text = _normalize_rule(initial_rule)
    if not initial_text:
        raise ValueError("The initial MARO decision rule cannot be empty.")

    initial_accuracy = await _evaluate_rule(
        initial_text,
        tasks,
        judge_task,
        concurrency=config.evaluation_concurrency,
    )
    initial = DecisionRule(text=initial_text, accuracy=initial_accuracy, iteration=0, accepted=True)
    accepted_rules = [initial]
    trajectory = [initial]
    best_rule = initial
    consecutive_non_improvements = 0
    iterations_completed = 0

    while (
        iterations_completed < config.max_iterations
        and consecutive_non_improvements < config.max_attempts
    ):
        iterations_completed += 1
        proposed = _normalize_rule(
            await propose_rule(
                trajectory=_top_trajectory(accepted_rules),
                best_rule=best_rule,
                iteration=iterations_completed,
            )
        )
        if not proposed or any(item.text == proposed for item in accepted_rules):
            candidate = DecisionRule(text=proposed, accuracy=0.0, iteration=iterations_completed, accepted=False)
            trajectory.append(candidate)
            consecutive_non_improvements += 1
            continue

        accuracy = await _evaluate_rule(
            proposed,
            tasks,
            judge_task,
            concurrency=config.evaluation_concurrency,
        )
        accepted = accuracy > best_rule.accuracy
        candidate = DecisionRule(
            text=proposed,
            accuracy=accuracy,
            iteration=iterations_completed,
            accepted=accepted,
        )
        trajectory.append(candidate)
        if accepted:
            accepted_rules.append(candidate)
            best_rule = candidate
            consecutive_non_improvements = 0
        else:
            consecutive_non_improvements += 1

    # The released INS code retains a ranked rule pool even when a candidate
    # does not replace the current best rule. Strict improvement still governs
    # ``best_rule``; inference votes over the top-K scored candidate trajectory.
    returned_rules = tuple(
        _top_trajectory([rule for rule in trajectory if rule.text])[: config.returned_rule_count]
    )
    stop_reason = (
        "max_consecutive_non_improvements"
        if consecutive_non_improvements >= config.max_attempts
        else "max_iterations"
    )
    return RuleOptimizationResult(
        initial_rule=initial,
        best_rule=best_rule,
        accepted_rules=tuple(accepted_rules),
        returned_rules=returned_rules,
        trajectory=tuple(trajectory),
        evaluated_task_count=len(tasks),
        iterations_completed=iterations_completed,
        consecutive_non_improvements=consecutive_non_improvements,
        stop_reason=stop_reason,
    )


@dataclass(frozen=True)
class _CaseView:
    case_id: str
    text: str
    label: str
    domain: str


def _case_view(
    case: Mapping[str, Any],
    position: int,
    *,
    label_space: tuple[str, ...],
    label_key: str,
) -> _CaseView | None:
    text = str(case.get("text") or "").strip()
    labels = case.get("labels") if isinstance(case.get("labels"), Mapping) else {}
    label = str(labels.get(label_key) or "").strip().lower()
    metadata = case.get("metadata") if isinstance(case.get("metadata"), Mapping) else {}
    domain = _normalize_domain(metadata.get("category"))
    if not text or label not in label_space or not domain:
        return None
    return _CaseView(
        case_id=str(case.get("case_id") or f"case-{position}"),
        text=text,
        label=label,
        domain=domain,
    )


def _sample_demonstration(
    grouped: Mapping[str, Mapping[str, list[_CaseView]]],
    domain: str,
    label: str,
    random: Random,
) -> CrossDomainDemonstration:
    row = random.choice(grouped[domain][label])
    return CrossDomainDemonstration(
        case_id=row.case_id,
        text=row.text,
        label=row.label,
        domain=row.domain,
    )


def _select_demo_domains(
    grouped: Mapping[str, Mapping[str, list[_CaseView]]],
    *,
    query_domain: str,
    label_plan: tuple[str, ...],
    random: Random,
) -> tuple[str, ...]:
    """Choose distinct supporting domains for a declared label plan."""

    def solve(position: int, selected: tuple[str, ...]) -> tuple[str, ...] | None:
        if position >= len(label_plan):
            return selected
        label = label_plan[position]
        candidates = [
            domain
            for domain, labels in grouped.items()
            if domain != query_domain and domain not in selected and labels.get(label)
        ]
        random.shuffle(candidates)
        for domain in candidates:
            solution = solve(position + 1, selected + (domain,))
            if solution is not None:
                return solution
        return None

    selected = solve(0, ())
    if selected is None:
        raise ValueError(
            "No distinct demonstration-domain assignment is available outside "
            f"query domain {query_domain!r} for labels {label_plan!r}."
        )
    return selected


async def _evaluate_rule(
    rule_text: str,
    tasks: list[CrossDomainValidationTask],
    judge_task: TaskJudge,
    *,
    concurrency: int,
) -> float:
    async def judge_one(task: CrossDomainValidationTask) -> str:
        return str(await judge_task(rule_text=rule_text, task=task)).strip().lower()

    predictions = await run_ordered_bounded(tasks, judge_one, concurrency=concurrency)
    correct = sum(prediction == task.query_label for prediction, task in zip(predictions, tasks, strict=True))
    return round(correct / len(tasks), 6)


def _top_trajectory(rules: list[DecisionRule]) -> list[DecisionRule]:
    return sorted(rules, key=lambda item: (-item.accuracy, item.iteration))[:10]


def _normalize_domain(value: Any) -> str:
    return str(value or "").strip().lower()


def _normalize_rule(value: Any) -> str:
    return " ".join(str(value or "").split())


def _validate_config(config: MARORuleOptimizationConfig) -> None:
    if config.validation_task_count < 1:
        raise ValueError("validation_task_count must be >= 1")
    if config.max_samples_per_source_domain < 1:
        raise ValueError("max_samples_per_source_domain must be >= 1")
    if config.max_iterations < 1:
        raise ValueError("max_iterations must be >= 1")
    if config.max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")
    if config.returned_rule_count < 1:
        raise ValueError("returned_rule_count must be >= 1")
    if config.evaluation_concurrency < 1:
        raise ValueError("evaluation_concurrency must be >= 1")
    labels = tuple(str(label).strip().lower() for label in config.label_space if str(label).strip())
    if len(labels) < 2 or len(set(labels)) != len(labels):
        raise ValueError("label_space must contain at least two distinct non-empty labels")
    if labels != config.label_space:
        raise ValueError("label_space labels must be normalized lowercase identifiers")
    if not config.demonstration_label_plan:
        raise ValueError("demonstration_label_plan must not be empty")
    if any(label not in config.label_space for label in config.demonstration_label_plan):
        raise ValueError("demonstration_label_plan contains a label outside label_space")
    if not str(config.label_key).strip():
        raise ValueError("label_key must not be empty")
