"""Canonical Risk Review facade.

The KT3 implementation remains in ``app.core.risk`` during the one-version
semantic migration window. This package is intentionally thin: it exposes the
same public module names lazily and must not contain independent business logic.
"""

from __future__ import annotations

from importlib import import_module
from types import ModuleType

from app.core import risk as _risk

__all__ = list(_risk.__all__)


def __getattr__(name: str) -> ModuleType:
    if name in __all__:
        return import_module(f"app.core.risk.{name}")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
