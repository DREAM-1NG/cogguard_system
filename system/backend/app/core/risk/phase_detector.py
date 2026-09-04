"""Compatibility wrapper for `app.core.review.phase_detector`."""

from importlib import import_module as _import_module
import sys as _sys

_LEGACY_NAME = __name__
_module = _import_module("app.core.review.phase_detector")
_sys.modules[_LEGACY_NAME] = _module
globals().update(_module.__dict__)