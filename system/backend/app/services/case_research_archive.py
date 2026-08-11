"""Load and verify append-only Case Workbench research archives."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from pathlib import Path
from typing import Any

from app.schemas.case_research import PlatformGap, ResearchArchiveEntry, StructuredSearchRecord


ARCHIVE_MANIFEST_FILENAME = "archive-manifest.json"
PLATFORM_GAP_FILENAME = "platform-gap.json"


def load_structured_search_records(path: Path) -> tuple[StructuredSearchRecord, ...]:
    """Load and validate the nonblank JSONL lines in a search-record file."""

    records: list[StructuredSearchRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(StructuredSearchRecord.model_validate(json.loads(line)))
    return tuple(records)


def load_research_archive_manifest(path: Path) -> tuple[ResearchArchiveEntry, ...]:
    """Load and validate the JSON array stored in an archive manifest."""

    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("research archive manifest must be a JSON array")
    return tuple(ResearchArchiveEntry.model_validate(entry) for entry in payload)


def verify_research_archive(root: Path, *, source_root: Path | None = None) -> tuple[ResearchArchiveEntry, ...]:
    """Verify committed Markdown, optional original sources, and reviewed excerpt spans."""

    resolved_root = root.resolve()
    manifest_path = resolved_root / ARCHIVE_MANIFEST_FILENAME
    if not manifest_path.is_file():
        return ()

    entries = load_research_archive_manifest(manifest_path)
    resolved_source_root = source_root.resolve() if source_root is not None else None
    for entry in entries:
        _verify_entry(entry, root=resolved_root, source_root=resolved_source_root)

    purposes = {entry.purpose for entry in entries}
    for required_purpose in ("primary_claim", "supplementary_claim"):
        if required_purpose not in purposes:
            raise ValueError(f"research archive requires a {required_purpose} entry")

    if "second_platform" not in purposes and not _has_unverified_second_platform_gap(resolved_root):
        raise ValueError("research archive requires a verified second-platform entry or platform-gap.json")
    return entries


def _verify_entry(
    entry: ResearchArchiveEntry,
    *,
    root: Path,
    source_root: Path | None,
) -> None:
    markdown_path = _resolve_within_root(entry.markdown_path, root=root, label="markdown_path")
    metadata_path = _resolve_within_root(entry.metadata_path, root=root, label="metadata_path")
    if not markdown_path.is_file():
        raise ValueError(f"markdown_path does not exist: {entry.markdown_path}")
    if not metadata_path.is_file():
        raise ValueError(f"metadata_path does not exist: {entry.metadata_path}")

    markdown_bytes = markdown_path.read_bytes()
    _require_sha256(markdown_bytes, entry.markdown_sha256, label="markdown")
    normalized_markdown = unicodedata.normalize("NFC", markdown_bytes.decode("utf-8"))
    start = entry.verified_span_start
    end = entry.verified_span_end
    if start < 0 or end < start or end > len(normalized_markdown):
        raise ValueError("verified excerpt span is outside normalized Markdown")
    if normalized_markdown[start:end] != entry.verified_excerpt:
        raise ValueError("verified excerpt does not match the normalized Markdown span")

    if source_root is not None:
        source_path = _resolve_within_root(entry.source_path, root=source_root, label="source_path")
        if not source_path.is_file():
            raise ValueError(f"source_path does not exist: {entry.source_path}")
        _require_sha256(source_path.read_bytes(), entry.source_sha256, label="source")


def _has_unverified_second_platform_gap(root: Path) -> bool:
    platform_gap_path = root / PLATFORM_GAP_FILENAME
    if not platform_gap_path.is_file():
        return False
    PlatformGap.model_validate(json.loads(platform_gap_path.read_text(encoding="utf-8")))
    return True


def _resolve_within_root(raw_path: str, *, root: Path, label: str) -> Path:
    resolved_path = (root / raw_path).resolve()
    if not resolved_path.is_relative_to(root):
        raise ValueError(f"{label} resolves outside the permitted root")
    return resolved_path


def _require_sha256(content: bytes, expected: str, *, label: str) -> None:
    actual = hashlib.sha256(content).hexdigest()
    if actual.lower() != expected.lower():
        raise ValueError(f"{label} SHA-256 does not match its archive manifest")


__all__ = [
    "load_research_archive_manifest",
    "load_structured_search_records",
    "verify_research_archive",
]
