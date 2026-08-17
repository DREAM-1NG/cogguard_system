"""Coordination Detect validation boundary.

Coordination Detect is the supervised validation layer for public labeled
datasets. It reuses Coordination Discover representations and must not become
the three-platform event labeler without approved labels.
"""

from __future__ import annotations

import importlib.util as _importlib_util
import sys as _sys
from pathlib import Path as _Path

_DISCOVER_DIR = _Path(__file__).resolve().parents[1] / "coordination_discover"
_MODULE_NAME = "_cogguard_coordination_discover_for_detect"
_cached = _sys.modules.get(_MODULE_NAME)
if _cached is None:
    _spec = _importlib_util.spec_from_file_location(
        _MODULE_NAME,
        _DISCOVER_DIR / "__init__.py",
        submodule_search_locations=[str(_DISCOVER_DIR)],
    )
    if _spec is None or _spec.loader is None:
        raise ImportError(f"Cannot load Coordination Discover package from {_DISCOVER_DIR}")
    _cached = _importlib_util.module_from_spec(_spec)
    _sys.modules[_MODULE_NAME] = _cached
    _spec.loader.exec_module(_cached)

DetectValidationRequest = _cached.DetectValidationRequest
DetectValidationResult = _cached.DetectValidationResult
run_detect_validation = _cached.run_detect_validation

from .contracts import ClusterDetectionBatch, ClusterDetectionVerdict, DetectionModelArtifact
# Shadow/baseline-only: the system primary Detection artifact is SocGFM.
from .learned import LearnedCoordinationDetector
from .socgfm import (
    SOCGFM_CROSS_ATTENTION_MODEL_ROLE,
    SOCGFM_CROSS_ATTENTION_MODEL_VERSION,
    SocGFMCrossAttentionArtifact,
    SocGFMCrossAttentionDetector,
)

__all__ = [
    "ClusterDetectionBatch",
    "ClusterDetectionVerdict",
    "DetectValidationRequest",
    "DetectValidationResult",
    "DetectionModelArtifact",
    "LearnedCoordinationDetector",
    "SOCGFM_CROSS_ATTENTION_MODEL_ROLE",
    "SOCGFM_CROSS_ATTENTION_MODEL_VERSION",
    "SocGFMCrossAttentionArtifact",
    "SocGFMCrossAttentionDetector",
    "run_detect_validation",
]
