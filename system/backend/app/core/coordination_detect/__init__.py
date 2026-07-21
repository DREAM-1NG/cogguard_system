"""Canonical Coordination Detect facade.

The current KT1 implementation remains in ``app.core.coordination`` during the
semantic migration window. This package exposes validation and baseline detect
entry points without creating an independent detector implementation.
"""

from app.core.coordination.detector import detect_groups, flag_speed_share
from app.core.coordination.stats import account_stats, group_stats

__all__ = [
    "account_stats",
    "detect_groups",
    "flag_speed_share",
    "group_stats",
]
