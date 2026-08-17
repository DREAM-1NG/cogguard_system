"""Review LLM provider adapters.

The manual agent review runner depends on the provider protocol, but provider
wire details belong in this module. Keep OpenAI-compatible HTTP behavior here
so orchestration code stays focused on review flow and audit output.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import asyncio
from contextvars import ContextVar
import random
import re

import httpx

from app.core import llm_cache


__all__ = [
    "OpenAICompatibleAgentProvider",
    "OpenAICompatibleConfig",
    "build_llm_provider_from_settings",
]


@dataclass(frozen=True)
class OpenAICompatibleConfig:
    api_key: str
    base_url: str
    model: str
    wire_api: str = "chat_completions"
    timeout_seconds: float = 180.0
    include_media_base64: bool = False
    require_vision: bool = False
    max_retries: int = 2
    retry_backoff_seconds: float = 2.0
    temperature: float = 0.2
    # ``None`` preserves the application-level LLM_CACHE_MODE. Performance
    # experiments pass ``False`` so a replayed response cannot hide latency.
    cache_enabled: bool | None = None


class OpenAICompatibleAgentProvider:
    """Minimal OpenAI-compatible provider with chat and Responses support."""

    def __init__(
        self,
        config: OpenAICompatibleConfig,
        *,
        client: httpx.AsyncClient | None = None,
    ):
        self.config = config
        self._client = client
        self._owns_client = client is None
        self._last_call_telemetry: ContextVar[dict[str, Any] | None] = ContextVar(
            "openai_compatible_agent_provider_telemetry",
            default=None,
        )

    @property
    def last_call_telemetry(self) -> dict[str, Any]:
        return dict(self._last_call_telemetry.get() or {})

    @last_call_telemetry.setter
    def last_call_telemetry(self, value: dict[str, Any]) -> None:
        self._last_call_telemetry.set(dict(value))

    async def aclose(self) -> None:
        """Close the client only when this provider created it."""
        if self._owns_client and self._client is not None:
            await self._client.aclose()

    async def __call__(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        user_prompt: str,
        input_bundle: dict[str, Any],
        model: str,
    ) -> str:
        if not self.config.api_key:
            raise RuntimeError("LLM API key is not configured")
        payload_model = model or self.config.model
        wire_api = _normalize_wire_api(self.config.wire_api)
        if wire_api == "responses":
            url = self.config.base_url.rstrip("/") + "/responses"
            payload = _openai_responses_payload(
                system_prompt,
                user_prompt,
                input_bundle,
                model=payload_model,
                temperature=self.config.temperature,
            )
        else:
            url = self.config.base_url.rstrip("/") + "/chat/completions"
            payload = {
                "model": payload_model,
                "messages": _openai_messages(system_prompt, user_prompt, input_bundle),
                "temperature": self.config.temperature,
            }
        use_cache = self.config.cache_enabled
        if use_cache is None:
            use_cache = llm_cache.cache_mode() != "off"
        cache_key = None
        cache_status = "disabled"
        if use_cache:
            cache_key = llm_cache.response_cache_key(
                channel=f"review.agent.{agent_name}",
                model=payload_model,
                payload=payload,
            )
            cached = llm_cache.load_cached_response(cache_key)
            if cached is not None:
                self.last_call_telemetry = {
                    "cache_hit": True,
                    "cache_status": "hit",
                    "attempt_count": 0,
                    "retry_count": 0,
                    "http_status": None,
                    "error_class": None,
                    "usage_available": False,
                    "input_tokens": None,
                    "output_tokens": None,
                    "total_tokens": None,
                }
                return cached
            cache_status = "miss"

        headers = {"Authorization": f"Bearer {self.config.api_key}"}
        data = None
        last_error: Exception | None = None
        http_status: int | None = None
        error_class: str | None = None
        retry_statuses: list[int] = []
        max_attempts = max(1, int(self.config.max_retries or 0) + 1)
        for attempt in range(1, max_attempts + 1):
            try:
                if self._client is None:
                    self._client = httpx.AsyncClient(timeout=self.config.timeout_seconds)
                response = await self._client.post(url, headers=headers, json=payload)
                http_status = response.status_code
                response.raise_for_status()
                data = response.json()
                break
            except httpx.HTTPStatusError as exc:
                last_error = exc
                status_code = exc.response.status_code if exc.response is not None else None
                http_status = status_code
                error_class = type(exc).__name__
                if status_code is not None:
                    retry_statuses.append(int(status_code))
                if attempt >= max_attempts or not _should_retry_status(status_code):
                    body = _redact_provider_detail(
                        exc.response.text[:1000] if exc.response is not None else "",
                        self.config.api_key,
                    )
                    self.last_call_telemetry = _provider_error_telemetry(
                        attempt=attempt,
                        http_status=http_status,
                        error_class=error_class,
                        cache_hit=False,
                        cache_status=cache_status,
                        retry_statuses=retry_statuses,
                    )
                    raise RuntimeError(f"{agent_name} provider HTTP {status_code if status_code else 'error'}: {body}") from exc
            except Exception as exc:
                last_error = exc
                error_class = type(exc).__name__
                if attempt >= max_attempts or not _should_retry_exception(exc):
                    detail = _redact_provider_detail(str(exc) or exc.__class__.__name__, self.config.api_key)
                    self.last_call_telemetry = _provider_error_telemetry(
                        attempt=attempt,
                        http_status=http_status,
                        error_class=error_class,
                        cache_hit=False,
                        cache_status=cache_status,
                        retry_statuses=retry_statuses,
                    )
                    raise RuntimeError(f"{agent_name} provider request failed: {detail}") from exc
            await asyncio.sleep(_retry_delay_seconds(self.config.retry_backoff_seconds, attempt))
        if data is None:
            detail = str(last_error) if last_error is not None else "unknown provider error"
            self.last_call_telemetry = _provider_error_telemetry(
                attempt=max_attempts,
                http_status=http_status,
                error_class=error_class or "UnknownProviderError",
                cache_hit=False,
                cache_status=cache_status,
                retry_statuses=retry_statuses,
            )
            raise RuntimeError(f"{agent_name} provider request failed: {detail}")
        if wire_api == "responses":
            text = _extract_responses_text(data, agent_name)
        else:
            choices = data.get("choices") or []
            if not choices:
                raise RuntimeError(f"{agent_name} returned no choices")
            message = choices[0].get("message") or {}
            content = message.get("content")
            if isinstance(content, list):
                text = "\n".join(str(item.get("text") or item) for item in content)
            elif isinstance(content, str) and content.strip():
                text = content.strip()
            else:
                raise RuntimeError(f"{agent_name} returned an empty report")

        usage = _usage_telemetry(data)
        self.last_call_telemetry = {
            "cache_hit": False,
            "cache_status": cache_status,
            "attempt_count": attempt,
            "retry_count": max(0, attempt - 1),
            "http_status": http_status,
            "error_class": None,
            "retry_statuses": retry_statuses,
            "rate_limit_retry_count": retry_statuses.count(429),
            **usage,
        }
        if use_cache and cache_key is not None:
            llm_cache.record_response(
                cache_key,
                text,
                channel=f"review.agent.{agent_name}",
                model=payload_model,
            )
        return text


def build_llm_provider_from_settings(settings: Any) -> OpenAICompatibleAgentProvider | None:
    api_key = str(getattr(settings, "LLM_API_KEY", "") or "")
    if not api_key:
        return None
    config = OpenAICompatibleConfig(
        api_key=api_key,
        base_url=str(getattr(settings, "LLM_API_BASE", "") or "https://api.deepseek.com/v1"),
        model=str(getattr(settings, "LLM_MODEL", "") or "deepseek-chat"),
        wire_api=str(getattr(settings, "LLM_API_WIRE", "") or "chat_completions"),
        timeout_seconds=float(getattr(settings, "LLM_TIMEOUT_SECONDS", 180.0) or 180.0),
        include_media_base64=bool(getattr(settings, "LLM_INCLUDE_MEDIA_BASE64", False)),
        require_vision=bool(getattr(settings, "LLM_REQUIRE_VISION", False)),
    )
    return OpenAICompatibleAgentProvider(config)


def _openai_messages(
    system_prompt: str,
    user_prompt: str,
    input_bundle: dict[str, Any],
) -> list[dict[str, Any]]:
    image_parts = []
    for item in _as_list(input_bundle.get("media_inputs")):
        data_url = item.get("data_url") if isinstance(item, dict) else None
        if data_url:
            image_parts.append({"type": "image_url", "image_url": {"url": data_url}})
    if not image_parts:
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    content = [{"type": "text", "text": user_prompt}, *image_parts]
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": content},
    ]


def _openai_responses_payload(
    system_prompt: str,
    user_prompt: str,
    input_bundle: dict[str, Any],
    *,
    model: str,
    temperature: float,
) -> dict[str, Any]:
    content: list[dict[str, Any]] = [{"type": "input_text", "text": user_prompt}]
    for item in _as_list(input_bundle.get("media_inputs")):
        data_url = item.get("data_url") if isinstance(item, dict) else None
        if data_url:
            content.append({"type": "input_image", "image_url": data_url})
    return {
        "model": model,
        "instructions": system_prompt,
        "input": [{"role": "user", "content": content}],
        "temperature": temperature,
    }


def _extract_responses_text(data: dict[str, Any], agent_name: str) -> str:
    output_text = data.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()
    chunks: list[str] = []
    for item in _as_list(data.get("output")):
        if not isinstance(item, dict):
            continue
        for content in _as_list(item.get("content")):
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())
    if chunks:
        return "\n".join(chunks)
    raise RuntimeError(f"{agent_name} returned an empty Responses report")


def _normalize_wire_api(value: str) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_")
    if normalized in {"responses", "response"}:
        return "responses"
    if normalized in {"chat", "chat_completion", "chat_completions", "completions"}:
        return "chat_completions"
    raise RuntimeError(f"Unsupported LLM_API_WIRE: {value}")


def _redact_provider_detail(detail: str, api_key: str | None = None) -> str:
    text = str(detail or "")
    if api_key:
        text = text.replace(api_key, "[REDACTED_API_KEY]")
    # Some gateways echo a masked key, so redact credential-shaped fragments too.
    return re.sub(r"(?i)sk-[A-Za-z0-9_.*-]{6,}", "sk-[REDACTED]", text)


def _should_retry_status(status_code: int | None) -> bool:
    return status_code in {408, 409, 429, 500, 502, 503, 504}


def _should_retry_exception(exc: Exception) -> bool:
    return isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError))


def _retry_delay_seconds(base_delay: float, attempt: int) -> float:
    base = max(0.25, float(base_delay or 0.0))
    jitter = random.uniform(0.0, 0.35)
    return min(8.0, base * attempt) + jitter


def _usage_telemetry(data: dict[str, Any]) -> dict[str, Any]:
    usage = data.get("usage") if isinstance(data, dict) else None
    if not isinstance(usage, dict):
        return {
            "usage_available": False,
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
        }
    input_tokens = usage.get("input_tokens", usage.get("prompt_tokens"))
    output_tokens = usage.get("output_tokens", usage.get("completion_tokens"))
    total_tokens = usage.get("total_tokens")
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        try:
            total_tokens = int(input_tokens) + int(output_tokens)
        except (TypeError, ValueError):
            total_tokens = None
    return {
        "usage_available": any(value is not None for value in (input_tokens, output_tokens, total_tokens)),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def _provider_error_telemetry(
    *,
    attempt: int,
    http_status: int | None,
    error_class: str | None,
    cache_hit: bool,
    cache_status: str,
    retry_statuses: list[int],
) -> dict[str, Any]:
    return {
        "cache_hit": cache_hit,
        "cache_status": cache_status,
        "attempt_count": attempt,
        "retry_count": max(0, attempt - 1),
        "http_status": http_status,
        "error_class": error_class,
        "retry_statuses": list(retry_statuses),
        "rate_limit_retry_count": retry_statuses.count(429),
        "usage_available": False,
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
    }


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]
