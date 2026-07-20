"""Compatibility wrapper for `app.core.review.kt3_trainable_post`."""

from importlib import import_module as _import_module
import sys as _sys

_LEGACY_NAME = __name__
_module = _import_module("app.core.review.kt3_trainable_post")
_sys.modules[_LEGACY_NAME] = _module
globals().update(_module.__dict__)