from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path


def _load_script_module(name: str):
    path = Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runtime_benchmark_covers_fixed_scenarios_and_emits_scalability_contract():
    benchmark = _load_script_module("benchmark_review_agent_runtime")

    result = asyncio.run(benchmark.run_benchmark(provider_delay_seconds=0.001))

    rows = result["cases"]
    assert [row["scenario"] for row in rows] == [
        "single_text_simple",
        "claim_complex",
        "multimodal_conflict",
        "propagation",
        "full_feature_complex",
    ]
    assert result["provider"]["kind"] == "fixed_latency_fake"
    assert result["summary"]["case_count"] == len(rows) == 5

    required_fields = {
        "requested_experts",
        "eligible_experts",
        "executed_experts",
        "planned_llm_calls",
        "actual_llm_calls",
        "critical_elapsed_ms",
        "provider_duration_sum_ms",
        "system_prompt_chars",
        "user_prompt_chars",
        "input_bundle_chars",
        "skip_reasons",
        "judge_completed",
    }
    assert all(required_fields <= row.keys() for row in rows)
    assert all(row["judge_completed"] is True for row in rows)
    assert all(row["actual_llm_calls"] <= row["planned_llm_calls"] for row in rows)
    assert all(row["provider_duration_sum_ms"] > 0 for row in rows)

    simple = rows[0]
    assert simple["requested_experts"] == 4
    assert simple["eligible_experts"] == 1
    assert simple["executed_experts"] == 1
    assert simple["executed_expert_names"] == ["PostHarmAgent"]
    assert simple["planned_llm_calls"] == 2
    assert simple["actual_llm_calls"] == 2
    assert {item["reason"] for item in simple["skip_reasons"]} == {
        "missing_claim_context",
        "missing_usable_media_or_cross_view_conflict",
        "missing_propagation_tree_or_post_post_edges",
    }

    claim_complex = rows[1]
    assert claim_complex["eligible_experts"] == 2
    assert claim_complex["executed_experts"] == 2
    assert {item["reason"] for item in claim_complex["skip_reasons"]} == {
        "missing_usable_media_or_cross_view_conflict",
        "missing_propagation_tree_or_post_post_edges",
    }

    full_feature = rows[-1]
    assert full_feature["requested_experts"] == 4
    assert full_feature["eligible_experts"] == 4
    assert full_feature["executed_experts"] == 4
    assert full_feature["skip_reasons"] == []


def test_runtime_benchmark_cli_writes_machine_readable_report(tmp_path, capsys):
    benchmark = _load_script_module("benchmark_review_agent_runtime")
    output_path = tmp_path / "runtime-benchmark.json"

    exit_code = benchmark.main(["--output", str(output_path), "--provider-delay-ms", "1"])

    assert exit_code == 0
    assert output_path.exists()
    assert '"case_count": 5' in capsys.readouterr().out
