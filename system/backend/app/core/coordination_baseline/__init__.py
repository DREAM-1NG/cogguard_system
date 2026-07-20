"""Canonical coordination baseline implementation boundary.

This package contains the CooRTweet-style fallback implementation used by the
analysis runtime when no approved Coordination Discover artifact is available.
The old ``app.core.coordination`` package is a thin compatibility alias.
"""

from app.core.coordination_baseline.characterization_runner import run_dyna_colm_characterize
from app.core.coordination_baseline.detector import detect_groups, flag_speed_share
from app.core.coordination_baseline.network import generate_coordinated_network
from app.core.coordination_baseline.stats import account_stats, group_stats

__all__ = [
    "account_stats",
    "detect_groups",
    "flag_speed_share",
    "generate_coordinated_network",
    "group_stats",
    "run_dyna_colm_characterize",
]
