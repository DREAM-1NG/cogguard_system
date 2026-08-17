from __future__ import annotations

import asyncio
import json

from app.core.review import maro_harm_protocol
from app.core.review.maro_harm_protocol import (
    HARM_ANALYSIS_BEGIN,
    HARM_ANALYSIS_END,
    HARM_REFLECTION_BEGIN,
    HARM_REFLECTION_END,
    MARO_HARM_POST_AGENT,
    MARO_HARM_REFLECTION_AGENT,
    has_complete_harm_analysis,
    parse_harm_analysis,
    run_maro_harm_multiagent_analysis,
)


def _analysis_footer(*, span: str = "you people are disgusting") -> str:
    payload = {
        "summary": "The post directly targets a group with degrading language.",
        "observed_spans": [span],
        "target_scope": "identity_group",
        "harm_cues": ["group-directed degradation"],
        "counter_context": [],
    }
    return f"Analysis\n{HARM_ANALYSIS_BEGIN}{json.dumps(payload)}{HARM_ANALYSIS_END}"


def test_harm_protocol_uses_only_post_and_advisory_policy_references():
    received: list[dict] = []

    async def provider(**kwargs: object) -> str:
        bundle = dict(kwargs["input_bundle"])
        received.append(bundle)
        agent = str(kwargs["agent_name"])
        if agent == MARO_HARM_REFLECTION_AGENT:
            return f"Review\n{HARM_REFLECTION_BEGIN}{json.dumps({'questions': ['Is the target explicit?']})}{HARM_REFLECTION_END}"
        assert agent == MARO_HARM_POST_AGENT
        return _analysis_footer()

    result = asyncio.run(
        run_maro_harm_multiagent_analysis(
            case={
                "case_id": "case-1",
                "text": "you people are disgusting",
                "labels": {"interpersonal_harm": "hate"},
                "explanation": "This must never reach the Agent.",
            },
            provider=provider,
            model="fake-model",
        )
    )

    assert result["summary"]["requested_agents"] == 3
    assert result["summary"]["completed"] == 3
    assert result["audit"] == {
        "gold_label_sent_to_agent": False,
        "dataset_explanation_sent_to_agent": False,
        "external_fact_retrieval_used": False,
        "policy_is_advisory_not_label_source": True,
        "policy_context_mode": "local_advisory",
    }
    assert all("labels" not in bundle and "explanation" not in bundle for bundle in received)
    assert all("post_text" in bundle for bundle in received)
    capsule = result["rationale_capsule"]
    assert capsule["capsule_quality_gate"] is True
    assert capsule["input_spans"] == ("you people are disgusting",)
    assert capsule["policy_refs"]


def test_policy_off_harm_protocol_excludes_policy_context_and_gate_requirement():
    received: list[dict] = []

    async def provider(**kwargs: object) -> str:
        bundle = dict(kwargs["input_bundle"])
        received.append(bundle)
        agent = str(kwargs["agent_name"])
        if agent == MARO_HARM_REFLECTION_AGENT:
            return f"Review\n{HARM_REFLECTION_BEGIN}{json.dumps({'questions': []})}{HARM_REFLECTION_END}"
        return _analysis_footer()

    result = asyncio.run(
        run_maro_harm_multiagent_analysis(
            case={"case_id": "case-off", "text": "you people are disgusting"},
            provider=provider,
            model="fake-model",
            include_policy_context=False,
        )
    )

    assert result["audit"]["policy_context_mode"] == "off"
    assert result["policy_selection"]["context_mode"] == "off"
    assert result["policy_selection"]["bundles"] == []
    assert result["rationale_capsule"]["policy_refs"] == ()
    assert result["rationale_capsule"]["capsule_quality_gate"] is True
    assert all(bundle["policy_context_mode"] == "off" for bundle in received)


def test_harm_capsule_rejects_hallucinated_input_spans():
    async def provider(**kwargs: object) -> str:
        agent = str(kwargs["agent_name"])
        if agent == MARO_HARM_REFLECTION_AGENT:
            return f"{HARM_REFLECTION_BEGIN}{json.dumps({'questions': []})}{HARM_REFLECTION_END}"
        return _analysis_footer(span="not present in the post")

    result = asyncio.run(
        run_maro_harm_multiagent_analysis(
            case={"case_id": "case-2", "text": "A neutral statement."},
            provider=provider,
            model="fake-model",
        )
    )

    capsule = result["rationale_capsule"]
    assert capsule["input_spans"] == ()
    # Policy matches, but the sidecar cannot claim an input-grounded rationale.
    assert capsule["capsule_quality_gate"] is False
    assert result["rationale_capsule_blockers"] == ["missing_input_span"]


def test_refinement_repeats_the_structured_contract_and_footer_only_uses_summary():
    prompt = maro_harm_protocol._post_harm_refinement_system_prompt()
    assert HARM_ANALYSIS_BEGIN in prompt
    assert HARM_ANALYSIS_END in prompt

    footer_only = _analysis_footer().split("\n", 1)[1]
    text, sidecar, error = parse_harm_analysis(
        footer_only,
        post_text="you people are disgusting",
    )
    assert error is None
    assert text == sidecar["summary"]


def test_harm_analysis_cache_rejects_unparseable_role_sidecars():
    record = {
        "analysis_summary": {"requested_agents": 1, "completed": 1},
        "agent_reports": [
            {
                "agent_name": MARO_HARM_POST_AGENT,
                "status": "completed",
                "structured_sidecar": {"parse_error": "missing_structured_footer"},
            }
        ],
    }
    assert has_complete_harm_analysis(record) is False
