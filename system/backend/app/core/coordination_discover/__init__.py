"""Canonical Coordination Discover facade over ``app.core.coordination_baseline``.

The historical ``app.core.coordination`` package remains a one-release
compatibility alias. This facade reaches the baseline implementation directly
without duplicating business logic or routing new callers through that alias.
"""

from app.core.coordination_baseline.characterization_runner import run_dyna_colm_characterize
from app.core.coordination_baseline.network import generate_coordinated_network, graph_to_dict
from app.core.coordination_baseline.reproduction_common import (
    DEFAULT_RELATIONS,
    normalize_event_table,
    read_event_table,
)
from app.core.coordination_baseline.reproduction_discover_runtime import run_dyna_colm_discover
from app.core.coordination_baseline.reproduction_graphs import (
    build_unmasking_similarity_graphs,
    fuse_similarity_graphs,
)

__all__ = [
    "DEFAULT_RELATIONS",
    "build_unmasking_similarity_graphs",
    "fuse_similarity_graphs",
    "generate_coordinated_network",
    "graph_to_dict",
    "normalize_event_table",
    "read_event_table",
    "run_dyna_colm_characterize",
    "run_dyna_colm_discover",
]
