"""Media and vision-input boundary for KT3 manual Agents."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import base64


__all__ = [
    "agent_requires_vision",
    "build_media_inputs_for_post",
    "build_provider_input_bundle_for_agent",
    "build_vision_input_status",
    "infer_media_type",
    "maybe_data_url",
    "provider_should_receive_media",
]


def build_media_inputs_for_post(
    post: dict[str, Any],
    *,
    include_media_base64: bool,
    max_keyframes: int,
) -> list[dict[str, Any]]:
    evidence = post.get("evidence") or {}
    raw = post.get("raw_data") or {}
    media_urls = _as_list(post.get("media_urls")) or _as_list(evidence.get("media_urls"))
    rows: list[dict[str, Any]] = []
    for index, url in enumerate(media_urls[:max_keyframes]):
        media_type = infer_media_type(str(url))
        row = {
            "post_id": post.get("post_id"),
            "media_index": index,
            "media_type": media_type,
            "uri": str(url),
            "selection_policy": "image_original_or_video_cover_then_uniform_keyframes",
            "ocr_text": _text(raw.get("ocr_text")) or _text(evidence.get("ocr_text")),
            "asr_text": _text(raw.get("asr_text")) or _text(evidence.get("asr_text")),
            "caption": _text(raw.get("caption")) or _text(evidence.get("caption")),
        }
        if include_media_base64:
            row["data_url"] = maybe_data_url(str(url))
        rows.append(row)
    if not rows and any(_text(raw.get(key)) or _text(evidence.get(key)) for key in ("ocr_text", "asr_text", "caption")):
        rows.append(
            {
                "post_id": post.get("post_id"),
                "media_index": 0,
                "media_type": "derived_text_only",
                "uri": "",
                "selection_policy": "no_media_file_reference_available",
                "ocr_text": _text(raw.get("ocr_text")) or _text(evidence.get("ocr_text")),
                "asr_text": _text(raw.get("asr_text")) or _text(evidence.get("asr_text")),
                "caption": _text(raw.get("caption")) or _text(evidence.get("caption")),
            }
        )
    return rows


def maybe_data_url(uri: str) -> str | None:
    path = Path(uri)
    if not path.exists() or not path.is_file():
        return None
    suffix = path.suffix.lower()
    mime = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(suffix)
    if not mime:
        return None
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def infer_media_type(uri: str) -> str:
    suffix = Path(uri).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return "image"
    if suffix in {".mp4", ".mov", ".avi", ".mkv", ".webm"}:
        return "video_keyframe_reference"
    return "media_reference"


def agent_requires_vision(
    agent_name: str,
    *,
    context: dict[str, Any],
    state: dict[str, Any],
) -> bool:
    if not bool(state.get("require_vision")):
        return False
    # Strict vision is scoped to the multimodal/keyframe review agent. Other
    # MARO-style agents may cite OCR/ASR/caption or detector outputs without
    # becoming raw visual reviewers.
    return agent_name == "MultimodalConsistencyAgent"


def build_vision_input_status(context: dict[str, Any]) -> dict[str, Any]:
    media_inputs = [item for item in _as_list(context.get("media_inputs")) if isinstance(item, dict)]
    data_url_count = sum(1 for item in media_inputs if item.get("data_url"))
    media_types = sorted({str(item.get("media_type") or "unknown") for item in media_inputs})
    return {
        "has_vision_input": data_url_count > 0,
        "media_input_count": len(media_inputs),
        "data_url_count": data_url_count,
        "media_types": media_types,
        "requires_base64_or_accessible_image_url": True,
    }


def build_provider_input_bundle_for_agent(
    agent_name: str,
    *,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Trim heavy visual payloads for text-only Agents."""
    if provider_should_receive_media(agent_name):
        return context
    trimmed = dict(context)
    trimmed["media_inputs"] = []
    return trimmed


def provider_should_receive_media(agent_name: str) -> bool:
    normalized = str(agent_name or "")
    return (
        normalized == "MultimodalConsistencyAgent"
        or normalized.startswith("MultimodalConsistencyAgent")
        or normalized.startswith("FullDebate:")
    )


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
