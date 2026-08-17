from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path

from app.core.review.agent_contracts import CLAIM_EVIDENCE_BEGIN, CLAIM_EVIDENCE_END, JUDGE_DECISION_BEGIN, JUDGE_DECISION_END
from app.core.review.maro_protocol import (
    MARO_COMMENT_AGENT,
    MARO_CONTENT_AGENT,
    MARO_FACT_AGENT,
    MARO_FACT_PLAN_BEGIN,
    MARO_FACT_PLAN_END,
    MARO_JUDGE_AGENT,
    MARO_QUESTION_AGENT,
    MARO_REFLECTION_AGENT,
    MARO_REFLECTION_PLAN_BEGIN,
    MARO_REFLECTION_PLAN_END,
    MARO_SUMMARIZER_AGENT,
    run_maro_paper_multi_dimensional_analysis,
    run_maro_paper_reference_review,
    run_maro_reference_review,
)


def _case(*, profile: str = "post_and_comments") -> dict:
    return {
        "case_id": "weibo21::fake::1",
        "dataset": "Weibo21",
        "split": "test",
        "source_id": "1",
        "text": "The city will close every school tomorrow.",
        "maro_inputs": {
            "input_profile": profile,
            "original_news": "The city will close every school tomorrow.",
            "comments": ["This was denied by the city office."] if profile == "post_and_comments" else [],
            "original_news_and_comment": (
                "[POST]\nThe city will close every school tomorrow.\n[COMMENTS]\n[COMMENT 1] This was denied by the city office."
                if profile == "post_and_comments"
                else "The city will close every school tomorrow."
            ),
        },
    }


def _fact_plan() -> str:
    payload = {
        "claim_assessment": "checkable",
        "claim": "The city will close every school tomorrow.",
        "assessment_reason": "It asserts a time-bounded government action.",
        "questions": ["Did the city announce a school closure for tomorrow?"],
    }
    return f"Questions\n{MARO_FACT_PLAN_BEGIN}{json.dumps(payload)}{MARO_FACT_PLAN_END}"


def _fact_footer() -> str:
    payload = {
        "claim_assessment": "checkable",
        "claim": "The city will close every school tomorrow.",
        "assessment_reason": "It asserts a time-bounded government action.",
        "relation": "contradicted",
        "source_ref_ids": ["city-1"],
        "quoted_spans": ["The city office states that schools remain open tomorrow."],
    }
    return f"Fact report\n{CLAIM_EVIDENCE_BEGIN}{json.dumps(payload)}{CLAIM_EVIDENCE_END}"


def _judge_footer(*, available: bool = True) -> str:
    payload = {
        "main_axes": {
            "attack_hate_offense": {"available": False, "label": "unavailable", "confidence": 0.0},
            "misinfo_claim_risk": {
                "available": available,
                "label": "harmful" if available else "unavailable",
                "confidence": 0.9 if available else 0.0,
            },
        },
        "stance": {"available": False, "label": "unlinked", "confidence": 0.0},
        "review_required": True,
        "review_reason": ["traceable contradiction"],
        "fine_labels": ["misinformation"],
    }
    return f"Judgment\n{JUDGE_DECISION_BEGIN}{json.dumps(payload)}{JUDGE_DECISION_END}"


def _load_offline_dataset_runner():
    path = Path(__file__).resolve().parents[1] / "scripts" / "run_review_agent_dataset_experiment.py"
    spec = importlib.util.spec_from_file_location("review_maro_protocol_runner", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_maro_protocol_preserves_official_role_order_and_comment_isolation():
    received: dict[str, dict] = {}

    async def provider(**kwargs: object) -> str:
        agent = str(kwargs["agent_name"])
        received[agent] = dict(kwargs["input_bundle"])
        if agent == MARO_QUESTION_AGENT:
            return _fact_plan()
        if agent == MARO_FACT_AGENT:
            return _fact_footer()
        if agent == MARO_JUDGE_AGENT:
            return _judge_footer()
        return f"{agent} report"

    async def retriever(*, query: str, context: dict, top_k: int) -> list[dict]:
        assert query == "Did the city announce a school closure for tomorrow?"
        assert context["claim"] == "The city will close every school tomorrow."
        assert top_k == 2
        return [
            {
                "doc_id": "city-1",
                "source": "city office",
                "url": "https://city.example/open",
                "text": "The city office states that schools remain open tomorrow.",
            }
        ]

    result = asyncio.run(
        run_maro_reference_review(
            case=_case(),
            provider=provider,
            model="fake-model",
            active_retriever=retriever,
            external_retrieval_enabled=True,
            retrieval_top_k=2,
            max_agent_calls_per_case=6,
        )
    )

    assert [item["agent_name"] for item in result["agent_reports"]] == [
        MARO_CONTENT_AGENT,
        MARO_COMMENT_AGENT,
        MARO_QUESTION_AGENT,
        MARO_SUMMARIZER_AGENT,
        MARO_FACT_AGENT,
        MARO_JUDGE_AGENT,
    ]
    assert received[MARO_CONTENT_AGENT] == {"original_news": _case()["text"]}
    assert "comments" not in received[MARO_CONTENT_AGENT]
    assert received[MARO_COMMENT_AGENT]["comments"] == ["This was denied by the city office."]
    assert "The city will close every school tomorrow." in received[MARO_COMMENT_AGENT]["original_news_and_comment"]
    assert result["evidence_bundle"]["relation"] == "contradicted"
    judge = result["agent_reports"][-1]
    assert judge["report_role"] == "judge_final"
    assert judge["structured_sidecar"]["teacher_prediction_valid"] is True


def test_maro_protocol_does_not_turn_missing_retrieval_into_evidence_insufficient():
    async def provider(**kwargs: object) -> str:
        agent = str(kwargs["agent_name"])
        if agent == MARO_QUESTION_AGENT:
            return _fact_plan()
        if agent == MARO_FACT_AGENT:
            payload = {
                "claim_assessment": "checkable",
                "claim": "The city will close every school tomorrow.",
                "assessment_reason": "time-bounded assertion",
                "relation": "not_applicable",
                "source_ref_ids": [],
                "quoted_spans": [],
            }
            return f"No traceable source\n{CLAIM_EVIDENCE_BEGIN}{json.dumps(payload)}{CLAIM_EVIDENCE_END}"
        if agent == MARO_JUDGE_AGENT:
            # The runtime must mask this unsupported Judge assertion rather
            # than trusting a prompt-following assumption.
            return _judge_footer(available=True)
        return "report"

    result = asyncio.run(
        run_maro_reference_review(
            case=_case(profile="post_only"),
            provider=provider,
            model="fake-model",
            active_retriever=None,
            external_retrieval_enabled=False,
            retrieval_top_k=1,
            max_agent_calls_per_case=6,
        )
    )

    assert result["evidence_bundle"]["retrieval_status"] == "provider_unavailable"
    assert result["evidence_bundle"]["relation"] == "not_applicable"
    assert "evidence_insufficient" not in json.dumps(result, ensure_ascii=False)
    assert result["agent_reports"][1]["input_scope"]["comments_available"] is False
    judge = result["agent_reports"][-1]["structured_sidecar"]
    assert judge["misinfo_prediction_masked"] is True
    assert judge["teacher_prediction"]["main_axes"]["misinfo_claim_risk"] == {
        "available": False,
        "label": "unavailable",
        "confidence": 0.0,
    }


def test_offline_dataset_runner_uses_maro_adapter_and_preserves_typed_judge_output():
    runner = _load_offline_dataset_runner()

    async def provider(**kwargs: object) -> str:
        agent = str(kwargs["agent_name"])
        if agent == MARO_QUESTION_AGENT:
            return _fact_plan()
        if agent == MARO_FACT_AGENT:
            return _fact_footer()
        if agent == MARO_JUDGE_AGENT:
            return _judge_footer()
        return "report"

    async def retriever(**_: object) -> list[dict]:
        return [
            {
                "doc_id": "city-1",
                "source": "city office",
                "url": "https://city.example/open",
                "text": "The city office states that schools remain open tomorrow.",
            }
        ]

    row = asyncio.run(
        runner.evaluate_case(
            case=_case(),
            provider=provider,
            model="fake-model",
            agent_names=[],
            prefer_embeddings=False,
            include_media_base64=False,
            require_vision=False,
            enable_active_retrieval=True,
            enable_external_retrieval=True,
            enable_light_debate=False,
            enable_full_debate=False,
            enable_deep_judge=False,
            debate_max_rounds=0,
            retrieval_top_k=1,
            max_agent_calls_per_case=6,
            active_retriever=retriever,
            maro_reference_protocol=True,
        )
    )

    assert row["judge_status"] == "completed"
    assert row["judge_sidecar"]["teacher_prediction_valid"] is True
    assert row["teacher_silver"]["main_axes"]["misinfo_claim_risk"]["label"] == "harmful"
    assert row["all_agent_reports"][-1]["maro_role"] == "Judgment Agent"


def test_paper_reference_protocol_reflects_and_revisits_each_analysis_dimension():
    received: list[tuple[str, dict]] = []

    async def provider(**kwargs: object) -> str:
        agent = str(kwargs["agent_name"])
        bundle = dict(kwargs["input_bundle"])
        received.append((agent, bundle))
        if agent == MARO_QUESTION_AGENT:
            return _fact_plan()
        if agent == MARO_REFLECTION_AGENT:
            payload = {
                "content_questions": ["Which attribution is missing?"],
                "comment_questions": ["Which comment claim is unverified?"],
                "fact_questions": ["Does the cited source address the date?"],
            }
            return f"Reflections {MARO_REFLECTION_PLAN_BEGIN}{json.dumps(payload)}{MARO_REFLECTION_PLAN_END}"
        if agent == MARO_FACT_AGENT:
            return _fact_footer()
        if agent == MARO_JUDGE_AGENT:
            return _judge_footer()
        return f"{agent} report"

    async def retriever(**_: object) -> list[dict]:
        return [
            {
                "doc_id": "city-1",
                "source": "city office",
                "url": "https://city.example/open",
                "text": "The city office states that schools remain open tomorrow.",
            }
        ]

    result = asyncio.run(
        run_maro_paper_reference_review(
            case=_case(),
            provider=provider,
            model="fake-model",
            active_retriever=retriever,
            external_retrieval_enabled=True,
            retrieval_top_k=1,
            max_agent_calls_per_case=10,
        )
    )

    assert [item["agent_name"] for item in result["agent_reports"]] == [
        MARO_CONTENT_AGENT,
        MARO_COMMENT_AGENT,
        MARO_QUESTION_AGENT,
        MARO_SUMMARIZER_AGENT,
        MARO_FACT_AGENT,
        MARO_REFLECTION_AGENT,
        MARO_CONTENT_AGENT,
        MARO_COMMENT_AGENT,
        MARO_FACT_AGENT,
        MARO_JUDGE_AGENT,
    ]
    refinement_inputs = [bundle for _, bundle in received if "reflection_questions" in bundle]
    assert len(refinement_inputs) == 3
    assert refinement_inputs[0]["reflection_questions"] == ["Which attribution is missing?"]
    assert refinement_inputs[1]["reflection_questions"] == ["Which comment claim is unverified?"]
    assert refinement_inputs[2]["reflection_questions"] == ["Does the cited source address the date?"]
    assert result["audit"]["protocol"] == "maro-weibo21-paper-adapter-v2"


def test_paper_analysis_stage_excludes_the_final_judge_before_ins_evaluation():
    called_agents: list[str] = []

    async def provider(**kwargs: object) -> str:
        agent = str(kwargs["agent_name"])
        called_agents.append(agent)
        if agent == MARO_QUESTION_AGENT:
            return _fact_plan()
        if agent == MARO_REFLECTION_AGENT:
            payload = {"content_questions": [], "comment_questions": [], "fact_questions": []}
            return f"{MARO_REFLECTION_PLAN_BEGIN}{json.dumps(payload)}{MARO_REFLECTION_PLAN_END}"
        if agent == MARO_FACT_AGENT:
            return _fact_footer()
        if agent == MARO_JUDGE_AGENT:
            raise AssertionError("The analysis stage must not run the INS Judge.")
        return "report"

    async def retriever(**_: object) -> list[dict]:
        return [
            {
                "doc_id": "city-1",
                "source": "city office",
                "url": "https://city.example/open",
                "text": "The city office states that schools remain open tomorrow.",
            }
        ]

    result = asyncio.run(
        run_maro_paper_multi_dimensional_analysis(
            case=_case(),
            provider=provider,
            model="fake-model",
            active_retriever=retriever,
            external_retrieval_enabled=True,
            retrieval_top_k=1,
            max_agent_calls_per_case=9,
        )
    )

    assert MARO_JUDGE_AGENT not in called_agents
    assert result["summary"]["planned_llm_call_count"] == 9
