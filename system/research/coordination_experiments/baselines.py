from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any, Mapping

from research.coordination_detect.heuristic_baseline import HeuristicBayesianBaseline

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
    implementation_id: str
    required_capabilities: tuple[str, ...] = ()
    optional_dependencies: tuple[str, ...] = ()
    warning: str | None = None
    claimable: bool = True
    selection_eligible: bool = False
    ablation_id: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("method_id", "method_version", "model_role", "implementation_id"):
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
        if self.ablation_id is not None:
            object.__setattr__(self, "ablation_id", _text(self.ablation_id, "ablation_id"))
            if self.ablation_id not in REQUIRED_ABLATIONS or self.ablation_id != self.method_id:
                raise ValueError("ablation_id must use the method's exact required ablation identity")
        heuristic_signal = (
            self.method_id == HEURISTIC_BASELINE_ID
            or self.method_version == HEURISTIC_BASELINE_ID
            or self.model_role == "heuristic_baseline"
        )
        heuristic_identity = (
            self.method_id == HEURISTIC_BASELINE_ID
            and self.method_version == HEURISTIC_BASELINE_ID
            and self.model_role == "heuristic_baseline"
        )
        if heuristic_signal and not heuristic_identity:
            raise ValueError("heuristic baseline identity fields must agree")
        if heuristic_identity and (
            self.warning != HEURISTIC_BASELINE_WARNING
            or self.claimable
            or self.selection_eligible
        ):
            raise ValueError("heuristic baseline requires its warning and is never selection eligible")
        if self.selection_eligible and not (
            self.method_id == "learned_fused_detector"
            and self.stage == "detection"
            and self.model_role == "primary_learned"
        ):
            raise ValueError("only the fused primary learned detector is selection eligible")

    def to_dict(self) -> dict[str, object]:
        return {
            "method_id": self.method_id,
            "method_version": self.method_version,
            "stage": self.stage,
            "model_role": self.model_role,
            "implementation_id": self.implementation_id,
            "required_capabilities": list(self.required_capabilities),
            "optional_dependencies": list(self.optional_dependencies),
            "warning": self.warning,
            "claimable": self.claimable,
            "selection_eligible": self.selection_eligible,
            "ablation_id": self.ablation_id,
        }


class DiscoveryImplementation:
    __slots__ = ()
    method_id = ""
    implementation_id = ""
    unavailable_reason: str | None = None

    def execute(self, execution_input: Any) -> Any:
        raise NotImplementedError


class LearnedDetectionImplementation:
    __slots__ = ()
    method_id = ""
    implementation_id = ""
    unavailable_reason: str | None = None

    def execute(self, partitions: Any) -> Any:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class HeuristicDetectionImplementation:
    _baseline_type: type[HeuristicBayesianBaseline] = field(
        default=HeuristicBayesianBaseline,
        init=False,
        repr=False,
        compare=False,
    )
    method_id = HEURISTIC_BASELINE_ID
    implementation_id = "heuristic-baseline-implementation-v1"
    unavailable_reason: str | None = None

    @property
    def baseline_type(self) -> type[HeuristicBayesianBaseline]:
        return self._baseline_type

    def execute(self, test_input: Any) -> Any:
        from .runner import DetectionExecutionOutput, DetectionPrediction, DetectionTestInput

        if not isinstance(test_input, DetectionTestInput):
            raise ValueError("heuristic execution requires an unlabeled DetectionTestInput")
        baseline = self._baseline_type()
        predictions: list[DetectionPrediction] = []
        for case in test_input.test_cases:
            features = dict(zip(case.feature_names, case.feature_values, strict=True))
            required = (
                "tsgs_density",
                "mhcr_coherence",
                "temporal_sync_score",
                "unsupervised_ranking",
            )
            missing = [name for name in required if name not in features]
            if missing:
                raise ValueError(f"heuristic baseline input is missing features: {missing}")
            verdict = baseline.predict(
                cluster_id=case.cluster_id,
                **{name: features[name] for name in required},
            )
            predictions.append(
                DetectionPrediction(
                    case_id=case.case_id,
                    harmful_probability=verdict.harmful_probability,
                    decision=verdict.decision,
                )
            )
        return DetectionExecutionOutput(model_artifact=None, predictions=tuple(predictions))


@dataclass(frozen=True, slots=True)
class _UnavailableDiscoveryImplementation(DiscoveryImplementation):
    method_id: str
    implementation_id: str
    unavailable_reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "method_id", _text(self.method_id, "method_id"))
        object.__setattr__(
            self, "implementation_id", _text(self.implementation_id, "implementation_id")
        )
        object.__setattr__(
            self, "unavailable_reason", _text(self.unavailable_reason, "unavailable_reason")
        )


@dataclass(frozen=True, slots=True)
class _UnavailableLearnedDetectionImplementation(LearnedDetectionImplementation):
    method_id: str
    implementation_id: str
    unavailable_reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "method_id", _text(self.method_id, "method_id"))
        object.__setattr__(
            self, "implementation_id", _text(self.implementation_id, "implementation_id")
        )
        object.__setattr__(
            self, "unavailable_reason", _text(self.unavailable_reason, "unavailable_reason")
        )


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
    __slots__ = ("_specs", "_implementations", "_sealed")

    def __init__(
        self,
        entries: tuple[
            tuple[
                BaselineSpec,
                DiscoveryImplementation
                | LearnedDetectionImplementation
                | HeuristicDetectionImplementation,
            ],
            ...,
        ],
    ) -> None:
        specs: dict[str, BaselineSpec] = {}
        implementations: dict[
            str,
            DiscoveryImplementation
            | LearnedDetectionImplementation
            | HeuristicDetectionImplementation,
        ] = {}
        for entry in entries:
            if not isinstance(entry, tuple) or len(entry) != 2:
                raise ValueError("registry entries must be (BaselineSpec, implementation) pairs")
            spec, implementation = entry
            if not isinstance(spec, BaselineSpec):
                raise ValueError("registry entries require BaselineSpec values")
            if spec.method_id in specs:
                raise ValueError(f"duplicate registered method: {spec.method_id}")
            if getattr(implementation, "method_id", None) != spec.method_id:
                raise ValueError("implementation method identity does not match registered spec")
            implementation_id = _text(
                getattr(implementation, "implementation_id", None), "implementation_id"
            )
            if spec.stage == "discovery" and not isinstance(
                implementation, DiscoveryImplementation
            ):
                raise ValueError("discovery methods require a DiscoveryImplementation")
            if spec.model_role == "heuristic_baseline":
                if type(implementation) is not HeuristicDetectionImplementation:
                    raise ValueError("heuristic method requires the concrete Stage 2 adapter")
            elif spec.stage == "detection" and not isinstance(
                implementation, LearnedDetectionImplementation
            ):
                raise ValueError("learned detection methods require a LearnedDetectionImplementation")
            specs[spec.method_id] = replace(spec, implementation_id=implementation_id)
            implementations[spec.method_id] = implementation
        object.__setattr__(self, "_specs", MappingProxyType(dict(sorted(specs.items()))))
        object.__setattr__(self, "_implementations", MappingProxyType(dict(sorted(implementations.items()))))
        object.__setattr__(self, "_sealed", True)

    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_sealed", False):
            raise AttributeError("BaselineRegistry is immutable")
        object.__setattr__(self, name, value)

    _specs: Mapping[str, BaselineSpec]
    _implementations: Mapping[
            str,
            DiscoveryImplementation
            | LearnedDetectionImplementation
            | HeuristicDetectionImplementation,
        ]

    def method_ids(self) -> tuple[str, ...]:
        return tuple(self._specs)

    def get(self, method_id: str) -> BaselineSpec:
        try:
            return self._specs[method_id]
        except KeyError as exc:
            raise ValueError(f"unknown baseline method: {method_id}") from exc

    def specs(self) -> tuple[BaselineSpec, ...]:
        return tuple(self._specs.values())

    def implementation(
        self, method_id: str
    ) -> DiscoveryImplementation | LearnedDetectionImplementation | HeuristicDetectionImplementation:
        try:
            return self._implementations[method_id]
        except KeyError as exc:
            raise ValueError(f"method implementation is not bound: {method_id}") from exc

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
        unavailable_reason = self.implementation(method_id).unavailable_reason
        if unavailable_reason is not None:
            blocked.append(f"implementation: {unavailable_reason}")
        if blocked:
            return BaselineResolution(spec=spec, status="blocked", reason="; ".join(blocked))
        return BaselineResolution(spec=spec, status="ready")


def default_baseline_registry() -> BaselineRegistry:
    specs = [
        BaselineSpec(
            "dense_cosine_leiden", "dense-cosine-leiden-v1", "discovery", "discovery_baseline",
            "dense-cosine-leiden-implementation-v1",
            ("coordination_discovery",), ("igraph", "leidenalg"),
        ),
        BaselineSpec(
            "frozen_system_evidence_prior", "coordination-evidence-runtime-v2", "discovery",
            "frozen_system_baseline", "frozen-system-evidence-implementation-v1",
            ("coordination_discovery",), claimable=False,
            warning="Frozen production evidence prior; research harness cannot modify or activate it.",
        ),
        BaselineSpec(
            "edgebank", "edgebank-v1", "discovery", "temporal_baseline",
            "edgebank-implementation-v1",
            ("coordination_discovery",),
        ),
        BaselineSpec(
            "tgn_style_memory_prior", "tgn-style-memory-prior-v1", "discovery", "temporal_baseline",
            "tgn-style-memory-implementation-v1",
            ("coordination_discovery", "observed_time_holdout"),
        ),
        BaselineSpec(
            "coordination_only_logistic", "coordination-only-logistic-v1", "detection", "learned_comparison",
            "coordination-only-logistic-implementation-v1",
            ("harmful_cib_detection", "external_label_evaluation"),
        ),
        BaselineSpec(
            "detection_features_only_classifier", "detection-features-only-logistic-v1", "detection",
            "learned_comparison", "detection-features-only-implementation-v1",
            ("harmful_cib_detection", "external_label_evaluation"),
        ),
        BaselineSpec(
            "learned_fused_detector", "learned-coordination-logistic-v1", "detection", "primary_learned",
            "learned-fused-implementation-v1",
            ("harmful_cib_detection", "external_label_evaluation"), selection_eligible=True,
        ),
        BaselineSpec(
            HEURISTIC_BASELINE_ID, HEURISTIC_BASELINE_ID, "detection", "heuristic_baseline",
            "heuristic-baseline-implementation-v1",
            ("harmful_cib_detection", "external_label_evaluation"),
            warning=HEURISTIC_BASELINE_WARNING, claimable=False,
        ),
        BaselineSpec(
            "no_tsgs", "coordination-discovery-no-tsgs-v1", "discovery", "ablation",
            "no-tsgs-implementation-v1", ("coordination_discovery",), ablation_id="no_tsgs",
        ),
        BaselineSpec(
            "no_mhcr", "coordination-discovery-no-mhcr-v1", "discovery", "ablation",
            "no-mhcr-implementation-v1", ("coordination_discovery",), ablation_id="no_mhcr",
        ),
        BaselineSpec(
            "no_relation_specific", "coordination-discovery-shared-relation-v1", "discovery", "ablation",
            "no-relation-specific-implementation-v1", ("coordination_discovery",),
            ablation_id="no_relation_specific",
        ),
        BaselineSpec(
            "no_temporal_augmentation", "coordination-discovery-no-temporal-augmentation-v1",
            "discovery", "ablation", "no-temporal-augmentation-implementation-v1",
            ("coordination_discovery",), ablation_id="no_temporal_augmentation",
        ),
        BaselineSpec(
            "coordination_only", "coordination-only-logistic-v1", "detection", "learned_comparison",
            "coordination-only-ablation-implementation-v1",
            ("harmful_cib_detection", "external_label_evaluation"), ablation_id="coordination_only",
        ),
        BaselineSpec(
            "detection_features_only", "detection-features-only-logistic-v1", "detection", "learned_comparison",
            "detection-features-only-ablation-implementation-v1",
            ("harmful_cib_detection", "external_label_evaluation"), ablation_id="detection_features_only",
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
                "discovery", "legacy_encoder_baseline", "legacy-temporal-edge-implementation-v1",
                ("coordination_discovery",),
                warning="Legacy encoder adapter is comparison-only and cannot be activated.",
                claimable=False,
            )
        )
    entries = []
    for spec in specs:
        if spec.method_id == HEURISTIC_BASELINE_ID:
            implementation = HeuristicDetectionImplementation()
        elif spec.stage == "discovery":
            implementation = _UnavailableDiscoveryImplementation(
                spec.method_id,
                spec.implementation_id,
                "explicit research adapter is unavailable in the default registry",
            )
        else:
            implementation = _UnavailableLearnedDetectionImplementation(
                spec.method_id,
                spec.implementation_id,
                "explicit learned research adapter is unavailable in the default registry",
            )
        entries.append((spec, implementation))
    return BaselineRegistry(tuple(entries))


__all__ = [
    "BaselineRegistry", "BaselineResolution", "BaselineSpec", "DiscoveryImplementation",
    "HeuristicDetectionImplementation", "LearnedDetectionImplementation",
    "HEURISTIC_BASELINE_ID", "HEURISTIC_BASELINE_WARNING", "REQUIRED_ABLATIONS",
    "default_baseline_registry",
]
