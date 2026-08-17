from __future__ import annotations

import asyncio

from app.core.review.maro_rule_optimization import (
    DecisionRule,
    MARO_HARM_3WAY_LABELS,
    MARORuleOptimizationConfig,
    build_cross_domain_validation_tasks,
    optimize_decision_rules,
)


def _case(domain: str, label: str, index: int) -> dict:
    return {
        "case_id": f"{domain}-{label}-{index}",
        "text": f"{domain} news {label} {index}",
        "labels": {"harmfulness": label},
        "metadata": {"category": domain},
    }


def _source_cases() -> list[dict]:
    return [
        _case(domain, label, index)
        for domain in ("finance", "health", "science", "sports", "technology")
        for label in ("harmful", "non_harmful")
        for index in range(4)
    ]


def test_cross_domain_tasks_keep_demo_domains_disjoint_from_each_query_domain():
    tasks = build_cross_domain_validation_tasks(
        _source_cases(),
        target_domain="politics",
        config=MARORuleOptimizationConfig(
            validation_task_count=6,
            max_samples_per_source_domain=4,
            random_state=42,
        ),
    )

    assert len(tasks) == 6
    assert {task.query_domain for task in tasks} == {"finance", "health", "science", "sports", "technology"}
    assert {task.query_label for task in tasks} == {"harmful", "non_harmful"}
    for task in tasks:
        assert task.query_domain != "politics"
        assert len(task.demonstrations) == 4
        assert {item.label for item in task.demonstrations} == {"harmful", "non_harmful"}
        assert all(item.domain not in {task.query_domain, "politics"} for item in task.demonstrations)


def test_rule_optimization_keeps_only_strict_validation_improvements():
    tasks = build_cross_domain_validation_tasks(
        _source_cases(),
        target_domain="politics",
        config=MARORuleOptimizationConfig(
            validation_task_count=6,
            max_samples_per_source_domain=4,
            max_iterations=4,
            max_attempts=1,
            returned_rule_count=3,
            random_state=42,
        ),
    )
    proposals = iter(["improved", "rejected"])

    async def propose_rule(*, trajectory: list[DecisionRule], **_: object) -> str:
        assert len(trajectory) <= 10
        return next(proposals)

    async def judge_task(*, rule_text: str, task, **_: object) -> str:
        if rule_text == "improved":
            return task.query_label
        return "harmful" if task.query_label == "non_harmful" else "non_harmful"

    result = asyncio.run(
        optimize_decision_rules(
            tasks=tasks,
            initial_rule="baseline",
            propose_rule=propose_rule,
            judge_task=judge_task,
            config=MARORuleOptimizationConfig(
                validation_task_count=6,
                max_samples_per_source_domain=4,
                max_iterations=4,
                max_attempts=1,
                returned_rule_count=3,
                random_state=42,
            ),
        )
    )

    assert result.best_rule.text == "improved"
    assert result.best_rule.accuracy == 1.0
    assert [item.text for item in result.accepted_rules] == ["baseline", "improved"]
    assert [item.text for item in result.returned_rules] == ["improved", "baseline", "rejected"]
    assert result.stop_reason == "max_consecutive_non_improvements"
    assert result.trajectory[-1].accepted is False


def test_three_way_adapter_keeps_target_domain_out_and_uses_one_demo_per_label():
    labels_by_domain = {
        "cad": ("non_harmful", "offensive", "hate"),
        "dynahate": ("non_harmful", "offensive", "hate"),
        "toraman": ("non_harmful", "offensive", "hate"),
        "gab": ("non_harmful", "hate"),
        "socialbias": ("non_harmful", "offensive"),
    }
    cases = [
        _case(domain, label, index)
        for domain, labels in labels_by_domain.items()
        for label in labels
        for index in range(3)
    ]

    tasks = build_cross_domain_validation_tasks(
        cases,
        target_domain="cad",
        config=MARORuleOptimizationConfig(
            validation_task_count=9,
            max_samples_per_source_domain=8,
            random_state=42,
            label_space=MARO_HARM_3WAY_LABELS,
            demonstration_label_plan=MARO_HARM_3WAY_LABELS,
        ),
    )

    assert len(tasks) == 9
    assert {task.query_label for task in tasks} == set(MARO_HARM_3WAY_LABELS)
    for task in tasks:
        assert task.query_domain != "cad"
        assert len(task.demonstrations) == 3
        assert tuple(item.label for item in task.demonstrations) == MARO_HARM_3WAY_LABELS
        assert len({item.domain for item in task.demonstrations}) == 3
        assert all(item.domain not in {task.query_domain, "cad"} for item in task.demonstrations)
