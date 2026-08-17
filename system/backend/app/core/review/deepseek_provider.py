"""DeepSeek provider construction for isolated Review experiments.

The provider deliberately delegates wire handling, retries, and redaction to
the existing OpenAI-compatible adapter. This module owns only environment
configuration so experiment scripts cannot accidentally accept a credential
as a tracked command-line or report value.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from app.config import settings
from app.core.review.agent_provider import (
    OpenAICompatibleAgentProvider,
    OpenAICompatibleConfig,
)

__all__ = ["DeepSeekExperimentConfig", "build_deepseek_provider", "has_deepseek_api_key"]


@dataclass(frozen=True)
class DeepSeekExperimentConfig:
    """Non-secret DeepSeek experiment settings resolved from the process."""

    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-chat"
    timeout_seconds: float = 180.0
    max_retries: int = 2
    retry_backoff_seconds: float = 2.0

    @classmethod
    def from_environment(cls) -> "DeepSeekExperimentConfig":
        return cls(
            base_url=(os.getenv("DEEPSEEK_BASE_URL") or settings.DEEPSEEK_BASE_URL or cls.base_url).strip().rstrip("/"),
            model=(os.getenv("DEEPSEEK_MODEL") or settings.DEEPSEEK_MODEL or cls.model).strip(),
            timeout_seconds=_positive_float(
                os.getenv("DEEPSEEK_TIMEOUT_SECONDS") or str(settings.DEEPSEEK_TIMEOUT_SECONDS),
                cls.timeout_seconds,
            ),
            max_retries=_non_negative_int(
                os.getenv("DEEPSEEK_MAX_RETRIES") or str(settings.DEEPSEEK_MAX_RETRIES),
                cls.max_retries,
            ),
            retry_backoff_seconds=_positive_float(
                os.getenv("DEEPSEEK_RETRY_BACKOFF_SECONDS") or str(settings.DEEPSEEK_RETRY_BACKOFF_SECONDS),
                cls.retry_backoff_seconds,
            ),
        )


def build_deepseek_provider(
    config: DeepSeekExperimentConfig | None = None,
    *,
    temperature: float = 0.2,
) -> tuple[OpenAICompatibleAgentProvider, DeepSeekExperimentConfig]:
    """Build a provider using only a process-scoped ``DEEPSEEK_API_KEY``.

    The returned config contains no credential. The key is held only by the
    provider instance for the lifetime of the current process.
    """

    api_key = _deepseek_api_key()
    if not api_key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY is not configured; set it in the current process "
            "or through CC-switch before starting the experiment."
        )
    resolved = config or DeepSeekExperimentConfig.from_environment()
    provider = OpenAICompatibleAgentProvider(
        OpenAICompatibleConfig(
            api_key=api_key,
            base_url=resolved.base_url,
            model=resolved.model,
            wire_api="chat_completions",
            timeout_seconds=resolved.timeout_seconds,
            include_media_base64=False,
            require_vision=False,
            max_retries=resolved.max_retries,
            retry_backoff_seconds=resolved.retry_backoff_seconds,
            temperature=_bounded_temperature(temperature),
            cache_enabled=False,
        )
    )
    return provider, resolved


def has_deepseek_api_key() -> bool:
    """Return whether the local process or ignored settings file has a key."""

    return bool(_deepseek_api_key())


def _deepseek_api_key() -> str:
    return (os.getenv("DEEPSEEK_API_KEY") or settings.DEEPSEEK_API_KEY or "").strip()


def _positive_float(value: str | None, default: float) -> float:
    if value is None or not value.strip():
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _non_negative_int(value: str | None, default: int) -> int:
    if value is None or not value.strip():
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed >= 0 else default


def _bounded_temperature(value: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return min(2.0, max(0.0, parsed))
