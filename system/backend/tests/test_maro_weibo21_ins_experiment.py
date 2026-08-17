from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_maro_weibo21_ins_experiment.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("maro_weibo21_ins_runner_test", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_maro_ins_runner_uses_maro_fallback_parser_and_complete_odd_vote():
    runner = _load_runner()

    assert runner.parse_binary_judgment("analysis\nJUDGMENT: 1") == "harmful"
    assert runner.parse_binary_judgment("结论：0") == "non_harmful"
    assert runner.parse_binary_judgment("analysis\nThe final result is 1") == "harmful"
    assert runner.parse_binary_judgment("analysis\n\nFake-News\n\ntrailing") == "harmful"
    assert runner.parse_binary_judgment("fake-news") == "harmful"
    assert runner.parse_binary_judgment("The report mentions both fake and real.") == "non_harmful"
    assert runner.majority_vote(["harmful", "non_harmful", "harmful"]) == "harmful"
    with pytest.raises(ValueError, match="binary"):
        runner.majority_vote(["harmful", None, "non_harmful"])


def test_maro_metrics_use_every_submitted_target_row_and_reject_invalid_predictions():
    runner = _load_runner()

    metrics = runner.evaluate_predictions([
        {"gold_label": "harmful", "prediction": "harmful"},
        {"gold_label": "non_harmful", "prediction": "harmful"},
    ])

    assert metrics["submitted_count"] == 2
    assert "decision_coverage" not in metrics
    assert "unavailable_count" not in metrics
    assert metrics["classification_metrics"]["accuracy"] == 0.5
    with pytest.raises(ValueError, match="non-binary prediction"):
        runner.evaluate_predictions([
            {"gold_label": "harmful", "prediction": "harmful"},
            {"gold_label": "non_harmful", "prediction": None},
        ])


def test_target_judge_task_and_prompt_do_not_contain_target_gold_label():
    runner = _load_runner()
    task = runner.target_task(
        {
            "case_id": "target-1",
            "text": "A target-domain claim.",
            "labels": {"harmfulness": "harmful"},
            "metadata": {"category": "technology"},
        },
        "technology",
    )

    prompt = runner.build_judge_prompt(rule_text="Use the reports.", task=task, analysis="analysis")

    assert not hasattr(task, "query_label")
    assert "harmful" not in prompt
    assert "label=" not in prompt


def test_judge_retry_exhaustion_fails_the_experiment_and_keeps_attempt_audit(tmp_path):
    runner = _load_runner()
    task = runner.target_task(
        {
            "case_id": "target-1",
            "text": "A target-domain claim.",
            "metadata": {"category": "technology"},
        },
        "technology",
    )

    async def empty_provider(**_: object) -> str:
        return ""

    audit_path = tmp_path / "judge_audit.jsonl"
    with pytest.raises(runner.JudgeExecutionError, match="after 2 attempts"):
        asyncio.run(
            runner.run_judge_with_retries(
                provider=empty_provider,
                model="test-model",
                rule_text="Use the reports.",
                task=task,
                analysis="analysis",
                phase="target",
                format_retries=1,
                audit_path=audit_path,
            )
        )

    records = runner.load_jsonl(audit_path)
    assert len(records) == 2
    assert {record["status"] for record in records} == {"empty_response"}
    assert all("gold_label" not in record["input_bundle"] for record in records)


def test_judge_provider_failure_audit_includes_non_secret_transport_telemetry(tmp_path):
    runner = _load_runner()
    task = runner.target_task(
        {
            "case_id": "target-1",
            "text": "A target-domain claim.",
            "metadata": {"category": "technology"},
        },
        "technology",
    )

    class FailedProvider:
        last_call_telemetry = {
            "http_status": 503,
            "error_class": "HTTPStatusError",
            "attempt_count": 3,
            "retry_count": 2,
            "rate_limit_retry_count": 0,
        }

        async def __call__(self, **_: object) -> str:
            raise RuntimeError("provider unavailable")

    audit_path = tmp_path / "judge_audit.jsonl"
    with pytest.raises(runner.JudgeExecutionError):
        asyncio.run(
            runner.run_judge_with_retries(
                provider=FailedProvider(),
                model="test-model",
                rule_text="Use the reports.",
                task=task,
                analysis="analysis",
                phase="target",
                format_retries=0,
                audit_path=audit_path,
            )
        )

    record = runner.load_jsonl(audit_path)[0]
    assert record["status"] == "provider_error"
    assert record["provider_http_status"] == 503
    assert record["provider_error_class"] == "HTTPStatusError"
    assert record["provider_attempt_count"] == 3
    assert record["provider_retry_count"] == 2
    assert "provider unavailable" not in str(record)


def test_seeded_analysis_cache_prefers_current_run_records(tmp_path):
    runner = _load_runner()
    seed_path = tmp_path / "seed.jsonl"
    current_path = tmp_path / "current.jsonl"
    runner.append_jsonl(seed_path, {"case_id": "seed-only", "analysis": "seed"})
    runner.append_jsonl(seed_path, {"case_id": "shared", "analysis": "seed"})
    runner.append_jsonl(current_path, {"case_id": "shared", "analysis": "current"})

    cache, provenance = runner.load_experiment_analysis_cache(
        output_cache_path=current_path,
        seed_cache_path=seed_path,
    )

    assert cache["seed-only"]["analysis"] == "seed"
    assert cache["shared"]["analysis"] == "current"
    assert provenance["seed_unique_record_count"] == 2
    assert provenance["current_unique_record_count"] == 1


def test_runner_builds_environment_retriever_without_importing_dataset_training_script(monkeypatch):
    runner = _load_runner()
    monkeypatch.setattr(runner.settings, "REVIEW_RETRIEVAL_API_KEY", "test-key")
    monkeypatch.setattr(runner.settings, "REVIEW_RETRIEVAL_BASE_URL", "https://example.invalid")
    monkeypatch.setattr(runner.settings, "REVIEW_RETRIEVAL_SEARCH_PATH", "/search")
    monkeypatch.setattr(runner.settings, "REVIEW_RETRIEVAL_PROVIDER_NAME", "test-provider")
    monkeypatch.setattr(runner.settings, "REVIEW_RETRIEVAL_ADAPTER", "exa")

    retriever = runner.build_environment_retriever()

    assert callable(retriever)


def test_safe_name_keeps_distinct_non_ascii_domains_in_separate_audit_directories():
    runner = _load_runner()

    assert runner.safe_name("科技") != runner.safe_name("政治")
    assert runner.safe_name("科技").startswith("domain-")


def test_calibration_case_selection_is_deterministic_and_does_not_require_labels():
    runner = _load_runner()
    cases = [
        {
            "case_id": f"case-{index}",
            "text": f"claim {index}",
            "metadata": {"category": "politics" if index % 2 else "technology"},
            "labels": _LabelsMustNotBeRead(),
        }
        for index in range(8)
    ]

    selected_once = runner.select_calibration_cases(
        cases,
        target_domains=["politics", "technology"],
        max_cases=3,
        random_state=42,
    )
    selected_twice = runner.select_calibration_cases(
        cases,
        target_domains=["politics", "technology"],
        max_cases=3,
        random_state=42,
    )

    assert [row["case_id"] for row in selected_once] == [row["case_id"] for row in selected_twice]
    assert len(selected_once) == 3


def test_target_sampling_is_exact_stratified_and_deterministic():
    runner = _load_runner()
    cases = [
        {
            "case_id": f"harmful-{index}",
            "text": f"fake claim {index}",
            "labels": {"harmfulness": "harmful"},
            "metadata": {"category": "politics"},
        }
        for index in range(30)
    ] + [
        {
            "case_id": f"non-harmful-{index}",
            "text": f"real claim {index}",
            "labels": {"harmfulness": "non_harmful"},
            "metadata": {"category": "politics"},
        }
        for index in range(30)
    ]

    selected_once = runner.select_target_cases(
        cases,
        max_cases=50,
        random_state=42,
        cases_per_label=25,
    )
    selected_twice = runner.select_target_cases(
        cases,
        max_cases=50,
        random_state=42,
        cases_per_label=25,
    )

    assert [case["case_id"] for case in selected_once] == [case["case_id"] for case in selected_twice]
    assert len(selected_once) == 50
    assert sum(runner.case_label(case) == "harmful" for case in selected_once) == 25
    assert sum(runner.case_label(case) == "non_harmful" for case in selected_once) == 25


def test_target_sampling_deduplicates_identical_case_ids_before_quota_selection():
    runner = _load_runner()
    cases = [
        {
            "case_id": "harmful-duplicate",
            "text": "same fake claim",
            "labels": {"harmfulness": "harmful"},
            "metadata": {"category": "politics"},
        },
        {
            "case_id": "harmful-duplicate",
            "text": "same fake claim",
            "labels": {"harmfulness": "harmful"},
            "metadata": {"category": "politics"},
        },
        *[
            {
                "case_id": f"harmful-{index}",
                "text": f"fake claim {index}",
                "labels": {"harmfulness": "harmful"},
                "metadata": {"category": "politics"},
            }
            for index in range(24)
        ],
        *[
            {
                "case_id": f"non-harmful-{index}",
                "text": f"real claim {index}",
                "labels": {"harmfulness": "non_harmful"},
                "metadata": {"category": "politics"},
            }
            for index in range(25)
        ],
    ]

    selected = runner.select_target_cases(
        cases,
        max_cases=50,
        random_state=42,
        cases_per_label=25,
    )

    assert len(selected) == 50
    assert len({case["case_id"] for case in selected}) == 50


def test_incomplete_analysis_is_not_reusable_and_is_rejected():
    runner = _load_runner()
    incomplete = {
        "case_id": "case-1",
        "analysis_summary": {"requested_agents": 9, "completed": 8},
        "agent_reports": [{"status": "completed"}] * 8 + [{"status": "failed"}],
    }

    assert runner.has_complete_analysis(incomplete) is False
    with pytest.raises(RuntimeError, match="analysis is incomplete"):
        runner.require_complete_analysis(incomplete)


def test_case_instance_normalization_removes_exact_duplicates_but_keeps_distinct_views():
    runner = _load_runner()
    base = {
        "case_id": "source-post-1",
        "text": "original claim",
        "maro_inputs": {"original_news": "original claim", "comments": ["first view"]},
        "labels": {"harmfulness": "harmful"},
        "metadata": {"category": "politics"},
    }
    variant = {
        **base,
        "maro_inputs": {"original_news": "original claim", "comments": ["second view"]},
    }

    normalized = runner.normalize_case_instances([base, dict(base), variant])

    assert len(normalized) == 2
    assert len({case["case_id"] for case in normalized}) == 2
    assert {runner.source_case_id(case) for case in normalized} == {"source-post-1"}


def test_complete_legacy_cache_is_reused_by_input_fingerprint_for_an_instance_id():
    runner = _load_runner()
    raw_case = {
        "case_id": "source-post-1",
        "text": "original claim",
        "maro_inputs": {"original_news": "original claim"},
        "labels": {"harmfulness": "harmful"},
        "metadata": {"category": "politics"},
    }
    instance = runner.normalize_case_instances([raw_case])[0]
    legacy = {
        "case_id": "source-post-1",
        "case_fingerprint": runner.case_fingerprint(raw_case),
        "analysis_summary": {"requested_agents": 9, "completed": 9},
        "agent_reports": [{"status": "completed"}] * 9,
        "analysis": "cached analysis",
    }

    resolved = runner.find_complete_cached_analysis(instance, {"source-post-1": legacy})

    assert resolved == legacy


def test_analysis_cache_loader_preserves_source_id_variants_by_fingerprint(tmp_path):
    runner = _load_runner()
    cache_path = tmp_path / "analysis_cache.jsonl"
    runner.append_jsonl(cache_path, {"case_id": "source-post-1", "case_fingerprint": "variant-a"})
    runner.append_jsonl(cache_path, {"case_id": "source-post-1", "case_fingerprint": "variant-b"})

    cache = runner.load_analysis_cache(cache_path)

    assert len(cache) == 2
    assert set(cache) == {"source-post-1::variant-a", "source-post-1::variant-b"}


def test_target_sampling_rejects_an_unavailable_label_quota():
    runner = _load_runner()
    cases = [
        {
            "case_id": f"harmful-{index}",
            "text": f"fake claim {index}",
            "labels": {"harmfulness": "harmful"},
            "metadata": {"category": "politics"},
        }
        for index in range(25)
    ] + [
        {
            "case_id": f"non-harmful-{index}",
            "text": f"real claim {index}",
            "labels": {"harmfulness": "non_harmful"},
            "metadata": {"category": "politics"},
        }
        for index in range(24)
    ]

    with pytest.raises(ValueError, match="does not contain enough cases"):
        runner.select_target_cases(
            cases,
            max_cases=50,
            random_state=42,
            cases_per_label=25,
        )


def test_target_sampling_manifest_marks_gold_labels_as_evaluation_only():
    runner = _load_runner()
    cases = [
        {
            "case_id": "harmful-1",
            "text": "fake claim",
            "labels": {"harmfulness": "harmful"},
            "metadata": {"category": "politics"},
        },
        {
            "case_id": "non-harmful-1",
            "text": "real claim",
            "labels": {"harmfulness": "non_harmful"},
            "metadata": {"category": "politics"},
        },
    ]

    manifest = runner.build_target_sampling_manifest(
        target_domain="politics",
        target_cases=cases,
        random_state=42,
        cases_per_label=1,
    )

    assert manifest["protocol"] == "weibo21-stratified-target-sample-v1"
    assert manifest["label_counts"] == {"harmful": 1, "non_harmful": 1}
    assert manifest["evaluation_only"] is True
    assert manifest["target_labels_sent_to_agent"] is False
    assert len(manifest["sample_manifest_sha256"]) == 64


def test_analysis_cache_writes_completed_records_once_in_input_order(tmp_path, monkeypatch):
    runner = _load_runner()
    cases = [
        {"case_id": "case-a", "text": "a", "metadata": {"category": "politics"}},
        {"case_id": "case-b", "text": "b", "metadata": {"category": "politics"}},
    ]

    async def fake_analysis(*, case, **_):
        await asyncio.sleep(0.01 if case["case_id"] == "case-a" else 0)
        return {
            "agent_reports": [{"status": "completed"}] * 9,
            "evidence_bundle": {},
            "active_retrieval": {"audit": {}},
            "audit": {},
            "summary": {"requested_agents": 9, "completed": 9},
            "schema_version": "test",
        }

    monkeypatch.setattr(runner, "run_maro_paper_multi_dimensional_analysis", fake_analysis)
    cache = {}
    cache_path = tmp_path / "analysis_cache.jsonl"
    args = type("Args", (), {"retrieval_top_k": 3, "max_agent_calls_per_case": 9, "llm_concurrency": 2})()

    asyncio.run(
        runner.ensure_analysis_reports(
            cases=cases,
            provider=object(),
            model="test-model",
            retriever=object(),
            args=args,
            cache=cache,
            cache_path=cache_path,
        )
    )

    assert list(cache) == ["case-a", "case-b"]
    assert [row["case_id"] for row in runner.load_jsonl(cache_path)] == ["case-a", "case-b"]


class _LabelsMustNotBeRead(dict):
    def get(self, *_: object, **__: object) -> object:
        raise AssertionError("calibration selection must not read gold labels")
