from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .protocol import DatasetCapability


HEURISTIC_BASELINE_WARNING = (
    "Research-only heuristic baseline; output is not a learned or production decision."
)
HEURISTIC_BASELINE_ID = "heuristic_" + "baseline_v1"
REQUIRED_ABLATIONS = (
    "no_tsgs",
    "no_mhcr",
    "no_relation_specific",
    "no_temporal_augmentation",
    "coordination_only",
    "detection_features_only",
)

_CAPABILITY_ATTRIBUTES = MappingProxyType(
    {
        "coordination_discovery": "supports_coordination_discovery",
        "external_label_evaluation": "supports_external_label_evaluation",
        "campaign_holdout": "supports_campaign_holdout",
        "observed_time_holdout": "supports_time_holdout",
        "social_bot_classification": "supports_social_bot_classification",
        "harmful_cib_detection": "supports_harmful_cib_detection",
        "campaign_io_evaluation": "supports_campaign_io_evaluation",
    }
)


def _text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{field_name} must be non-empty canonical text")
    return value


@dataclass(frozen=True, slots=True)
class BaselineSpec:
    method_id: str
    method_version: str
    stage: str
    model_role: str
    required_capabilities: tuple[str, ...] = ()
    optional_dependencies: tuple[str, ...] = ()
    warning: str | None = None
    claimable: bool = True

    def __post_init__(self) -> None:
        for field_name in ("method_id", "method_version", "model_role"):
            object.__setattr__(self, field_name, _text(getattr(self, field_name), field_name))
        if self.stage not in {"discovery", "detection"}:
            raise ValueError("stage must be discovery or detection")
        capabilities = tuple(_text(value, "required capability") for value in self.required_capabilities)
        if len(capabilities) != len(set(capabilities)) or set(capabilities) - set(_CAPABILITY_ATTRIBUTES):
            raise ValueError("required_capabilities contain duplicates or unknown values")
        dependencies = tuple(_text(value, "optional dependency") for value in self.optional_dependencies)
        if len(dependencies) != len(set(dependencies)):
            raise ValueError("optional_dependencies contain duplicates")
        object.__setattr__(self, "required_capabilities", capabilities)
        object.__setattr__(self, "optional_dependencies", dependencies)
        if self.model_role == "heuristic_baseline":
            if self.method_id != HEURISTIC_BASELINE_ID or self.method_version != HEURISTIC_BASELINE_ID:
                raise ValueError("heuristic baseline identity is fixed")
            if self.warning != HEURISTIC_BASELINE_WARNING or self.claimable:
                raise ValueError("heuristic baseline requires its warning and is not claimable as learned")

    def to_dict(self) -> dict[str, object]:
        return {
            "method_id": self.method_id,
            "method_version": self.method_version,
            "stage": self.stage,
            "model_role": self.model_role,
            "required_capabilities": list(self.required_capabilities),
            "optional_dependencies": list(self.optional_dependencies),
            "warning": self.warning,
            "claimable": self.claimable,
        }


@dataclass(frozen=True, slots=True)
class BaselineResolution:
    spec: BaselineSpec
    status: str
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.status not in {"ready", "blocked"}:
            raise ValueError("resolution status must be ready or blocked")
        if (self.status == "blocked") != bool(self.reason):
            raise ValueError("blocked resolutions require a reason and ready resolutions do not")


class BaselineRegistry:
    def __init__(self, specs: tuple[BaselineSpec, ...]) -> None:
        indexed = {spec.method_id: spec for spec in specs}
        if len(indexed) != len(specs):
            raise ValueError("baseline method IDs must be unique")
        self._specs: Mapping[str, BaselineSpec] = MappingProxyType(dict(sorted(indexed.items())))

    def method_ids(self) -> tuple[str, ...]:
        return tuple(self._specs)

    def get(self, method_id: str) -> BaselineSpec:
        try:
            return self._specs[method_id]
        except KeyError as exc:
            raise ValueError(f"unknown baseline method: {method_id}") from exc

    def specs(self) -> tuple[BaselineSpec, ...]:
        return tuple(self._specs.values())

    def resolve(self, method_id: str, *, capability: DatasetCapability) -> BaselineResolution:
        if not isinstance(capability, DatasetCapability):
            raise ValueError("capability must be a DatasetCapability")
        spec = self.get(method_id)
        blocked: list[str] = []
        for required in spec.required_capabilities:
            if not getattr(capability, _CAPABILITY_ATTRIBUTES[required]):
                reason = capability.blocked_reasons.get(required, "dataset capability unavailable")
                blocked.append(f"{required}: {reason}")
        for dependency in spec.optional_dependencies:
            try:
                available = importlib.util.find_spec(dependency) is not None
            except (ImportError, ModuleNotFoundError, ValueError):
                available = False
            if not available:
                blocked.append(f"optional_dependency: {dependency} is unavailable")
        if blocked:
            return BaselineResolution(spec=spec, status="blocked", reason="; ".join(blocked))
        return BaselineResolution(spec=spec, status="ready")


def default_baseline_registry() -> BaselineRegistry:
    specs = [
        BaselineSpec(
            "dense_cosine_leiden", "dense-cosine-leiden-v1", "discovery", "discovery_baseline",
            ("coordination_discovery",), ("igraph", "leidenalg"),
        ),
        BaselineSpec(
            "frozen_system_evidence_prior", "coordination-evidence-runtime-v2", "discovery",
            "frozen_system_baseline", ("coordination_discovery",), claimable=False,
            warning="Frozen production evidence prior; research harness cannot modify or activate it.",
        ),
        BaselineSpec(
            "edgebank", "edgebank-v1", "discovery", "temporal_baseline",
            ("coordination_discovery",),
        ),
        BaselineSpec(
            "tgn_style_memory_prior", "tgn-style-memory-prior-v1", "discovery", "temporal_baseline",
            ("coordination_discovery", "observed_time_holdout"),
        ),
        BaselineSpec(
            "coordination_only_logistic", "coordination-only-logistic-v1", "detection", "primary_learned",
            ("harmful_cib_detection", "external_label_evaluation"),
        ),
        BaselineSpec(
            "detection_features_only_classifier", "detection-features-only-logistic-v1", "detection",
            "primary_learned", ("harmful_cib_detection", "external_label_evaluation"),
        ),
        BaselineSpec(
            "learned_fused_detector", "learned-coordination-logistic-v1", "detection", "primary_learned",
            ("harmful_cib_detection", "external_label_evaluation"),
        ),
        BaselineSpec(
            HEURISTIC_BASELINE_ID, HEURISTIC_BASELINE_ID, "detection", "heuristic_baseline",
            ("harmful_cib_detection", "external_label_evaluation"),
            warning=HEURISTIC_BASELINE_WARNING, claimable=False,
        ),
        BaselineSpec(
            "no_tsgs", "coordination-discovery-no-tsgs-v1", "discovery", "ablation",
            ("coordination_discovery",),
        ),
        BaselineSpec(
            "no_mhcr", "coordination-discovery-no-mhcr-v1", "discovery", "ablation",
            ("coordination_discovery",),
        ),
        BaselineSpec(
            "no_relation_specific", "coordination-discovery-shared-relation-v1", "discovery", "ablation",
            ("coordination_discovery",),
        ),
        BaselineSpec(
            "no_temporal_augmentation", "coordination-discovery-no-temporal-augmentation-v1",
            "discovery", "ablation", ("coordination_discovery",),
        ),
        BaselineSpec(
            "coordination_only", "coordination-only-logistic-v1", "detection", "ablation",
            ("harmful_cib_detection", "external_label_evaluation"),
        ),
        BaselineSpec(
            "detection_features_only", "detection-features-only-logistic-v1", "detection", "ablation",
            ("harmful_cib_detection", "external_label_evaluation"),
        ),
    ]
    try:
        legacy_available = importlib.util.find_spec(
            "research.coordination_discover.temporal_edge_model"
        ) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        legacy_available = False
    if legacy_available:
        specs.append(
            BaselineSpec(
                "legacy_temporal_edge_encoder", "legacy-temporal-edge-encoder-adapter-v1",
                "discovery", "legacy_encoder_baseline", ("coordination_discovery",),
                warning="Legacy encoder adapter is comparison-only and cannot be activated.",
                claimable=False,
            )
        )
    return BaselineRegistry(tuple(specs))


__all__ = [
    "BaselineRegistry", "BaselineResolution", "BaselineSpec",
    "HEURISTIC_BASELINE_ID", "HEURISTIC_BASELINE_WARNING", "REQUIRED_ABLATIONS",
    "default_baseline_registry",
]
