"""Target-centered KNN support hyperedges from learned representations."""

from __future__ import annotations

import torch
from torch import Tensor
import torch.nn.functional as F

__all__ = ["build_reference_hyperedges", "build_support_hyperedges", "neighbor_similarities", "propagate_support"]


def build_support_hyperedges(
    representations: Tensor,
    support_k: int,
    *,
    query_chunk_size: int = 512,
) -> Tensor:
    """Return exact target-centered KNN neighbors without an NxN allocation."""

    if representations.ndim != 2:
        raise ValueError("representations must have shape [accounts, dimensions]")
    count = representations.shape[0]
    if count < 2:
        return torch.empty((count, 0), dtype=torch.long, device=representations.device)
    k = min(max(int(support_k), 1), count - 1)
    normalized = F.normalize(representations, p=2, dim=1)
    chunks: list[Tensor] = []
    chunk_size = max(1, int(query_chunk_size))
    for start in range(0, count, chunk_size):
        stop = min(start + chunk_size, count)
        similarities = normalized[start:stop] @ normalized.T
        offsets = torch.arange(stop - start, device=representations.device)
        similarities[offsets, offsets + start] = -torch.inf
        chunks.append(similarities.topk(k=k, dim=1).indices)
    return torch.cat(chunks, dim=0)


def build_reference_hyperedges(
    query: Tensor,
    reference: Tensor,
    support_k: int,
    *,
    query_chunk_size: int = 512,
) -> Tensor:
    """Return exact query-to-reference KNN neighbors with bounded memory."""

    if query.ndim != 2 or reference.ndim != 2 or query.shape[1] != reference.shape[1]:
        raise ValueError("query and reference must be rank-two tensors with equal dimensions")
    if reference.shape[0] == 0:
        return torch.empty((query.shape[0], 0), dtype=torch.long, device=query.device)
    k = min(max(int(support_k), 1), reference.shape[0])
    query_normalized = F.normalize(query, p=2, dim=1)
    reference_normalized = F.normalize(reference, p=2, dim=1)
    chunks: list[Tensor] = []
    chunk_size = max(1, int(query_chunk_size))
    for start in range(0, query.shape[0], chunk_size):
        similarities = query_normalized[start : start + chunk_size] @ reference_normalized.T
        chunks.append(similarities.topk(k=k, dim=1).indices)
    return torch.cat(chunks, dim=0)


def propagate_support(representations: Tensor, neighbors: Tensor, weights: Tensor | None = None) -> Tensor:
    """Aggregate each target-centered support hyperedge representation."""

    if neighbors.numel() == 0:
        return torch.zeros_like(representations)
    values = representations[neighbors]
    if weights is None:
        return values.mean(dim=1)
    normalized_weights = weights / weights.sum(dim=1, keepdim=True).clamp_min(1e-8)
    return (values * normalized_weights.unsqueeze(-1)).sum(dim=1)


def neighbor_similarities(representations: Tensor, neighbors: Tensor) -> Tensor:
    """Return non-negative cosine similarities aligned with each hyperedge."""

    if neighbors.numel() == 0:
        return torch.empty_like(neighbors, dtype=representations.dtype)
    normalized = F.normalize(representations, p=2, dim=1)
    return (normalized.unsqueeze(1) * normalized[neighbors]).sum(dim=2).clamp_min(0.0)
