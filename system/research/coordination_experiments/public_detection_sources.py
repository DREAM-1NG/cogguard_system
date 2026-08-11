from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Any


_SOURCE_PATHS: dict[str, str] = {}


def _text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text")
    return value.strip()


def register_public_detection_sources(cases: Sequence[Mapping[str, Any]]) -> None:
    if isinstance(cases, (str, bytes)) or not isinstance(cases, Sequence):
        raise ValueError("cases must be a sequence")
    for case in cases:
        if not isinstance(case, Mapping):
            raise ValueError("case source records must be mappings")
        case_id = _text(case.get("case_id"), "case_id")
        source_path = _text(case.get("source_path"), "source_path")
        resolved = Path(source_path).resolve(strict=False)
        if not resolved.is_absolute():
            raise ValueError("public Detection source paths must be absolute")
        _SOURCE_PATHS[case_id] = resolved.as_posix()


def clear_public_detection_sources() -> None:
    _SOURCE_PATHS.clear()


def resolve_public_detection_source_path(case_id: str) -> Path:
    normalized = _text(case_id, "case_id")
    try:
        return Path(_SOURCE_PATHS[normalized])
    except KeyError as exc:
        raise ValueError(
            "public Detection graph source was not registered for this case_id"
        ) from exc


def registered_public_detection_sources() -> Mapping[str, str]:
    return MappingProxyType(dict(sorted(_SOURCE_PATHS.items())))


__all__ = [
    "clear_public_detection_sources",
    "registered_public_detection_sources",
    "register_public_detection_sources",
    "resolve_public_detection_source_path",
]
