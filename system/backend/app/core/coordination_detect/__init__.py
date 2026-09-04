"""Canonical Coordination Detect facade over ``app.core.coordination_baseline``.

The historical ``app.core.coordination`` package remains a one-release
compatibility alias. This facade reaches the baseline implementation directly
without creating an independent detector implementation.
"""

from app.core.coordination_baseline.detector import detect_groups, flag_speed_share
from app.core.coordination_baseline.pretrained_detect import PRETRAINED_CHECKPOINT_PATH
from app.core.coordination_baseline.pretrained_detect import ensure_china_pretrained_fusion_checkpoint
from app.core.coordination_baseline.pretrained_detect import run_china_pretrained_detect
from app.core.coordination_baseline.reproduction_common import extract_labels
from app.core.coordination_baseline.reproduction_detect import run_dyna_colm_detect
from app.core.coordination_baseline.stats import account_stats, group_stats

__all__ = [
    "PRETRAINED_CHECKPOINT_PATH",
    "account_stats",
    "detect_groups",
    "ensure_china_pretrained_fusion_checkpoint",
    "extract_labels",
    "flag_speed_share",
    "group_stats",
    "run_china_pretrained_detect",
    "run_dyna_colm_detect",
]
