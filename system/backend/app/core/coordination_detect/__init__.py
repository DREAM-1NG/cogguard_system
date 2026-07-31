"""Canonical Coordination Detect facade.

The current implementation remains in ``app.core.coordination`` during the
semantic migration window. This package exposes Coordination Detect and validation
entry points without creating an independent detector implementation.
"""

from app.core.coordination.detector import detect_groups, flag_speed_share
from app.core.coordination.io_reproduction import extract_labels
from app.core.coordination.io_reproduction import run_dyna_colm_detect
from app.core.coordination.pretrained_detect import PRETRAINED_CHECKPOINT_PATH
from app.core.coordination.pretrained_detect import ensure_china_pretrained_fusion_checkpoint
from app.core.coordination.pretrained_detect import run_china_pretrained_detect
from app.core.coordination.stats import account_stats, group_stats

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
