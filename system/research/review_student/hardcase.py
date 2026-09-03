"""Uncertainty-based Hardcase selection outside the Student model."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any


def binary_entropy(probability: float) -> float:
    value = min(1.0 - 1e-7, max(1e-7, float(probability)))
    return -(value * math.log2(value) + (1.0 - value) * math.log2(1.0 - value))


def rank_hardcases(rows: Sequence[Mapping[str, Any]], *, ratio: float) -> list[dict[str, Any]]:
    if not 0.0 < float(ratio) <= 1.0:
        raise ValueError("Hardcase ratio must be in (0, 1]")
    ranked = []
    for row in rows:
        attack = float(row.get("attack_hate_offense", 0.5))
        misinfo = float(row.get("misinfo_claim_risk", 0.5))
        uncertainty = max(binary_entropy(attack), binary_entropy(misinfo))
        ranked.append({**dict(row), "uncertainty": round(uncertainty, 6)})
    ranked.sort(key=lambda row: (-float(row["uncertainty"]), str(row.get("case_id") or "")))
    count = max(1, math.ceil(len(ranked) * float(ratio))) if ranked else 0
    return ranked[:count]


__all__ = ["binary_entropy", "rank_hardcases"]
