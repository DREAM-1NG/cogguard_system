"""Low-order trainable account detector."""

from __future__ import annotations

import torch
from torch import Tensor, nn

__all__ = ["BaseDetector"]


class BaseDetector(nn.Module):
    """Predict account labels from learned text representations."""

    def __init__(self, input_dim: int, hidden_dim: int, dropout: float) -> None:
        super().__init__()
        self.representation = nn.Sequential(
            nn.LayerNorm(input_dim),
            nn.Linear(input_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
        )
        self.classifier = nn.Linear(hidden_dim, 2)

    def forward(self, inputs: Tensor) -> tuple[Tensor, Tensor]:
        representation = self.representation(inputs)
        return self.classifier(representation), representation
