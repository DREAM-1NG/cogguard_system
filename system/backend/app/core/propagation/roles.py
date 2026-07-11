from __future__ import annotations

from app.core.propagation.types import BetweennessScores, PropagationGraph


def identify_key_roles(G: PropagationGraph, bc: BetweennessScores) -> dict:
    if G.number_of_nodes() == 0:
        return {"originators": [], "bridges": [], "amplifiers": []}

    originators = []
    for node_id in G.nodes():
        out_degree = G.out_degree(node_id)
        in_degree = G.in_degree(node_id)
        if out_degree > 0 and out_degree >= in_degree:
            originators.append(
                {
                    "account_id": node_id,
                    "out_degree": out_degree,
                    "in_degree": in_degree,
                    "author_name": G.nodes[node_id].get("author_name", node_id),
                }
            )
    originators.sort(key=lambda item: item["out_degree"], reverse=True)

    bridges = []
    for node_id, score in sorted(bc.items(), key=lambda item: item[1], reverse=True):
        in_degree = G.in_degree(node_id)
        out_degree = G.out_degree(node_id)
        if score > 0:
            bridges.append(
                {
                    "account_id": node_id,
                    "betweenness": round(score, 4),
                    "bridge_score": round(score, 4),
                    "in_degree": in_degree,
                    "out_degree": out_degree,
                    "author_name": G.nodes[node_id].get("author_name", node_id),
                }
            )
        if len(bridges) >= 10:
            break

    if not bridges:
        relay_candidates = []
        for node_id in G.nodes():
            in_degree = G.in_degree(node_id)
            out_degree = G.out_degree(node_id)
            if in_degree > 0 and out_degree > 0:
                relay_candidates.append(
                    {
                        "account_id": node_id,
                        "betweenness": round(float(bc.get(node_id, 0.0)), 4),
                        "bridge_score": round((2 * in_degree * out_degree) / max(in_degree + out_degree, 1), 4),
                        "in_degree": in_degree,
                        "out_degree": out_degree,
                        "author_name": G.nodes[node_id].get("author_name", node_id),
                    }
                )
        relay_candidates.sort(
            key=lambda item: (
                item["bridge_score"],
                item["out_degree"],
                item["in_degree"],
            ),
            reverse=True,
        )
        bridges = relay_candidates[:10]

    amplifiers = []
    for node_id in G.nodes():
        in_degree = G.in_degree(node_id)
        if in_degree > 0:
            amplifiers.append(
                {
                    "account_id": node_id,
                    "in_degree": in_degree,
                    "author_name": G.nodes[node_id].get("author_name", node_id),
                }
            )
    amplifiers.sort(key=lambda item: item["in_degree"], reverse=True)

    return {
        "originators": originators[:10],
        "bridges": bridges[:10],
        "amplifiers": amplifiers[:10],
    }
