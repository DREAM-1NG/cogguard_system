"""Benchmark Review agent runtime scalability with deterministic local latency."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.review.agent_review import run_manual_agent_review  # noqa: E402


EXPERT_AGENTS = [
    "PostHarmAgent",
    "MultimodalConsistencyAgent",
    "ClaimEvidenceAgent",
    "PropagationTreeAgent",
]


class FixedLatencyProvider:
    """Provider double that makes orchestration latency comparable between runs."""

    def __init__(self, delay_seconds: float) -> None:
        self.delay_seconds = max(0.0, float(delay_seconds))
        self.calls: list[str] = []

    async def __call__(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        user_prompt: str,
        input_bundle: dict[str, Any],
        model: str,
    ) -> str:
        self.calls.append(agent_name)
        await asyncio.sleep(self.delay_seconds)
        return f"benchmark completed: {agent_name}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="")
    parser.add_argument("--provider-delay-ms", type=float, default=10.0)
    args = parser.parse_args(argv)

    result = asyncio.run(run_benchmark(provider_delay_seconds=args.provider_delay_ms / 1000))
    encoded = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(encoded, encoding="utf-8")
    print(encoded)
    return 0


async def run_benchmark(*, provider_delay_seconds: float = 0.01) -> dict[str, Any]:
    """Run fixed cases that exercise selection, expansion, and full complex paths."""
    provider = FixedLatencyProvider(provider_delay_seconds)
    rows = []
    for scenario in _scenarios():
        rows.append(await _run_scenario(scenario, provider))
    return {
        "schema_version": "review-agent-runtime-benchmark-v1",
        "provider": {
            "kind": "fixed_latency_fake",
            "configured_delay_ms": round(provider.delay_seconds * 1000, 3),
        },
        "cases": rows,
        "summary": _summarize(rows),
    }


async def _run_scenario(scenario: dict[str, Any], provider: FixedLatencyProvider) -> dict[str, Any]:
    started = perf_counter()
    result = await run_manual_agent_review(
        report=scenario["report"],
        agent_names=EXPERT_AGENTS,
        provider=provider,
        provider_name="fixed_latency_fake",
        model="benchmark-fixed-latency",
        runtime_mode=scenario["runtime_mode"],
        enable_active_retrieval=bool(scenario.get("enable_active_retrieval")),
        enable_light_debate=bool(scenario.get("enable_light_debate")),
        enable_full_debate=bool(scenario.get("enable_full_debate")),
        selected_post_ids=scenario["selected_post_ids"],
        selected_tree_ids=scenario.get("selected_tree_ids") or [],
    )
    critical_elapsed_ms = round((perf_counter() - started) * 1000, 3)
    summary = result["summary"]
    execution_plan = result["audit"]["execution_plan"]
    call_audit = result["audit"]["llm_call_audit"]
    judge_report = next(
        (item for item in result["agent_reports"] if item.get("report_role") == "judge_final"),
        {},
    )
    return {
        "scenario": scenario["name"],
        "runtime_mode": result["audit"]["effective_runtime_mode"],
        "requested_experts": len([agent for agent in result["audit"]["agent_names"] if agent in EXPERT_AGENTS]),
        "eligible_experts": summary["eligible_expert_agents"],
        "executed_experts": summary["executed_expert_agents"],
        "requested_expert_names": [agent for agent in result["audit"]["agent_names"] if agent in EXPERT_AGENTS],
        "eligible_expert_names": execution_plan["eligible_agents"],
        "executed_expert_names": execution_plan["expert_agents"],
        "planned_llm_calls": summary["planned_llm_call_count"],
        "actual_llm_calls": summary["actual_llm_call_count"],
        "critical_elapsed_ms": critical_elapsed_ms,
        "provider_duration_sum_ms": round(sum(float(item.get("provider_duration_ms") or 0) for item in call_audit), 3),
        "system_prompt_chars": sum(int(item.get("system_prompt_chars") or 0) for item in call_audit),
        "user_prompt_chars": sum(int(item.get("user_prompt_chars") or 0) for item in call_audit),
        "input_bundle_chars": sum(int(item.get("input_bundle_chars") or 0) for item in call_audit),
        "skip_reasons": execution_plan["skipped_agents"],
        "judge_completed": judge_report.get("status") == "completed",
    }


def _scenarios() -> list[dict[str, Any]]:
    simple = _base_report("simple")
    claim = _base_report("claim")
    claim["post_semantics"]["posts"][0]["claims"] = [{"claim_id": "claim-1", "text": "A claim requires verification."}]
    claim["review_harmfulness"] = {"review_queue": {"retrieval_tasks": [{"claim_id": "claim-1", "query": "authoritative verification"}]}}

    multimodal = _base_report("multimodal")
    multimodal_post = multimodal["post_semantics"]["posts"][0]
    multimodal_post["media_urls"] = ["https://example.invalid/conflict.jpg"]
    multimodal_post["post_view_detection"] = {"conflict": {"score": 0.8}, "review_reason": ["media context conflict"]}

    propagation = _base_report("propagation")
    propagation["review_harmfulness"] = {
        "propagation_context": {"has_thread_context": True, "tree_metrics": {"node_count": 3, "edge_count": 2}}
    }

    full = _base_report("full")
    full_post = full["post_semantics"]["posts"][0]
    full_post["claims"] = [{"claim_id": "claim-full", "text": "A contested claim."}]
    full_post["media_urls"] = ["https://example.invalid/full.jpg"]
    full_post["post_view_detection"] = {"conflict": {"score": 0.9}, "review_reason": ["media context conflict"]}
    full["review_harmfulness"] = {
        "review_queue": {"retrieval_tasks": [{"claim_id": "claim-full", "query": "authoritative evidence"}]},
        "propagation_context": {"has_thread_context": True, "tree_metrics": {"node_count": 3, "edge_count": 2}},
    }

    return [
        _scenario("single_text_simple", simple, "simple"),
        _scenario("claim_complex", claim, "complex"),
        _scenario("multimodal_conflict", multimodal, "complex", enable_light_debate=True),
        _scenario("propagation", propagation, "complex"),
        _scenario("full_feature_complex", full, "complex", enable_active_retrieval=True, enable_light_debate=True),
    ]


def _scenario(name: str, report: dict[str, Any], runtime_mode: str, **options: Any) -> dict[str, Any]:
    return {"name": name, "report": report, "runtime_mode": runtime_mode, "selected_post_ids": [report["post_semantics"]["posts"][0]["post_id"]], **options}


def _base_report(name: str) -> dict[str, Any]:
    return {
        "report_id": f"benchmark-{name}",
        "event_id": f"event-{name}",
        "platform": "weibo",
        "post_semantics": {"posts": [{"post_id": f"post-{name}", "content": "Benchmark review text."}]},
    }


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "case_count": len(rows),
        "total_actual_llm_calls": sum(row["actual_llm_calls"] for row in rows),
        "total_provider_duration_sum_ms": round(sum(row["provider_duration_sum_ms"] for row in rows), 3),
        "all_judges_completed": all(row["judge_completed"] for row in rows),
    }


if __name__ == "__main__":
    raise SystemExit(main())
