"""Selective residual correction over support hyperedges."""

from __future__ import annotations

import torch
from torch import Tensor, nn

__all__ = ["ResidualCorrection"]


class ResidualCorrection(nn.Module):
    """Fuse target and support representations and classify routed accounts."""

    def __init__(self, representation_dim: int, projection_dim: int, dropout: float) -> None:
        super().__init__()
        self.projection = nn.Sequential(
            nn.Linear(representation_dim * 2, projection_dim),
            nn.GELU(),
            nn.Dropout(dropout),
        )
        self.classifier = nn.Linear(projection_dim, 2)

    def forward(self, target: Tensor, support: Tensor) -> Tensor:
        fused = self.projection(torch.cat([target, support], dim=1))
        return self.classifier(fused)
