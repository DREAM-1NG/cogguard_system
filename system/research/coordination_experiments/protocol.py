from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping as MappingABC, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping


_SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_CAPABILITY_FIELDS = {
    "coordination_discovery": "supports_coordination_discovery",
    "external_label_evaluation": "supports_external_label_evaluation",
    "campaign_holdout": "supports_campaign_holdout",
    "observed_time_holdout": "supports_time_holdout",
    "social_bot_classification": "supports_social_bot_classification",
    "harmful_cib_detection": "supports_harmful_cib_detection",
    "campaign_io_evaluation": "supports_campaign_io_evaluation",
}


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _fingerprint(value: Mapping[str, Any]) -> str:
    return f"sha256:{hashlib.sha256(_canonical_json(value)).hexdigest()}"


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _seed(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("seed must be an integer")
    return value


def _non_negative_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


def _text_tuple(values: Any, field_name: str, *, allow_empty: bool = True) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ValueError(f"{field_name} must be a sequence of strings")
    result = tuple(sorted({_required_text(value, field_name) for value in values}))
    if not allow_empty and not result:
        raise ValueError(f"{field_name} must be non-empty")
    return result


def _text_mapping(value: Any, field_name: str) -> Mapping[str, str]:
    if not isinstance(value, MappingABC):
        raise ValueError(f"{field_name} must be a mapping")
    normalized = {
        _required_text(key, f"{field_name} key"): _required_text(item, f"{field_name} value")
        for key, item in value.items()
    }
    return MappingProxyType(dict(sorted(normalized.items())))


def _schema(value: Any, field_name: str, fields: frozenset[str]) -> Mapping[str, Any]:
    if not isinstance(value, MappingABC):
        raise ValueError(f"{field_name} must be a mapping")
    actual = set(value)
    unknown = actual - fields
    if unknown:
        raise ValueError(f"{field_name} contains unknown fields: {sorted(map(str, unknown))}")
    missing = fields - actual
    if missing:
        raise ValueError(f"{field_name} is missing required fields: {sorted(missing)}")
    return value


def _validate_declared_fingerprint(value: Any, actual: str, field_name: str) -> None:
    if _required_text(value, field_name) != actual:
        raise ValueError(f"{field_name} does not match canonical payload")


@dataclass(frozen=True, slots=True)
class DatasetCapability:
    dataset_id: str
    supports_coordination_discovery: bool
    supports_external_label_evaluation: bool
    supports_campaign_holdout: bool
    supports_time_holdout: bool
    supports_social_bot_classification: bool
    supports_harmful_cib_detection: bool
    supports_campaign_io_evaluation: bool
    blocked_reasons: Mapping[str, str] = field(default_factory=dict)
    claim_markers: tuple[str, ...] = ()

    _FIELDS = frozenset(
        {
            "dataset_id",
            *_CAPABILITY_FIELDS.values(),
            "blocked_reasons",
            "claim_markers",
            "fingerprint",
        }
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "dataset_id", _required_text(self.dataset_id, "dataset_id"))
        for field_name in _CAPABILITY_FIELDS.values():
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name} must be boolean")
        reasons = _text_mapping(self.blocked_reasons, "blocked_reasons")
        object.__setattr__(self, "blocked_reasons", reasons)
        object.__setattr__(self, "claim_markers", _text_tuple(self.claim_markers, "claim_markers"))
        for task, field_name in _CAPABILITY_FIELDS.items():
            supported = getattr(self, field_name)
            if not supported and task not in reasons:
                raise ValueError(f"unsupported capability {task} requires a blocked reason")
            if supported and task in reasons:
                raise ValueError(f"supported capability {task} cannot have a blocked reason")
        unknown_tasks = set(reasons) - set(_CAPABILITY_FIELDS)
        if unknown_tasks:
            raise ValueError(f"blocked_reasons contains unknown capabilities: {sorted(unknown_tasks)}")

    def _identity_payload(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            **{field_name: getattr(self, field_name) for field_name in _CAPABILITY_FIELDS.values()},
            "blocked_reasons": dict(self.blocked_reasons),
            "claim_markers": list(self.claim_markers),
        }

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self._identity_payload())

    def to_dict(self) -> dict[str, Any]:
        payload = self._identity_payload()
        payload["fingerprint"] = self.fingerprint
        return payload

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DatasetCapability":
        value = _schema(value, "DatasetCapability", cls._FIELDS)
        result = cls(
            dataset_id=value["dataset_id"],
            supports_coordination_discovery=value["supports_coordination_discovery"],
            supports_external_label_evaluation=value["supports_external_label_evaluation"],
            supports_campaign_holdout=value["supports_campaign_holdout"],
            supports_time_holdout=value["supports_time_holdout"],
            supports_social_bot_classification=value["supports_social_bot_classification"],
            supports_harmful_cib_detection=value["supports_harmful_cib_detection"],
            supports_campaign_io_evaluation=value["supports_campaign_io_evaluation"],
            blocked_reasons=value["blocked_reasons"],
            claim_markers=value["claim_markers"],
        )
        _validate_declared_fingerprint(value["fingerprint"], result.fingerprint, "fingerprint")
        return result


@dataclass(frozen=True, slots=True)
class ResearchDatasetManifest:
    dataset_id: str
    seed: int
    source_paths: tuple[str, ...]
    source_checksums: Mapping[str, str]
    source_checksum_scope: str
    label_semantics: str
    sample_count: int
    source_case_ids: tuple[str, ...]
    campaign_axis: tuple[str, ...]
    platform_axis: tuple[str, ...]
    time_axis: str
    quality_markers: tuple[str, ...] = ()
    claim_markers: tuple[str, ...] = ()

    _FIELDS = frozenset(
        {
            "dataset_id",
            "seed",
            "source_paths",
            "source_checksums",
            "source_checksum_scope",
            "label_semantics",
            "sample_count",
            "source_case_ids",
            "campaign_axis",
            "platform_axis",
            "time_axis",
            "quality_markers",
            "claim_markers",
            "fingerprint",
        }
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "dataset_id", _required_text(self.dataset_id, "dataset_id"))
        object.__setattr__(self, "seed", _seed(self.seed))
        paths = _text_tuple(self.source_paths, "source_paths", allow_empty=False)
        checksums = _text_mapping(self.source_checksums, "source_checksums")
        if set(paths) != set(checksums):
            raise ValueError("source_checksums must contain exactly every source path")
        normalized_checksums: dict[str, str] = {}
        for path, checksum in checksums.items():
            normalized = checksum.lower()
            if not _SHA256_PATTERN.fullmatch(normalized):
                raise ValueError("source_checksums must use sha256:<64 lowercase hex>")
            normalized_checksums[path] = normalized
        object.__setattr__(self, "source_paths", paths)
        object.__setattr__(self, "source_checksums", MappingProxyType(normalized_checksums))
        object.__setattr__(self, "source_checksum_scope", _required_text(self.source_checksum_scope, "source_checksum_scope"))
        object.__setattr__(self, "label_semantics", _required_text(self.label_semantics, "label_semantics"))
        object.__setattr__(self, "sample_count", _non_negative_int(self.sample_count, "sample_count"))
        object.__setattr__(self, "source_case_ids", _text_tuple(self.source_case_ids, "source_case_ids", allow_empty=False))
        object.__setattr__(self, "campaign_axis", _text_tuple(self.campaign_axis, "campaign_axis"))
        object.__setattr__(self, "platform_axis", _text_tuple(self.platform_axis, "platform_axis"))
        object.__setattr__(self, "time_axis", _required_text(self.time_axis, "time_axis"))
        object.__setattr__(self, "quality_markers", _text_tuple(self.quality_markers, "quality_markers"))
        object.__setattr__(self, "claim_markers", _text_tuple(self.claim_markers, "claim_markers"))

    def _identity_payload(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "seed": self.seed,
            "source_paths": list(self.source_paths),
            "source_checksums": dict(self.source_checksums),
            "source_checksum_scope": self.source_checksum_scope,
            "label_semantics": self.label_semantics,
            "sample_count": self.sample_count,
            "source_case_ids": list(self.source_case_ids),
            "campaign_axis": list(self.campaign_axis),
            "platform_axis": list(self.platform_axis),
            "time_axis": self.time_axis,
            "quality_markers": list(self.quality_markers),
            "claim_markers": list(self.claim_markers),
        }

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self._identity_payload())

    def to_dict(self) -> dict[str, Any]:
        payload = self._identity_payload()
        payload["fingerprint"] = self.fingerprint
        return payload

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ResearchDatasetManifest":
        value = _schema(value, "ResearchDatasetManifest", cls._FIELDS)
        result = cls(
            dataset_id=value["dataset_id"],
            seed=value["seed"],
            source_paths=value["source_paths"],
            source_checksums=value["source_checksums"],
            source_checksum_scope=value["source_checksum_scope"],
            label_semantics=value["label_semantics"],
            sample_count=value["sample_count"],
            source_case_ids=value["source_case_ids"],
            campaign_axis=value["campaign_axis"],
            platform_axis=value["platform_axis"],
            time_axis=value["time_axis"],
            quality_markers=value["quality_markers"],
            claim_markers=value["claim_markers"],
        )
        _validate_declared_fingerprint(value["fingerprint"], result.fingerprint, "fingerprint")
        return result


@dataclass(frozen=True, slots=True)
class ExperimentSplit:
    policy: str
    seed: int
    train_ids: tuple[str, ...]
    validation_ids: tuple[str, ...]
    test_ids: tuple[str, ...]
    train_group_ids: tuple[str, ...]
    validation_group_ids: tuple[str, ...]
    test_group_ids: tuple[str, ...]
    transform_fit_ids: tuple[str, ...]

    _FIELDS = frozenset(
        {
            "policy",
            "seed",
            "train_ids",
            "validation_ids",
            "test_ids",
            "train_group_ids",
            "validation_group_ids",
            "test_group_ids",
            "transform_fit_ids",
            "fingerprint",
        }
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy", _required_text(self.policy, "policy"))
        object.__setattr__(self, "seed", _seed(self.seed))
        for field_name in (
            "train_ids",
            "validation_ids",
            "test_ids",
            "train_group_ids",
            "validation_group_ids",
            "test_group_ids",
            "transform_fit_ids",
        ):
            object.__setattr__(self, field_name, _text_tuple(getattr(self, field_name), field_name, allow_empty=False))
        id_sets = [set(self.train_ids), set(self.validation_ids), set(self.test_ids)]
        group_sets = [set(self.train_group_ids), set(self.validation_group_ids), set(self.test_group_ids)]
        if any(left & right for index, left in enumerate(id_sets) for right in id_sets[index + 1 :]):
            raise ValueError("train, validation, and test IDs must be pairwise disjoint")
        if any(left & right for index, left in enumerate(group_sets) for right in group_sets[index + 1 :]):
            raise ValueError("train, validation, and test groups must be pairwise disjoint")
        if self.transform_fit_ids != self.train_ids:
            raise ValueError("transform_fit_ids must equal train_ids exactly")

    def _identity_payload(self) -> dict[str, Any]:
        return {
            "policy": self.policy,
            "seed": self.seed,
            "train_ids": list(self.train_ids),
            "validation_ids": list(self.validation_ids),
            "test_ids": list(self.test_ids),
            "train_group_ids": list(self.train_group_ids),
            "validation_group_ids": list(self.validation_group_ids),
            "test_group_ids": list(self.test_group_ids),
            "transform_fit_ids": list(self.transform_fit_ids),
        }

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self._identity_payload())

    def to_dict(self) -> dict[str, Any]:
        payload = self._identity_payload()
        payload["fingerprint"] = self.fingerprint
        return payload

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ExperimentSplit":
        value = _schema(value, "ExperimentSplit", cls._FIELDS)
        result = cls(
            policy=value["policy"],
            seed=value["seed"],
            train_ids=value["train_ids"],
            validation_ids=value["validation_ids"],
            test_ids=value["test_ids"],
            train_group_ids=value["train_group_ids"],
            validation_group_ids=value["validation_group_ids"],
            test_group_ids=value["test_group_ids"],
            transform_fit_ids=value["transform_fit_ids"],
        )
        _validate_declared_fingerprint(value["fingerprint"], result.fingerprint, "fingerprint")
        return result


def build_campaign_holdout(
    sample_campaigns: Mapping[str, str],
    validation_campaigns: Sequence[str],
    test_campaigns: Sequence[str],
    seed: int,
) -> ExperimentSplit:
    if not isinstance(sample_campaigns, MappingABC) or not sample_campaigns:
        raise ValueError("sample_campaigns must be a non-empty mapping")
    normalized = {
        _required_text(sample_id, "sample ID"): _required_text(campaign, "campaign")
        for sample_id, campaign in sample_campaigns.items()
    }
    validation = set(_text_tuple(validation_campaigns, "validation campaigns", allow_empty=False))
    test = set(_text_tuple(test_campaigns, "test campaigns", allow_empty=False))
    if validation & test:
        raise ValueError("validation and test campaigns overlap")
    available = set(normalized.values())
    missing = (validation | test) - available
    if missing:
        raise ValueError(f"missing requested campaigns: {sorted(missing)}")
    train = available - validation - test
    if not train:
        raise ValueError("train campaign partition must be non-empty")

    def ids_for(groups: set[str]) -> tuple[str, ...]:
        return tuple(sorted(sample_id for sample_id, group in normalized.items() if group in groups))

    return ExperimentSplit(
        policy="campaign_holdout",
        seed=_seed(seed),
        train_ids=ids_for(train),
        validation_ids=ids_for(validation),
        test_ids=ids_for(test),
        train_group_ids=tuple(train),
        validation_group_ids=tuple(validation),
        test_group_ids=tuple(test),
        transform_fit_ids=ids_for(train),
    )


def _aware_utc(value: Any, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} timestamp must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def build_time_holdout(
    sample_times: Mapping[str, datetime],
    train_end: datetime,
    validation_end: datetime,
    seed: int,
) -> ExperimentSplit:
    if not isinstance(sample_times, MappingABC) or not sample_times:
        raise ValueError("sample_times must be a non-empty mapping")
    train_boundary = _aware_utc(train_end, "train boundary")
    validation_boundary = _aware_utc(validation_end, "validation boundary")
    if train_boundary >= validation_boundary:
        raise ValueError("train boundary must precede validation boundary")
    normalized = {
        _required_text(sample_id, "sample ID"): _aware_utc(observed_at, "sample")
        for sample_id, observed_at in sample_times.items()
    }
    train_ids = tuple(sorted(key for key, value in normalized.items() if value <= train_boundary))
    validation_ids = tuple(
        sorted(key for key, value in normalized.items() if train_boundary < value <= validation_boundary)
    )
    test_ids = tuple(sorted(key for key, value in normalized.items() if value > validation_boundary))

    def groups(ids: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted({normalized[sample_id].isoformat() for sample_id in ids}))

    try:
        return ExperimentSplit(
            policy="observed_time_holdout",
            seed=_seed(seed),
            train_ids=train_ids,
            validation_ids=validation_ids,
            test_ids=test_ids,
            train_group_ids=groups(train_ids),
            validation_group_ids=groups(validation_ids),
            test_group_ids=groups(test_ids),
            transform_fit_ids=train_ids,
        )
    except ValueError as exc:
        raise ValueError(f"time holdout partition invalid: {exc}") from exc


__all__ = [
    "DatasetCapability",
    "ExperimentSplit",
    "ResearchDatasetManifest",
    "build_campaign_holdout",
    "build_time_holdout",
]
