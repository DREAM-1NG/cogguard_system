"""Pydantic contracts for reviewed Case Workbench research archives."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator


_SHA256_PATTERN = re.compile(r"[0-9a-fA-F]{64}")


class StructuredSearchHit(BaseModel):
    """One result returned by a recorded research query."""

    model_config = ConfigDict(extra="forbid")

    rank: int
    title: str
    url: AnyHttpUrl
    source_account: str | None = None
    published_at: datetime | None = None
    snippet: str
    disposition: Literal["candidate", "verified", "rejected"]
    disposition_reason: str | None = None

    @model_validator(mode="after")
    def require_disposition_evidence(self) -> StructuredSearchHit:
        if self.disposition == "verified" and (not self.source_account or self.published_at is None):
            raise ValueError("verified hits require source_account and published_at")
        if self.disposition == "rejected" and not str(self.disposition_reason or "").strip():
            raise ValueError("rejected hits require disposition_reason")
        return self


class StructuredSearchRecord(BaseModel):
    """An append-only record of one research query and its returned hits."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["cogguard.case_research.search.v1"]
    search_id: str
    purpose: Literal["primary_claim", "supplementary_claim", "second_platform"]
    query: str
    provider: str
    searched_at: datetime
    filters: dict[str, str]
    hits: list[StructuredSearchHit]


class ResearchArchiveEntry(BaseModel):
    """A reviewed MarkItDown conversion with source and excerpt provenance."""

    model_config = ConfigDict(extra="forbid")

    archive_id: str
    purpose: Literal["primary_claim", "supplementary_claim", "second_platform"]
    source_url: AnyHttpUrl
    source_path: str
    markdown_path: str
    metadata_path: str
    source_sha256: str
    markdown_sha256: str
    converter: Literal["Microsoft MarkItDown"]
    converter_version: str
    verified_excerpt: str
    verified_span_start: int
    verified_span_end: int
    archived_at: datetime

    @field_validator("source_sha256", "markdown_sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        if not _SHA256_PATTERN.fullmatch(value):
            raise ValueError("must be a 64-character SHA-256 hexadecimal digest")
        return value


class PlatformGapSearch(BaseModel):
    """One attempted second-platform evidence search that did not verify."""

    model_config = ConfigDict(extra="forbid")

    candidate_platform: Literal["douyin", "xhs"]
    query: str
    provider: str
    searched_at: datetime
    rejected_urls: list[AnyHttpUrl] = Field(default_factory=list)
    disposition_reason: str

    @model_validator(mode="after")
    def require_rejection_reason(self) -> PlatformGapSearch:
        if not self.disposition_reason.strip():
            raise ValueError("platform gap searches require disposition_reason")
        return self


class PlatformGap(BaseModel):
    """The record used when no same-event second-platform source is verified."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["unverified_second_platform"]
    summary: str = Field(min_length=1)
    searches: list[PlatformGapSearch] = Field(min_length=1)


__all__ = [
    "PlatformGap",
    "PlatformGapSearch",
    "ResearchArchiveEntry",
    "StructuredSearchHit",
    "StructuredSearchRecord",
]
