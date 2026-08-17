"""Torch-free deterministic text features shared by Review adapters.

Keeping these helpers independent from the trainable model module allows RAG,
Teacher Silver, and contract tests to run without importing a native Torch
runtime.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np


TOKEN_RE = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(str(text or "").lower())


def hash_text_features(texts: list[str], *, dim: int = 256) -> np.ndarray:
    """Build stable normalized token-hash vectors for local retrieval/smoke paths."""

    rows = np.zeros((len(texts), dim), dtype="float32")
    for row_index, text in enumerate(texts):
        tokens = tokenize(text)
        if not tokens:
            continue
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8", errors="ignore"), digest_size=8).digest()
            raw = int.from_bytes(digest, byteorder="little", signed=False)
            index = raw % dim
            sign = 1.0 if (raw >> 8) & 1 else -1.0
            rows[row_index, index] += sign
        norm = float(np.linalg.norm(rows[row_index]))
        if norm > 0:
            rows[row_index] /= norm
    return rows


__all__ = ["hash_text_features", "tokenize"]
