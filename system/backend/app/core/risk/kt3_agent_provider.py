"""KT3 LLM provider adapters.

The manual agent review runner depends on the provider protocol, but provider
wire details belong in this module. Keep OpenAI-compatible HTTP behavior here
so orchestration code stays focused on review flow and audit output.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import asyncio
import random

import httpx


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


class OpenAICompatibleAgentProvider:
    """Minimal OpenAI-compatible provider with chat and Responses support."""

    def __init__(self, config: OpenAICompatibleConfig):
        self.config = config

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
            )
        else:
            url = self.config.base_url.rstrip("/") + "/chat/completions"
            payload = {
                "model": payload_model,
                "messages": _openai_messages(system_prompt, user_prompt, input_bundle),
                "temperature": 0.2,
            }
        headers = {"Authorization": f"Bearer {self.config.api_key}"}
        data = None
        last_error: Exception | None = None
        max_attempts = max(1, int(self.config.max_retries or 0) + 1)
        for attempt in range(1, max_attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                    response = await client.post(url, headers=headers, json=payload)
                    response.raise_for_status()
                    data = response.json()
                    break
            except httpx.HTTPStatusError as exc:
                last_error = exc
                status_code = exc.response.status_code if exc.response is not None else None
                if attempt >= max_attempts or not _should_retry_status(status_code):
                    body = exc.response.text[:1000] if exc.response is not None else ""
                    raise RuntimeError(f"{agent_name} provider HTTP {status_code if status_code else 'error'}: {body}") from exc
            except Exception as exc:
                last_error = exc
                if attempt >= max_attempts or not _should_retry_exception(exc):
                    detail = str(exc) or exc.__class__.__name__
                    raise RuntimeError(f"{agent_name} provider request failed: {detail}") from exc
            await asyncio.sleep(_retry_delay_seconds(self.config.retry_backoff_seconds, attempt))
        if data is None:
            detail = str(last_error) if last_error is not None else "unknown provider error"
            raise RuntimeError(f"{agent_name} provider request failed: {detail}")
        if wire_api == "responses":
            return _extract_responses_text(data, agent_name)
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(f"{agent_name} returned no choices")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, list):
            return "\n".join(str(item.get("text") or item) for item in content)
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError(f"{agent_name} returned an empty report")
        return content.strip()


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
        "temperature": 0.2,
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


def _should_retry_status(status_code: int | None) -> bool:
    return status_code in {408, 409, 429, 500, 502, 503, 504}


def _should_retry_exception(exc: Exception) -> bool:
    return isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError))


def _retry_delay_seconds(base_delay: float, attempt: int) -> float:
    base = max(0.25, float(base_delay or 0.0))
    jitter = random.uniform(0.0, 0.35)
    return min(8.0, base * attempt) + jitter


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]
