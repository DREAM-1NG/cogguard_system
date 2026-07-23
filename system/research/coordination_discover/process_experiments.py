from __future__ import annotations

from collections import Counter, defaultdict
from statistics import median
from typing import Any

from .contracts import EvidenceGraph


def build_process_causal_experiment_report(graph: EvidenceGraph) -> dict[str, Any]:
    """Extract process-mining candidates without making causal claims."""

    motifs = _process_motifs(graph)
    return {
        "status": "ready_for_exploratory_validation" if motifs else "data_insufficient",
        "role": "exploratory_non_claimable",
        "claim_boundary": "process motifs are descriptive evidence; causal tests require a separate protocol",
        "process_motifs": motifs,
        "causal_tests": {
            "status": "not_run",
            "reason": "requires labeled interventions or lagged exogenous variables",
        },
    }


def _process_motifs(graph: EvidenceGraph) -> list[dict[str, Any]]:
    by_account: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in graph.edges:
        by_account[edge.source_account_id].append(
            {
                "account_id": edge.source_account_id,
                "evidence_kind": edge.evidence_kind,
                "relation_type": edge.relation_type,
                "content_id": edge.content_id,
                "observed_at": float(edge.observed_at),
            }
        )

    motif_counts: Counter[tuple[str, str]] = Counter()
    motif_deltas: dict[tuple[str, str], list[float]] = defaultdict(list)
    for rows in by_account.values():
        ordered = sorted(rows, key=lambda item: (item["observed_at"], item["content_id"], item["relation_type"]))
        for left, right in zip(ordered, ordered[1:]):
            if left["evidence_kind"] == right["evidence_kind"]:
                continue
            motif = (str(left["evidence_kind"]), str(right["evidence_kind"]))
            motif_counts[motif] += 1
            motif_deltas[motif].append(max(0.0, float(right["observed_at"]) - float(left["observed_at"])))

    rows = []
    for (source_kind, target_kind), count in motif_counts.most_common(25):
        deltas = motif_deltas[(source_kind, target_kind)]
        rows.append(
            {
                "motif": f"{source_kind}->{target_kind}",
                "source_evidence_kind": source_kind,
                "target_evidence_kind": target_kind,
                "support_count": int(count),
                "median_delta_seconds": round(float(median(deltas)) if deltas else 0.0, 6),
            }
        )
    return rows


__all__ = ["build_process_causal_experiment_report"]
