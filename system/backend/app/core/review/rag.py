"""Local retrieval support for Review external evidence.

The first deliverable RAG path is intentionally lightweight and reproducible:
public DISARM framework/STIX files are normalized into JSONL documents, then
queried with deterministic hash embeddings. It is a local evidence retriever,
not an online vector database or LLM generator.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json

import numpy as np

from app.core.review.trainable_post import hash_text_features, tokenize


@dataclass(frozen=True)
class RagDocument:
    doc_id: str
    source: str
    title: str
    text: str


class LocalHashRag:
    def __init__(self, documents: list[RagDocument], *, dim: int = 512):
        self.documents = documents
        self.dim = dim
        self.matrix = hash_text_features([doc.text for doc in documents], dim=dim)

    @classmethod
    def from_jsonl(cls, path: str | Path, *, dim: int = 512) -> "LocalHashRag":
        path = Path(path)
        documents = []
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    text = str(row.get("text") or "").strip()
                    if text:
                        documents.append(
                            RagDocument(
                                doc_id=str(row.get("doc_id") or len(documents)),
                                source=str(row.get("source") or path.name),
                                title=str(row.get("title") or ""),
                                text=text,
                            )
                        )
        return cls(documents, dim=dim)

    def retrieve(self, query: str, *, top_k: int = 3) -> list[dict[str, Any]]:
        query = " ".join(tokenize(query))
        if not query or not self.documents:
            return []
        query_vector = hash_text_features([query], dim=self.dim)[0]
        scores = self.matrix @ query_vector
        if not np.any(scores):
            return []
        top_indices = np.argsort(-scores)[: max(1, top_k)]
        rows = []
        for index in top_indices:
            score = float(scores[index])
            if score <= 0:
                continue
            doc = self.documents[int(index)]
            rows.append(
                {
                    "doc_id": doc.doc_id,
                    "source": doc.source,
                    "title": doc.title,
                    "score": round(score, 6),
                    "text": doc.text[:600],
                }
            )
        return rows


def augment_context_with_rag(context: str, evidence: list[dict[str, Any]]) -> str:
    if not evidence:
        return context
    snippets = [
        f"[{item.get('source')}::{item.get('title')}] {item.get('text')}"
        for item in evidence
        if item.get("text")
    ]
    return " ".join([context, *snippets]).strip()
