import torch

from research.social_bot_detection.hypergraph import build_reference_hyperedges, build_support_hyperedges, neighbor_similarities, propagate_support
from research.social_bot_detection.reliability import select_routed_accounts


def test_support_hyperedges_exclude_target_account():
    representation = torch.eye(4)
    neighbors = build_support_hyperedges(representation, support_k=2)
    assert neighbors.shape == (4, 2)
    for index, row in enumerate(neighbors.tolist()):
        assert index not in row
    weights = neighbor_similarities(representation, neighbors)
    assert torch.all(weights >= 0)
    assert propagate_support(representation, neighbors, weights).shape == representation.shape


def test_routing_budget_selects_highest_risk_accounts():
    selected = select_routed_accounts(torch.tensor([0.1, 0.9, 0.4, 0.8]), 0.5)
    assert selected.tolist() == [1, 3]


def test_reference_hyperedges_use_bounded_query_chunks():
    query = torch.eye(4)
    neighbors = build_reference_hyperedges(query, query, support_k=2, query_chunk_size=1)
    assert neighbors.shape == (4, 2)
    assert torch.equal(neighbors[:, 0], torch.arange(4))
