import hashlib
import json
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.case_research import ResearchArchiveEntry, StructuredSearchHit
from app.services.case_research_archive import (
    load_research_archive_manifest,
    load_structured_search_records,
    verify_research_archive,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _entry(root: Path, purpose: str, *, markdown_text: str = "Verified excerpt") -> dict[str, object]:
    slug = purpose.replace("_", "-")
    markdown_relative = f"sources/{slug}.md"
    metadata_relative = f"sources/{slug}.meta.json"
    markdown_path = root / markdown_relative
    metadata_path = root / metadata_relative
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(markdown_text, encoding="utf-8")
    metadata_path.write_text(
        json.dumps({"converter": "Microsoft MarkItDown", "converter_version": "test"}),
        encoding="utf-8",
    )
    normalized = unicodedata.normalize("NFC", markdown_text)
    return {
        "archive_id": f"archive-{slug}",
        "purpose": purpose,
        "source_url": f"https://example.com/{slug}",
        "source_path": f"originals/{slug}.html",
        "markdown_path": markdown_relative,
        "metadata_path": metadata_relative,
        "source_sha256": "0" * 64,
        "markdown_sha256": _sha256(markdown_path),
        "converter": "Microsoft MarkItDown",
        "converter_version": "test",
        "verified_excerpt": normalized,
        "verified_span_start": 0,
        "verified_span_end": len(normalized),
        "archived_at": datetime(2026, 8, 11, tzinfo=timezone.utc).isoformat(),
    }


def _write_manifest(root: Path, entries: list[dict[str, object]]) -> None:
    (root / "archive-manifest.json").write_text(json.dumps(entries), encoding="utf-8")


def _write_platform_gap(root: Path) -> None:
    (root / "platform-gap.json").write_text(
        json.dumps({"status": "unverified_second_platform"}),
        encoding="utf-8",
    )


def test_load_structured_search_records_rejects_verified_hit_without_provenance(tmp_path: Path):
    records_path = tmp_path / "structured-search-records.jsonl"
    record = {
        "schema_version": "cogguard.case_research.search.v1",
        "search_id": "search-1",
        "purpose": "primary_claim",
        "query": "example query",
        "provider": "test-provider",
        "searched_at": "2026-08-11T00:00:00+00:00",
        "filters": {},
        "hits": [
            {
                "rank": 1,
                "title": "Candidate",
                "url": "https://example.com/source",
                "snippet": "result",
                "disposition": "candidate",
            }
        ],
    }
    records_path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    records = load_structured_search_records(records_path)

    assert records[0].hits[0].disposition == "candidate"
    record["hits"][0]["disposition"] = "verified"
    records_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="source_account and published_at"):
        load_structured_search_records(records_path)


def test_structured_search_hit_rejects_rejected_hit_without_disposition_reason():
    with pytest.raises(ValidationError, match="disposition_reason"):
        StructuredSearchHit.model_validate(
            {
                "rank": 1,
                "title": "Rejected result",
                "url": "https://example.com/source",
                "snippet": "result",
                "disposition": "rejected",
            }
        )


def test_research_archive_entry_rejects_non_sha256_values(tmp_path: Path):
    entry = _entry(tmp_path, "primary_claim")
    entry["markdown_sha256"] = "not-a-sha256"

    with pytest.raises(ValidationError):
        ResearchArchiveEntry.model_validate(entry)


def test_verify_research_archive_validates_nfc_span_hashes_and_source_bytes(tmp_path: Path):
    root = tmp_path / "archive"
    root.mkdir()
    primary = _entry(root, "primary_claim", markdown_text="Cafe\u0301")
    supplementary = _entry(root, "supplementary_claim")
    _write_manifest(root, [primary, supplementary])
    _write_platform_gap(root)

    source_root = tmp_path / "source-input"
    for entry in (primary, supplementary):
        source_path = source_root / str(entry["source_path"])
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(str(entry["archive_id"]), encoding="utf-8")
        entry["source_sha256"] = _sha256(source_path)
    _write_manifest(root, [primary, supplementary])

    entries = verify_research_archive(root, source_root=source_root)

    assert {entry.purpose for entry in entries} == {"primary_claim", "supplementary_claim"}
    assert entries[0].verified_excerpt == "Caf\u00e9"


def test_verify_research_archive_requires_claim_sources_and_second_platform_outcome(tmp_path: Path):
    root = tmp_path / "archive"
    root.mkdir()
    _write_manifest(root, [_entry(root, "primary_claim")])

    with pytest.raises(ValueError, match="supplementary_claim"):
        verify_research_archive(root)

    _write_manifest(root, [_entry(root, "primary_claim"), _entry(root, "supplementary_claim")])
    with pytest.raises(ValueError, match="second-platform"):
        verify_research_archive(root)

    _write_platform_gap(root)
    assert len(verify_research_archive(root)) == 2


@pytest.mark.parametrize(
    ("metadata", "match"),
    [
        ({"converter": "Different converter", "converter_version": "test"}, "metadata converter"),
        ({"converter": "Microsoft MarkItDown", "converter_version": "different"}, "metadata converter version"),
    ],
)
def test_verify_research_archive_rejects_metadata_converter_mismatch(
    tmp_path: Path,
    metadata: dict[str, str],
    match: str,
):
    root = tmp_path / "archive"
    root.mkdir()
    primary = _entry(root, "primary_claim")
    supplementary = _entry(root, "supplementary_claim")
    (root / str(primary["metadata_path"])).write_text(json.dumps(metadata), encoding="utf-8")
    _write_manifest(root, [primary, supplementary])
    _write_platform_gap(root)

    with pytest.raises(ValueError, match=match):
        verify_research_archive(root)


def test_verify_research_archive_rejects_verified_second_platform_with_platform_gap(tmp_path: Path):
    root = tmp_path / "archive"
    root.mkdir()
    _write_manifest(
        root,
        [
            _entry(root, "primary_claim"),
            _entry(root, "supplementary_claim"),
            _entry(root, "second_platform"),
        ],
    )
    _write_platform_gap(root)

    with pytest.raises(ValueError, match="mutually exclusive"):
        verify_research_archive(root)


def test_verify_research_archive_rejects_paths_and_excerpt_mismatches_outside_root(tmp_path: Path):
    root = tmp_path / "archive"
    root.mkdir()
    primary = _entry(root, "primary_claim")
    supplementary = _entry(root, "supplementary_claim")
    primary["markdown_path"] = "../outside.md"
    outside = tmp_path / "outside.md"
    outside.write_text("Verified excerpt", encoding="utf-8")
    _write_manifest(root, [primary, supplementary])
    _write_platform_gap(root)

    with pytest.raises(ValueError, match="outside"):
        verify_research_archive(root)


def test_load_research_archive_manifest_accepts_verified_second_platform_entry(tmp_path: Path):
    root = tmp_path / "archive"
    root.mkdir()
    entries = [
        _entry(root, "primary_claim"),
        _entry(root, "supplementary_claim"),
        _entry(root, "second_platform"),
    ]
    manifest_path = root / "archive-manifest.json"
    _write_manifest(root, entries)

    loaded = load_research_archive_manifest(manifest_path)

    assert [entry.purpose for entry in loaded] == ["primary_claim", "supplementary_claim", "second_platform"]
    assert len(verify_research_archive(root)) == 3
