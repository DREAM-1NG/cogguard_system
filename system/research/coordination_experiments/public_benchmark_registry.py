from __future__ import annotations

from collections.abc import Mapping as MappingABC
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .iohunter import iohunter_capability
from .protocol import DatasetCapability


_FEASIBILITY_STATUSES = {"ready", "adapter_required", "proxy_only", "method_only", "blocked"}
_ACCESS_MODES = {"local_available", "open_download", "public_archive", "paper_data", "access_audit_required"}
_SIGNALS = {
    "observed_timestamps",
    "temporal_edges",
    "multiplex_relations",
    "weighted_edges",
    "account_membership_labels",
    "control_accounts",
    "graph_labels",
    "handcrafted_feature_table",
    "coordination_edge_gold",
    "community_gold",
    "binary_detection_gold",
    "harmfulness_gold",
}


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{field_name} must be non-empty canonical text")
    return value


def _text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise ValueError(f"{field_name} must be a tuple")
    normalized = tuple(_text(value, field_name) for value in values)
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{field_name} contains duplicate values")
    return normalized


def _bool(value: object, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be boolean")
    return value


@dataclass(frozen=True, slots=True)
class PublicCoordinationDatasetSpec:
    dataset_id: str
    name: str
    primary_source_url: str
    access_mode: str
    capability: DatasetCapability
    has_observed_timestamps: bool
    has_temporal_edges: bool
    has_multiplex_relations: bool
    has_weighted_edges: bool
    has_account_membership_labels: bool
    has_control_accounts: bool
    has_graph_labels: bool
    has_handcrafted_feature_table: bool
    has_coordination_edge_gold: bool
    has_community_gold: bool
    has_binary_detection_gold: bool
    has_harmfulness_gold: bool
    recommended_uses: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "dataset_id", _text(self.dataset_id, "dataset_id"))
        object.__setattr__(self, "name", _text(self.name, "name"))
        object.__setattr__(self, "primary_source_url", _text(self.primary_source_url, "primary_source_url"))
        if self.access_mode not in _ACCESS_MODES:
            raise ValueError(f"access_mode must be one of {sorted(_ACCESS_MODES)}")
        if not isinstance(self.capability, DatasetCapability):
            raise ValueError("capability must be a DatasetCapability")
        if self.capability.dataset_id != self.dataset_id:
            raise ValueError("capability dataset_id must match dataset_id")
        for field_name in (
            "has_observed_timestamps",
            "has_temporal_edges",
            "has_multiplex_relations",
            "has_weighted_edges",
            "has_account_membership_labels",
            "has_control_accounts",
            "has_graph_labels",
            "has_handcrafted_feature_table",
            "has_coordination_edge_gold",
            "has_community_gold",
            "has_binary_detection_gold",
            "has_harmfulness_gold",
        ):
            object.__setattr__(self, field_name, _bool(getattr(self, field_name), field_name))
        object.__setattr__(self, "recommended_uses", _text_tuple(self.recommended_uses, "recommended_uses"))
        object.__setattr__(self, "limitations", _text_tuple(self.limitations, "limitations"))

    @property
    def available_signals(self) -> frozenset[str]:
        fields = {
            "observed_timestamps": self.has_observed_timestamps,
            "temporal_edges": self.has_temporal_edges,
            "multiplex_relations": self.has_multiplex_relations,
            "weighted_edges": self.has_weighted_edges,
            "account_membership_labels": self.has_account_membership_labels,
            "control_accounts": self.has_control_accounts,
            "graph_labels": self.has_graph_labels,
            "handcrafted_feature_table": self.has_handcrafted_feature_table,
            "coordination_edge_gold": self.has_coordination_edge_gold,
            "community_gold": self.has_community_gold,
            "binary_detection_gold": self.has_binary_detection_gold,
            "harmfulness_gold": self.has_harmfulness_gold,
        }
        return frozenset(signal for signal, present in fields.items() if present)


@dataclass(frozen=True, slots=True)
class PublicCoordinationMethodSpec:
    method_id: str
    name: str
    family: str
    primary_reference_url: str
    required_signals: tuple[str, ...]
    reproduction_route: str
    coordination_claim_scope: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "method_id", _text(self.method_id, "method_id"))
        object.__setattr__(self, "name", _text(self.name, "name"))
        object.__setattr__(self, "family", _text(self.family, "family"))
        object.__setattr__(self, "primary_reference_url", _text(self.primary_reference_url, "primary_reference_url"))
        required = _text_tuple(self.required_signals, "required_signals")
        unknown = set(required) - _SIGNALS
        if unknown:
            raise ValueError(f"required_signals contains unknown values: {sorted(unknown)}")
        object.__setattr__(self, "required_signals", required)
        object.__setattr__(self, "reproduction_route", _text(self.reproduction_route, "reproduction_route"))
        object.__setattr__(
            self,
            "coordination_claim_scope",
            _text(self.coordination_claim_scope, "coordination_claim_scope"),
        )


@dataclass(frozen=True, slots=True)
class BenchmarkFeasibility:
    dataset_id: str
    method_id: str
    status: str
    reason: str
    missing_signals: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "dataset_id", _text(self.dataset_id, "dataset_id"))
        object.__setattr__(self, "method_id", _text(self.method_id, "method_id"))
        if self.status not in _FEASIBILITY_STATUSES:
            raise ValueError(f"status must be one of {sorted(_FEASIBILITY_STATUSES)}")
        object.__setattr__(self, "reason", _text(self.reason, "reason"))
        object.__setattr__(self, "missing_signals", _text_tuple(self.missing_signals, "missing_signals"))

    def to_dict(self) -> dict[str, object]:
        return {
            "dataset_id": self.dataset_id,
            "method_id": self.method_id,
            "status": self.status,
            "reason": self.reason,
            "missing_signals": list(self.missing_signals),
        }


class PublicBenchmarkRegistry:
    __slots__ = ("_datasets", "_methods", "_sealed")

    def __init__(
        self,
        *,
        datasets: tuple[PublicCoordinationDatasetSpec, ...],
        methods: tuple[PublicCoordinationMethodSpec, ...],
    ) -> None:
        dataset_map = {dataset.dataset_id: dataset for dataset in datasets}
        method_map = {method.method_id: method for method in methods}
        if len(dataset_map) != len(datasets):
            raise ValueError("duplicate public dataset ids")
        if len(method_map) != len(methods):
            raise ValueError("duplicate public method ids")
        object.__setattr__(self, "_datasets", MappingProxyType(dataset_map))
        object.__setattr__(self, "_methods", MappingProxyType(method_map))
        object.__setattr__(self, "_sealed", True)

    def __setattr__(self, name: str, value: object) -> None:
        if getattr(self, "_sealed", False):
            raise AttributeError("PublicBenchmarkRegistry is immutable")
        object.__setattr__(self, name, value)

    @property
    def dataset_ids(self) -> tuple[str, ...]:
        return tuple(self._datasets)

    @property
    def method_ids(self) -> tuple[str, ...]:
        return tuple(self._methods)

    def dataset(self, dataset_id: str) -> PublicCoordinationDatasetSpec:
        try:
            return self._datasets[_text(dataset_id, "dataset_id")]
        except KeyError as exc:
            raise ValueError(f"unknown public coordination dataset: {dataset_id}") from exc

    def method(self, method_id: str) -> PublicCoordinationMethodSpec:
        try:
            return self._methods[_text(method_id, "method_id")]
        except KeyError as exc:
            raise ValueError(f"unknown public coordination method: {method_id}") from exc

    def feasibility(self, dataset_id: str, method_id: str) -> BenchmarkFeasibility:
        dataset = self.dataset(dataset_id)
        method = self.method(method_id)
        missing = tuple(signal for signal in method.required_signals if signal not in dataset.available_signals)
        if missing:
            return BenchmarkFeasibility(
                dataset_id=dataset.dataset_id,
                method_id=method.method_id,
                status="blocked",
                reason="dataset is missing required structural signals for a fair reproduction",
                missing_signals=missing,
            )
        if not dataset.capability.supports_coordination_discovery:
            return BenchmarkFeasibility(
                dataset_id=dataset.dataset_id,
                method_id=method.method_id,
                status="method_only",
                reason="dataset can reproduce the graph-learning method but has no coordination labels",
            )
        if dataset.access_mode != "local_available":
            return BenchmarkFeasibility(
                dataset_id=dataset.dataset_id,
                method_id=method.method_id,
                status="adapter_required",
                reason="source appears suitable, but CogGuard has no locked local adapter and checksum manifest yet",
            )
        if not dataset.has_coordination_edge_gold and not dataset.has_community_gold:
            return BenchmarkFeasibility(
                dataset_id=dataset.dataset_id,
                method_id=method.method_id,
                status="proxy_only",
                reason="dataset supports account-recovery proxy evaluation, not true edge/community recovery",
            )
        return BenchmarkFeasibility(
            dataset_id=dataset.dataset_id,
            method_id=method.method_id,
            status="ready",
            reason="dataset provides the required structural signals and claim labels",
        )

    def feasibility_matrix(self) -> Mapping[str, Mapping[str, BenchmarkFeasibility]]:
        return MappingProxyType(
            {
                dataset_id: MappingProxyType(
                    {method_id: self.feasibility(dataset_id, method_id) for method_id in self.method_ids}
                )
                for dataset_id in self.dataset_ids
            }
        )


def _capability(
    *,
    dataset_id: str,
    discovery: bool,
    external_labels: bool,
    campaign_holdout: bool,
    time_holdout: bool,
    bot: bool,
    binary_detection: bool,
    harmful: bool,
    campaign_io: bool,
    blocked_reasons: Mapping[str, str],
    claim_markers: tuple[str, ...],
) -> DatasetCapability:
    if not isinstance(blocked_reasons, MappingABC):
        raise ValueError("blocked_reasons must be a mapping")
    return DatasetCapability(
        dataset_id=dataset_id,
        supports_coordination_discovery=discovery,
        supports_external_label_evaluation=external_labels,
        supports_campaign_holdout=campaign_holdout,
        supports_time_holdout=time_holdout,
        supports_social_bot_classification=bot,
        supports_binary_coordination_detection=binary_detection,
        supports_harmful_cib_detection=harmful,
        supports_campaign_io_evaluation=campaign_io,
        blocked_reasons=dict(blocked_reasons),
        claim_markers=claim_markers,
    )


def default_public_benchmark_registry() -> PublicBenchmarkRegistry:
    iohunter = iohunter_capability()
    datasets = (
        PublicCoordinationDatasetSpec(
            dataset_id=iohunter.dataset_id,
            name="IOHunter processed",
            primary_source_url="local:G:/CISCN/dataset/iohunter/data/processed",
            access_mode="local_available",
            capability=iohunter,
            has_observed_timestamps=False,
            has_temporal_edges=False,
            has_multiplex_relations=True,
            has_weighted_edges=True,
            has_account_membership_labels=True,
            has_control_accounts=True,
            has_graph_labels=False,
            has_handcrafted_feature_table=False,
            has_coordination_edge_gold=False,
            has_community_gold=False,
            has_binary_detection_gold=False,
            has_harmfulness_gold=False,
            recommended_uses=("static_external_account_recovery_proxy", "campaign_holdout_proxy"),
            limitations=(
                "no_observed_event_timestamps",
                "no_coordination_edge_gold",
                "no_community_gold",
                "no_harmfulness_gold",
            ),
        ),
        PublicCoordinationDatasetSpec(
            dataset_id="seckin_2024_labeled_io",
            name="Labeled Datasets for Research on Information Operations",
            primary_source_url="https://doi.org/10.5281/zenodo.14141549",
            access_mode="access_audit_required",
            capability=_capability(
                dataset_id="seckin_2024_labeled_io",
                discovery=True,
                external_labels=True,
                campaign_holdout=True,
                time_holdout=True,
                bot=False,
                binary_detection=False,
                harmful=False,
                campaign_io=True,
                blocked_reasons={
                    "binary_coordination_detection": "dataset has IO/control account labels, not cluster or graph binary Detection labels",
                    "social_bot_classification": "labels identify IO/control accounts, not social bots",
                    "harmful_cib_detection": "dataset has IO membership labels, not harmfulness taxonomy labels",
                },
                claim_markers=("public_io_control_dataset", "requires_local_adapter"),
            ),
            has_observed_timestamps=True,
            has_temporal_edges=True,
            has_multiplex_relations=True,
            has_weighted_edges=True,
            has_account_membership_labels=True,
            has_control_accounts=True,
            has_graph_labels=False,
            has_handcrafted_feature_table=False,
            has_coordination_edge_gold=False,
            has_community_gold=False,
            has_binary_detection_gold=False,
            has_harmfulness_gold=False,
            recommended_uses=("temporal_external_account_recovery_proxy", "cross_campaign_holdout"),
            limitations=(
                "zenodo_files_forbidden_in_current_environment",
                "no_coordination_edge_gold",
                "no_community_gold",
                "no_harmfulness_gold",
            ),
        ),
        PublicCoordinationDatasetSpec(
            dataset_id="twitter_state_backed_io_archive",
            name="X/Twitter state-backed information operations archive",
            primary_source_url="https://cyber.fsi.stanford.edu/io/news/twitter-takedown-data-archive",
            access_mode="public_archive",
            capability=_capability(
                dataset_id="twitter_state_backed_io_archive",
                discovery=True,
                external_labels=True,
                campaign_holdout=True,
                time_holdout=True,
                bot=False,
                binary_detection=False,
                harmful=False,
                campaign_io=True,
                blocked_reasons={
                    "binary_coordination_detection": "platform takedown membership is not cluster or graph binary Detection gold",
                    "social_bot_classification": "platform takedown labels are not bot labels",
                    "harmful_cib_detection": "platform takedown membership is not a harmfulness taxonomy",
                },
                claim_markers=("platform_takedown_membership", "requires_local_adapter"),
            ),
            has_observed_timestamps=True,
            has_temporal_edges=True,
            has_multiplex_relations=True,
            has_weighted_edges=True,
            has_account_membership_labels=True,
            has_control_accounts=False,
            has_graph_labels=False,
            has_handcrafted_feature_table=False,
            has_coordination_edge_gold=False,
            has_community_gold=False,
            has_binary_detection_gold=False,
            has_harmfulness_gold=False,
            recommended_uses=("temporal_discovery_case_study", "state_backed_account_recovery"),
            limitations=("no_control_accounts_by_default", "no_coordination_edge_gold", "no_harmfulness_gold"),
        ),
        PublicCoordinationDatasetSpec(
            dataset_id="guo_vosoughi_2022_io_controls",
            name="Guo and Vosoughi state-backed IO control datasets",
            primary_source_url="https://ojs.aaai.org/index.php/ICWSM/article/view/19375",
            access_mode="paper_data",
            capability=_capability(
                dataset_id="guo_vosoughi_2022_io_controls",
                discovery=True,
                external_labels=True,
                campaign_holdout=True,
                time_holdout=True,
                bot=False,
                binary_detection=False,
                harmful=False,
                campaign_io=True,
                blocked_reasons={
                    "binary_coordination_detection": "dataset has IO/control account labels, not cluster or graph binary Detection labels",
                    "social_bot_classification": "labels identify IO/control accounts, not social bots",
                    "harmful_cib_detection": "dataset has IO membership labels, not harmfulness labels",
                },
                claim_markers=("public_io_control_dataset", "requires_access_audit"),
            ),
            has_observed_timestamps=True,
            has_temporal_edges=True,
            has_multiplex_relations=True,
            has_weighted_edges=True,
            has_account_membership_labels=True,
            has_control_accounts=True,
            has_graph_labels=False,
            has_handcrafted_feature_table=False,
            has_coordination_edge_gold=False,
            has_community_gold=False,
            has_binary_detection_gold=False,
            has_harmfulness_gold=False,
            recommended_uses=("temporal_external_account_recovery_proxy", "cross_campaign_holdout"),
            limitations=("access_and_schema_need_audit", "no_coordination_edge_gold", "no_community_gold"),
        ),
        PublicCoordinationDatasetSpec(
            dataset_id="tgb_temporal_graph_benchmark",
            name="Temporal Graph Benchmark",
            primary_source_url="https://tgb.complexdatalab.com/",
            access_mode="open_download",
            capability=_capability(
                dataset_id="tgb_temporal_graph_benchmark",
                discovery=False,
                external_labels=False,
                campaign_holdout=False,
                time_holdout=True,
                bot=False,
                binary_detection=False,
                harmful=False,
                campaign_io=False,
                blocked_reasons={
                    "coordination_discovery": "TGB is a temporal graph ML benchmark, not a CIB dataset",
                    "external_label_evaluation": "no state-backed IO account labels",
                    "campaign_holdout": "no IO campaign axis",
                    "binary_coordination_detection": "no coordination Detection labels",
                    "social_bot_classification": "no bot-authenticity labels",
                    "harmful_cib_detection": "no harmful coordination labels",
                    "campaign_io_evaluation": "no IO campaign membership labels",
                },
                claim_markers=("method_reproduction_only",),
            ),
            has_observed_timestamps=True,
            has_temporal_edges=True,
            has_multiplex_relations=True,
            has_weighted_edges=True,
            has_account_membership_labels=False,
            has_control_accounts=False,
            has_graph_labels=False,
            has_handcrafted_feature_table=False,
            has_coordination_edge_gold=False,
            has_community_gold=False,
            has_binary_detection_gold=False,
            has_harmfulness_gold=False,
            recommended_uses=("temporal_graph_method_reproduction", "dynamic_link_prediction_sanity"),
            limitations=("not_coordination_detection_data", "no_io_labels"),
        ),
        PublicCoordinationDatasetSpec(
            dataset_id="large_engagement_networks",
            name="Large Engagement Networks",
            primary_source_url="local:G:/CISCN/dataset/LEN",
            access_mode="local_available",
            capability=_capability(
                dataset_id="large_engagement_networks",
                discovery=True,
                external_labels=True,
                campaign_holdout=True,
                time_holdout=False,
                bot=False,
                binary_detection=True,
                harmful=False,
                campaign_io=True,
                blocked_reasons={
                    "observed_time_holdout": "local LEN files are graph-level JSONs, not a locked event stream",
                    "social_bot_classification": "labels are campaign/non-campaign graph labels, not bot labels",
                    "harmful_cib_detection": "labels are campaign/non-campaign graphs, not a harmfulness taxonomy",
                },
                claim_markers=(
                    "local_campaign_graph_classification",
                    "not_harmful_cib_claim",
                    "stage2_detection_candidate",
                ),
            ),
            has_observed_timestamps=False,
            has_temporal_edges=False,
            has_multiplex_relations=False,
            has_weighted_edges=True,
            has_account_membership_labels=False,
            has_control_accounts=True,
            has_graph_labels=True,
            has_handcrafted_feature_table=False,
            has_coordination_edge_gold=False,
            has_community_gold=False,
            has_binary_detection_gold=True,
            has_harmfulness_gold=False,
            recommended_uses=("stage2_graph_classification", "campaign_noncampaign_detection"),
            limitations=("no_locked_event_stream_adapter", "no_coordination_edge_gold", "no_community_gold"),
        ),
        PublicCoordinationDatasetSpec(
            dataset_id="astroturf_legitimate_classification",
            name="Astroturf/Legitimate Classification",
            primary_source_url="local:G:/CISCN/dataset/ALClassification",
            access_mode="local_available",
            capability=_capability(
                dataset_id="astroturf_legitimate_classification",
                discovery=False,
                external_labels=True,
                campaign_holdout=False,
                time_holdout=False,
                bot=False,
                binary_detection=True,
                harmful=False,
                campaign_io=False,
                blocked_reasons={
                    "coordination_discovery": "dataset is a Truthy meme feature table, not raw coordination events",
                    "campaign_holdout": "feature table has no campaign axis",
                    "observed_time_holdout": "feature table has no raw observed event timestamps",
                    "social_bot_classification": "labels are truthy/legitimate memes, not bots",
                    "harmful_cib_detection": "labels are astroturf/legitimate memes, not a harmfulness taxonomy",
                    "campaign_io_evaluation": "labels are astroturf/legitimate, not state-backed IO campaigns",
                },
                claim_markers=(
                    "local_truthy_feature_baseline",
                    "not_harmful_cib_claim",
                    "stage2_classic_smoke",
                ),
            ),
            has_observed_timestamps=False,
            has_temporal_edges=False,
            has_multiplex_relations=False,
            has_weighted_edges=False,
            has_account_membership_labels=False,
            has_control_accounts=True,
            has_graph_labels=False,
            has_handcrafted_feature_table=True,
            has_coordination_edge_gold=False,
            has_community_gold=False,
            has_binary_detection_gold=True,
            has_harmfulness_gold=False,
            recommended_uses=("stage2_classic_feature_baseline", "truthy_legitimate_smoke"),
            limitations=("no_raw_event_stream", "no_graph_structure", "no_campaign_holdout"),
        ),
    )
    methods = (
        PublicCoordinationMethodSpec(
            method_id="tgat",
            name="Temporal Graph Attention Network",
            family="temporal_graph_neural_network",
            primary_reference_url="https://arxiv.org/abs/2002.07962",
            required_signals=("observed_timestamps", "temporal_edges"),
            reproduction_route="DyGLib/TGB-style temporal edge stream adapter",
            coordination_claim_scope="temporal proxy only unless evaluated on IO/control data with timestamped interactions",
        ),
        PublicCoordinationMethodSpec(
            method_id="tgn",
            name="Temporal Graph Networks",
            family="temporal_graph_neural_network",
            primary_reference_url="https://github.com/twitter-research/tgn",
            required_signals=("observed_timestamps", "temporal_edges"),
            reproduction_route="official TGN or TGB/DyGLib runner",
            coordination_claim_scope="temporal proxy only unless evaluated on IO/control data with timestamped interactions",
        ),
        PublicCoordinationMethodSpec(
            method_id="dygformer",
            name="DyGFormer",
            family="temporal_graph_transformer",
            primary_reference_url="https://arxiv.org/abs/2303.13047",
            required_signals=("observed_timestamps", "temporal_edges"),
            reproduction_route="TGB-compatible dynamic graph transformer runner",
            coordination_claim_scope="temporal proxy only unless evaluated on IO/control data with timestamped interactions",
        ),
        PublicCoordinationMethodSpec(
            method_id="temporal_multiplex_multislice",
            name="Temporal multiplex or multislice coordination model",
            family="temporal_multilayer_coordination",
            primary_reference_url="https://doi.org/10.1609/icwsm.v20i1.42682",
            required_signals=("observed_timestamps", "temporal_edges", "multiplex_relations"),
            reproduction_route="windowed multiplex graph adapter plus dynamic community evaluation",
            coordination_claim_scope="requires timestamped multi-relation IO data; IOHunter processed is blocked",
        ),
        PublicCoordinationMethodSpec(
            method_id="polya_filter",
            name="Polya urn network backbone filter",
            family="statistical_backbone",
            primary_reference_url="https://doi.org/10.1038/s41467-019-08667-3",
            required_signals=("weighted_edges",),
            reproduction_route="weighted evidence graph backbone extraction",
            coordination_claim_scope="static or per-window backbone proxy; does not classify harmfulness",
        ),
        PublicCoordinationMethodSpec(
            method_id="noise_corrected_backbone",
            name="Noise-Corrected backbone",
            family="statistical_backbone",
            primary_reference_url="https://arxiv.org/abs/1701.07336",
            required_signals=("weighted_edges",),
            reproduction_route="weighted evidence graph backbone extraction",
            coordination_claim_scope="static or per-window backbone proxy; does not classify harmfulness",
        ),
        PublicCoordinationMethodSpec(
            method_id="ecm_backbone",
            name="Enhanced configuration model backbone",
            family="statistical_backbone",
            primary_reference_url="https://doi.org/10.1038/s41467-018-08160-3",
            required_signals=("weighted_edges",),
            reproduction_route="degree/strength-conditioned graph backbone extraction",
            coordination_claim_scope="static or per-window backbone proxy; does not classify harmfulness",
        ),
        PublicCoordinationMethodSpec(
            method_id="flow_stability",
            name="Flow Stability",
            family="dynamic_community_detection",
            primary_reference_url="https://github.com/bovet-research-group/flow_stability",
            required_signals=("observed_timestamps", "temporal_edges", "weighted_edges"),
            reproduction_route="temporal or multislice graph community runner",
            coordination_claim_scope="dynamic community recovery requires community Gold or analyst validation",
        ),
    )
    return PublicBenchmarkRegistry(datasets=datasets, methods=methods)


__all__ = [
    "BenchmarkFeasibility",
    "PublicBenchmarkRegistry",
    "PublicCoordinationDatasetSpec",
    "PublicCoordinationMethodSpec",
    "default_public_benchmark_registry",
]
