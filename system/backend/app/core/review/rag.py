"""Typed local retrieval adapters for Review evidence and policy.

The first deliverable RAG path is intentionally lightweight and reproducible:
public DISARM framework/STIX files are normalized into JSONL documents, then
queried with deterministic hash embeddings. It is a local evidence retriever,
not an online vector database or LLM generator.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
import json

import numpy as np

from app.core.review.evidence_contracts import ClaimAssessment, EvidenceBundle, PolicyBundle
from app.core.review.text_features import hash_text_features, tokenize


@dataclass(frozen=True)
class RagDocument:
    doc_id: str
    source: str
    title: str
    text: str
    source_uri: str = ""
    published_at: str = ""
    source_snapshot_hash: str = ""
    effective: bool = True


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
                                source_uri=str(row.get("source_uri") or row.get("uri") or ""),
                                published_at=str(row.get("published_at") or ""),
                                source_snapshot_hash=str(row.get("source_snapshot_hash") or ""),
                                effective=bool(row.get("effective", True)),
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
                    "source_uri": doc.source_uri,
                    "published_at": doc.published_at,
                    "source_snapshot_hash": doc.source_snapshot_hash,
                    "effective": doc.effective,
                    "score": round(score, 6),
                    "text": doc.text[:600],
                }
            )
        return rows


class EvidenceRagProvider(Protocol):
    def retrieve_evidence(
        self,
        claim: str,
        *,
        claim_assessment: ClaimAssessment = "not_assessed",
        top_k: int = 3,
    ) -> EvidenceBundle:
        """Return traceable evidence for one eligible claim."""


class PolicyRagProvider(Protocol):
    def retrieve_policy(self, query: str, *, top_k: int = 3) -> list[PolicyBundle]:
        """Return currently effective policy clauses for analyst review."""


class EvidenceRAG:
    """Claim-gated adapter over a deterministic local retriever."""

    def __init__(self, retriever: LocalHashRag | None = None):
        self.retriever = retriever

    def retrieve_evidence(
        self,
        claim: str,
        *,
        claim_assessment: ClaimAssessment = "not_assessed",
        top_k: int = 3,
    ) -> EvidenceBundle:
        normalized_claim = str(claim or "").strip()
        if claim_assessment != "checkable" or not normalized_claim:
            return EvidenceBundle(
                claim="",
                claim_assessment=claim_assessment if claim_assessment != "checkable" else "extraction_failed",
                assessment_provenance="evidence_rag",
                assessment_reason="claim_not_explicitly_checkable",
                relation="not_applicable",
                retrieval_status="skipped_non_eligible_claim",
                missing_fields=("claim",) if not normalized_claim else (),
            )
        if self.retriever is None:
            return EvidenceBundle(
                claim=normalized_claim,
                claim_assessment="checkable",
                assessment_provenance="upstream_structured_claim",
                relation="not_applicable",
                retrieval_status="provider_unavailable",
                missing_fields=("source_refs", "quoted_spans"),
            )
        try:
            rows = self.retriever.retrieve(normalized_claim, top_k=top_k)
        except Exception:
            return EvidenceBundle(
                claim=normalized_claim,
                claim_assessment="checkable",
                assessment_provenance="upstream_structured_claim",
                relation="not_applicable",
                retrieval_status="provider_failed",
            )
        source_refs = tuple(
            {
                "doc_id": item.get("doc_id"),
                "source": item.get("source"),
                "source_uri": item.get("source_uri"),
                "published_at": item.get("published_at"),
                "source_snapshot_hash": item.get("source_snapshot_hash"),
                "source_origin": "curated_evidence",
                "score": item.get("score"),
            }
            for item in rows
        )
        quoted_spans = tuple(str(item.get("text") or "")[:600] for item in rows if item.get("text"))
        return EvidenceBundle(
            claim=normalized_claim,
            claim_assessment="checkable",
            assessment_provenance="upstream_structured_claim",
            query=normalized_claim,
            source_refs=source_refs,
            quoted_spans=quoted_spans,
            relation="not_applicable",
            source_quality="unverified_local_retrieval" if rows else "unknown",
            retrieval_status="completed" if rows else "completed_no_relevant_evidence",
        )


class PolicyRAG:
    """Policy-only adapter that filters out inactive clauses."""

    def __init__(self, retriever: LocalHashRag | None = None, *, policy_version: str = ""):
        self.retriever = retriever
        self.policy_version = policy_version

    def retrieve_policy(self, query: str, *, top_k: int = 3) -> list[PolicyBundle]:
        if self.retriever is None or not str(query or "").strip():
            return []
        rows = self.retriever.retrieve(str(query), top_k=top_k)
        bundles: list[PolicyBundle] = []
        for item in rows:
            if item.get("effective", True) is False:
                continue
            bundle = PolicyBundle(
                policy_version=self.policy_version,
                clause_id=str(item.get("doc_id") or ""),
                applicability=str(item.get("title") or ""),
                effective=bool(self.policy_version and item.get("doc_id")),
                source_ref=str(item.get("source_uri") or item.get("source") or ""),
            )
            if bundle.usable:
                bundles.append(bundle)
        return bundles


class ReasonBank:
    """Offline rationale/example lookup; never a factual evidence source."""

    def __init__(self, retriever: LocalHashRag | None = None):
        self.retriever = retriever

    def retrieve(self, text: str, *, top_k: int = 3) -> list[dict[str, Any]]:
        if self.retriever is None:
            return []
        return [
            {**row, "retrieval_kind": "rationale_example"}
            for row in self.retriever.retrieve(text, top_k=top_k)
        ]


def augment_context_with_rag(context: str, evidence: list[dict[str, Any]]) -> str:
    if not evidence:
        return context
    snippets = [
        f"[{item.get('source')}::{item.get('title')}] {item.get('text')}"
        for item in evidence
        if item.get("text")
    ]
    return " ".join([context, *snippets]).strip()


__all__ = [
    "EvidenceRAG",
    "EvidenceRagProvider",
    "LocalHashRag",
    "PolicyRAG",
    "PolicyRagProvider",
    "RagDocument",
    "ReasonBank",
    "augment_context_with_rag",
]
