"""Sequence joint model used by Propagation Analysis checkpoint inference."""

from __future__ import annotations


def safe_torch():
    """Import PyTorch lazily so unavailable ML dependencies produce abstain results."""
    try:
        import torch
        import torch.nn as nn
    except Exception as exc:  # pragma: no cover - environment dependent.
        return None, None, exc
    return torch, nn, None


def _masked_mean(torch, values, mask, dim: int):
    mask = mask.unsqueeze(-1).to(values.dtype)
    return (values * mask).sum(dim=dim) / mask.sum(dim=dim).clamp_min(1.0)


def make_sequence_joint_model(torch, nn, user_hash_buckets: int, hidden_dim: int, trend_steps: int, hyperedge_count: int):
    """Build the runtime model matching the deployed Twitter checkpoint."""

    class GradientReversal(torch.autograd.Function):
        @staticmethod
        def forward(ctx, value, alpha: float):
            ctx.alpha = alpha
            return value.view_as(value)

        @staticmethod
        def backward(ctx, grad_output):
            return -ctx.alpha * grad_output, None

    class RelationGNN(nn.Module):
        def __init__(self, emb_dim: int) -> None:
            super().__init__()
            self.message = nn.Sequential(nn.Linear(emb_dim * 2, hidden_dim), nn.ReLU())

        def forward(self, user_emb, neighbor_emb, seq_users):
            neighbor_state = neighbor_emb.mean(dim=2)
            relation_tokens = self.message(torch.cat([user_emb, neighbor_state], dim=-1))
            return _masked_mean(torch, relation_tokens, seq_users.ne(0), dim=1)

    class DynamicCasHGNN(nn.Module):
        def __init__(self, emb_dim: int) -> None:
            super().__init__()
            self.hyperedge_update = nn.Sequential(nn.Linear(emb_dim, hidden_dim), nn.ReLU())
            self.stage_attention = nn.Linear(hidden_dim, 1)

        def forward(self, hyperedge_emb, hyperedge_users):
            node_mask = hyperedge_users.ne(0)
            edge_state = _masked_mean(torch, hyperedge_emb, node_mask, dim=2)
            edge_state = self.hyperedge_update(edge_state)
            edge_mask = node_mask.any(dim=2)
            attention = self.stage_attention(edge_state).squeeze(-1)
            attention = attention.masked_fill(~edge_mask, -1e9)
            weights = torch.softmax(attention, dim=1).unsqueeze(-1)
            weights = torch.where(edge_mask.unsqueeze(-1), weights, torch.zeros_like(weights))
            denominator = weights.sum(dim=1).clamp_min(1e-6)
            return (edge_state * weights).sum(dim=1) / denominator

    class EulerTrendDecoder(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.dynamics = nn.Sequential(
                nn.Linear(hidden_dim + 2, hidden_dim), nn.Tanh(), nn.Linear(hidden_dim, hidden_dim)
            )
            self.increment = nn.Linear(hidden_dim, 1)

        def forward(self, macro_repr, observed_log, obs_ratios):
            latent = macro_repr
            current = observed_log
            checkpoints = []
            dt = 1.0 / float(trend_steps)
            for step in range(1, trend_steps + 1):
                time_value = torch.full(
                    (macro_repr.shape[0], 1), step / float(trend_steps), device=macro_repr.device
                )
                latent = latent + dt * self.dynamics(
                    torch.cat([latent, time_value, obs_ratios.unsqueeze(-1)], dim=-1)
                )
                delta = torch.nn.functional.softplus(self.increment(latent).squeeze(-1)) * dt
                current = current + delta
                checkpoints.append(current)
            return torch.stack(checkpoints, dim=1)

    class PropagationSequenceJointModel(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            emb_dim = max(8, hidden_dim // 2)
            self.user_embedding = nn.Embedding(user_hash_buckets, emb_dim, padding_idx=0)
            self.relation_gnn = RelationGNN(emb_dim)
            self.dynamic_cascade_hgnn = DynamicCasHGNN(emb_dim)
            self.shared_lstm = nn.LSTM(emb_dim + hidden_dim + 1, hidden_dim, batch_first=True)
            self.shared_projection = nn.Sequential(nn.Linear(hidden_dim * 3 + 2, hidden_dim), nn.ReLU())
            self.macro_private = nn.Sequential(nn.Linear(hidden_dim, hidden_dim), nn.ReLU())
            self.micro_private = nn.Sequential(nn.Linear(hidden_dim, hidden_dim), nn.ReLU())
            self.final_growth_head = nn.Linear(hidden_dim, 1)
            self.trend_decoder = EulerTrendDecoder()
            self.user_decoder = nn.Linear(hidden_dim, emb_dim)
            self.stage_adversary = nn.Linear(hidden_dim, hyperedge_count)

        def forward(self, seq_users, seq_times, relation_neighbors, hyperedge_users, observed_counts, obs_ratios):
            embedding = self.user_embedding(seq_users)
            relation_embedding = self.user_embedding(relation_neighbors)
            relation_context = self.relation_gnn(embedding, relation_embedding, seq_users)
            relation_tokens = relation_context.unsqueeze(1).expand(-1, seq_users.shape[1], -1)
            sequence_input = torch.cat([embedding, relation_tokens, seq_times.unsqueeze(-1)], dim=-1)
            _output, (hidden, _cell) = self.shared_lstm(sequence_input)
            hyperedge_embedding = self.user_embedding(hyperedge_users)
            hypergraph_context = self.dynamic_cascade_hgnn(hyperedge_embedding, hyperedge_users)
            shared = self.shared_projection(
                torch.cat(
                    [
                        hidden[-1],
                        relation_context,
                        hypergraph_context,
                        torch.log1p(observed_counts).unsqueeze(-1),
                        obs_ratios.unsqueeze(-1),
                    ],
                    dim=-1,
                )
            )
            macro_repr = self.macro_private(shared)
            micro_repr = self.micro_private(shared)
            observed_log = torch.log1p(observed_counts)
            final_log = observed_log + torch.nn.functional.softplus(self.final_growth_head(macro_repr).squeeze(-1))
            trend_log = self.trend_decoder(macro_repr, observed_log, obs_ratios)
            final_log = torch.maximum(final_log, trend_log[:, -1])
            decoder_state = self.user_decoder(micro_repr)
            return final_log, trend_log, decoder_state, shared, macro_repr, micro_repr

        def adversarial_logits(self, shared, alpha: float = 1.0):
            return self.stage_adversary(GradientReversal.apply(shared, alpha))

    return PropagationSequenceJointModel()


__all__ = [
    "make_sequence_joint_model",
    "safe_torch",
]
