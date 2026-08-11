"""Pydantic contract for the archived Twitter IO benchmark manifest."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


_SHA256_PATTERN = re.compile(r"[0-9a-fA-F]{64}")


class TwitterBenchmarkManifest(BaseModel):
    """A digest-only manifest for a Twitter benchmark CSV kept outside git."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["cogguard.twitter_io.manifest.v1"]
    source_path: str
    byte_size: int
    sha256: str
    columns: tuple[str, ...]
    rows: int
    users: int
    retweets: int
    replies: int
    quotes: int

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        if not _SHA256_PATTERN.fullmatch(value):
            raise ValueError("must be a 64-character SHA-256 hexadecimal digest")
        return value.upper()


__all__ = ["TwitterBenchmarkManifest"]
