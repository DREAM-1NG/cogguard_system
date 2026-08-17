from __future__ import annotations

import pytest

from app.config import settings
from app.core.review.agent_contracts import build_agent_output_contract, build_agent_system_prompt
from app.core.review.deepseek_provider import (
    DeepSeekExperimentConfig,
    build_deepseek_provider,
    has_deepseek_api_key,
)
from app.core.review.agent_provider import OpenAICompatibleAgentProvider, OpenAICompatibleConfig


def test_deepseek_config_uses_non_secret_environment(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://example.invalid/v1/")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat-test")
    monkeypatch.setenv("DEEPSEEK_TIMEOUT_SECONDS", "12")
    monkeypatch.setenv("DEEPSEEK_MAX_RETRIES", "0")

    config = DeepSeekExperimentConfig.from_environment()

    assert config.base_url == "https://example.invalid/v1"
    assert config.model == "deepseek-chat-test"
    assert config.timeout_seconds == 12.0
    assert config.max_retries == 0


def test_deepseek_provider_requires_process_environment_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "")

    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        build_deepseek_provider()


def test_deepseek_provider_does_not_put_key_in_config(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-secret")
    provider, config = build_deepseek_provider(
        DeepSeekExperimentConfig(base_url="https://example.invalid/v1", model="deepseek-chat")
    )

    try:
        assert provider.config.api_key == "sk-test-secret"
        assert "api_key" not in config.__dict__
        assert "sk-test-secret" not in repr(config)
    finally:
        import asyncio

        asyncio.run(provider.aclose())


def test_deepseek_provider_reads_local_settings_without_exposing_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "sk-local-settings-secret")

    provider, config = build_deepseek_provider()

    try:
        assert provider.config.api_key == "sk-local-settings-secret"
        assert "api_key" not in config.__dict__
        assert "sk-local-settings-secret" not in repr(config)
    finally:
        import asyncio

        asyncio.run(provider.aclose())


def test_deepseek_key_presence_uses_environment_or_local_settings(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "")
    assert not has_deepseek_api_key()

    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "sk-local-settings-secret")
    assert has_deepseek_api_key()


def test_deepseek_provider_accepts_experiment_temperature(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-secret")
    provider, _ = build_deepseek_provider(temperature=1.0)

    try:
        assert provider.config.temperature == 1.0
    finally:
        import asyncio

        asyncio.run(provider.aclose())


def test_agent_provider_telemetry_is_task_local_for_concurrent_calls():
    import asyncio

    provider = OpenAICompatibleAgentProvider(
        OpenAICompatibleConfig(
            api_key="sk-test-secret",
            base_url="https://example.invalid/v1",
            model="test-model",
        )
    )

    async def capture(marker: str, delay: float) -> str:
        provider.last_call_telemetry = {"marker": marker}
        await asyncio.sleep(delay)
        return str(provider.last_call_telemetry["marker"])

    async def exercise() -> tuple[str, str]:
        return tuple(await asyncio.gather(capture("first", 0.01), capture("second", 0.0)))

    first, second = asyncio.run(exercise())

    assert first == "first"
    assert second == "second"


def test_judge_contract_explicitly_names_stance_and_axis_enums():
    prompt = build_agent_system_prompt("HarmfulnessJudgeAgent")
    contract = build_agent_output_contract("HarmfulnessJudgeAgent")

    assert "support, deny, query, neutral, unlinked, or uncertain" in prompt
    assert "harmful, non_harmful, uncertain, or unavailable" in prompt
    assert contract["machine_footer"]["schema"]["stance"]["label"] == [
        "deny",
        "neutral",
        "query",
        "support",
        "uncertain",
        "unlinked",
    ]
