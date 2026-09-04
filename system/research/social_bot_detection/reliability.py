"""Reliability-guided routing from base posterior and local references."""

from __future__ import annotations

import torch
from torch import Tensor

__all__ = ["compute_correction_risk", "select_routed_accounts"]


def compute_correction_risk(
    probabilities: Tensor,
    neighbors: Tensor,
    weights: Tensor | None = None,
) -> Tensor:
    """Estimate local correction risk without using target labels.

    Risk combines confidence deficit with disagreement between a target's base
    posterior and the similarity neighborhood's posterior. The reference
    weights are derived from representation similarity supplied by callers in
    the full training path; this compact form keeps the routing contract
    deterministic and label-free.
    """

    confidence_deficit = 1.0 - probabilities.max(dim=1).values
    if neighbors.numel() == 0:
        return confidence_deficit
    reference_values = probabilities[neighbors]
    if weights is None:
        reference = reference_values.mean(dim=1)
    else:
        normalized_weights = weights / weights.sum(dim=1, keepdim=True).clamp_min(1e-8)
        reference = (reference_values * normalized_weights.unsqueeze(-1)).sum(dim=1)
    disagreement = (reference - probabilities).abs().mean(dim=1)
    return (0.5 * confidence_deficit + 0.5 * disagreement).clamp(0.0, 1.0)


def select_routed_accounts(risk: Tensor, routing_budget: float) -> Tensor:
    """Select the highest-risk accounts under a fractional budget."""

    if risk.ndim != 1:
        raise ValueError("risk must have shape [accounts]")
    budget = min(max(float(routing_budget), 0.0), 1.0)
    count = int(torch.ceil(torch.tensor(risk.numel() * budget)).item()) if budget else 0
    if count == 0 or risk.numel() == 0:
        return torch.empty((0,), dtype=torch.long, device=risk.device)
    return torch.topk(risk, k=min(count, risk.numel()), largest=True, sorted=True).indices
