from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest



def _load_runner():
    path = Path(__file__).resolve().parents[1] / "scripts" / "run_maro_hatecot_harm_experiment.py"
    spec = importlib.util.spec_from_file_location("maro_hatecot_harm_runner", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_harm_judge_requires_explicit_three_way_output_and_votes_odd_rules():
    runner = _load_runner()

    assert runner.parse_harm_judgment("Reasoning\nJUDGMENT: 2") == "hate"
    assert runner.parse_harm_judgment("This seems offensive but has no footer") is None
    assert runner.majority_vote(["offensive", "hate", "offensive"]) == "offensive"
    assert runner.majority_vote(["hate", "offensive", "non_harmful"]) == "hate"


def test_target_task_and_prompt_do_not_carry_gold_label():
    runner = _load_runner()
    case = {
        "case_id": "hatecot::cad::1",
        "text": "Example input.",
        "labels": {"interpersonal_harm": "hate"},
        "metadata": {"category": "cad"},
    }

    task = runner.target_task(case, "cad")
    assert not hasattr(task, "query_label")
    prompt = runner.build_judge_prompt(
        rule_text="Use the post text.",
        task=task,
        analysis="[POST_HARM_REFINEMENT] observable words only",
    )
    assert "Example input." in prompt
    assert "gold_label" not in prompt
    assert "interpersonal_harm" not in prompt


def _case(domain: str, label: str, index: int) -> dict:
    return {
        "case_id": f"hatecot::{domain}::{label}::{index}",
        "source_id": f"{domain}-{label}-{index}",
        "text": f"{domain} {label} example {index}",
        "labels": {"interpersonal_harm": label},
        "metadata": {"category": domain},
    }


def test_source_split_is_deterministic_and_target_sampling_is_exact():
    runner = _load_runner()
    cases = [
        _case(domain, label, index)
        for domain in ("cad", "dynahate", "toraman", "gab")
        for label in runner.HATECOT_EVALUATION_LABELS
        for index in range(10)
    ]

    train_a, dev_a, manifest_a = runner.split_source_cases(
        cases,
        target_domain="cad",
        train_fraction=0.8,
        random_state=42,
    )
    train_b, dev_b, manifest_b = runner.split_source_cases(
        cases,
        target_domain="cad",
        train_fraction=0.8,
        random_state=42,
    )
    target = runner.select_target_cases(
        [case for case in cases if runner.case_domain(case) == "cad"],
        cases_per_label=3,
        random_state=42,
    )
    target_manifest = runner.build_target_sampling_manifest(
        target_domain="cad",
        target_cases=target,
        random_state=42,
        cases_per_label=3,
    )

    assert [case["case_id"] for case in train_a] == [case["case_id"] for case in train_b]
    assert [case["case_id"] for case in dev_a] == [case["case_id"] for case in dev_b]
    assert manifest_a["split_manifest_sha256"] == manifest_b["split_manifest_sha256"]
    assert not ({case["case_id"] for case in train_a} & {case["case_id"] for case in dev_a})
    assert not ({case["case_id"] for case in train_a + dev_a} & {case["case_id"] for case in target})
    assert target_manifest["label_counts"] == {label: 3 for label in runner.HATECOT_EVALUATION_LABELS}


def test_policy_mode_is_visible_in_judge_prompt_without_exposing_target_gold():
    runner = _load_runner()
    task = runner.target_task(_case("cad", "hate", 1), "cad")

    policy_off = runner.build_judge_prompt(
        rule_text="classify observable harm",
        task=task,
        analysis="observed span",
        policy_context_mode="off",
    )
    policy_on = runner.build_judge_prompt(
        rule_text="classify observable harm",
        task=task,
        analysis="observed span",
        policy_context_mode="local_advisory",
    )

    assert "LOCAL POLICY CONTEXT" not in policy_off
    assert "LOCAL POLICY CONTEXT" in policy_on
    assert "gold_label" not in policy_off
    assert "gold_label" not in policy_on


def test_candidate_pool_contains_only_source_train_accepted_rules():
    runner = _load_runner()
    result = type(
        "Optimization",
        (),
        {
            "accepted_rules": (
                runner.DecisionRule("initial", 0.25, 0, True),
                runner.DecisionRule("improved", 0.75, 1, True),
            ),
            "trajectory": (
                runner.DecisionRule("initial", 0.25, 0, True),
                runner.DecisionRule("improved", 0.75, 1, True),
                runner.DecisionRule("rejected", 0.50, 2, False),
            ),
        },
    )()

    assert runner.candidate_rules_from_optimization(result) == ["initial", "improved"]


def test_resume_rejects_a_fold_report_from_a_different_protocol(tmp_path, monkeypatch):
    runner = _load_runner()
    monkeypatch.setattr(sys, "argv", ["runner", "--resume"])
    args = runner.parse_args()
    cases = [
        _case(domain, label, index)
        for domain in ("cad", "dynahate", "toraman", "gab")
        for label in runner.HATECOT_EVALUATION_LABELS
        for index in range(4)
    ]
    train, dev, source_manifest = runner.split_source_cases(
        cases,
        target_domain="cad",
        random_state=42,
    )
    target = runner.select_target_cases(
        [case for case in cases if runner.case_domain(case) == "cad"],
        cases_per_label=1,
        random_state=42,
    )
    split_manifest = {
        "source": source_manifest,
        "target": runner.build_target_sampling_manifest(
            target_domain="cad",
            target_cases=target,
            random_state=42,
            cases_per_label=1,
        ),
    }
    report_path = tmp_path / "report.json"
    report_path.write_text(
        '{"protocol_hash":"stale","policy_context_mode":"off"}',
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="protocol hash"):
        runner.load_resumable_fold_report(
            report_path,
            split_manifest=split_manifest,
            args=args,
            policy_context_mode="off",
        )
