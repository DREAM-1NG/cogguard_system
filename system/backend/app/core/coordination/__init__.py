"""Coordination Discover / Detect baseline compatibility package.

This package exposes the Python CooRTweet-style baseline while newer KT1
research adapters continue to use the governed Coordination Discover / Detect
method language.
"""

from app.core.coordination.detector import detect_groups, flag_speed_share
from app.core.coordination.network import generate_coordinated_network
from app.core.coordination.stats import account_stats, group_stats
from app.core.coordination.characterization_runner import run_dyna_colm_characterize

__all__ = [
    "detect_groups",
    "flag_speed_share",
    "generate_coordinated_network",
    "account_stats",
    "group_stats",
    "run_dyna_colm_characterize",
]
