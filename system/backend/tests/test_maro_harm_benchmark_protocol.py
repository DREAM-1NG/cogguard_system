from __future__ import annotations

from app.core.review.maro_harm_benchmark_protocol import (
    BenchmarkJudgeTask,
    benchmark_majority_vote,
    build_benchmark_judge_prompt,
    evaluate_benchmark_predictions,
    parse_benchmark_judgment,
)


def test_target_task_has_no_gold_label_and_prompt_declares_only_protocol_labels():
    task = BenchmarkJudgeTask(
        task_id="HateCheck::1",
        query_case_id="hatecheck::1",
        query_text="Targeted post text.",
        query_domain="hatecheck",
        target_benchmark="HateCheck",
    )
    prompt = build_benchmark_judge_prompt(
        label_space=("non_hateful", "hateful"),
        rule_text="Use the observable post only.",
        task=task,
        analysis="Observed target and context.",
    )

    assert "0=non_hateful, 1=hateful" in prompt
    assert "Targeted post text." in prompt
    assert "gold_label" not in prompt
    assert "benchmark_label" not in prompt


def test_judgment_parser_rejects_labels_outside_the_declared_target_space():
    assert parse_benchmark_judgment("Reasoning\nJUDGMENT: 1", ("non_hateful", "hateful")) == "hateful"
    assert parse_benchmark_judgment("Reasoning\nJUDGMENT: 2", ("non_hateful", "hateful")) is None
    assert parse_benchmark_judgment("No strict footer", ("normal", "offensive", "hate")) is None


def test_three_way_vote_tie_uses_the_best_returned_rule_deterministically():
    labels = ("normal", "offensive", "hate")

    assert benchmark_majority_vote(["hate", "offensive", "normal"], labels) == "hate"
    assert benchmark_majority_vote(["offensive", "offensive", "hate"], labels) == "offensive"


def test_metrics_use_the_declared_label_space_and_every_target_prediction():
    metrics = evaluate_benchmark_predictions(
        [
            {"gold_label": "normal", "prediction": "normal"},
            {"gold_label": "offensive", "prediction": "hate"},
            {"gold_label": "hate", "prediction": "hate"},
        ],
        label_space=("normal", "offensive", "hate"),
    )

    assert metrics["submitted_count"] == 3
    assert metrics["classification_metrics"]["accuracy"] == 0.666667
    assert metrics["confusion_matrix"]["label_order"] == ["normal", "offensive", "hate"]
