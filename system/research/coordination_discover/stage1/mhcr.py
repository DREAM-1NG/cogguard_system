from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import timedelta

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from .contracts import STAGE1_LABEL_POLICY
from .events import CoordinationEvent, validate_coordination_relation
from .tsgs import TSGSResult


MHCR_OBJECTIVE = "self_supervised_infonce"
FEATURE_SOURCE = "events_only_structural_activity"
FEATURE_NAMES = (
    "event_count",
    "weight_sum",
    "relation_diversity",
    "object_diversity",
    "active_bucket_count",
    "temporal_span",
)
AUGMENTATIONS = ("seeded_temporal_jitter", "seeded_hyperedge_drop")


def _positive_int(value: object, field_name: str, *, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{field_name} must be an integer >= {minimum}")
    return value


def _finite_float(
    value: object,
    field_name: str,
    *,
    minimum: float,
    maximum: float | None = None,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be numeric")
    number = float(value)
    if not math.isfinite(number) or number < minimum or (
        maximum is not None and number > maximum
    ):
        raise ValueError(f"{field_name} is outside its supported finite range")
    return number


@dataclass(frozen=True, slots=True)
class MHCRConfig:
    time_bucket_seconds: int = 300
    hidden_dimension: int = 16
    epochs: int = 12
    learning_rate: float = 0.02
    temperature: float = 0.2
    temporal_jitter_seconds: int = 30
    hyperedge_drop_rate: float = 0.2
    seed: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "time_bucket_seconds",
            _positive_int(self.time_bucket_seconds, "time_bucket_seconds"),
        )
        object.__setattr__(
            self,
            "hidden_dimension",
            _positive_int(self.hidden_dimension, "hidden_dimension", minimum=2),
        )
        object.__setattr__(self, "epochs", _positive_int(self.epochs, "epochs"))
        object.__setattr__(
            self,
            "learning_rate",
            _finite_float(self.learning_rate, "learning_rate", minimum=np.finfo(float).tiny),
        )
        object.__setattr__(
            self,
            "temperature",
            _finite_float(self.temperature, "temperature", minimum=np.finfo(float).tiny),
        )
        object.__setattr__(
            self,
            "temporal_jitter_seconds",
            _positive_int(
                self.temporal_jitter_seconds,
                "temporal_jitter_seconds",
                minimum=0,
            ),
        )
        object.__setattr__(
            self,
            "hyperedge_drop_rate",
            _finite_float(
                self.hyperedge_drop_rate,
                "hyperedge_drop_rate",
                minimum=0.0,
                maximum=1.0,
            ),
        )
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise ValueError("seed must be an integer")


@dataclass(frozen=True, slots=True, order=True)
class HyperedgeIncidence:
    account_id: str
    weight: float
    temporal_position: float


@dataclass(frozen=True, slots=True)
class HyperedgeAudit:
    hyperedge_id: str
    relation: str
    object_id: str
    time_bucket: int
    incidence: tuple[HyperedgeIncidence, ...]


@dataclass(frozen=True, slots=True)
class ViewDiagnostics:
    name: str
    seed: int
    temporal_jitter_seconds: int
    hyperedge_drop_rate: float
    source_hyperedge_count: int
    retained_hyperedge_count: int
    dropped_hyperedge_count: int
    dropped_hyperedge_ids: tuple[str, ...]
    content_signature: str


@dataclass(frozen=True, slots=True)
class MHCRTrainingDiagnostics:
    objective: str
    augmentations: tuple[str, ...]
    view_count: int
    views: tuple[ViewDiagnostics, ...]
    epoch_infonce_losses: tuple[float, ...]
    final_infonce_loss: float
    relation_transform_count: int
    node_to_hyperedge_normalization: str
    hyperedge_to_node_normalization: str
    node_channel: str


@dataclass(frozen=True, slots=True)
class MHCRRepresentation:
    account_ids: tuple[str, ...]
    embeddings: tuple[tuple[float, ...], ...]
    hyperedges: tuple[HyperedgeAudit, ...]
    relation_names: tuple[str, ...]
    training_diagnostics: MHCRTrainingDiagnostics
    feature_names: tuple[str, ...] = FEATURE_NAMES
    feature_source: str = FEATURE_SOURCE
    objective: str = MHCR_OBJECTIVE
    label_policy: str = STAGE1_LABEL_POLICY


@dataclass(frozen=True, slots=True)
class SparseCandidateChannel:
    account_count: int
    source_indices: torch.Tensor
    target_indices: torch.Tensor
    normalized_weights: torch.Tensor


def _ordered_events(events: Iterable[CoordinationEvent]) -> tuple[CoordinationEvent, ...]:
    materialized = tuple(events)
    if not all(isinstance(event, CoordinationEvent) for event in materialized):
        raise ValueError("events must contain CoordinationEvent values")
    for event in materialized:
        validate_coordination_relation(event.relation)
    return tuple(
        sorted(
            materialized,
            key=lambda event: (
                event.account_id,
                event.relation,
                event.object_id,
                event.observed_at,
                event.evidence_ref,
                event.weight,
            ),
        )
    )


def _hyperedge_id(relation: str, object_id: str, time_bucket: int) -> str:
    payload = f"{relation}\0{object_id}\0{time_bucket}".encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()[:20]
    return f"hyperedge-{digest}"


def _build_hyperedges(
    events: tuple[CoordinationEvent, ...],
    time_bucket_seconds: int,
) -> tuple[HyperedgeAudit, ...]:
    incidence: defaultdict[
        tuple[str, str, int], defaultdict[str, list[float]]
    ] = defaultdict(
        lambda: defaultdict(lambda: [0.0, 0.0])
    )
    for event in events:
        if event.weight <= 0.0:
            continue
        timestamp = event.observed_at.timestamp()
        bucket = math.floor(timestamp / time_bucket_seconds)
        temporal_position = (timestamp - bucket * time_bucket_seconds) / time_bucket_seconds
        account_values = incidence[(event.relation, event.object_id, bucket)][event.account_id]
        account_values[0] += event.weight
        account_values[1] += event.weight * temporal_position

    return tuple(
        HyperedgeAudit(
            hyperedge_id=_hyperedge_id(relation, object_id, bucket),
            relation=relation,
            object_id=object_id,
            time_bucket=bucket,
            incidence=tuple(
                HyperedgeIncidence(
                    account_id=account_id,
                    weight=float(values[0]),
                    temporal_position=float(values[1] / values[0]),
                )
                for account_id, values in sorted(members.items())
            ),
        )
        for (relation, object_id, bucket), members in sorted(incidence.items())
        if members
    )


def _initial_features(
    events: tuple[CoordinationEvent, ...],
    account_ids: tuple[str, ...],
    time_bucket_seconds: int,
) -> torch.Tensor:
    by_account: defaultdict[str, list[CoordinationEvent]] = defaultdict(list)
    for event in events:
        by_account[event.account_id].append(event)

    rows = []
    for account_id in account_ids:
        account_events = by_account.get(account_id, [])
        times = [event.observed_at.timestamp() for event in account_events]
        buckets = {
            math.floor(timestamp / time_bucket_seconds) for timestamp in times
        }
        rows.append(
            (
                float(len(account_events)),
                math.fsum(event.weight for event in account_events),
                float(len({event.relation for event in account_events})),
                float(len({(event.relation, event.object_id) for event in account_events})),
                float(len(buckets)),
                float(max(times) - min(times)) if len(times) > 1 else 0.0,
            )
        )

    if not rows:
        return torch.empty((0, len(FEATURE_NAMES)), dtype=torch.float32)
    values = np.asarray(rows, dtype=np.float32)
    values[:, :5] = np.log1p(values[:, :5])
    values[:, 5] = np.log1p(values[:, 5])
    scale = np.max(values, axis=0)
    scale[scale == 0.0] = 1.0
    return torch.from_numpy(values / scale)


def _jitter_events(
    events: tuple[CoordinationEvent, ...],
    jitter_seconds: int,
    rng: np.random.Generator,
) -> tuple[CoordinationEvent, ...]:
    if jitter_seconds == 0:
        return events
    jittered = []
    for event in events:
        offset = int(rng.integers(-jitter_seconds, jitter_seconds + 1))
        jittered.append(
            CoordinationEvent(
                account_id=event.account_id,
                relation=event.relation,
                object_id=event.object_id,
                observed_at=event.observed_at + timedelta(seconds=offset),
                weight=event.weight,
                evidence_ref=event.evidence_ref,
            )
        )
    return tuple(jittered)


def _drop_hyperedges(
    hyperedges: tuple[HyperedgeAudit, ...],
    drop_rate: float,
    rng: np.random.Generator,
) -> tuple[tuple[HyperedgeAudit, ...], tuple[HyperedgeAudit, ...]]:
    if not hyperedges or drop_rate == 0.0:
        return hyperedges, ()
    drop_count = min(
        len(hyperedges) - 1,
        max(1, math.ceil(len(hyperedges) * drop_rate)),
    )
    ranks = rng.random(len(hyperedges))
    dropped = set(np.argsort(ranks, kind="stable")[:drop_count].tolist())
    return (
        tuple(edge for index, edge in enumerate(hyperedges) if index not in dropped),
        tuple(edge for index, edge in enumerate(hyperedges) if index in dropped),
    )


def _force_distinct_drop_mask(
    hyperedges: tuple[HyperedgeAudit, ...],
    retained: tuple[HyperedgeAudit, ...],
    dropped: tuple[HyperedgeAudit, ...],
    other_dropped_indices: tuple[int, ...],
) -> tuple[tuple[HyperedgeAudit, ...], tuple[HyperedgeAudit, ...]]:
    dropped_set = set(dropped)
    dropped_indices = tuple(
        index for index, edge in enumerate(hyperedges) if edge in dropped_set
    )
    if dropped_indices != other_dropped_indices:
        return retained, dropped
    for shift in range(1, len(hyperedges)):
        shifted = tuple(
            sorted((index + shift) % len(hyperedges) for index in dropped_indices)
        )
        if shifted != other_dropped_indices:
            shifted_set = set(shifted)
            return (
                tuple(edge for index, edge in enumerate(hyperedges) if index not in shifted_set),
                tuple(edge for index, edge in enumerate(hyperedges) if index in shifted_set),
            )
    return retained, dropped


def _view_signature(hyperedges: tuple[HyperedgeAudit, ...]) -> str:
    payload = "\n".join(
        "|".join(
            (
                edge.hyperedge_id,
                edge.relation,
                edge.object_id,
                str(edge.time_bucket),
                ";".join(
                    f"{item.account_id}:{item.weight:.17g}:{item.temporal_position:.17g}"
                    for item in edge.incidence
                ),
            )
        )
        for edge in hyperedges
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _view_diagnostics(
    name: str,
    seed: int,
    config: MHCRConfig,
    source: tuple[HyperedgeAudit, ...],
    retained: tuple[HyperedgeAudit, ...],
    dropped: tuple[HyperedgeAudit, ...],
) -> ViewDiagnostics:
    return ViewDiagnostics(
        name=name,
        seed=seed,
        temporal_jitter_seconds=config.temporal_jitter_seconds,
        hyperedge_drop_rate=config.hyperedge_drop_rate,
        source_hyperedge_count=len(source),
        retained_hyperedge_count=len(retained),
        dropped_hyperedge_count=len(dropped),
        dropped_hyperedge_ids=tuple(sorted(edge.hyperedge_id for edge in dropped)),
        content_signature=_view_signature(retained),
    )


def _build_two_views(
    events: Iterable[CoordinationEvent],
    config: MHCRConfig,
) -> tuple[
    tuple[HyperedgeAudit, ...],
    tuple[HyperedgeAudit, ...],
    tuple[ViewDiagnostics, ViewDiagnostics],
]:
    ordered_events = _ordered_events(events)
    seeds = (config.seed ^ 0x4D484352, config.seed ^ 0x56494557)
    sources = []
    retained_views = []
    dropped_views = []
    for seed in seeds:
        jitter_rng = np.random.default_rng(seed)
        jittered = _jitter_events(
            ordered_events, config.temporal_jitter_seconds, jitter_rng
        )
        source = _build_hyperedges(jittered, config.time_bucket_seconds)
        retained, dropped = _drop_hyperedges(
            source,
            config.hyperedge_drop_rate,
            np.random.default_rng(seed ^ 0x44524F50),
        )
        sources.append(source)
        retained_views.append(retained)
        dropped_views.append(dropped)

    if (
        config.hyperedge_drop_rate > 0.0
        and len(sources[0]) == 1
        and len(sources[1]) == 1
    ):
        retained_views[0], dropped_views[0] = sources[0], ()
        retained_views[1], dropped_views[1] = (), sources[1]

    if (
        config.temporal_jitter_seconds > 0
        and config.hyperedge_drop_rate == 0.0
        and len(sources[0]) >= 2
        and len(sources[1]) >= 2
        and _view_signature(retained_views[0]) == _view_signature(retained_views[1])
    ):
        for direction in (1, -1):
            forced_events = tuple(
                CoordinationEvent(
                    account_id=event.account_id,
                    relation=event.relation,
                    object_id=event.object_id,
                    observed_at=event.observed_at
                    + timedelta(
                        seconds=(
                            direction * config.temporal_jitter_seconds
                            if index % 2 == 0
                            else -direction * config.temporal_jitter_seconds
                        )
                    ),
                    weight=event.weight,
                    evidence_ref=event.evidence_ref,
                )
                for index, event in enumerate(ordered_events)
            )
            forced_source = _build_hyperedges(
                forced_events, config.time_bucket_seconds
            )
            if _view_signature(forced_source) != _view_signature(retained_views[0]):
                sources[1] = forced_source
                retained_views[1] = forced_source
                dropped_views[1] = ()
                break

    if (
        config.hyperedge_drop_rate > 0.0
        and len(sources[0]) >= 2
        and len(sources[1]) >= 2
        and len(sources[0]) == len(sources[1])
    ):
        first_dropped_set = set(dropped_views[0])
        first_indices = tuple(
            index
            for index, edge in enumerate(sources[0])
            if edge in first_dropped_set
        )
        retained_views[1], dropped_views[1] = _force_distinct_drop_mask(
            sources[1], retained_views[1], dropped_views[1], first_indices
        )

    diagnostics = (
        _view_diagnostics(
            "view_a", seeds[0], config, sources[0], retained_views[0], dropped_views[0]
        ),
        _view_diagnostics(
            "view_b", seeds[1], config, sources[1], retained_views[1], dropped_views[1]
        ),
    )
    return retained_views[0], retained_views[1], diagnostics


def _candidate_channel(tsgs_result: TSGSResult) -> SparseCandidateChannel:
    account_count = len(tsgs_result.account_ids)
    node_index = {
        account_id: index for index, account_id in enumerate(tsgs_result.account_ids)
    }
    degrees: defaultdict[int, float] = defaultdict(float)
    for edge in tsgs_result.candidate_graph_edges:
        left = node_index[edge.source_account_id]
        right = node_index[edge.target_account_id]
        degrees[left] += edge.weight
        degrees[right] += edge.weight

    directed_edges = []
    for edge in tsgs_result.candidate_graph_edges:
        left = node_index[edge.source_account_id]
        right = node_index[edge.target_account_id]
        directed_edges.append((left, right, edge.weight / degrees[right]))
        directed_edges.append((right, left, edge.weight / degrees[left]))

    if directed_edges:
        source_indices = torch.tensor(
            [source for source, _, _ in directed_edges], dtype=torch.long
        )
        target_indices = torch.tensor(
            [target for _, target, _ in directed_edges], dtype=torch.long
        )
        normalized_weights = torch.tensor(
            [weight for _, _, weight in directed_edges], dtype=torch.float32
        )
    else:
        source_indices = torch.empty((0,), dtype=torch.long)
        target_indices = torch.empty((0,), dtype=torch.long)
        normalized_weights = torch.empty((0,), dtype=torch.float32)
    return SparseCandidateChannel(
        account_count=account_count,
        source_indices=source_indices,
        target_indices=target_indices,
        normalized_weights=normalized_weights,
    )


def _aggregate_candidate_channel(
    state: torch.Tensor,
    channel: SparseCandidateChannel,
) -> torch.Tensor:
    if state.shape[0] != channel.account_count:
        raise ValueError("candidate channel account count must match node state")
    aggregated = torch.zeros_like(state)
    if channel.source_indices.numel() == 0:
        return aggregated
    source_indices = channel.source_indices.to(device=state.device)
    target_indices = channel.target_indices.to(device=state.device)
    weights = channel.normalized_weights.to(device=state.device, dtype=state.dtype)
    messages = state.index_select(0, source_indices) * weights.unsqueeze(1)
    aggregated.index_add_(0, target_indices, messages)
    return aggregated


class _RelationAwareHypergraphEncoder(nn.Module):
    def __init__(
        self,
        input_dimension: int,
        hidden_dimension: int,
        relation_names: tuple[str, ...],
    ) -> None:
        super().__init__()
        self.relation_index = {
            relation: index for index, relation in enumerate(relation_names)
        }
        self.input_transform = nn.Linear(input_dimension, hidden_dimension, bias=False)
        self.self_transform = nn.Linear(hidden_dimension, hidden_dimension, bias=False)
        self.relation_transforms = nn.ModuleList(
            nn.Linear(hidden_dimension, hidden_dimension, bias=False)
            for _ in relation_names
        )
        self.graph_transform = nn.Linear(hidden_dimension, hidden_dimension, bias=False)

    def forward(
        self,
        features: torch.Tensor,
        hyperedges: tuple[HyperedgeAudit, ...],
        account_ids: tuple[str, ...],
        candidate_channel: SparseCandidateChannel,
    ) -> torch.Tensor:
        state = self.input_transform(features)
        if not account_ids:
            return state
        node_index = {account_id: index for index, account_id in enumerate(account_ids)}
        hypergraph_message = torch.zeros_like(state)
        node_incidence_degree = torch.zeros((len(account_ids), 1), dtype=state.dtype)

        for edge in hyperedges:
            incidence = torch.zeros((len(account_ids), 1), dtype=state.dtype)
            for item in edge.incidence:
                index = node_index.get(item.account_id)
                if index is not None:
                    incidence[index, 0] = float(
                        item.weight * (1.0 + item.temporal_position)
                    )
            hyperedge_degree = incidence.sum().clamp_min(1.0)
            hyperedge_state = (incidence.transpose(0, 1) @ state) / hyperedge_degree
            transformed = self.relation_transforms[
                self.relation_index[edge.relation]
            ](hyperedge_state)
            hypergraph_message = hypergraph_message + incidence @ transformed
            node_incidence_degree = node_incidence_degree + incidence

        hypergraph_message = hypergraph_message / node_incidence_degree.clamp_min(1.0)
        graph_message = self.graph_transform(
            _aggregate_candidate_channel(state, candidate_channel)
        )
        output = torch.tanh(self.self_transform(state) + hypergraph_message + graph_message)
        return F.normalize(output, p=2, dim=1, eps=1e-12)


def _symmetric_infonce(
    first: torch.Tensor,
    second: torch.Tensor,
    temperature: float,
) -> torch.Tensor:
    if first.shape[0] == 0:
        return first.sum() * 0.0
    similarities = first @ second.transpose(0, 1) / temperature
    matching_indices = torch.arange(first.shape[0], dtype=torch.long)
    forward_loss = F.cross_entropy(similarities, matching_indices)
    reverse_loss = F.cross_entropy(similarities.transpose(0, 1), matching_indices)
    return (forward_loss + reverse_loss) * 0.5


class MHCREncoder:
    def __init__(self, config: MHCRConfig | None = None) -> None:
        self.config = config or MHCRConfig()
        if not isinstance(self.config, MHCRConfig):
            raise ValueError("config must be an MHCRConfig")

    def fit_transform(
        self,
        events: Iterable[CoordinationEvent],
        tsgs_result: TSGSResult,
    ) -> MHCRRepresentation:
        if not isinstance(tsgs_result, TSGSResult):
            raise ValueError("tsgs_result must be a TSGSResult")
        ordered_events = _ordered_events(events)
        observed_accounts = tuple(sorted({event.account_id for event in ordered_events}))
        if observed_accounts != tsgs_result.account_ids:
            raise ValueError("events and tsgs_result must contain the same sorted account IDs")

        account_ids = tsgs_result.account_ids
        canonical_hyperedges = _build_hyperedges(
            ordered_events, self.config.time_bucket_seconds
        )
        relation_names = tuple(sorted({event.relation for event in ordered_events}))
        features = _initial_features(
            ordered_events, account_ids, self.config.time_bucket_seconds
        )
        candidate_channel = _candidate_channel(tsgs_result)
        first_view, second_view, view_diagnostics = _build_two_views(
            ordered_events, self.config
        )

        losses: list[float] = []
        previous_thread_count = torch.get_num_threads()
        if previous_thread_count != 1:
            torch.set_num_threads(1)
        try:
            if account_ids:
                with torch.random.fork_rng(devices=[]):
                    torch.manual_seed(self.config.seed)
                    model = _RelationAwareHypergraphEncoder(
                        len(FEATURE_NAMES), self.config.hidden_dimension, relation_names
                    )
                    optimizer = torch.optim.Adam(
                        model.parameters(), lr=self.config.learning_rate
                    )
                    for _ in range(self.config.epochs):
                        optimizer.zero_grad(set_to_none=True)
                        first_embedding = model(
                            features, first_view, account_ids, candidate_channel
                        )
                        second_embedding = model(
                            features, second_view, account_ids, candidate_channel
                        )
                        loss = _symmetric_infonce(
                            first_embedding, second_embedding, self.config.temperature
                        )
                        loss.backward()
                        optimizer.step()
                        losses.append(float(loss.detach().cpu()))
                    with torch.no_grad():
                        embedding_tensor = model(
                            features,
                            canonical_hyperedges,
                            account_ids,
                            candidate_channel,
                        )
            else:
                losses = [0.0] * self.config.epochs
                embedding_tensor = torch.empty(
                    (0, self.config.hidden_dimension), dtype=torch.float32
                )
        finally:
            if previous_thread_count != 1:
                torch.set_num_threads(previous_thread_count)

        embeddings = tuple(
            tuple(float(value) for value in row)
            for row in embedding_tensor.detach().cpu().tolist()
        )
        training_diagnostics = MHCRTrainingDiagnostics(
            objective=MHCR_OBJECTIVE,
            augmentations=AUGMENTATIONS,
            view_count=2,
            views=view_diagnostics,
            epoch_infonce_losses=tuple(losses),
            final_infonce_loss=losses[-1],
            relation_transform_count=len(relation_names),
            node_to_hyperedge_normalization="hyperedge_degree",
            hyperedge_to_node_normalization="node_incidence_degree",
            node_channel="explicit_tsgs_candidate_graph",
        )
        return MHCRRepresentation(
            account_ids=account_ids,
            embeddings=embeddings,
            hyperedges=canonical_hyperedges,
            relation_names=relation_names,
            training_diagnostics=training_diagnostics,
        )


__all__ = [
    "HyperedgeAudit",
    "HyperedgeIncidence",
    "MHCRConfig",
    "MHCREncoder",
    "MHCRRepresentation",
    "MHCRTrainingDiagnostics",
    "SparseCandidateChannel",
    "ViewDiagnostics",
]
