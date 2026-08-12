"""Same-protocol learned adapters for formal propagation comparisons.

The adapters in this file intentionally share one data pipeline, vocabulary,
candidate universe, and metric implementation. The method differences are
restricted to which heads/losses are enabled so the resulting rows are
comparable under the fair protocol.
"""

from __future__ import annotations

import copy
import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from benchmark.adapters.fair_protocol import (
    DEFAULT_K_LIST,
    FIRST_REAL_USER_ID,
    PROTOCOL_ID,
    UNK_USER_ID,
    Cascade,
    PrefixWindow,
    TrainingUserVocabulary,
    build_fair_protocol_audit,
    build_prefix_windows,
    build_training_user_vocabulary,
    compute_macro_metrics,
    gate_fair_protocol,
    load_original_cascade_splits,
)

DEFAULT_OBS_RATIOS = (0.1, 0.3, 0.5)
DEFAULT_TREND_STEPS = 4
DEFAULT_RELATION_NEIGHBORS = 4


@dataclass(frozen=True)
class AdapterSpec:
    model: str
    macro_supported: bool
    micro_supported: bool
    use_relation_context: bool
    use_trend_head: bool
    use_soft_consistency: bool
    method_family: str
    methodology: str


MODEL_SPECS: dict[str, AdapterSpec] = {
    "Ours": AdapterSpec(
        model="Ours",
        macro_supported=True,
        micro_supported=True,
        use_relation_context=True,
        use_trend_head=True,
        use_soft_consistency=True,
        method_family="unified_macro_micro_sequence",
        methodology=(
            "Unified sequence model with train-only user vocabulary, relation context, "
            "autoregressive next-user logits, final-size head, monotonic trend head, "
            "and macro/micro soft consistency."
        ),
    ),
    "MINDS": AdapterSpec(
        model="MINDS",
        macro_supported=True,
        micro_supported=True,
        use_relation_context=True,
        use_trend_head=False,
        use_soft_consistency=False,
        method_family="dynamic_cascade_sequence_backbone",
        methodology=(
            "MINDS-aligned same-protocol adapter: relation-aware sequence backbone with "
            "final-size and next-user heads; trend supervision and soft consistency are disabled."
        ),
    ),
    "FOREST": AdapterSpec(
        model="FOREST",
        macro_supported=False,
        micro_supported=True,
        use_relation_context=False,
        use_trend_head=False,
        use_soft_consistency=False,
        method_family="micro_next_user_sequence",
        methodology=(
            "FOREST-aligned same-protocol micro adapter: learned autoregressive next-user "
            "logits under the shared prefix and candidate protocol."
        ),
    ),
    "CasFT": AdapterSpec(
        model="CasFT",
        macro_supported=True,
        micro_supported=False,
        use_relation_context=False,
        use_trend_head=True,
        use_soft_consistency=False,
        method_family="continuous_trend_macro",
        methodology=(
            "CasFT-aligned same-protocol macro adapter: final-size and monotonic future "
            "trend heads under the shared observed-prefix protocol."
        ),
    ),
}


def _safe_torch():
    try:
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader, TensorDataset
    except Exception as exc:  # pragma: no cover - environment dependent.
        return None, None, None, None, exc
    return torch, nn, DataLoader, TensorDataset, None


def _pad_int(values: Sequence[int], length: int, pad_value: int = 0) -> list[int]:
    row = [int(value) for value in values[:length]]
    row.extend([pad_value] * max(0, length - len(row)))
    return row


def _pad_float(values: Sequence[float], length: int, pad_value: float = 0.0) -> list[float]:
    row = [float(value) for value in values[:length]]
    row.extend([pad_value] * max(0, length - len(row)))
    return row


def _relative_time_features(times: Sequence[int], max_sequence_len: int) -> list[float]:
    if not times:
        return [0.0] * max_sequence_len
    start = int(times[0])
    end = int(times[-1])
    span = max(float(end - start), 1.0)
    return _pad_float([(int(timestamp) - start) / span for timestamp in times], max_sequence_len)


def _build_relation_neighbors(
    train_cascades: Sequence[Cascade],
    vocabulary: TrainingUserVocabulary,
    *,
    relation_neighbor_count: int,
) -> dict[int, list[int]]:
    transitions: dict[int, Counter[int]] = defaultdict(Counter)
    for cascade in train_cascades:
        encoded = [vocabulary.encode(user_id) for user_id, _timestamp in cascade]
        for source, target in zip(encoded, encoded[1:]):
            if source >= FIRST_REAL_USER_ID and target >= FIRST_REAL_USER_ID and source != target:
                transitions[source][target] += 1
    neighbors: dict[int, list[int]] = {}
    for user_id, counter in transitions.items():
        ranked = [target for target, _count in counter.most_common(relation_neighbor_count)]
        neighbors[user_id] = _pad_int(ranked, relation_neighbor_count)
    return neighbors


def _relation_matrix(
    observed_vocab_ids: Sequence[int],
    relation_neighbors: Mapping[int, Sequence[int]],
    *,
    max_sequence_len: int,
    relation_neighbor_count: int,
) -> list[list[int]]:
    rows = [
        _pad_int(relation_neighbors.get(int(user_id), []), relation_neighbor_count)
        for user_id in observed_vocab_ids[:max_sequence_len]
    ]
    while len(rows) < max_sequence_len:
        rows.append([0] * relation_neighbor_count)
    return rows


def _windows_to_tensors(
    windows: Sequence[PrefixWindow],
    *,
    max_sequence_len: int,
    relation_neighbors: Mapping[int, Sequence[int]],
    relation_neighbor_count: int,
    torch,
) -> tuple[Any, list[PrefixWindow]]:
    seq_users = []
    seq_times = []
    relation_ids = []
    observed_counts = []
    obs_ratios = []
    final_logs = []
    trend_logs = []
    targets = []
    kept: list[PrefixWindow] = []
    for window in windows:
        if not window.observed_vocab_ids:
            continue
        seq_users.append(_pad_int(window.observed_vocab_ids, max_sequence_len))
        seq_times.append(_relative_time_features(window.observed_times, max_sequence_len))
        relation_ids.append(
            _relation_matrix(
                window.observed_vocab_ids,
                relation_neighbors,
                max_sequence_len=max_sequence_len,
                relation_neighbor_count=relation_neighbor_count,
            )
        )
        observed_counts.append(float(window.observed_size))
        obs_ratios.append(float(window.obs_ratio))
        final_logs.append(math.log1p(float(window.final_size)))
        trend_logs.append([math.log1p(value) for value in window.trend_counts])
        targets.append(int(window.target_vocab_id))
        kept.append(window)

    return (
        (
            torch.tensor(seq_users, dtype=torch.long),
            torch.tensor(seq_times, dtype=torch.float32),
            torch.tensor(relation_ids, dtype=torch.long),
            torch.tensor(observed_counts, dtype=torch.float32),
            torch.tensor(obs_ratios, dtype=torch.float32),
            torch.tensor(final_logs, dtype=torch.float32),
            torch.tensor(trend_logs, dtype=torch.float32),
            torch.tensor(targets, dtype=torch.long),
        ),
        kept,
    )


def _make_model(torch, nn, *, vocab_size: int, hidden_dim: int, trend_steps: int, use_relation_context: bool):
    class FairSequenceModel(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            emb_dim = max(8, hidden_dim // 2)
            self.embedding = nn.Embedding(vocab_size, emb_dim, padding_idx=0)
            self.use_relation_context = bool(use_relation_context)
            self.gru = nn.GRU(emb_dim + 1, hidden_dim, batch_first=True)
            self.relation_projection = nn.Linear(emb_dim, hidden_dim)
            context_dim = hidden_dim * (2 if self.use_relation_context else 1) + 2
            self.context = nn.Sequential(nn.Linear(context_dim, hidden_dim), nn.ReLU())
            self.final_growth = nn.Linear(hidden_dim, 1)
            self.trend_increment = nn.Sequential(nn.Linear(hidden_dim + 1, hidden_dim), nn.ReLU(), nn.Linear(hidden_dim, 1))
            self.micro_decoder = nn.Linear(hidden_dim, vocab_size)

        def forward(self, seq_users, seq_times, relation_ids, observed_counts, obs_ratios):
            emb = self.embedding(seq_users)
            gru_input = torch.cat([emb, seq_times.unsqueeze(-1)], dim=-1)
            _out, hidden = self.gru(gru_input)
            pieces = [hidden[-1]]
            if self.use_relation_context:
                relation_emb = self.embedding(relation_ids)
                relation_mask = relation_ids.ne(0).unsqueeze(-1)
                relation_sum = (relation_emb * relation_mask).sum(dim=(1, 2))
                relation_count = relation_mask.sum(dim=(1, 2)).clamp_min(1)
                pieces.append(self.relation_projection(relation_sum / relation_count))
            pieces.extend([torch.log1p(observed_counts).unsqueeze(-1), obs_ratios.unsqueeze(-1)])
            state = self.context(torch.cat(pieces, dim=-1))
            observed_log = torch.log1p(observed_counts)
            final_log = observed_log + torch.nn.functional.softplus(self.final_growth(state).squeeze(-1))
            current = observed_log
            trend_values = []
            for step in range(1, trend_steps + 1):
                step_ratio = torch.full((state.shape[0], 1), step / float(trend_steps), device=state.device)
                increment = torch.nn.functional.softplus(self.trend_increment(torch.cat([state, step_ratio], dim=-1)).squeeze(-1))
                current = current + increment / float(trend_steps)
                trend_values.append(current)
            trend_log = torch.stack(trend_values, dim=1)
            logits = self.micro_decoder(state)
            return {"final_log": final_log, "trend_log": trend_log, "logits": logits}

    return FairSequenceModel()


def _train_model(
    tensors,
    *,
    spec: AdapterSpec,
    vocab_size: int,
    hidden_dim: int,
    trend_steps: int,
    epochs: int,
    batch_size: int,
    lr: float,
    weight_decay: float,
    device,
    torch,
    nn,
    DataLoader,
    TensorDataset,
):
    model = _make_model(
        torch,
        nn,
        vocab_size=vocab_size,
        hidden_dim=hidden_dim,
        trend_steps=trend_steps,
        use_relation_context=spec.use_relation_context,
    ).to(device)
    dataset = TensorDataset(*[tensor.to(device) for tensor in tensors])
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    ce_loss = nn.CrossEntropyLoss()
    loss_curve = []
    best_state = None
    best_loss = float("inf")

    for _epoch in range(max(1, int(epochs))):
        model.train()
        total_loss = 0.0
        total_rows = 0
        for seq_users, seq_times, relation_ids, observed_counts, obs_ratios, final_logs, trend_logs, targets in loader:
            output = model(seq_users, seq_times, relation_ids, observed_counts, obs_ratios)
            loss = torch.tensor(0.0, device=device)
            if spec.macro_supported:
                loss = loss + torch.nn.functional.mse_loss(output["final_log"], final_logs)
                if spec.use_trend_head:
                    loss = loss + 0.5 * torch.nn.functional.mse_loss(output["trend_log"], trend_logs)
            if spec.micro_supported:
                loss = loss + 0.5 * ce_loss(output["logits"], targets)
            if spec.use_soft_consistency and spec.macro_supported and spec.micro_supported:
                top_prob = torch.softmax(output["logits"], dim=-1).topk(k=min(20, output["logits"].shape[-1]), dim=-1).values
                expected_micro_growth = top_prob.sum(dim=-1)
                predicted_growth = torch.expm1(output["final_log"]) - observed_counts
                loss = loss + 0.02 * torch.nn.functional.smooth_l1_loss(
                    torch.log1p(torch.relu(predicted_growth)),
                    torch.log1p(expected_micro_growth),
                )
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
            optimizer.step()
            rows = int(seq_users.shape[0])
            total_loss += float(loss.detach().cpu()) * rows
            total_rows += rows
        epoch_loss = total_loss / max(total_rows, 1)
        loss_curve.append(epoch_loss)
        if epoch_loss < best_loss:
            best_loss = epoch_loss
            best_state = copy.deepcopy(model.state_dict())

    if best_state is not None:
        model.load_state_dict(best_state)
    model.training_summary = {"epoch_loss_curve": loss_curve, "final_epoch_loss": loss_curve[-1] if loss_curve else None}
    return model


def _evaluate_model(
    model,
    tensors,
    windows: Sequence[PrefixWindow],
    *,
    spec: AdapterSpec,
    candidate_ids: Sequence[int],
    batch_size: int,
    device,
    torch,
    DataLoader,
    TensorDataset,
    k_list: Sequence[int],
) -> dict[str, Any]:
    dataset = TensorDataset(*[tensor.to(device) for tensor in tensors])
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False)
    model.eval()
    final_predictions = []
    trend_predictions = []
    logits_rows = []
    with torch.no_grad():
        for seq_users, seq_times, relation_ids, observed_counts, obs_ratios, _final_logs, _trend_logs, _targets in loader:
            output = model(seq_users, seq_times, relation_ids, observed_counts, obs_ratios)
            final_predictions.extend(torch.expm1(output["final_log"]).detach().cpu().numpy().tolist())
            trend_predictions.extend(torch.expm1(output["trend_log"]).detach().cpu().numpy().tolist())
            if spec.micro_supported:
                logits_rows.append(output["logits"].detach().cpu())

    result: dict[str, Any] = {
        "eval_window_count": len(windows),
        "macro_supported": spec.macro_supported,
        "micro_supported": spec.micro_supported,
    }
    if spec.macro_supported:
        result.update(
            compute_macro_metrics(
                observed_sizes=[window.observed_size for window in windows],
                final_sizes=[window.final_size for window in windows],
                predicted_sizes=final_predictions,
                trend_true=[window.trend_counts for window in windows],
                trend_pred=trend_predictions,
            )
        )
    if spec.micro_supported:
        logits = torch.cat(logits_rows, dim=0) if logits_rows else torch.empty((0, 0))
        result.update(_micro_metrics_from_logits(logits, windows, candidate_ids=candidate_ids, k_list=k_list, torch=torch))
    return result


def _micro_metrics_from_logits(logits, windows: Sequence[PrefixWindow], *, candidate_ids: Sequence[int], k_list: Sequence[int], torch) -> dict[str, float]:
    candidate_ids = [int(candidate_id) for candidate_id in candidate_ids if int(candidate_id) >= FIRST_REAL_USER_ID]
    candidate_set = set(candidate_ids)
    requested = len(windows)
    evaluable = [index for index, window in enumerate(windows) if int(window.target_vocab_id) in candidate_set]
    metrics: dict[str, float] = {
        "candidate_recall": float(len(evaluable) / requested) if requested else 0.0,
        "candidate_recall_full": float(len(evaluable) / requested) if requested else 0.0,
        "target_oov_count": float(requested - len(evaluable)),
        "evaluated_micro_count": float(len(evaluable)),
        "mrr": 0.0,
    }
    for k in k_list:
        metrics[f"hits@{k}"] = 0.0
        metrics[f"map@{k}"] = 0.0
        metrics[f"ndcg@{k}"] = 0.0
    if not evaluable or logits.numel() == 0:
        return metrics

    candidate_tensor = torch.tensor(candidate_ids, dtype=torch.long)
    candidate_logits = logits[:, candidate_tensor]
    total = 0.0
    accum = {key: 0.0 for key in metrics if key.startswith(("hits@", "map@", "ndcg@"))}
    mrr_total = 0.0
    for index in evaluable:
        target = int(windows[index].target_vocab_id)
        target_position = candidate_ids.index(target)
        scores = candidate_logits[index]
        target_score = scores[target_position]
        rank = int((scores > target_score).sum().item()) + 1
        total += 1.0
        mrr_total += 1.0 / rank
        for k in k_list:
            if rank <= k:
                accum[f"hits@{k}"] += 1.0
                accum[f"map@{k}"] += 1.0 / rank
                accum[f"ndcg@{k}"] += 1.0 / math.log2(rank + 1)
    for key, value in accum.items():
        metrics[key] = value / total
    metrics["mrr"] = mrr_total / total
    return metrics


def run_fair_learned_adapter(
    data_dir: str | Path,
    *,
    model_name: str,
    dataset: str | None = None,
    obs_ratios: Sequence[float] = DEFAULT_OBS_RATIOS,
    epochs: int = 200,
    batch_size: int = 64,
    hidden_dim: int = 64,
    max_sequence_len: int = 128,
    trend_steps: int = DEFAULT_TREND_STEPS,
    relation_neighbor_count: int = DEFAULT_RELATION_NEIGHBORS,
    max_train_cascades: int = 0,
    max_eval_cascades: int = 0,
    max_train_users: int = 0,
    seed: int = 42,
    device: str = "cpu",
    lr: float = 1e-3,
    weight_decay: float = 1e-4,
    k_list: Sequence[int] = DEFAULT_K_LIST,
) -> dict[str, Any]:
    """Train and evaluate one same-protocol learned adapter."""

    if model_name not in MODEL_SPECS:
        return {"model": model_name, "status": "unsupported", "reason": "No fair learned adapter is registered."}
    torch, nn, DataLoader, TensorDataset, err = _safe_torch()
    dataset_name = dataset or Path(data_dir).name
    if err is not None:
        return {
            "model": model_name,
            "dataset": dataset_name,
            "status": "model_unavailable",
            "reason": f"PyTorch unavailable: {type(err).__name__}: {err}",
        }

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    target_device = torch.device("cuda" if device == "cuda" and torch.cuda.is_available() else "cpu")
    spec = MODEL_SPECS[model_name]
    splits = load_original_cascade_splits(
        data_dir,
        min_length=3,
        train_limit=max_train_cascades,
        valid_limit=max_eval_cascades,
        test_limit=max_eval_cascades,
    )
    train = splits["train"]
    valid = splits["valid"]
    test = splits["test"]
    eval_split = "test" if test else "valid"
    eval_cascades = test or valid
    if not train or not eval_cascades:
        return {
            "model": model_name,
            "dataset": dataset_name,
            "status": "missing_data",
            "reason": "Native FOREST train/eval cascade split is empty.",
        }

    vocabulary = build_training_user_vocabulary(train, max_train_users=max_train_users)
    social_graph_status = "edges_txt" if (Path(data_dir) / "edges.txt").exists() else "no_social_edges"
    audit = build_fair_protocol_audit(
        train_cascades=train,
        valid_cascades=valid,
        test_cascades=test,
        vocabulary=vocabulary,
        uses_original_splits=True,
        uses_train_only_vocabulary=True,
        uses_hash_buckets=False,
        uses_proxy_ranking=False,
        candidate_generation_reads_future_tail=False,
        future_nodes_injected=False,
        model_score_source="learned_logits",
        social_graph_status=social_graph_status,
    )
    if not gate_fair_protocol(audit):
        return {
            "model": model_name,
            "dataset": dataset_name,
            "status": "protocol_rejected",
            "fair_protocol_passed": False,
            "candidate_protocol_audit": audit,
        }

    relation_neighbors = _build_relation_neighbors(
        train,
        vocabulary,
        relation_neighbor_count=relation_neighbor_count,
    )
    train_windows = build_prefix_windows(
        train,
        split="train",
        obs_ratios=obs_ratios,
        vocabulary=vocabulary,
        trend_steps=trend_steps,
    )
    eval_windows = build_prefix_windows(
        eval_cascades,
        split=eval_split,
        obs_ratios=obs_ratios,
        vocabulary=vocabulary,
        trend_steps=trend_steps,
    )
    if not train_windows or not eval_windows:
        return {
            "model": model_name,
            "dataset": dataset_name,
            "status": "missing_data",
            "reason": "No train/eval prefix windows were produced.",
        }

    train_tensors, train_windows = _windows_to_tensors(
        train_windows,
        max_sequence_len=max_sequence_len,
        relation_neighbors=relation_neighbors,
        relation_neighbor_count=relation_neighbor_count,
        torch=torch,
    )
    eval_tensors, eval_windows = _windows_to_tensors(
        eval_windows,
        max_sequence_len=max_sequence_len,
        relation_neighbors=relation_neighbors,
        relation_neighbor_count=relation_neighbor_count,
        torch=torch,
    )
    model = _train_model(
        train_tensors,
        spec=spec,
        vocab_size=vocabulary.size,
        hidden_dim=hidden_dim,
        trend_steps=trend_steps,
        epochs=epochs,
        batch_size=batch_size,
        lr=lr,
        weight_decay=weight_decay,
        device=target_device,
        torch=torch,
        nn=nn,
        DataLoader=DataLoader,
        TensorDataset=TensorDataset,
    )
    metrics = _evaluate_model(
        model,
        eval_tensors,
        eval_windows,
        spec=spec,
        candidate_ids=vocabulary.candidate_ids,
        batch_size=batch_size,
        device=target_device,
        torch=torch,
        DataLoader=DataLoader,
        TensorDataset=TensorDataset,
        k_list=k_list,
    )
    row: dict[str, Any] = {
        "schema": "cogguard.propagation.fair_adapter_result.v1",
        "protocol_id": PROTOCOL_ID,
        "model": model_name,
        "dataset": dataset_name,
        "seed": int(seed),
        "status": "ok",
        "implementation_level": "same_protocol_learned_adapter",
        "method_family": spec.method_family,
        "methodology": spec.methodology,
        "macro_supported": spec.macro_supported,
        "micro_supported": spec.micro_supported,
        "fair_protocol_passed": True,
        "candidate_protocol_audit": audit,
        "train_cascades_used": len(train),
        "valid_cascades_used": len(valid),
        "eval_cascades_used": len(eval_cascades),
        "eval_split": eval_split,
        "train_windows": len(train_windows),
        "eval_windows": len(eval_windows),
        "epochs": int(epochs),
        "batch_size": int(batch_size),
        "hidden_dim": int(hidden_dim),
        "max_sequence_len": int(max_sequence_len),
        "trend_steps": int(trend_steps),
        "obs_ratios": [float(value) for value in obs_ratios],
        "vocabulary_size": vocabulary.size,
        "train_user_count": vocabulary.train_user_count,
        "candidate_count": len(vocabulary.candidate_ids),
        "training_loss_curve": model.training_summary["epoch_loss_curve"],
        "final_epoch_loss": model.training_summary["final_epoch_loss"],
        "result_claim_boundary": (
            "Comparable only with rows that share protocol_id, split files, train-only vocabulary, "
            "candidate universe, metric implementation, and fair_protocol_passed=true."
        ),
    }
    row.update(metrics)
    if not spec.macro_supported:
        row.update({metric: None for metric in ("msle", "mae", "rmse", "mape_percent", "smape_percent", "direction_accuracy", "trend_mae", "trend_rmse")})
    if not spec.micro_supported:
        row.update({metric: None for metric in ("candidate_recall", "candidate_recall_full", "target_oov_count", "evaluated_micro_count", "mrr")})
        for k in k_list:
            row[f"hits@{k}"] = None
            row[f"map@{k}"] = None
            row[f"ndcg@{k}"] = None
    return row


__all__ = [
    "DEFAULT_OBS_RATIOS",
    "MODEL_SPECS",
    "AdapterSpec",
    "run_fair_learned_adapter",
]
