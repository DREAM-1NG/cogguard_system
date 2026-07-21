"""Canonical Coordination Discover facade.

The current KT1 implementation remains in ``app.core.coordination`` during the
semantic migration window. This package exposes discovery-facing entry points
without duplicating baseline business logic.
"""

from app.core.coordination.characterization_runner import run_dyna_colm_characterize
from app.core.coordination.network import generate_coordinated_network

__all__ = [
    "generate_coordinated_network",
    "run_dyna_colm_characterize",
]
