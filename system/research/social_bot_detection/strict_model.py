"""Strict BotRHG model components."""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import Tensor, nn
from torch.nn import functional as F

from .base_detector import BaseDetector
from .correction import ResidualCorrection

__all__ = [
    "PropertyEncoder",
    "RelationalGraphEncoder",
    "StrictBotRHGModel",
]


@dataclass(frozen=True, slots=True)
class StrictModelShape:
    """Shape metadata for the strict model stack."""

    text_dim: int
    property_dim: int
    graph_dim: int
    hidden_dim: int
    projection_dim: int


class PropertyEncoder(nn.Module):
    """Encode normalized numeric and one-hot categorical properties."""

    def __init__(self, input_dim: int, hidden_dim: int, dropout: float) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.LeakyReLU(negative_slope=0.2),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim),
            nn.LeakyReLU(negative_slope=0.2),
        )

    def forward(self, inputs: Tensor) -> Tensor:
        return self.network(inputs)


class RelationalGraphEncoder(nn.Module):
    """Two-layer relational graph encoder compatible with BotRHG graphs."""

    def __init__(self, input_dim: int, hidden_dim: int, num_relations: int, dropout: float, num_layers: int = 2) -> None:
        super().__init__()
        self.input_projection = nn.Linear(input_dim, hidden_dim)
        self.dropout = nn.Dropout(dropout)
        self.num_relations = int(max(num_relations, 0))
        self.num_layers = int(max(num_layers, 0))
        self.enabled = self.num_relations > 0 and self.num_layers > 0
        if self.enabled:
            try:
                from torch_geometric.nn import RGCNConv
            except ImportError as error:  # pragma: no cover - dependency guard
                raise ImportError("torch_geometric is required for the strict BotRHG graph encoder") from error

            self.convs = nn.ModuleList(
                [RGCNConv(hidden_dim, hidden_dim, self.num_relations) for _ in range(self.num_layers)]
            )
            self.norms = nn.ModuleList([nn.LayerNorm(hidden_dim) for _ in range(self.num_layers)])
        else:
            self.convs = nn.ModuleList()
            self.norms = nn.ModuleList()

    def forward(
        self,
        node_features: Tensor,
        edge_index: Tensor | None = None,
        edge_type: Tensor | None = None,
    ) -> Tensor:
        hidden = self.input_projection(node_features)
        if not self.enabled or edge_index is None or edge_type is None or edge_index.numel() == 0:
            return hidden
        for conv, norm in zip(self.convs, self.norms):
            hidden = conv(hidden, edge_index, edge_type)
            hidden = norm(hidden)
            hidden = F.relu(hidden)
            hidden = self.dropout(hidden)
        return hidden


class StrictBotRHGModel(nn.Module):
    """Paper-aligned BotRHG stack with text, property, graph, and correction heads."""

    def __init__(
        self,
        *,
        text_dim: int,
        property_dim: int,
        graph_dim: int,
        hidden_dim: int,
        projection_dim: int,
        dropout: float,
        num_relations: int,
    ) -> None:
        super().__init__()
        self.property_encoder = PropertyEncoder(property_dim, hidden_dim, dropout)
        self.graph_encoder = RelationalGraphEncoder(text_dim + hidden_dim, graph_dim, num_relations, dropout)
        self.base_detector = BaseDetector(graph_dim + text_dim + hidden_dim, hidden_dim, dropout)
        self.support_projection = nn.Linear(graph_dim + text_dim + hidden_dim, hidden_dim)
        self.correction = ResidualCorrection(hidden_dim, projection_dim, dropout)

    def encode_nodes(
        self,
        text_repr: Tensor,
        property_features: Tensor,
        edge_index: Tensor | None = None,
        edge_type: Tensor | None = None,
    ) -> tuple[Tensor, Tensor, Tensor, Tensor, Tensor]:
        """Return the node features used by the base and correction stages."""

        property_repr = self.property_encoder(property_features)
        node_features = torch.cat([text_repr, property_repr], dim=1)
        graph_repr = self.graph_encoder(node_features, edge_index, edge_type)
        combined = torch.cat([graph_repr, node_features], dim=1)
        support_anchor = self.support_projection(combined)
        logits, low_order_repr = self.base_detector(combined)
        return logits, low_order_repr, combined, support_anchor, property_repr
