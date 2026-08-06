from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, ClassVar, Literal, TypeAlias, cast


CoordinationRelationKind: TypeAlias = Literal[
    "shared_url",
    "shared_domain",
    "shared_hashtag",
    "shared_keyword",
    "shared_entity",
    "shared_target",
    "discussion_target",
    "repost_target",
    "reply_target",
    "mention_target",
    "near_duplicate",
    "native_relation",
    "higher_order",
]
CANONICAL_COORDINATION_RELATIONS: frozenset[str] = frozenset(
    {
        "shared_url",
        "shared_domain",
        "shared_hashtag",
        "shared_keyword",
        "shared_entity",
        "shared_target",
        "discussion_target",
        "repost_target",
        "reply_target",
        "mention_target",
        "near_duplicate",
        "native_relation",
        "higher_order",
    }
)


def validate_coordination_relation(value: object) -> CoordinationRelationKind:
    if not isinstance(value, str) or value.strip() not in CANONICAL_COORDINATION_RELATIONS:
        raise ValueError("relation must be a canonical label-free relation")
    return cast(CoordinationRelationKind, value.strip())


@dataclass(frozen=True, slots=True)
class CoordinationEvent:
    account_id: str
    relation: CoordinationRelationKind
    object_id: str
    observed_at: datetime
    weight: float
    evidence_ref: str

    _FIELDS: ClassVar[frozenset[str]] = frozenset(
        {"account_id", "relation", "object_id", "observed_at", "weight", "evidence_ref"}
    )
    _FORBIDDEN_LABEL_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {"label", "risk", "verdict", "class", "bot", "harmful"}
    )

    def __post_init__(self) -> None:
        for field_name in ("account_id", "relation", "object_id", "evidence_ref"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")
            object.__setattr__(self, field_name, value.strip())
        object.__setattr__(self, "relation", validate_coordination_relation(self.relation))

        if not isinstance(self.observed_at, datetime):
            raise ValueError("observed_at must be a timezone-aware datetime")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be a timezone-aware datetime")
        object.__setattr__(self, "observed_at", self.observed_at.astimezone(timezone.utc))

        if isinstance(self.weight, bool) or not isinstance(self.weight, (int, float)):
            raise ValueError("weight must be a finite non-negative number")
        weight = float(self.weight)
        if not math.isfinite(weight) or weight < 0.0:
            raise ValueError("weight must be a finite non-negative number")
        object.__setattr__(self, "weight", weight)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "CoordinationEvent":
        if not isinstance(value, Mapping):
            raise ValueError("CoordinationEvent input must be a mapping")
        actual_fields = set(value)
        forbidden = actual_fields & cls._FORBIDDEN_LABEL_FIELDS
        if forbidden:
            raise ValueError(f"CoordinationEvent contains forbidden label-bearing fields: {sorted(forbidden)}")
        unknown = actual_fields - cls._FIELDS
        if unknown:
            raise ValueError(f"CoordinationEvent contains unknown fields: {sorted(map(str, unknown))}")
        missing = cls._FIELDS - actual_fields
        if missing:
            raise ValueError(f"CoordinationEvent is missing required fields: {sorted(missing)}")

        observed_at = value["observed_at"]
        if isinstance(observed_at, str):
            normalized = f"{observed_at[:-1]}+00:00" if observed_at.endswith("Z") else observed_at
            try:
                observed_at = datetime.fromisoformat(normalized)
            except ValueError as exc:
                raise ValueError("observed_at must be an ISO-8601 timestamp") from exc

        return cls(
            account_id=value["account_id"],
            relation=value["relation"],
            object_id=value["object_id"],
            observed_at=observed_at,
            weight=value["weight"],
            evidence_ref=value["evidence_ref"],
        )


__all__ = [
    "CANONICAL_COORDINATION_RELATIONS",
    "CoordinationEvent",
    "CoordinationRelationKind",
    "validate_coordination_relation",
]
