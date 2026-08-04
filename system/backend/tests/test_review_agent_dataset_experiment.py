from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_review_agent_dataset_experiment.py"


def load_runner_module():
    spec = importlib.util.spec_from_file_location("review_agent_dataset_experiment", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def offline_case(*, case_id: str = "case-1", harmfulness: str = "harmful") -> dict[str, object]:
    return {
        "case_id": case_id,
        "dataset": "fixture",
        "split": "test",
        "source_id": f"source-{case_id}",
        "text": "A factual fixture post.",
        "labels": {"harmfulness": harmfulness},
        "metadata": {"platform": "fixture-platform"},
    }


def write_cases(case_dir: Path, cases: list[dict[str, object]]) -> None:
    case_dir.mkdir()
    case_path = case_dir / "fixture.jsonl"
    case_path.write_text(
        "".join(json.dumps(case) + "\n" for case in cases),
        encoding="utf-8",
    )


def test_minimal_report_excludes_gold_harmfulness_from_detector_risk_fields():
    runner = load_runner_module()

    harmful_report = runner.build_minimal_report(offline_case(harmfulness="harmful"), prefer_embeddings=False)
    benign_report = runner.build_minimal_report(offline_case(harmfulness="not_harmful"), prefer_embeddings=False)

    assert "labels" not in json.dumps(harmful_report, sort_keys=True)
    assert harmful_report["scores"] == benign_report["scores"]
    assert (
        harmful_report["review_harmfulness"]["global_summary"]
        == benign_report["review_harmfulness"]["global_summary"]
    )


def test_cli_loads_explicit_policy_and_error_memory_paths_for_agent_runtime(monkeypatch, tmp_path):
    runner = load_runner_module()
    case_dir = tmp_path / "cases"
    output_dir = tmp_path / "output"
    write_cases(case_dir, [offline_case()])
    policy_path = tmp_path / "active-policy.json"
    error_memory_path = tmp_path / "error-memory.json"
    policy = {"policy_id": "offline-policy", "policy": {"strict": True}}
    error_memory = {"recent_failures": [{"kind": "timeout"}]}
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    error_memory_path.write_text(json.dumps(error_memory), encoding="utf-8")
    captured: dict[str, object] = {}

    class FakeProvider:
        def __init__(self, config):
            self.config = config

    async def fake_review(**kwargs):
        captured.update(kwargs)
        return {"summary": {}, "agent_reports": []}

    monkeypatch.setattr(runner, "OpenAICompatibleAgentProvider", FakeProvider)
    monkeypatch.setattr(runner, "run_manual_agent_review", fake_review)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "runner",
            "--case-dir", str(case_dir),
            "--output-dir", str(output_dir),
            "--datasets", "fixture",
            "--api-key", "offline-test-key",
            "--active-policy-path", str(policy_path),
            "--error-memory-path", str(error_memory_path),
        ],
    )

    assert runner.main() == 0
    assert captured["policy"] == policy
    assert captured["error_memory_summary"] == error_memory


@pytest.mark.asyncio
async def test_dataset_runner_bounds_concurrency_for_runtime_options_and_preserves_input_order(monkeypatch, tmp_path):
    runner = load_runner_module()
    case_dir = tmp_path / "cases"
    output_dir = tmp_path / "output"
    cases = [offline_case(case_id=f"case-{index}") for index in range(3)]
    write_cases(case_dir, cases)
    observed: list[tuple[str, str, bool]] = []
    active = 0
    peak_active = 0

    async def fake_evaluate_case(*, case, runtime_mode, enable_deep_judge, **kwargs):
        nonlocal active, peak_active
        active += 1
        peak_active = max(peak_active, active)
        observed.append((case["case_id"], runtime_mode, enable_deep_judge))
        await asyncio.sleep(0.02 if case["case_id"] == "case-0" else 0)
        active -= 1
        return {
            "case_id": case["case_id"],
            "dataset": case["dataset"],
            "judge_status": "completed",
            "agent_summary": {},
            "teacher_silver": {},
        }

    monkeypatch.setattr(runner, "evaluate_case", fake_evaluate_case)

    result = await runner.evaluate_dataset(
        dataset="fixture",
        case_dir=case_dir,
        output_dir=output_dir,
        max_cases=0,
        prefer_embeddings=False,
        provider=object(),
        model="offline-model",
        agent_names=["HarmfulnessJudgeAgent"],
        include_media_base64=False,
        require_vision=False,
        enable_active_retrieval=False,
        enable_external_retrieval=False,
        enable_light_debate=False,
        enable_full_debate=False,
        enable_deep_judge=True,
        runtime_mode="complex",
        debate_max_rounds=1,
        retrieval_top_k=1,
        case_timeout_seconds=5,
        dataset_concurrency=2,
        flush_every_case=False,
        verbose_progress=False,
        active_retriever=None,
    )

    rows = [json.loads(line) for line in (output_dir / "agent_predictions.jsonl").read_text(encoding="utf-8").splitlines()]
    assert peak_active == 2
    assert observed == [("case-0", "complex", True), ("case-1", "complex", True), ("case-2", "complex", True)]
    assert [row["case_id"] for row in rows] == ["case-0", "case-1", "case-2"]
    assert result["case_count"] == 3


def test_experiment_report_records_latency_and_call_budget_configuration(monkeypatch, tmp_path):
    runner = load_runner_module()
    output_dir = tmp_path / "output"

    class FakeProvider:
        def __init__(self, config):
            self.config = config

    async def fake_evaluate_dataset(**kwargs):
        return {"dataset": kwargs["dataset"], "status": "skipped", "reason": "test"}

    monkeypatch.setattr(runner, "OpenAICompatibleAgentProvider", FakeProvider)
    monkeypatch.setattr(runner, "evaluate_dataset", fake_evaluate_dataset)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "runner",
            "--case-dir", str(tmp_path / "cases"),
            "--output-dir", str(output_dir),
            "--datasets", "fixture",
            "--api-key", "offline-test-key",
            "--timeout-seconds", "12.5",
            "--case-timeout-seconds", "34",
            "--dataset-concurrency", "3",
            "--max-agent-calls-per-case", "7",
        ],
    )

    assert runner.main() == 0
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert report["execution_budget"] == {
        "provider_timeout_seconds": 12.5,
        "case_timeout_seconds": 34.0,
        "dataset_concurrency": 3,
        "max_agent_calls_per_case": 7,
    }
