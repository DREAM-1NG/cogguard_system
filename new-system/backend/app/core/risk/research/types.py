"""研究复现统一 schema。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RiskTask(str, Enum):
    HARMFUL = "harmful"
    STANCE = "stance"


class RiskSplit(str, Enum):
    TRAIN = "train"
    DEV = "dev"
    TEST = "test"
    UNSPECIFIED = "unspecified"


@dataclass(frozen=True)
class ResearchSample:
    dataset: str
    task: RiskTask
    text: str
    label: str
    target: str | None = None
    split: RiskSplit = RiskSplit.UNSPECIFIED
    sample_id: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)
