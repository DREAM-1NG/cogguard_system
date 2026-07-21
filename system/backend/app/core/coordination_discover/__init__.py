"""Canonical Coordination Discover facade.

The current implementation remains in ``app.core.coordination`` during the
semantic migration window. This package exposes Coordination Discover entry points
without duplicating baseline business logic.
"""

from app.core.coordination.characterization_runner import run_dyna_colm_characterize
from app.core.coordination.io_reproduction import DEFAULT_RELATIONS
from app.core.coordination.io_reproduction import build_unmasking_similarity_graphs
from app.core.coordination.io_reproduction import fuse_similarity_graphs
from app.core.coordination.io_reproduction import normalize_event_table
from app.core.coordination.io_reproduction import read_event_table
from app.core.coordination.io_reproduction import run_dyna_colm_discover
from app.core.coordination.network import generate_coordinated_network, graph_to_dict

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
