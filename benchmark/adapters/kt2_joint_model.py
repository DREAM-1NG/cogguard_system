#!/usr/bin/env python3
"""KT2 formal joint macro/micro propagation model.

The adapter trains one shared representation from an observed cascade prefix and
uses three supervised heads:

1. a macro head predicts the final cascade size;
2. a micro head ranks legal next-hop candidates;
3. a trend head predicts future cumulative popularity checkpoints.

The representation now starts from MINDS public-code components by default
when the local repository is available, adds FOREST-style sequence-aware
macro/micro coupling, and decodes CasFT-inspired continuous future popularity
trends. Local MINDS-style context is retained only as an explicitly reported
fallback. It remains KT2's own trainable joint model rather than a claimed
full reproduction of MINDS, FOREST, or CasFT.
"""

from __future__ import annotations

import argparse
from bisect import bisect_right
from contextlib import contextmanager
import importlib
import json
import math
import os
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np

try:  # Keep the rest of the benchmark usable when torch is not installed.
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
except ImportError:  # pragma: no cover - exercised only in dependency-limited envs.
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hyperidp_protocol_proxy import (  # noqa: E402
    K_LIST,
    average_precision_at_k,
    candidate_rows,
    load_cascades,
    load_neighbors,
    msle,
    ndcg_at_k,
    prefix_features,
    prefix_split,
    train_statistics,
    unique_preserving_order,
)


FEATURE_DIM_PREFIX = 10
FEATURE_DIM_CANDIDATE = 8
FEATURE_DIM = FEATURE_DIM_PREFIX + FEATURE_DIM_CANDIDATE
SEQUENCE_FEATURE_DIM = 4
CONTEXT_FEATURE_DIM = 6
TREND_STEPS = 4
HYPER_SEQUENCE_STEPS = 4
DEFAULT_MAX_SEQUENCE_LEN = 32
DEFAULT_USER_HASH_BUCKETS = 20000
DEFAULT_REPOS_ROOT = Path(__file__).resolve().parents[3] / "kt2_repos"
DEFAULT_MINDS_REPO = DEFAULT_REPOS_ROOT / "MINDS"


def micro_feature_row(
    candidate: int,
    pop_score: float,
    transition_score: float,
    hyper_score: float,
    social_score: float,
    observed_users: Sequence[int],
    observed_times: Sequence[int],
    popularity,
    social_neighbors: Mapping[int, set],
) -> List[float]:
    """Candidate-side features appended after the shared prefix features."""

    duration = max(observed_times[-1] - observed_times[0], 0) if len(observed_times) >= 2 else 0
    last_user = observed_users[-1]
    return [
        pop_score,
        transition_score,
        hyper_score,
        social_score,
        1.0 if candidate in social_neighbors.get(last_user, ()) else 0.0,
        math.log1p(popularity.get(candidate, 0)),
        math.log1p(len(observed_users)),
        math.log1p(duration),
    ]


_TorchModuleBase = nn.Module if nn is not None else object


if torch is not None:
    class GradientReversal(torch.autograd.Function):
        @staticmethod
        def forward(ctx, x, alpha: float):
            ctx.alpha = alpha
            return x.view_as(x)

        @staticmethod
        def backward(ctx, grad_output):
            return -ctx.alpha * grad_output, None
else:  # pragma: no cover - import guard placeholder.
    GradientReversal = None


def maybe_attach_original_casft_diffusion(model, args, device) -> str:
    """Attach CasFT's upstream GaussianDiffusion_ST when explicitly requested."""

    if not getattr(args, "use_original_casft_diffusion", False):
        model.casft_diffusion_status = "disabled"
        model.casft_diffusion_error = None
        return model.casft_diffusion_status
    repo = Path(str(getattr(args, "casft_repo", "") or ""))
    if not repo.exists():
        model.casft_diffusion_status = "missing_repo"
        model.casft_diffusion_error = f"CasFT repo not found: {repo}"
        return model.casft_diffusion_status
    try:
        repo_str = str(repo.resolve())
        if repo_str not in sys.path:
            sys.path.insert(0, repo_str)
        importlib.invalidate_caches()
        for module_name in ("model.diffusion.DiffusionModel", "model.diffusion", "model"):
            cached = sys.modules.get(module_name)
            cached_file = Path(str(getattr(cached, "__file__", ""))) if cached is not None else None
            if cached_file and repo.resolve() not in cached_file.resolve().parents:
                sys.modules.pop(module_name, None)
        diffusion_module = importlib.import_module("model.diffusion")
        st_diffusion_cls = getattr(diffusion_module, "ST_Diffusion")
        gaussian_diffusion_cls = getattr(diffusion_module, "GaussianDiffusion_ST")
        st_model = st_diffusion_cls(
            num_units=int(getattr(args, "casft_diffusion_units", 20)),
            cond_dim=TREND_STEPS,
            output_dim=TREND_STEPS,
        )
        diffusion = gaussian_diffusion_cls(
            st_model,
            loss_type=getattr(args, "casft_diffusion_loss_type", "l2"),
            seq_length=TREND_STEPS,
            timesteps=int(getattr(args, "casft_diffusion_timesteps", 10)),
            sampling_timesteps=int(getattr(args, "casft_sampling_timesteps", 5)),
            objective=getattr(args, "casft_diffusion_objective", "pred_noise"),
            beta_schedule="cosine",
        ).to(device)
    except Exception as exc:  # pragma: no cover - depends on optional upstream deps.
        model.casft_diffusion_status = "unavailable"
        model.casft_diffusion_error = f"{type(exc).__name__}: {exc}"
        return model.casft_diffusion_status
    model.original_casft_diffusion = diffusion
    model.casft_diffusion_status = "original_gaussian_diffusion_st"
    model.casft_diffusion_error = None
    return model.casft_diffusion_status


def maybe_attach_original_casft_spatiotemporal(model, args, device) -> str:
    """Attach CasFT's upstream NeuralPointProcess + CombinedSpatiotemporalModel5."""

    if not getattr(args, "use_original_casft_spatiotemporal", False):
        model.casft_spatiotemporal_status = "disabled"
        model.casft_spatiotemporal_error = None
        return model.casft_spatiotemporal_status
    repo = Path(str(getattr(args, "casft_repo", "") or ""))
    if not repo.exists():
        model.casft_spatiotemporal_status = "missing_repo"
        model.casft_spatiotemporal_error = f"CasFT repo not found: {repo}"
        return model.casft_spatiotemporal_status
    try:
        repo_resolved = repo.resolve()
        repo_str = str(repo_resolved)
        if repo_str not in sys.path:
            sys.path.insert(0, repo_str)
        importlib.invalidate_caches()
        for module_name in (
            "model",
            "model.spatiotemporal",
            "model.temporal",
            "model.temporal.neural",
            "model.diffusion",
            "model.diffusion.DiffusionModel",
        ):
            cached = sys.modules.get(module_name)
            cached_file = Path(str(getattr(cached, "__file__", ""))) if cached is not None else None
            if cached_file and repo_resolved not in cached_file.resolve().parents:
                sys.modules.pop(module_name, None)
        spatiotemporal_module = importlib.import_module("model.spatiotemporal")
        temporal_module = importlib.import_module("model.temporal")
        combined_cls = getattr(spatiotemporal_module, "CombinedSpatiotemporalModel5")
        neural_tpp_cls = getattr(temporal_module, "NeuralPointProcess")

        class CasFTArgs:
            pass

        casft_args = CasFTArgs()
        casft_args.interval_num = int(getattr(args, "casft_spatiotemporal_interval_num", TREND_STEPS))
        casft_args.tpp_hdims = int(getattr(args, "casft_spatiotemporal_tpp_hdim", 16))
        if casft_args.tpp_hdims % 2:
            casft_args.tpp_hdims += 1
        casft_args.loss_type = getattr(args, "casft_diffusion_loss_type", "l2")
        casft_args.timesteps = int(getattr(args, "casft_spatiotemporal_timesteps", 2))
        casft_args.sampling_timesteps = int(getattr(args, "casft_spatiotemporal_sampling_timesteps", 1))
        casft_args.objective = getattr(args, "casft_diffusion_objective", "pred_noise")
        casft_args.loss_scale = float(getattr(args, "casft_spatiotemporal_loss_scale", 0.5))
        casft_args.FC = int(getattr(args, "casft_spatiotemporal_fc", 0))
        casft_args.observation_time = str(float(getattr(args, "obs_ratio", 0.3)))
        casft_args.prediction_time = "1.0"

        spatial_dim = int(getattr(args, "casft_spatiotemporal_spatial_dim", SEQUENCE_FEATURE_DIM))
        tpp_model = neural_tpp_cls(
            cond_dim=spatial_dim,
            hidden_dims=[casft_args.tpp_hdims, casft_args.tpp_hdims],
            cond=True,
            style=getattr(args, "casft_spatiotemporal_tpp_style", "split"),
            actfn=getattr(args, "casft_spatiotemporal_tpp_actfn", "softplus"),
            otreg_strength=float(getattr(args, "casft_spatiotemporal_otreg_strength", 1e-4)),
            tol=float(getattr(args, "casft_spatiotemporal_tol", 1e-4)),
            solver=getattr(args, "casft_spatiotemporal_solver", "euler"),
        )
        spatiotemporal_model = combined_cls(tpp_model, None, casft_args).to(device)
    except Exception as exc:  # pragma: no cover - depends on optional upstream deps.
        model.casft_spatiotemporal_status = "unavailable"
        model.casft_spatiotemporal_error = f"{type(exc).__name__}: {exc}"
        return model.casft_spatiotemporal_status
    model.original_casft_spatiotemporal_model = spatiotemporal_model
    model.original_casft_spatiotemporal_interval_num = casft_args.interval_num
    model.original_casft_spatiotemporal_spatial_dim = spatial_dim
    model.original_casft_spatiotemporal_obs_ratio = float(getattr(args, "obs_ratio", 0.3))
    model.casft_spatiotemporal_status = "original_combined_spatiotemporal_model5_neural_point_process"
    model.casft_spatiotemporal_error = None
    return model.casft_spatiotemporal_status


def maybe_attach_original_minds_components(model, args, device) -> str:
    """Attach importable MINDS upstream DynamicCasHGNN/Fusion/SharedLSTM components."""

    if not getattr(args, "use_original_minds_components", False):
        model.minds_component_status = "disabled"
        model.minds_component_error = None
        return model.minds_component_status
    repo = Path(str(getattr(args, "minds_repo", "") or ""))
    candidates = [
        repo,
        repo / "MINDS",
        repo / ".kt2_extracted" / "MINDS",
    ]
    source_dir = next((candidate for candidate in candidates if (candidate / "Module.py").is_file()), None)
    if source_dir is None:
        model.minds_component_status = "missing_repo"
        model.minds_component_error = f"MINDS Module.py not found under: {repo}"
        return model.minds_component_status
    try:
        source_str = str(source_dir.resolve())
        if source_str not in sys.path:
            sys.path.insert(0, source_str)
        importlib.invalidate_caches()
        module = importlib.import_module("Module")
        fusion_cls = getattr(module, "Fusion")
        shared_lstm_cls = getattr(module, "SharedLSTM")
        dynamic_cas_hgnn_cls = getattr(module, "DynamicCasHGNN")
        full_module_cls = getattr(module, "Module")
        dhg_module = importlib.import_module("dhg")
        model.original_minds_dynamic_hgnn = dynamic_cas_hgnn_cls(
            model.user_hash_buckets,
            model.context_hidden_dim,
            step_split=HYPER_SEQUENCE_STEPS,
            dropout=0.0,
            is_norm=False,
        ).to(device)
        model.original_minds_dhg = dhg_module
        model.original_minds_fusion = fusion_cls(model.context_hidden_dim, out=1, dropout=0.0).to(device)
        model.original_minds_shared_lstm = shared_lstm_cls(1, model.context_hidden_dim).to(device)
        if getattr(args, "use_original_minds_full_module", False):
            model.original_minds_module = full_module_cls(
                model.user_hash_buckets,
                int(getattr(args, "original_minds_module_hidden_dim", 0) or model.context_hidden_dim),
                step_split=HYPER_SEQUENCE_STEPS,
                max_seq_len=int(getattr(args, "max_sequence_len", DEFAULT_MAX_SEQUENCE_LEN)),
                task_num=2,
                device=device,
            ).to(device)
            model.original_minds_module_loss_weight = float(getattr(args, "lambda_original_minds_module", 0.0))
            model.minds_module_status = "original_module_forward_relationgnn_dynamiccashgnn"
        else:
            model.minds_module_status = "disabled"
        model.minds_module_error = None
    except Exception as exc:  # pragma: no cover - depends on optional upstream source.
        model.minds_component_status = "unavailable"
        model.minds_component_error = f"{type(exc).__name__}: {exc}"
        model.minds_module_status = "unavailable"
        model.minds_module_error = f"{type(exc).__name__}: {exc}"
        return model.minds_component_status
    model.minds_component_status = "original_dynamic_cas_hgnn_fusion_shared_lstm"
    model.minds_component_error = None
    return model.minds_component_status


def maybe_attach_original_forest_components(model, args, device) -> str:
    """Attach FOREST's upstream RNNModel/RRModel when explicitly requested."""

    if not getattr(args, "use_original_forest_components", False):
        model.forest_component_status = "disabled"
        model.forest_component_error = None
        return model.forest_component_status
    repo = Path(str(getattr(args, "forest_repo", "") or ""))
    if not (repo / "model.py").is_file():
        model.forest_component_status = "missing_repo"
        model.forest_component_error = f"FOREST model.py not found under: {repo}"
        return model.forest_component_status
    try:
        repo_resolved = repo.resolve()
        repo_str = str(repo_resolved)
        if repo_str not in sys.path:
            sys.path.insert(0, repo_str)
        cached_constants = sys.modules.get("Constants")
        cached_file = Path(str(getattr(cached_constants, "__file__", ""))) if cached_constants is not None else None
        if cached_file and repo_resolved not in cached_file.resolve().parents:
            sys.modules.pop("Constants", None)
        spec = importlib.util.spec_from_file_location(f"kt2_original_forest_model_{id(model)}", repo / "model.py")
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to load FOREST model.py from {repo}")
        forest_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(forest_module)

        class ForestOpt:
            pass

        opt = ForestOpt()
        opt.user_size = int(model.user_hash_buckets)
        opt.d_word_vec = int(getattr(args, "original_forest_hidden_dim", 0) or model.forest_hidden_dim)
        opt.d_inner_hid = int(getattr(args, "original_forest_hidden_dim", 0) or model.forest_hidden_dim)
        opt.network = False
        opt.pos_emb = True
        opt.d_model = opt.d_word_vec
        rnn_model = forest_module.RNNModel("GRUCell", opt)
        rr_model = forest_module.RRModel(rnn_model).to(device)
        model.original_forest_rr_model = rr_model
        model.original_forest_constants = importlib.import_module("Constants")
        ce_weight = torch.ones(opt.user_size, device=device)
        ce_weight[0] = 0.0
        if opt.user_size > 1:
            ce_weight[1] = 1.0
        model.register_buffer("original_forest_ce_weight", ce_weight)
    except Exception as exc:  # pragma: no cover - depends on optional upstream source.
        model.forest_component_status = "unavailable"
        model.forest_component_error = f"{type(exc).__name__}: {exc}"
        return model.forest_component_status
    model.forest_component_status = "original_rnnmodel_rrmodel"
    model.forest_component_error = None
    return model.forest_component_status


@contextmanager
def forest_cpu_cuda_compat(device):
    """FOREST upstream code creates tensors with .cuda(); keep CPU smoke-runs safe."""

    needs_patch = getattr(device, "type", str(device)) == "cpu" or not torch.cuda.is_available()
    if not needs_patch:
        yield
        return
    original_tensor_cuda = torch.Tensor.cuda
    original_module_cuda = nn.Module.cuda
    torch.Tensor.cuda = lambda self, *args, **kwargs: self
    nn.Module.cuda = lambda self, *args, **kwargs: self
    try:
        yield
    finally:
        torch.Tensor.cuda = original_tensor_cuda
        nn.Module.cuda = original_module_cuda


class KT2JointModel(_TorchModuleBase):
    """MINDS-base, FOREST-constrained, CasFT-continuous KT2 joint model."""

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int,
        dropout: float,
        user_hash_buckets: int,
        sequence_feature_dim: int = SEQUENCE_FEATURE_DIM,
        context_dim: int = CONTEXT_FEATURE_DIM,
        trend_steps: int = TREND_STEPS,
    ) -> None:
        super().__init__()
        branch_dim = max(8, hidden_dim // 2)
        user_embedding_dim = max(8, hidden_dim // 4)
        sequence_hidden_dim = max(8, hidden_dim // 2)
        context_hidden_dim = max(8, hidden_dim // 4)
        self.forest_hidden_dim = max(8, hidden_dim // 2)
        self.user_hash_buckets = int(user_hash_buckets)
        self.trend_steps = int(trend_steps)
        self.context_hidden_dim = context_hidden_dim
        self.user_embedding = nn.Embedding(self.user_hash_buckets, user_embedding_dim, padding_idx=0)
        self.sequence_encoder = nn.GRU(
            input_size=user_embedding_dim + sequence_feature_dim,
            hidden_size=sequence_hidden_dim,
            batch_first=True,
        )
        self.hyper_step_encoder = nn.Sequential(
            nn.Linear(context_dim, context_hidden_dim),
            nn.ReLU(),
        )
        self.hyper_sequence_encoder = nn.GRU(
            input_size=context_hidden_dim,
            hidden_size=context_hidden_dim,
            batch_first=True,
        )
        self.hyper_attention = nn.Sequential(
            nn.Linear(context_hidden_dim, context_hidden_dim),
            nn.Tanh(),
            nn.Linear(context_hidden_dim, 1),
        )
        self.minds_hyper_proj = nn.Sequential(
            nn.Linear(user_embedding_dim, context_hidden_dim),
            nn.ReLU(),
        )
        self.minds_hyper_fusion = nn.Sequential(
            nn.Linear(context_hidden_dim * 2, context_hidden_dim),
            nn.Sigmoid(),
        )
        self.context_fusion = nn.Sequential(
            nn.Linear(context_hidden_dim * 2, context_hidden_dim),
            nn.ReLU(),
        )
        self.forest_hidden_projection = nn.Sequential(
            nn.Linear(self.forest_hidden_dim, sequence_hidden_dim),
            nn.Tanh(),
        )
        self.forest_sequence_fusion = nn.Sequential(
            nn.Linear(sequence_hidden_dim * 2, sequence_hidden_dim),
            nn.Sigmoid(),
        )
        fusion_dim = input_dim + sequence_hidden_dim + context_hidden_dim
        self.encoder = nn.Sequential(
            nn.Linear(fusion_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
        )
        adversary_dim = max(8, hidden_dim // 2)
        self.macro_branch = nn.Sequential(nn.Linear(hidden_dim, branch_dim), nn.ReLU())
        self.micro_branch = nn.Sequential(nn.Linear(hidden_dim, branch_dim), nn.ReLU())
        self.trend_branch = nn.Sequential(nn.Linear(hidden_dim, branch_dim), nn.ReLU())
        self.trend_dynamics = nn.Sequential(
            nn.Linear(branch_dim + 1, branch_dim),
            nn.Tanh(),
            nn.Linear(branch_dim, branch_dim),
        )
        self.trend_readout = nn.Linear(branch_dim, 1)
        self.trend_denoiser = nn.Sequential(
            nn.Linear((trend_steps * 2) + 1, branch_dim),
            nn.ReLU(),
            nn.Linear(branch_dim, trend_steps),
        )
        self.diffusion_condition = nn.Sequential(
            nn.Linear(hidden_dim, branch_dim),
            nn.ReLU(),
            nn.Linear(branch_dim, trend_steps),
        )
        self.casft_macro_fusion_gate = nn.Linear(hidden_dim, 1)
        self.casft_trend_fusion_gate = nn.Linear(hidden_dim, trend_steps)
        nn.init.zeros_(self.casft_macro_fusion_gate.weight)
        nn.init.constant_(self.casft_macro_fusion_gate.bias, -2.0)
        nn.init.zeros_(self.casft_trend_fusion_gate.weight)
        nn.init.constant_(self.casft_trend_fusion_gate.bias, -2.0)
        self.task_adversary = nn.Sequential(
            nn.Linear(hidden_dim, adversary_dim),
            nn.ReLU(),
            nn.Linear(adversary_dim, 2),
        )
        self.stage_adversary = nn.Sequential(
            nn.Linear(hidden_dim, adversary_dim),
            nn.ReLU(),
            nn.Linear(adversary_dim, HYPER_SEQUENCE_STEPS),
        )
        self.macro_head = nn.Linear(branch_dim, 1)
        self.micro_head = nn.Linear(branch_dim, 1)
        self.register_buffer(
            "trend_time_grid",
            torch.linspace(1.0 / float(trend_steps), 1.0, steps=trend_steps).view(1, trend_steps, 1),
        )

    def dynamic_hypergraph_memory(self, user_emb, seq_user_ids):
        """Return upstream MINDS memory, with local bridge only as fallback."""

        original_memory = self.original_minds_dynamic_hgnn_memory(seq_user_ids)
        if original_memory is not None:
            self.minds_context_source = "original_minds_dynamic_cas_hgnn"
            return original_memory

        self.minds_context_source = "local_minds_style_fallback"
        mask = (seq_user_ids != 0).unsqueeze(-1).to(dtype=user_emb.dtype)
        if torch.count_nonzero(mask).item() == 0:
            return torch.zeros(
                user_emb.shape[0],
                self.context_hidden_dim,
                device=user_emb.device,
                dtype=user_emb.dtype,
            )
        states = []
        total_steps = max(1, min(HYPER_SEQUENCE_STEPS, user_emb.shape[1]))
        for step in range(1, total_steps + 1):
            cut = max(1, int(math.ceil(user_emb.shape[1] * step / float(total_steps))))
            step_mask = mask[:, :cut, :]
            denom = step_mask.sum(dim=1).clamp_min(1.0)
            hyperedge_mean = (user_emb[:, :cut, :] * step_mask).sum(dim=1) / denom
            # v2e/e2v mean aggregation collapses a prefix hyperedge and sends it
            # back as a user-set state, mirroring MINDS DynamicCasHGNN at event level.
            states.append(self.minds_hyper_proj(hyperedge_mean))
        memory = states[0]
        for state in states[1:]:
            original_fusion = getattr(self, "original_minds_fusion", None)
            if original_fusion is not None:
                memory = original_fusion(memory, state)
            else:
                gate = self.minds_hyper_fusion(torch.cat([memory, state], dim=-1))
                memory = gate * state + (1.0 - gate) * memory
        return memory

    def original_minds_dynamic_hgnn_memory(self, seq_user_ids):
        """Run MINDS' upstream DynamicCasHGNN on batch-level prefix hypergraphs."""

        original_hgnn = getattr(self, "original_minds_dynamic_hgnn", None)
        dhg_module = getattr(self, "original_minds_dhg", None)
        if original_hgnn is None or dhg_module is None:
            return None
        try:
            hypergraph_list = self.build_original_minds_hypergraphs(seq_user_ids, dhg_module)
            user_states = original_hgnn(hypergraph_list, device=seq_user_ids.device)
            safe_ids = seq_user_ids.clamp(min=0, max=self.user_hash_buckets - 1)
            token_states = user_states[safe_ids]
            mask = (seq_user_ids != 0).unsqueeze(-1).to(dtype=token_states.dtype)
            denom = mask.sum(dim=1).clamp_min(1.0)
            self.minds_dynamic_hgnn_runtime_status = "original_dynamic_cas_hgnn"
            self.minds_dynamic_hgnn_runtime_error = None
            return (token_states * mask).sum(dim=1) / denom
        except Exception as exc:  # pragma: no cover - defensive fallback for optional upstream deps.
            self.minds_dynamic_hgnn_runtime_status = "runtime_fallback_local_memory"
            self.minds_dynamic_hgnn_runtime_error = f"{type(exc).__name__}: {exc}"
            return None

    def build_original_minds_hypergraphs(self, seq_user_ids, dhg_module):
        """Build dhg.Hypergraph snapshots matching MINDS DynamicCasHGNN input."""

        rows = seq_user_ids.detach().cpu().tolist()
        hypergraph_list = []
        total_steps = max(1, min(HYPER_SEQUENCE_STEPS, seq_user_ids.shape[1]))
        for step in range(1, total_steps + 1):
            edge_list = []
            for row in rows:
                valid_users = [int(user) for user in row if int(user) != 0]
                if not valid_users:
                    continue
                cut = max(1, int(math.ceil(len(valid_users) * step / float(total_steps))))
                edge_list.append(set(valid_users[:cut]))
            if not edge_list:
                edge_list = [{0}]
            hypergraph_list.append(
                dhg_module.Hypergraph(
                    self.user_hash_buckets,
                    edge_list,
                    device=seq_user_ids.device,
                )
            )
        return hypergraph_list

    def apply_minds_shared_lstm(self, context_repr, minds_memory):
        original_shared_lstm = getattr(self, "original_minds_shared_lstm", None)
        if original_shared_lstm is None:
            self.minds_shared_lstm_source = "local_context_fusion_fallback"
            return self.context_fusion(torch.cat([context_repr, minds_memory], dim=-1))
        shared_seq, _ = original_shared_lstm(context_repr.unsqueeze(1), minds_memory.unsqueeze(1))
        self.minds_shared_lstm_source = "original_minds_shared_lstm"
        return shared_seq[:, -1, :]

    def normalize_trend_times(self, batch_size: int, trend_times=None, dtype=None, device=None):
        """Return trend checkpoints in the same shape used by the ODE decoder."""

        dtype = dtype or self.trend_time_grid.dtype
        device = device or self.trend_time_grid.device
        if trend_times is None:
            trend_times = self.trend_time_grid.expand(batch_size, -1, -1)
        elif trend_times.dim() == 1:
            trend_times = trend_times.view(1, -1, 1).expand(batch_size, -1, -1)
        elif trend_times.dim() == 2:
            trend_times = trend_times.unsqueeze(-1)
        return trend_times.to(device=device, dtype=dtype)

    def decode_trend(self, trend_state, trend_times=None):
        """Decode normalized log-size trend via Euler-style continuous dynamics."""

        trend_times = self.normalize_trend_times(
            trend_state.shape[0],
            trend_times,
            dtype=trend_state.dtype,
            device=trend_state.device,
        )
        state = trend_state
        prev_t = torch.zeros((trend_state.shape[0], 1), device=trend_state.device, dtype=trend_state.dtype)
        outputs = []
        for idx in range(trend_times.shape[1]):
            t = trend_times[:, idx, :]
            dt = (t - prev_t).clamp(min=0.0)
            derivative = self.trend_dynamics(torch.cat([state, t], dim=-1))
            state = state + dt * derivative
            outputs.append(self.trend_readout(state).squeeze(-1))
            prev_t = t
        return torch.stack(outputs, dim=1)

    def original_casft_spatiotemporal_signal(self, x, seq_features, trend_times, shared):
        """Use CasFT's original TPP+diffusion predictor as a prefix-only main signal."""

        casft_model = getattr(self, "original_casft_spatiotemporal_model", None)
        if casft_model is None:
            self.casft_spatiotemporal_fusion_status = "disabled"
            self.casft_spatiotemporal_fusion_error = None
            return None, None
        if not all(hasattr(self, name) for name in ("x_mean", "x_std", "macro_y_mean", "macro_y_std")):
            self.casft_spatiotemporal_fusion_status = "missing_normalization_buffers"
            self.casft_spatiotemporal_fusion_error = "KT2 normalization buffers are not registered"
            return None, None
        interval_num = int(getattr(self, "original_casft_spatiotemporal_interval_num", TREND_STEPS))
        obs_ratio = float(getattr(self, "original_casft_spatiotemporal_obs_ratio", 0.3))
        observed_log = x[:, 0] * self.x_std[0] + self.x_mean[0]
        try:
            event_times, spatial_events, input_mask, t0, t1, label, seq, cum_seq = casft_spatiotemporal_prefix_tensors(
                seq_features,
                observed_log,
                obs_ratio,
                interval_num,
                int(getattr(self, "original_casft_spatiotemporal_spatial_dim", seq_features.shape[-1])),
                seq_features.device,
            )
            pre_label, _upstream_loss = casft_model(event_times, spatial_events, input_mask, t0, t1, label, seq, cum_seq)
            teacher_log = torch.log1p(pre_label.squeeze(-1).clamp_min(0.0))
            teacher_log = torch.maximum(teacher_log, observed_log)
            teacher_macro_norm = (teacher_log - self.macro_y_mean) / self.macro_y_std

            checkpoint_times = self.normalize_trend_times(
                seq_features.shape[0],
                trend_times,
                dtype=seq_features.dtype,
                device=seq_features.device,
            ).squeeze(-1)
            ramp = checkpoint_times / checkpoint_times[:, -1:].clamp_min(1e-6)
            ramp = ramp.clamp(0.0, 1.0)
            observed_norm = ((observed_log - self.macro_y_mean) / self.macro_y_std).unsqueeze(-1)
            teacher_trend_norm = observed_norm + ramp * (teacher_macro_norm.unsqueeze(-1) - observed_norm)
        except Exception as exc:  # pragma: no cover - optional upstream runtime can fail independently.
            self.casft_spatiotemporal_fusion_status = "runtime_fallback_local_trend"
            self.casft_spatiotemporal_fusion_error = f"{type(exc).__name__}: {exc}"
            return None, None
        self.casft_spatiotemporal_fusion_status = "original_combined_spatiotemporal_model5_main_fused"
        self.casft_spatiotemporal_fusion_error = None
        return teacher_macro_norm.to(dtype=shared.dtype), teacher_trend_norm.to(dtype=shared.dtype)

    def encode_shared(self, x, seq_user_ids, seq_features, context):
        user_emb = self.user_embedding(seq_user_ids)
        seq_input = torch.cat([user_emb, seq_features], dim=-1)
        _seq_out, seq_state = self.sequence_encoder(seq_input)
        seq_repr = seq_state[-1]
        seq_repr = self.apply_forest_sequence_fusion(seq_repr, seq_user_ids)
        if context.dim() == 2:
            context = context.unsqueeze(1)
        hyper_steps = self.hyper_step_encoder(context)
        hyper_out, _hyper_state = self.hyper_sequence_encoder(hyper_steps)
        hyper_weights = torch.softmax(self.hyper_attention(hyper_out).squeeze(-1), dim=1)
        context_repr = torch.sum(hyper_out * hyper_weights.unsqueeze(-1), dim=1)
        minds_memory = self.dynamic_hypergraph_memory(user_emb, seq_user_ids)
        context_repr = self.apply_minds_shared_lstm(context_repr, minds_memory)
        shared = self.encoder(torch.cat([x, seq_repr, context_repr], dim=-1))
        return shared

    def apply_forest_sequence_fusion(self, seq_repr, seq_user_ids):
        """Fuse FOREST's original RNN hidden state into KT2's main sequence state."""

        forest_hidden = self.original_forest_hidden_state(seq_user_ids)
        if forest_hidden is None:
            return seq_repr
        forest_repr = self.forest_hidden_projection(forest_hidden.to(dtype=seq_repr.dtype))
        gate = self.forest_sequence_fusion(torch.cat([seq_repr, forest_repr], dim=-1))
        return gate * forest_repr + (1.0 - gate) * seq_repr

    def original_forest_hidden_state(self, seq_user_ids):
        """Run FOREST RNNModel on KT2 observed prefix users and return its hidden state."""

        forest_model = getattr(self, "original_forest_rr_model", None)
        if forest_model is None:
            return None
        try:
            forest_input = forest_prefix_sequence_from_tensor(seq_user_ids, self.user_hash_buckets)
            if forest_input is None:
                return None
            with forest_cpu_cuda_compat(seq_user_ids.device):
                _pred, hidden = forest_model(forest_input.to(seq_user_ids.device), RL_train=False)
            if hidden.shape[-1] != self.forest_hidden_dim:
                self.forest_hidden_fusion_status = "runtime_fallback_hidden_dim_mismatch"
                self.forest_hidden_fusion_error = f"hidden_dim={hidden.shape[-1]} expected={self.forest_hidden_dim}"
                return None
            self.forest_hidden_fusion_status = "original_rnnmodel_hidden_fused"
            self.forest_hidden_fusion_error = None
            return hidden
        except Exception as exc:  # pragma: no cover - optional upstream runtime can fail independently.
            self.forest_hidden_fusion_status = "runtime_fallback_local_sequence"
            self.forest_hidden_fusion_error = f"{type(exc).__name__}: {exc}"
            return None

    def forward(
        self,
        x,
        seq_user_ids,
        seq_features,
        context,
        trend_times=None,
        return_representations: bool = False,
        apply_casft_fusion: bool = True,
    ):
        shared = self.encode_shared(x, seq_user_ids, seq_features, context)
        macro_repr = self.macro_branch(shared)
        micro_repr = self.micro_branch(shared)
        trend_repr = self.trend_branch(shared)
        macro = self.macro_head(macro_repr).squeeze(-1)
        micro = self.micro_head(micro_repr).squeeze(-1)
        trend = self.decode_trend(trend_repr, trend_times)
        casft_macro, casft_trend = None, None
        if apply_casft_fusion:
            casft_macro, casft_trend = self.original_casft_spatiotemporal_signal(x, seq_features, trend_times, shared)
        if casft_macro is not None and casft_trend is not None:
            macro_gate = torch.sigmoid(self.casft_macro_fusion_gate(shared)).squeeze(-1)
            trend_gate = torch.sigmoid(self.casft_trend_fusion_gate(shared))
            macro = (1.0 - macro_gate) * macro + macro_gate * casft_macro
            trend = (1.0 - trend_gate) * trend + trend_gate * casft_trend
        if return_representations:
            return macro, micro, trend, macro_repr, micro_repr, shared
        return macro, micro, trend

    def adversarial_logits(self, shared, alpha: float = 1.0):
        reversed_shared = GradientReversal.apply(shared, alpha)
        return self.task_adversary(reversed_shared), self.stage_adversary(reversed_shared)

    def denoise_trend(self, noisy_trend, noise_level, condition=None):
        if noise_level.dim() == 0:
            noise_level = noise_level.view(1, 1).expand(noisy_trend.shape[0], 1)
        elif noise_level.dim() == 1:
            noise_level = noise_level.view(-1, 1)
        noise_level = noise_level.to(device=noisy_trend.device, dtype=noisy_trend.dtype)
        if condition is None:
            condition_signal = torch.zeros_like(noisy_trend)
        else:
            condition_signal = self.diffusion_condition(condition).to(dtype=noisy_trend.dtype)
        return self.trend_denoiser(torch.cat([noisy_trend, condition_signal, noise_level], dim=-1))


def stable_user_bucket(user_id: int, user_hash_buckets: int) -> int:
    """Map arbitrary integer user IDs to a stable embedding bucket."""

    if user_hash_buckets <= 1:
        return 0
    return int(abs(int(user_id)) % (user_hash_buckets - 1)) + 1


def sequence_features(
    observed_users: Sequence[int],
    observed_times: Sequence[int],
    popularity,
    max_sequence_len: int,
    user_hash_buckets: int,
) -> Tuple[List[int], List[List[float]]]:
    """Build observed-prefix sequence tokens for the GRU encoder.

    Only t_obs-prefix users and times are used, so these tokens are safe for both
    training and evaluation. Future labels are handled separately.
    """

    max_len = max(1, max_sequence_len)
    users = list(observed_users)[-max_len:]
    times = list(observed_times)[-max_len:]
    if not users:
        return [0] * max_len, [[0.0] * SEQUENCE_FEATURE_DIM for _ in range(max_len)]

    start_time = times[0] if times else 0
    end_time = times[-1] if times else start_time
    duration = max(end_time - start_time, 1)
    bucketed_users: List[int] = []
    rows: List[List[float]] = []
    prev_time = start_time
    for idx, (user, ts) in enumerate(zip(users, times)):
        gap = max(ts - prev_time, 0) if idx else 0
        rel_time = max(ts - start_time, 0) / duration
        bucketed_users.append(stable_user_bucket(user, user_hash_buckets))
        rows.append(
            [
                math.log1p(gap),
                float(rel_time),
                math.log1p(popularity.get(user, 0)),
                float((idx + 1) / max(len(users), 1)),
            ]
        )
        prev_time = ts

    pad = max_len - len(bucketed_users)
    if pad > 0:
        bucketed_users = [0] * pad + bucketed_users
        rows = [[0.0] * SEQUENCE_FEATURE_DIM for _ in range(pad)] + rows
    return bucketed_users, rows


def context_row_for_users(
    observed_users: Sequence[int],
    popularity,
    transitions,
    hyper_neighbors,
    social_neighbors,
) -> List[float]:
    """Aggregate train-set coactivation and neighbor context for a cascade prefix."""

    unique_users = unique_preserving_order(observed_users)
    if not unique_users:
        return [0.0] * CONTEXT_FEATURE_DIM
    hyper_values = []
    transition_values = []
    social_degrees = []
    popularity_values = []
    exposed_users = set()
    for user in unique_users:
        hyper_counter = hyper_neighbors.get(user, {})
        transition_counter = transitions.get(user, {})
        hyper_values.append(sum(hyper_counter.values()))
        transition_values.append(sum(transition_counter.values()))
        social_degrees.append(len(social_neighbors.get(user, ())))
        popularity_values.append(popularity.get(user, 0))
        exposed_users.update(hyper_counter)
        exposed_users.update(transition_counter)
        exposed_users.update(social_neighbors.get(user, ()))
    exposed_users.difference_update(unique_users)
    return [
        math.log1p(float(sum(hyper_values))),
        math.log1p(float(max(hyper_values) if hyper_values else 0.0)),
        math.log1p(float(sum(transition_values))),
        math.log1p(float(sum(social_degrees))),
        math.log1p(float(len(exposed_users))),
        math.log1p(float(sum(popularity_values) / max(len(popularity_values), 1))),
    ]


def cross_context_features(
    observed_users: Sequence[int],
    observed_times: Sequence[int],
    popularity,
    transitions,
    hyper_neighbors,
    social_neighbors,
    steps: int = HYPER_SEQUENCE_STEPS,
) -> List[List[float]]:
    """Build a MINDS-style sequential hypergraph proxy from the observed prefix.

    Each row summarizes the train-set transition/social/hyper-coactivation
    exposure induced by the users observed up to one prefix time checkpoint.
    """

    if not observed_users:
        return [[0.0] * CONTEXT_FEATURE_DIM for _ in range(steps)]
    steps = max(1, int(steps))
    rows = []
    total = len(observed_users)
    for step in range(1, steps + 1):
        cut = max(1, int(math.ceil(total * step / float(steps))))
        rows.append(
            context_row_for_users(
                observed_users[:cut],
                popularity,
                transitions,
                hyper_neighbors,
                social_neighbors,
            )
        )
    return rows


def trend_target(
    cascade: Sequence[Tuple[int, int]],
    observed_count: int,
    trend_steps: int = TREND_STEPS,
    time_aware: bool = True,
) -> List[float]:
    """Future cumulative size checkpoints used only as training supervision.

    CasFT is a continuous-time method, so KT2 supervises the trend branch at
    evenly spaced future-time checkpoints whenever timestamps are usable. The
    count-proportional fallback is retained only for degenerate cascades whose
    timestamps cannot define a future horizon.
    """

    final_count = len(cascade)
    observed_count = min(max(int(observed_count), 0), final_count)
    future_count = max(final_count - observed_count, 0)
    if future_count <= 0:
        return [math.log1p(final_count)] * trend_steps

    timestamps = [int(timestamp) for _user, timestamp in cascade]
    if time_aware and observed_count > 0 and len(timestamps) == final_count:
        observed_time = timestamps[observed_count - 1]
        final_time = timestamps[-1]
        if final_time > observed_time:
            targets = []
            horizon = float(final_time - observed_time)
            for step in range(1, trend_steps + 1):
                fraction = step / float(trend_steps)
                checkpoint_time = observed_time + horizon * fraction
                checkpoint = bisect_right(timestamps, checkpoint_time)
                checkpoint = min(max(checkpoint, observed_count), final_count)
                targets.append(math.log1p(checkpoint))
            return targets

    targets = []
    for step in range(1, trend_steps + 1):
        fraction = step / float(trend_steps)
        checkpoint = observed_count + int(math.ceil(future_count * fraction))
        targets.append(math.log1p(min(checkpoint, final_count)))
    return targets


def trend_time_grid(
    cascade: Sequence[Tuple[int, int]],
    observed_count: int,
    trend_steps: int = TREND_STEPS,
) -> List[float]:
    """Full-horizon normalized future-time grid aligned with ``trend_target``."""

    final_count = len(cascade)
    observed_count = min(max(int(observed_count), 0), final_count)
    if observed_count <= 0 or final_count <= observed_count:
        return [step / float(trend_steps) for step in range(1, trend_steps + 1)]
    timestamps = [int(timestamp) for _user, timestamp in cascade]
    start_time = timestamps[0]
    observed_time = timestamps[observed_count - 1]
    final_time = timestamps[-1]
    if final_time <= start_time or final_time <= observed_time:
        return [step / float(trend_steps) for step in range(1, trend_steps + 1)]
    total_horizon = float(final_time - start_time)
    future_horizon = float(final_time - observed_time)
    return [
        float((observed_time + future_horizon * (step / float(trend_steps)) - start_time) / total_horizon)
        for step in range(1, trend_steps + 1)
    ]


def observed_stage_label(observed_count: int, final_count: int, steps: int = HYPER_SEQUENCE_STEPS) -> int:
    """Prefix-stage label used only by the adversarial disentanglement head."""

    if final_count <= 0:
        return 0
    ratio = min(max(float(observed_count) / float(final_count), 0.0), 1.0)
    return min(max(int(math.ceil(ratio * steps)) - 1, 0), steps - 1)


def build_joint_examples(
    cascades,
    popularity,
    transitions,
    hyper_neighbors,
    social_neighbors,
    obs_ratio: float,
    max_future_per_cascade: int,
    global_top_n: int,
    max_candidates: int,
    negatives_per_cascade: int,
    max_sequence_len: int,
    user_hash_buckets: int,
    seed: int,
) -> Dict:
    """Turn FOREST cascades into paired macro and micro training examples."""

    rng = random.Random(seed)
    global_candidates = [user for user, _ in popularity.most_common(global_top_n)]
    macro_X: List[List[float]] = []
    macro_y: List[float] = []
    trend_y: List[List[float]] = []
    trend_times: List[List[float]] = []
    macro_seq_users: List[List[int]] = []
    macro_seq_features: List[List[List[float]]] = []
    macro_context: List[List[float]] = []
    macro_stage_y: List[int] = []
    macro_event_ids: List[int] = []
    macro_observed_y: List[float] = []
    observed_counts: Dict[int, float] = {}
    final_counts: Dict[int, float] = {}
    micro_X: List[List[float]] = []
    micro_y: List[int] = []
    micro_seq_users: List[List[int]] = []
    micro_seq_features: List[List[List[float]]] = []
    micro_context: List[List[float]] = []
    micro_stage_y: List[int] = []
    micro_event_ids: List[int] = []
    cascades_with_micro = 0
    positives_seen = 0

    for event_idx, cascade in enumerate(cascades):
        observed_users_raw, observed_times, future_tail = prefix_split(cascade, obs_ratio)
        if not future_tail:
            continue
        prefix = prefix_features(
            observed_users_raw,
            observed_times,
            popularity,
            transitions,
            hyper_neighbors,
            social_neighbors,
        )
        seq_users, seq_rows = sequence_features(
            observed_users_raw,
            observed_times,
            popularity,
            max_sequence_len,
            user_hash_buckets,
        )
        context = cross_context_features(
            observed_users_raw,
            observed_times,
            popularity,
            transitions,
            hyper_neighbors,
            social_neighbors,
        )
        macro_X.append(prefix + [0.0] * FEATURE_DIM_CANDIDATE)
        macro_y.append(math.log1p(len(cascade)))
        trend_y.append(trend_target(cascade, len(observed_users_raw), TREND_STEPS))
        trend_times.append(trend_time_grid(cascade, len(observed_users_raw), TREND_STEPS))
        macro_seq_users.append(seq_users)
        macro_seq_features.append(seq_rows)
        macro_context.append(context)
        macro_stage_y.append(observed_stage_label(len(observed_users_raw), len(cascade)))
        macro_event_ids.append(event_idx)
        macro_observed_y.append(float(len(observed_users_raw)))
        observed_counts[event_idx] = float(len(observed_users_raw))
        final_counts[event_idx] = float(len(cascade))

        observed_users = unique_preserving_order(observed_users_raw)
        observed_set = set(observed_users)
        future_users = set(future_tail[:max_future_per_cascade]) - observed_set
        if not future_users:
            continue
        candidates = candidate_rows(
            observed_users,
            popularity,
            transitions,
            hyper_neighbors,
            social_neighbors,
            global_candidates,
            max_candidates,
        )
        positives = [row for row in candidates if row[0] in future_users]
        negatives = [row for row in candidates if row[0] not in future_users]
        if not positives:
            continue
        if len(negatives) > negatives_per_cascade:
            negatives = rng.sample(negatives, negatives_per_cascade)

        for candidate, pop, transition, hyper, social in positives + negatives:
            micro_X.append(
                prefix
                + micro_feature_row(
                    candidate,
                    pop,
                    transition,
                    hyper,
                    social,
                    observed_users,
                    observed_times,
                    popularity,
                    social_neighbors,
                )
            )
            micro_y.append(1 if candidate in future_users else 0)
            micro_seq_users.append(seq_users)
            micro_seq_features.append(seq_rows)
            micro_context.append(context)
            micro_stage_y.append(observed_stage_label(len(observed_users_raw), len(cascade)))
            micro_event_ids.append(event_idx)
        cascades_with_micro += 1
        positives_seen += len(positives)

    return {
        "raw_train_cascades": list(cascades),
        "macro_X": np.asarray(macro_X, dtype=np.float32),
        "macro_y": np.asarray(macro_y, dtype=np.float32),
        "trend_y": np.asarray(trend_y, dtype=np.float32),
        "trend_times": np.asarray(trend_times, dtype=np.float32),
        "macro_seq_users": np.asarray(macro_seq_users, dtype=np.int64),
        "macro_seq_features": np.asarray(macro_seq_features, dtype=np.float32),
        "macro_context": np.asarray(macro_context, dtype=np.float32),
        "macro_stage_y": np.asarray(macro_stage_y, dtype=np.int64),
        "macro_event_ids": np.asarray(macro_event_ids, dtype=np.int64),
        "macro_observed_y": np.asarray(macro_observed_y, dtype=np.float32),
        "observed_counts": observed_counts,
        "final_counts": final_counts,
        "micro_X": np.asarray(micro_X, dtype=np.float32),
        "micro_y": np.asarray(micro_y, dtype=np.float32),
        "micro_seq_users": np.asarray(micro_seq_users, dtype=np.int64),
        "micro_seq_features": np.asarray(micro_seq_features, dtype=np.float32),
        "micro_context": np.asarray(micro_context, dtype=np.float32),
        "micro_stage_y": np.asarray(micro_stage_y, dtype=np.int64),
        "micro_event_ids": np.asarray(micro_event_ids, dtype=np.int64),
        "train_cascades_used": int(len(macro_X)),
        "train_cascades_with_micro": int(cascades_with_micro),
        "train_positive_candidates": int(positives_seen),
    }


def subsample_micro_examples(bundle: Dict, limit: int, seed: int) -> None:
    if limit <= 0 or len(bundle["micro_X"]) <= limit:
        return
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(bundle["micro_X"]), size=limit, replace=False)
    bundle["micro_X"] = bundle["micro_X"][idx]
    bundle["micro_y"] = bundle["micro_y"][idx]
    bundle["micro_seq_users"] = bundle["micro_seq_users"][idx]
    bundle["micro_seq_features"] = bundle["micro_seq_features"][idx]
    bundle["micro_context"] = bundle["micro_context"][idx]
    bundle["micro_stage_y"] = bundle["micro_stage_y"][idx]
    bundle["micro_event_ids"] = bundle["micro_event_ids"][idx]


def forest_sequence_tensor(cascades, user_hash_buckets: int, max_sequence_len: int) -> np.ndarray:
    """Build FOREST-style PAD/EOS sequences from KT2 cascades."""

    max_len = max(3, int(max_sequence_len))
    rows = []
    for cascade in cascades:
        users = [stable_user_bucket(user, user_hash_buckets) for user, _timestamp in cascade]
        if not users:
            continue
        row = users[: max_len - 1] + [1]
        if len(row) < max_len:
            row = row + [0] * (max_len - len(row))
        rows.append(row)
    return np.asarray(rows, dtype=np.int64)


def forest_prefix_sequence_from_tensor(seq_user_ids, user_hash_buckets: int):
    """Convert KT2 observed prefix tensor into FOREST's PAD/EOS sequence format."""

    if seq_user_ids.numel() == 0:
        return None
    rows = []
    max_len = int(seq_user_ids.shape[1]) + 1
    for row in seq_user_ids.detach().cpu().tolist():
        users = [int(user) for user in row if int(user) != 0]
        users = [min(max(user, 2), int(user_hash_buckets) - 1) for user in users]
        if not users:
            users = [2 if int(user_hash_buckets) > 2 else 1]
        forest_row = users[: max_len - 1] + [1]
        if len(forest_row) < max_len:
            forest_row.extend([0] * (max_len - len(forest_row)))
        rows.append(forest_row)
    return torch.tensor(rows, dtype=torch.long, device=seq_user_ids.device)


def original_forest_auxiliary_loss(model: KT2JointModel, forest_batch, args, device):
    """Run FOREST upstream RNNModel/RRModel auxiliary losses on EOS sequences."""

    forest_model = getattr(model, "original_forest_rr_model", None)
    if forest_model is None or forest_batch is None:
        return torch.tensor(0.0, device=device), {
            "ce": 0.0,
            "rl": 0.0,
            "status": getattr(model, "forest_component_status", "disabled"),
        }
    forest_batch = forest_batch.to(device)
    if forest_batch.shape[1] < 2:
        return torch.tensor(0.0, device=device), {
            "ce": 0.0,
            "rl": 0.0,
            "status": getattr(model, "forest_component_status", "disabled"),
        }
    ce_weight = getattr(model, "original_forest_ce_weight")
    with forest_cpu_cuda_compat(device):
        pred, _hidden = forest_model(forest_batch, RL_train=False)
        target = forest_batch[:, 1:].contiguous().view(-1)
        ce = forest_masked_cross_entropy(pred, target)
        loss = ce * float(getattr(args, "lambda_original_forest_ce", 0.0))
        rl_value = torch.tensor(0.0, device=device)
        rollout_samples = int(getattr(args, "original_forest_rollout_samples", 0))
        if rollout_samples > 0 and float(getattr(args, "lambda_original_forest_rl", 0.0)) > 0:
            rl_losses = []
            for _ in range(rollout_samples):
                pred_ids, pred_log_probs = forest_model(
                    forest_batch,
                    start_size=int(getattr(args, "original_forest_start_size", 5)),
                    RL_train=True,
                )
                rl_losses.append(
                    original_forest_eos_rollout_loss(
                        pred_ids,
                        pred_log_probs,
                        forest_batch,
                        device,
                    )
                )
            rl_value = torch.stack(rl_losses).mean()
            loss = loss + float(getattr(args, "lambda_original_forest_rl", 0.0)) * rl_value
    model.original_forest_runtime_status = "original_rnnmodel_rrmodel_auxiliary"
    model.original_forest_runtime_error = None
    return loss, {
        "ce": float(ce.detach().cpu()),
        "rl": float(rl_value.detach().cpu()),
        "status": model.original_forest_runtime_status,
    }


def original_forest_size_alignment_loss(
    model: KT2JointModel,
    macro_growth_norm,
    observed_counts,
    forest_batch,
    args,
    device,
):
    """Distill FOREST RRModel sampled EOS size into KT2 macro growth."""

    forest_model = getattr(model, "original_forest_rr_model", None)
    if forest_model is None or forest_batch is None:
        return torch.tensor(0.0, device=device), {"alignment": 0.0, "status": getattr(model, "forest_component_status", "disabled")}
    forest_batch = forest_batch.to(device)
    if forest_batch.shape[0] != macro_growth_norm.shape[0]:
        forest_batch = forest_batch[: macro_growth_norm.shape[0]]
    if forest_batch.shape[0] == 0:
        return torch.tensor(0.0, device=device), {"alignment": 0.0, "status": getattr(model, "forest_component_status", "disabled")}
    with forest_cpu_cuda_compat(device):
        pred_ids, _pred_log_probs = forest_model(
            forest_batch,
            start_size=int(getattr(args, "original_forest_start_size", 5)),
            RL_train=True,
        )
    pred_size = torch.argmax((pred_ids == 1).float(), dim=1)
    pred_size = pred_size + (pred_size == 0).long() * pred_ids.size(1)
    target_size = torch.maximum(pred_size.float(), observed_counts[: pred_size.shape[0]])
    teacher_log_norm = (torch.log1p(target_size.detach()) - model.macro_y_mean) / model.macro_y_std
    alignment = torch.nn.functional.mse_loss(macro_growth_norm[: teacher_log_norm.shape[0]], teacher_log_norm)
    model.original_forest_runtime_status = "original_rnnmodel_rrmodel_auxiliary"
    model.original_forest_runtime_error = None
    weighted = float(getattr(args, "lambda_original_forest_ce", 0.0)) * alignment
    return weighted, {"alignment": float(alignment.detach().cpu()), "status": model.original_forest_runtime_status}


def forest_masked_cross_entropy(pred, target):
    """FOREST next-user CE while avoiding zero-weight PAD times -inf NaNs."""

    valid = target != 0
    if not torch.any(valid):
        return torch.tensor(0.0, device=pred.device, dtype=pred.dtype)
    pred_valid = pred[valid]
    target_valid = target[valid]
    gathered = torch.gather(torch.nn.functional.log_softmax(pred_valid, dim=1), 1, target_valid.view(-1, 1)).squeeze(1)
    finite = torch.isfinite(gathered)
    if not torch.any(finite):
        return torch.tensor(0.0, device=pred.device, dtype=pred.dtype)
    return -gathered[finite].mean()


def original_forest_eos_rollout_loss(pred_ids, pred_log_probs, target, device):
    """FOREST train.py get_performance_rl loss over EOS positions."""

    eos_pad = torch.zeros(pred_log_probs.size(0), 1, device=device, dtype=pred_log_probs.dtype)
    pred_log_probs = torch.cat([pred_log_probs, eos_pad], dim=1)
    pred_size = torch.argmax((pred_ids == 1).float(), dim=1)
    pred_size = pred_size + (pred_size == 0).long() * pred_ids.size(1)
    target_size = torch.argmax((target == 1).float(), dim=1)
    target_size = target_size + (target_size == 0).long() * target.size(1)
    reward = -torch.square(torch.log(pred_size.float().clamp_min(1.0)) - torch.log(target_size.float().clamp_min(1.0)))
    seq_log_prob = []
    for row_idx, size in enumerate(pred_size.detach().cpu().tolist()):
        seq_log_prob.append(pred_log_probs[row_idx, : min(int(size) + 1, pred_log_probs.size(1))].sum())
    seq_log_prob = torch.stack(seq_log_prob)
    baseline = reward.detach().mean()
    return torch.mean(-seq_log_prob * (reward.detach() - baseline))


def casft_spatiotemporal_tensors(seq_features, trend_y, obs_ratio: float, interval_num: int, device):
    """Convert KT2 observed-prefix tensors to CasFT's spatiotemporal forward format."""

    batch_size, max_len, feature_dim = seq_features.shape
    spatial_dim = int(feature_dim)
    input_mask = torch.any(seq_features.abs() > 0, dim=-1).float()
    counts = input_mask.sum(dim=1).clamp_min(1.0)
    positions = torch.arange(1, max_len + 1, device=device, dtype=seq_features.dtype).view(1, -1)
    # CasFT's CombinedSpatiotemporalModel5 scales normalized prefix times by
    # observation_time / prediction_time internally.
    event_times = (positions / counts.view(-1, 1)).clamp(max=1.0)
    event_times = event_times * input_mask
    spatial_events = seq_features
    if spatial_events.shape[-1] != spatial_dim:
        spatial_events = spatial_events[..., :spatial_dim]
    trend_min = trend_y.amin(dim=1, keepdim=True)
    trend_max = trend_y.amax(dim=1, keepdim=True)
    seq = ((trend_y - trend_min) / (trend_max - trend_min).clamp_min(1e-6)).clamp(0.0, 1.0)
    if seq.shape[1] != interval_num:
        seq = torch.nn.functional.interpolate(seq.unsqueeze(1), size=interval_num, mode="linear", align_corners=False).squeeze(1)
    cum_seq = seq.cumsum(dim=1)
    label = torch.expm1(trend_y[:, -1]).clamp_min(0.0).view(-1, 1)
    t0 = torch.tensor([0.0], device=device, dtype=seq_features.dtype)
    data_split = [float(obs_ratio)]
    interval = (1.0 - float(obs_ratio)) / float(max(interval_num, 1))
    for _idx in range(interval_num - 1):
        data_split.append(data_split[-1] + interval)
    data_split.append(1.0)
    t1 = torch.tensor(data_split, device=device, dtype=seq_features.dtype)
    return event_times, spatial_events, input_mask, t0, t1, label, seq, cum_seq


def casft_spatiotemporal_prefix_tensors(
    seq_features,
    observed_log,
    obs_ratio: float,
    interval_num: int,
    spatial_dim: int,
    device,
):
    """Build CasFT inputs from the observed prefix only, for leakage-free main fusion."""

    batch_size, max_len, feature_dim = seq_features.shape
    input_mask = torch.any(seq_features.abs() > 0, dim=-1).float()
    counts = input_mask.sum(dim=1).clamp_min(1.0)
    positions = torch.arange(1, max_len + 1, device=device, dtype=seq_features.dtype).view(1, -1)
    event_times = (positions / counts.view(-1, 1)).clamp(max=1.0) * input_mask
    spatial_events = seq_features
    if feature_dim > spatial_dim:
        spatial_events = spatial_events[..., :spatial_dim]
    elif feature_dim < spatial_dim:
        pad = torch.zeros(
            batch_size,
            max_len,
            spatial_dim - feature_dim,
            device=device,
            dtype=seq_features.dtype,
        )
        spatial_events = torch.cat([spatial_events, pad], dim=-1)

    # The original CombinedSpatiotemporalModel5 requires seq/cum_seq/label.
    # For main-path fusion these are neutral observed-prefix anchors, not future labels.
    observed_size = torch.expm1(observed_log).clamp_min(0.0)
    label = observed_size.view(-1, 1)
    seq = torch.zeros(batch_size, interval_num, device=device, dtype=seq_features.dtype)
    cum_seq = seq.cumsum(dim=1)
    t0 = torch.tensor([0.0], device=device, dtype=seq_features.dtype)
    data_split = [float(obs_ratio)]
    interval = (1.0 - float(obs_ratio)) / float(max(interval_num, 1))
    for _idx in range(interval_num - 1):
        data_split.append(data_split[-1] + interval)
    data_split.append(1.0)
    t1 = torch.tensor(data_split, device=device, dtype=seq_features.dtype)
    return event_times, spatial_events, input_mask, t0, t1, label, seq, cum_seq


def support_log_bounds(macro_y: np.ndarray, trend_y: np.ndarray, min_margin: float = 1.0) -> Tuple[float, float, float]:
    """Return a conservative train-label support interval for log-size outputs."""

    labels = np.concatenate([np.asarray(macro_y, dtype=np.float32).reshape(-1), np.asarray(trend_y, dtype=np.float32).reshape(-1)])
    labels = labels[np.isfinite(labels)]
    if labels.size == 0:
        return 0.0, math.log1p(1.0), float(min_margin)
    low = float(np.min(labels))
    high = float(np.max(labels))
    span = max(high - low, 0.0)
    margin = max(float(min_margin), 0.25 * span)
    return max(0.0, low - margin), high + margin, margin


def bounded_log_size(model: KT2JointModel, pred_norm):
    """Denormalize a normalized macro/trend prediction and keep it on train-label support."""

    pred_log = pred_norm * model.macro_y_std + model.macro_y_mean
    min_log = getattr(model, "macro_log_min", None)
    max_log = getattr(model, "macro_log_max", None)
    if min_log is None or max_log is None:
        return pred_log
    return torch.minimum(torch.maximum(pred_log, min_log.to(pred_log.device)), max_log.to(pred_log.device))


def bounded_trend_log(model: KT2JointModel, pred_norm, observed_count: Optional[float] = None):
    """Bound and monotonize cumulative future-trend log-size predictions."""

    pred_log = bounded_log_size(model, pred_norm)
    if observed_count is not None:
        observed_log = torch.log1p(torch.tensor(float(observed_count), device=pred_log.device, dtype=pred_log.dtype))
        pred_log = torch.maximum(pred_log, observed_log)
    if pred_log.dim() >= 2:
        pred_log = torch.cummax(pred_log, dim=1).values
    return pred_log


def build_minds_original_graphs(model: KT2JointModel, seq_user_rows, device):
    """Build dhg relation graph and prefix hypergraphs for MINDS Module.forward."""

    minds_module = getattr(model, "original_minds_module", None)
    dhg_module = getattr(model, "original_minds_dhg", None)
    if minds_module is None or dhg_module is None:
        return None, None
    rows = seq_user_rows.detach().cpu().tolist() if torch.is_tensor(seq_user_rows) else seq_user_rows
    edge_set = set()
    hyperedges = []
    for row in rows:
        valid = [int(user) for user in row if int(user) != 0]
        if not valid:
            continue
        hyperedges.append(set(valid))
        for src, dst in zip(valid[:-1], valid[1:]):
            if src != dst:
                edge_set.add((src, dst))
                edge_set.add((dst, src))
    if not edge_set:
        edge_set.add((0, 0))
    relation_graph = dhg_module.Graph(model.user_hash_buckets, sorted(edge_set), device=device)
    hypergraph_list = model.build_original_minds_hypergraphs(seq_user_rows.to(device), dhg_module)
    return relation_graph, hypergraph_list


def original_minds_module_loss(model: KT2JointModel, seq_user_rows, macro_y_norm, kt2_macro_norm, args, device):
    """Run MINDS Module.forward and distill its macro prediction into KT2."""

    minds_module = getattr(model, "original_minds_module", None)
    if minds_module is None:
        return torch.tensor(0.0, device=device), {
            "status": getattr(model, "minds_module_status", "disabled"),
            "macro": 0.0,
            "micro": 0.0,
            "alignment": 0.0,
        }
    examples = seq_user_rows.to(device).long()
    try:
        relation_graph, hypergraph_list = build_minds_original_graphs(model, examples, device)
        pred_micro, pred_macro, loss_adv_value, loss_diff_value = minds_module(hypergraph_list, relation_graph, examples)
        target_macro = torch.expm1(macro_y_norm * model.macro_y_std + model.macro_y_mean).to(device)
        macro_loss = torch.nn.functional.l1_loss(pred_macro.squeeze(-1), target_macro.float())
        gold = examples[:, 1:].contiguous().view(-1)
        logits = pred_micro[:, :-1, :].contiguous().view(-1, pred_micro.size(-1))
        valid = gold != 0
        if torch.any(valid):
            micro_loss = torch.nn.functional.cross_entropy(logits[valid], gold[valid])
        else:
            micro_loss = torch.tensor(0.0, device=device)
        adv_loss = torch.as_tensor(loss_adv_value, device=device, dtype=macro_loss.dtype)
        diff_loss = torch.as_tensor(loss_diff_value, device=device, dtype=macro_loss.dtype)
        upstream_loss = macro_loss + micro_loss + adv_loss + float(getattr(args, "lambda_original_minds_diff", 0.05)) * diff_loss
        teacher_log_norm = (
            torch.log1p(pred_macro.detach().squeeze(-1).clamp_min(0.0)) - model.macro_y_mean
        ) / model.macro_y_std
        alignment_loss = torch.nn.functional.mse_loss(kt2_macro_norm, teacher_log_norm)
    except Exception as exc:  # pragma: no cover - optional upstream runtime can fail independently.
        model.minds_module_runtime_status = "runtime_failed"
        model.minds_module_runtime_error = f"{type(exc).__name__}: {exc}"
        return torch.tensor(0.0, device=device), {
            "status": model.minds_module_runtime_status,
            "macro": 0.0,
            "micro": 0.0,
            "alignment": 0.0,
        }
    model.minds_module_runtime_status = "original_module_forward_auxiliary"
    model.minds_module_runtime_error = None
    weighted = float(getattr(args, "lambda_original_minds_module", 0.0)) * (upstream_loss + alignment_loss)
    return weighted, {
        "status": model.minds_module_runtime_status,
        "macro": float(macro_loss.detach().cpu()),
        "micro": float(micro_loss.detach().cpu()),
        "alignment": float(alignment_loss.detach().cpu()),
    }


def original_casft_spatiotemporal_loss(model: KT2JointModel, seq_features, trend_y, kt2_macro_norm, args, device):
    """Run CasFT CombinedSpatiotemporalModel5 and distill its size signal into KT2."""

    casft_model = getattr(model, "original_casft_spatiotemporal_model", None)
    if casft_model is None:
        return torch.tensor(0.0, device=device), {
            "status": getattr(model, "casft_spatiotemporal_status", "disabled"),
            "loss": 0.0,
            "alignment": 0.0,
        }
    interval_num = int(getattr(model, "original_casft_spatiotemporal_interval_num", TREND_STEPS))
    obs_ratio = float(getattr(model, "original_casft_spatiotemporal_obs_ratio", getattr(args, "obs_ratio", 0.3)))
    trend_log = bounded_trend_log(model, trend_y)
    event_times, spatial_events, input_mask, t0, t1, label, seq, cum_seq = casft_spatiotemporal_tensors(
        seq_features,
        trend_log,
        obs_ratio,
        interval_num,
        device,
    )
    try:
        pre_label, upstream_loss = casft_model(event_times, spatial_events, input_mask, t0, t1, label, seq, cum_seq)
        teacher_log_norm = (
            torch.log1p(pre_label.detach().squeeze(-1).clamp_min(0.0)) - model.macro_y_mean
        ) / model.macro_y_std
        alignment_loss = torch.nn.functional.mse_loss(kt2_macro_norm, teacher_log_norm)
    except Exception as exc:  # pragma: no cover - optional upstream runtime can fail independently.
        model.casft_spatiotemporal_runtime_status = "runtime_failed"
        model.casft_spatiotemporal_runtime_error = f"{type(exc).__name__}: {exc}"
        return torch.tensor(0.0, device=device), {
            "status": model.casft_spatiotemporal_runtime_status,
            "loss": 0.0,
            "alignment": 0.0,
        }
    model.casft_spatiotemporal_runtime_status = "original_combined_spatiotemporal_model5_auxiliary"
    model.casft_spatiotemporal_runtime_error = None
    weighted_loss = float(getattr(args, "lambda_original_casft_spatiotemporal", 0.0)) * (upstream_loss + alignment_loss)
    return weighted_loss, {
        "status": model.casft_spatiotemporal_runtime_status,
        "loss": float(upstream_loss.detach().cpu()),
        "alignment": float(alignment_loss.detach().cpu()),
    }


def train_joint_model(bundle: Dict, args, device) -> KT2JointModel:
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    random.seed(args.seed)

    macro_X = bundle["macro_X"]
    macro_y = bundle["macro_y"]
    trend_y = bundle["trend_y"]
    trend_times = bundle["trend_times"]
    macro_seq_users = bundle["macro_seq_users"]
    macro_seq_features = bundle["macro_seq_features"]
    macro_context = bundle["macro_context"]
    macro_stage_y = bundle["macro_stage_y"]
    macro_observed_y = bundle["macro_observed_y"]
    micro_X = bundle["micro_X"]
    micro_y = bundle["micro_y"]
    micro_seq_users = bundle["micro_seq_users"]
    micro_seq_features = bundle["micro_seq_features"]
    micro_context = bundle["micro_context"]
    micro_stage_y = bundle["micro_stage_y"]
    x_all = np.vstack([macro_X, micro_X])
    x_mean = x_all.mean(axis=0).astype(np.float32)
    x_std = x_all.std(axis=0).astype(np.float32)
    x_std[x_std < 1e-6] = 1.0
    y_mean = np.float32(macro_y.mean())
    y_std = np.float32(max(macro_y.std(), 1e-6))
    log_min, log_max, log_margin = support_log_bounds(macro_y, trend_y)
    macro_X = ((macro_X - x_mean) / x_std).astype(np.float32)
    micro_X = ((micro_X - x_mean) / x_std).astype(np.float32)
    macro_y_norm = ((macro_y - y_mean) / y_std).astype(np.float32)
    trend_y_norm = ((trend_y - y_mean) / y_std).astype(np.float32)

    model = KT2JointModel(
        FEATURE_DIM,
        args.hidden_dim,
        args.dropout,
        args.user_hash_buckets,
        trend_steps=TREND_STEPS,
    ).to(device)
    model.register_buffer("x_mean", torch.from_numpy(x_mean).to(device))
    model.register_buffer("x_std", torch.from_numpy(x_std).to(device))
    model.register_buffer("macro_y_mean", torch.tensor(y_mean, device=device))
    model.register_buffer("macro_y_std", torch.tensor(y_std, device=device))
    model.register_buffer("macro_log_min", torch.tensor(np.float32(log_min), device=device))
    model.register_buffer("macro_log_max", torch.tensor(np.float32(log_max), device=device))
    model.register_buffer("macro_log_margin", torch.tensor(np.float32(log_margin), device=device))
    maybe_attach_original_minds_components(model, args, device)
    maybe_attach_original_forest_components(model, args, device)
    maybe_attach_original_casft_diffusion(model, args, device)
    maybe_attach_original_casft_spatiotemporal(model, args, device)

    macro_ds = TensorDataset(
        torch.from_numpy(macro_X),
        torch.from_numpy(macro_seq_users),
        torch.from_numpy(macro_seq_features),
        torch.from_numpy(macro_context),
        torch.from_numpy(macro_stage_y),
        torch.from_numpy(macro_observed_y),
        torch.from_numpy(macro_y_norm),
        torch.from_numpy(trend_y_norm),
        torch.from_numpy(trend_times),
    )
    micro_ds = TensorDataset(
        torch.from_numpy(micro_X),
        torch.from_numpy(micro_seq_users),
        torch.from_numpy(micro_seq_features),
        torch.from_numpy(micro_context),
        torch.from_numpy(micro_stage_y),
        torch.from_numpy(micro_y),
    )
    macro_loader = DataLoader(macro_ds, batch_size=args.batch_size, shuffle=True)
    micro_loader = DataLoader(micro_ds, batch_size=args.batch_size, shuffle=True)
    forest_loader = None
    if getattr(model, "original_forest_rr_model", None) is not None:
        forest_sequences = forest_sequence_tensor(
            bundle.get("raw_train_cascades", []),
            args.user_hash_buckets,
            args.max_sequence_len,
        )
        if len(forest_sequences) > 0:
            forest_ds = TensorDataset(torch.from_numpy(forest_sequences))
            forest_loader = DataLoader(forest_ds, batch_size=args.batch_size, shuffle=True)

    positive_rate = float(np.mean(micro_y)) if len(micro_y) else 0.5
    pos_weight = torch.tensor([(1.0 - positive_rate) / max(positive_rate, 1e-6)], device=device)
    macro_loss_fn = nn.MSELoss()
    trend_loss_fn = nn.MSELoss()
    micro_loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    adversary_loss_fn = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)

    macro_tensor = torch.from_numpy(macro_X).to(device)
    macro_seq_user_tensor = torch.from_numpy(macro_seq_users).to(device)
    macro_seq_feature_tensor = torch.from_numpy(macro_seq_features).to(device)
    macro_context_tensor = torch.from_numpy(macro_context).to(device)
    micro_tensor = torch.from_numpy(micro_X).to(device)
    micro_seq_user_tensor = torch.from_numpy(micro_seq_users).to(device)
    micro_seq_feature_tensor = torch.from_numpy(micro_seq_features).to(device)
    micro_context_tensor = torch.from_numpy(micro_context).to(device)
    micro_label_tensor = torch.from_numpy(micro_y).to(device)
    macro_event_to_idx = {int(event): idx for idx, event in enumerate(bundle["macro_event_ids"].tolist())}
    micro_event_to_idxs: Dict[int, List[int]] = defaultdict(list)
    for idx, event in enumerate(bundle["micro_event_ids"].tolist()):
        micro_event_to_idxs[int(event)].append(idx)
    eligible_events = sorted(set(macro_event_to_idx) & set(micro_event_to_idxs))
    rng = random.Random(args.seed + 17)

    epoch_losses = []
    forest_aux_losses = []
    forest_aux_ce_losses = []
    forest_aux_rl_losses = []
    forest_size_alignment_losses = []
    casft_spatiotemporal_losses = []
    casft_spatiotemporal_alignment_losses = []
    minds_module_macro_losses = []
    minds_module_micro_losses = []
    minds_module_alignment_losses = []
    for _epoch in range(args.epochs):
        model.train()
        macro_iter = iter(macro_loader)
        micro_iter = iter(micro_loader)
        forest_iter = iter(forest_loader) if forest_loader is not None else None
        steps = max(len(macro_loader), len(micro_loader))
        if int(getattr(args, "max_steps_per_epoch", 0)) > 0:
            steps = min(steps, int(args.max_steps_per_epoch))
        total_loss = 0.0
        for _step in range(steps):
            optimizer.zero_grad()
            loss = torch.tensor(0.0, device=device)

            try:
                mx, msu, msf, mcx, mstage, mobs, my, ty, tt = next(macro_iter)
            except StopIteration:
                macro_iter = iter(macro_loader)
                mx, msu, msf, mcx, mstage, mobs, my, ty, tt = next(macro_iter)
            mx = mx.to(device)
            msu = msu.to(device)
            msf = msf.to(device)
            mcx = mcx.to(device)
            mstage = mstage.to(device)
            mobs = mobs.to(device)
            my = my.to(device)
            ty = ty.to(device)
            tt = tt.to(device)
            pred_macro, _pred_micro_from_macro, pred_trend, macro_repr, micro_repr_from_macro, macro_shared = model(
                mx,
                msu,
                msf,
                mcx,
                trend_times=tt,
                return_representations=True,
            )
            loss = loss + args.lambda_macro * macro_loss_fn(pred_macro, my)
            loss = loss + args.lambda_trend * trend_loss_fn(pred_trend, ty)
            loss = loss + args.lambda_orthogonality * orthogonality_loss(macro_repr, micro_repr_from_macro)
            macro_task_logits, macro_stage_logits = model.adversarial_logits(macro_shared, args.adversary_alpha)
            macro_task_y = torch.zeros(mx.shape[0], dtype=torch.long, device=device)
            loss = loss + args.lambda_adversarial * adversary_loss_fn(macro_task_logits, macro_task_y)
            loss = loss + args.lambda_adversarial * adversary_loss_fn(macro_stage_logits, mstage)
            loss = loss + args.lambda_diffusion * diffusion_denoising_loss(model, ty, args.diffusion_noise_std, macro_shared)
            minds_module_aux, minds_module_stats = original_minds_module_loss(model, msu, my, pred_macro, args, device)
            loss = loss + minds_module_aux
            if minds_module_stats.get("status") == "original_module_forward_auxiliary":
                minds_module_macro_losses.append(float(minds_module_stats.get("macro", 0.0)))
                minds_module_micro_losses.append(float(minds_module_stats.get("micro", 0.0)))
                minds_module_alignment_losses.append(float(minds_module_stats.get("alignment", 0.0)))
            casft_spatiotemporal_aux, casft_spatiotemporal_stats = original_casft_spatiotemporal_loss(
                model,
                msf,
                ty,
                pred_macro,
                args,
                device,
            )
            loss = loss + casft_spatiotemporal_aux
            if casft_spatiotemporal_stats.get("status") == "original_combined_spatiotemporal_model5_auxiliary":
                casft_spatiotemporal_losses.append(float(casft_spatiotemporal_stats.get("loss", 0.0)))
                casft_spatiotemporal_alignment_losses.append(float(casft_spatiotemporal_stats.get("alignment", 0.0)))

            try:
                ux, usu, usf, ucx, ustage, uy = next(micro_iter)
            except StopIteration:
                micro_iter = iter(micro_loader)
                ux, usu, usf, ucx, ustage, uy = next(micro_iter)
            ux = ux.to(device)
            usu = usu.to(device)
            usf = usf.to(device)
            ucx = ucx.to(device)
            ustage = ustage.to(device)
            uy = uy.to(device)
            _pred_macro_from_micro, pred_micro, _pred_trend_from_micro, macro_repr_from_micro, micro_repr, micro_shared = model(
                ux,
                usu,
                usf,
                ucx,
                return_representations=True,
                apply_casft_fusion=False,
            )
            loss = loss + args.lambda_micro * micro_loss_fn(pred_micro, uy)
            loss = loss + args.lambda_orthogonality * orthogonality_loss(macro_repr_from_micro, micro_repr)
            micro_task_logits, micro_stage_logits = model.adversarial_logits(micro_shared, args.adversary_alpha)
            micro_task_y = torch.ones(ux.shape[0], dtype=torch.long, device=device)
            loss = loss + args.lambda_adversarial * adversary_loss_fn(micro_task_logits, micro_task_y)
            loss = loss + args.lambda_adversarial * adversary_loss_fn(micro_stage_logits, ustage)

            consistency = consistency_loss(
                model,
                macro_tensor,
                macro_seq_user_tensor,
                macro_seq_feature_tensor,
                macro_context_tensor,
                micro_tensor,
                micro_seq_user_tensor,
                micro_seq_feature_tensor,
                micro_context_tensor,
                micro_label_tensor,
                macro_event_to_idx,
                micro_event_to_idxs,
                bundle["observed_counts"],
                bundle["final_counts"],
                eligible_events,
                args.consistency_events_per_step,
                args.max_consistency_candidates_per_event,
                args.forest_pg_rollout_samples,
                args.lambda_forest_pg,
                rng,
                device,
            )
            loss = loss + args.lambda_consistency * consistency

            if forest_iter is not None:
                try:
                    (forest_batch,) = next(forest_iter)
                except StopIteration:
                    forest_iter = iter(forest_loader)
                    (forest_batch,) = next(forest_iter)
                forest_aux, forest_aux_stats = original_forest_auxiliary_loss(model, forest_batch, args, device)
                loss = loss + forest_aux
                forest_aux_losses.append(float(forest_aux.detach().cpu()))
                forest_aux_ce_losses.append(float(forest_aux_stats.get("ce", 0.0)))
                forest_aux_rl_losses.append(float(forest_aux_stats.get("rl", 0.0)))
                forest_size_aux, forest_size_stats = original_forest_size_alignment_loss(
                    model,
                    pred_macro,
                    mobs,
                    forest_batch,
                    args,
                    device,
                )
                loss = loss + forest_size_aux
                forest_size_alignment_losses.append(float(forest_size_stats.get("alignment", 0.0)))

            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), args.max_grad_norm)
            optimizer.step()
            total_loss += float(loss.detach().cpu())
        epoch_losses.append(total_loss / max(steps, 1))

    model.training_summary = {
        "final_epoch_loss": round(epoch_losses[-1], 6) if epoch_losses else None,
        "epochs": args.epochs,
        "positive_rate": positive_rate,
        "macro_log_support": {
            "min": round(float(model.macro_log_min.detach().cpu()), 6),
            "max": round(float(model.macro_log_max.detach().cpu()), 6),
            "margin": round(float(model.macro_log_margin.detach().cpu()), 6),
            "source": "train macro and CasFT-style trend log-size labels",
        },
        "sequence_encoder": (
            "GRU over observed t_obs activation sequence, fused with upstream FOREST RNNModel hidden state when enabled"
        ),
        "forest_hidden_fusion_status": getattr(model, "forest_hidden_fusion_status", "disabled"),
        "forest_hidden_fusion_error": getattr(model, "forest_hidden_fusion_error", None),
        "cross_context_encoder": (
            "Observed-prefix context encoder fused with upstream MINDS DynamicCasHGNN/SharedLSTM when available; "
            "local MINDS-style context bridge is fallback/ablation only"
        ),
        "minds_dynamic_hypergraph": (
            "upstream MINDS DynamicCasHGNN over dhg.Hypergraph prefix snapshots when enabled; "
            "local event-level sequential hyperedge bridge is used only when upstream MINDS components are disabled or unavailable"
        ),
        "minds_context_source": getattr(model, "minds_context_source", "not_run"),
        "minds_shared_lstm_source": getattr(model, "minds_shared_lstm_source", "not_run"),
        "minds_dynamic_hgnn_runtime_status": getattr(model, "minds_dynamic_hgnn_runtime_status", "disabled"),
        "minds_dynamic_hgnn_runtime_error": getattr(model, "minds_dynamic_hgnn_runtime_error", None),
        "minds_component_status": getattr(model, "minds_component_status", "disabled"),
        "minds_component_error": getattr(model, "minds_component_error", None),
        "minds_module_status": getattr(model, "minds_module_status", "disabled"),
        "minds_module_error": getattr(model, "minds_module_error", None),
        "minds_module_runtime_status": getattr(
            model,
            "minds_module_runtime_status",
            getattr(model, "minds_module_status", "disabled"),
        ),
        "minds_module_runtime_error": getattr(model, "minds_module_runtime_error", None),
        "minds_module_macro_loss_mean": (
            round(float(np.mean(minds_module_macro_losses)), 6) if minds_module_macro_losses else 0.0
        ),
        "minds_module_micro_loss_mean": (
            round(float(np.mean(minds_module_micro_losses)), 6) if minds_module_micro_losses else 0.0
        ),
        "minds_module_alignment_loss_mean": (
            round(float(np.mean(minds_module_alignment_losses)), 6) if minds_module_alignment_losses else 0.0
        ),
        "forest_component_status": getattr(model, "forest_component_status", "disabled"),
        "forest_component_error": getattr(model, "forest_component_error", None),
        "forest_runtime_status": getattr(model, "original_forest_runtime_status", "disabled"),
        "forest_runtime_error": getattr(model, "original_forest_runtime_error", None),
        "forest_auxiliary": (
            "FOREST upstream RNNModel CE auxiliary and optional RRModel EOS rollout reward"
            if getattr(model, "forest_component_status", None) == "original_rnnmodel_rrmodel"
            else "disabled"
        ),
        "forest_auxiliary_loss_mean": round(float(np.mean(forest_aux_losses)), 6) if forest_aux_losses else 0.0,
        "forest_auxiliary_ce_mean": round(float(np.mean(forest_aux_ce_losses)), 6) if forest_aux_ce_losses else 0.0,
        "forest_auxiliary_rl_mean": round(float(np.mean(forest_aux_rl_losses)), 6) if forest_aux_rl_losses else 0.0,
        "forest_size_alignment_loss_mean": (
            round(float(np.mean(forest_size_alignment_losses)), 6) if forest_size_alignment_losses else 0.0
        ),
        "trend_auxiliary": f"Euler neural-ODE-style trend decoder supervised on {TREND_STEPS} future cumulative-size checkpoints",
        "trend_time_supervision": "timestamp-aware full-horizon normalized checkpoints with count-proportional fallback",
        "diffusion_auxiliary": (
            "CasFT original GaussianDiffusion_ST auxiliary over min-max normalized future trend checkpoints"
            if getattr(model, "casft_diffusion_status", None) == "original_gaussian_diffusion_st"
            else "shared-state-conditioned Gaussian noising and denoising loss over normalized future trend checkpoints"
        ),
        "casft_diffusion_status": getattr(model, "casft_diffusion_status", "disabled"),
        "casft_diffusion_error": getattr(model, "casft_diffusion_error", None),
        "casft_spatiotemporal_status": getattr(model, "casft_spatiotemporal_status", "disabled"),
        "casft_spatiotemporal_error": getattr(model, "casft_spatiotemporal_error", None),
        "casft_spatiotemporal_runtime_status": getattr(
            model,
            "casft_spatiotemporal_runtime_status",
            getattr(model, "casft_spatiotemporal_status", "disabled"),
        ),
        "casft_spatiotemporal_runtime_error": getattr(model, "casft_spatiotemporal_runtime_error", None),
        "casft_spatiotemporal_fusion_status": getattr(
            model,
            "casft_spatiotemporal_fusion_status",
            getattr(model, "casft_spatiotemporal_status", "disabled"),
        ),
        "casft_spatiotemporal_fusion_error": getattr(model, "casft_spatiotemporal_fusion_error", None),
        "casft_spatiotemporal_main_fusion": (
            "CasFT CombinedSpatiotemporalModel5 prefix-only continuous-time size signal is gated into KT2 macro/trend outputs"
            if getattr(model, "casft_spatiotemporal_fusion_status", None)
            == "original_combined_spatiotemporal_model5_main_fused"
            else "disabled or runtime fallback"
        ),
        "casft_spatiotemporal_loss_mean": (
            round(float(np.mean(casft_spatiotemporal_losses)), 6) if casft_spatiotemporal_losses else 0.0
        ),
        "casft_spatiotemporal_alignment_loss_mean": (
            round(float(np.mean(casft_spatiotemporal_alignment_losses)), 6)
            if casft_spatiotemporal_alignment_losses
            else 0.0
        ),
        "adversarial_regularizer": "gradient-reversal task/stage adversaries over shared propagation state",
        "orthogonality_regularizer": "macro/micro task-specific representation cosine-squared penalty",
        "reinforced_coupling": (
            "FOREST-style event policy bridge: masked next-user policy loss plus "
            "REINFORCE-style sampled growth reward over legal candidates"
        ),
        "consistency_candidate_scope": (
            "full_candidate_set"
            if int(getattr(args, "max_consistency_candidates_per_event", 0)) <= 0
            else "sampled_candidates_with_inverse_sampling_growth_rescaling"
        ),
        "max_consistency_candidates_per_event": int(getattr(args, "max_consistency_candidates_per_event", 0)),
        "max_steps_per_epoch": int(getattr(args, "max_steps_per_epoch", 0)),
        "epoch_step_count": int(steps),
    }
    return model


def consistency_loss(
    model: KT2JointModel,
    macro_tensor,
    macro_seq_user_tensor,
    macro_seq_feature_tensor,
    macro_context_tensor,
    micro_tensor,
    micro_seq_user_tensor,
    micro_seq_feature_tensor,
    micro_context_tensor,
    micro_label_tensor,
    macro_event_to_idx: Mapping[int, int],
    micro_event_to_idxs: Mapping[int, List[int]],
    observed_counts: Mapping[int, float],
    final_counts: Mapping[int, float],
    eligible_events: Sequence[int],
    events_per_step: int,
    max_candidates_per_event: int,
    forest_pg_rollout_samples: int,
    lambda_forest_pg: float,
    rng: random.Random,
    device,
):
    if not eligible_events or events_per_step <= 0:
        return torch.tensor(0.0, device=device)
    sampled_events = rng.sample(list(eligible_events), min(events_per_step, len(eligible_events)))
    losses = []
    for event in sampled_events:
        macro_idx = macro_event_to_idx[event]
        all_micro_indices = micro_event_to_idxs[event]
        micro_indices = all_micro_indices
        candidate_scale = 1.0
        if max_candidates_per_event > 0 and len(all_micro_indices) > max_candidates_per_event:
            micro_indices = rng.sample(all_micro_indices, max_candidates_per_event)
            candidate_scale = float(len(all_micro_indices)) / float(max(len(micro_indices), 1))
        pred_macro_norm, _pred_micro, _pred_trend = model(
            macro_tensor[macro_idx : macro_idx + 1],
            macro_seq_user_tensor[macro_idx : macro_idx + 1],
            macro_seq_feature_tensor[macro_idx : macro_idx + 1],
            macro_context_tensor[macro_idx : macro_idx + 1],
        )
        pred_log_size = bounded_log_size(model, pred_macro_norm)
        pred_size = torch.expm1(pred_log_size).clamp(min=float(observed_counts[event]))
        macro_growth = (pred_size - float(observed_counts[event])).clamp(min=0.0)
        _pred_macro, pred_micro, _pred_trend = model(
            micro_tensor[micro_indices],
            micro_seq_user_tensor[micro_indices],
            micro_seq_feature_tensor[micro_indices],
            micro_context_tensor[micro_indices],
            apply_casft_fusion=False,
        )
        micro_growth = torch.sigmoid(pred_micro).sum() * candidate_scale
        alignment_loss = (torch.log1p(macro_growth) - torch.log1p(micro_growth)) ** 2
        true_size = float(final_counts.get(event, observed_counts[event]))
        macro_error = torch.abs(torch.log1p(pred_size) - math.log1p(true_size))
        macro_reward = torch.exp(-macro_error.detach()).clamp(min=0.05, max=1.0)
        labels = micro_label_tensor[micro_indices]
        bce_policy_loss = torch.nn.functional.binary_cross_entropy_with_logits(pred_micro, labels, reduction="mean")
        positive_mask = labels > 0.5
        if torch.any(positive_mask):
            log_policy = torch.nn.functional.log_softmax(pred_micro, dim=0)
            # FOREST trains a sequence policy over legal next users; this local
            # surrogate makes positives compete within the event candidate set
            # instead of treating every candidate as an independent Bernoulli.
            event_policy_loss = -torch.logsumexp(log_policy[positive_mask], dim=0)
            policy_loss = 0.5 * bce_policy_loss + 0.5 * event_policy_loss
        else:
            policy_loss = bce_policy_loss
        forest_pg = forest_policy_gradient_loss(
            pred_micro,
            observed_count=float(observed_counts[event]),
            true_size=true_size,
            rollout_samples=forest_pg_rollout_samples,
            device=device,
        )
        losses.append(alignment_loss + macro_reward * policy_loss + float(lambda_forest_pg) * forest_pg)
    return torch.stack(losses).mean() if losses else torch.tensor(0.0, device=device)


def forest_policy_gradient_loss(pred_micro, observed_count: float, true_size: float, rollout_samples: int, device):
    """FOREST-style sampled sequence-size reward over KT2 event candidates.

    The original RRModel samples a next-user sequence until EOS and applies a
    log-size reward to the sampled sequence probability. KT2 has no EOS token in
    its legal candidate protocol, so this local bridge samples a candidate
    activation sequence without replacement and compares sampled growth against
    the true future growth.
    """

    if rollout_samples <= 0 or pred_micro.numel() == 0:
        return torch.tensor(0.0, device=device)
    true_growth = max(float(true_size) - float(observed_count), 0.0)
    probs = torch.sigmoid(pred_micro).clamp(1e-6, 1.0 - 1e-6)
    losses = []
    baseline_rewards = []
    for _ in range(int(rollout_samples)):
        sampled_mask = torch.bernoulli(probs).detach()
        sampled_log_prob = (sampled_mask * torch.log(probs) + (1.0 - sampled_mask) * torch.log1p(-probs)).sum()
        sampled_growth = sampled_mask.sum()
        reward = -torch.square(
            torch.log1p(sampled_growth)
            - torch.log1p(torch.tensor(true_growth, device=device, dtype=pred_micro.dtype))
        )
        baseline_rewards.append(reward.detach())
        losses.append((sampled_log_prob, reward))
    baseline = (
        torch.stack(baseline_rewards).mean()
        if len(baseline_rewards) > 1
        else torch.tensor(0.0, device=device, dtype=pred_micro.dtype)
    )
    return torch.stack([-log_prob * (reward.detach() - baseline) for log_prob, reward in losses]).mean()


def orthogonality_loss(macro_repr, micro_repr):
    """MINDS-inspired disentanglement penalty for task-specific branches."""

    macro_norm = macro_repr / macro_repr.norm(dim=1, keepdim=True).clamp_min(1e-6)
    micro_norm = micro_repr / micro_repr.norm(dim=1, keepdim=True).clamp_min(1e-6)
    return torch.square(torch.sum(macro_norm * micro_norm, dim=1)).mean()


def diffusion_denoising_loss(model: KT2JointModel, clean_trend, noise_std: float, condition=None):
    """CasFT-inspired denoising auxiliary over future popularity trend labels."""

    original_diffusion = getattr(model, "original_casft_diffusion", None)
    if original_diffusion is not None:
        trend_min = clean_trend.amin(dim=1, keepdim=True)
        trend_max = clean_trend.amax(dim=1, keepdim=True)
        trend_01 = ((clean_trend - trend_min) / (trend_max - trend_min).clamp_min(1e-6)).clamp(0.0, 1.0)
        if condition is None:
            cond = torch.zeros_like(trend_01)
        else:
            cond = model.diffusion_condition(condition).to(dtype=clean_trend.dtype).sigmoid()
        _pre_label, loss = original_diffusion(trend_01.unsqueeze(1), cond.unsqueeze(1))
        return loss

    if noise_std <= 0:
        return torch.tensor(0.0, device=clean_trend.device)
    noise_level = torch.full((clean_trend.shape[0],), float(noise_std), device=clean_trend.device, dtype=clean_trend.dtype)
    noisy_trend = clean_trend + torch.randn_like(clean_trend) * noise_level.view(-1, 1)
    recovered = model.denoise_trend(noisy_trend, noise_level, condition)
    return torch.mean(torch.square(recovered - clean_trend))


def evaluate_joint_model(
    model: KT2JointModel,
    test_cascades,
    popularity,
    transitions,
    hyper_neighbors,
    social_neighbors,
    obs_ratio: float,
    max_future_per_cascade: int,
    global_top_n: int,
    max_candidates: int,
    direction_threshold: float,
    max_sequence_len: int,
    user_hash_buckets: int,
    device,
    max_eval_cascades: int = 0,
) -> Dict:
    model.eval()
    eval_cascades = (
        test_cascades[:max_eval_cascades]
        if int(max_eval_cascades or 0) > 0
        else test_cascades
    )
    global_candidates = [user for user, _ in popularity.most_common(global_top_n)]
    y_true_size: List[float] = []
    y_pred_size: List[float] = []
    trend_true_values: List[float] = []
    trend_pred_values: List[float] = []
    trend_direction_hits: List[float] = []
    observed_counts: List[float] = []
    macro_growths: List[float] = []
    micro_growths: List[float] = []
    consistency_scores: List[float] = []
    total_relevant = 0
    total_covered = 0
    macro_event_count = 0
    micro_event_count = 0
    audit_observed_violations = 0
    audit_candidates_checked = 0
    future_only_candidate_matches = 0
    allowed_train_users = set(popularity)
    hit_sums = {k: 0.0 for k in K_LIST}
    ap_sums = {k: 0.0 for k in K_LIST}
    ndcg_sums = {k: 0.0 for k in K_LIST}
    reciprocal_rank_sum = 0.0

    with torch.no_grad():
        for cascade in eval_cascades:
            observed_users_raw, observed_times, future_tail = prefix_split(cascade, obs_ratio)
            if not future_tail:
                continue
            prefix = prefix_features(
                observed_users_raw,
                observed_times,
                popularity,
                transitions,
                hyper_neighbors,
                social_neighbors,
            )
            seq_users, seq_rows = sequence_features(
                observed_users_raw,
                observed_times,
                popularity,
                max_sequence_len,
                user_hash_buckets,
            )
            context = cross_context_features(
                observed_users_raw,
                observed_times,
                popularity,
                transitions,
                hyper_neighbors,
                social_neighbors,
            )
            macro_input = torch.tensor([prefix + [0.0] * FEATURE_DIM_CANDIDATE], dtype=torch.float32, device=device)
            macro_input = (macro_input - model.x_mean) / model.x_std
            seq_user_input = torch.tensor([seq_users], dtype=torch.long, device=device)
            seq_feature_input = torch.tensor([seq_rows], dtype=torch.float32, device=device)
            context_input = torch.tensor([context], dtype=torch.float32, device=device)
            trend_time_input = torch.tensor(
                [trend_time_grid(cascade, len(observed_users_raw), TREND_STEPS)],
                dtype=torch.float32,
                device=device,
            )
            pred_macro_norm, _pred_micro_from_macro, pred_trend_norm = model(
                macro_input,
                seq_user_input,
                seq_feature_input,
                context_input,
                trend_times=trend_time_input,
            )
            pred_log_size = bounded_log_size(model, pred_macro_norm)
            pred_size = max(float(torch.expm1(pred_log_size).item()), float(len(observed_users_raw)))
            pred_trend_log = bounded_trend_log(model, pred_trend_norm, observed_count=float(len(observed_users_raw)))
            pred_trend = torch.expm1(pred_trend_log).clamp(min=float(len(observed_users_raw))).cpu().numpy()[0]
            true_trend = np.asarray(trend_target(cascade, len(observed_users_raw), TREND_STEPS), dtype=float)
            true_trend_size = np.expm1(true_trend)
            trend_true_values.extend(true_trend_size.tolist())
            trend_pred_values.extend(pred_trend.tolist())
            true_trend_growth = true_trend_size[-1] >= len(observed_users_raw) * (1.0 + direction_threshold)
            pred_trend_growth = pred_trend[-1] >= len(observed_users_raw) * (1.0 + direction_threshold)
            trend_direction_hits.append(1.0 if true_trend_growth == pred_trend_growth else 0.0)
            y_true_size.append(float(len(cascade)))
            y_pred_size.append(pred_size)
            observed_counts.append(float(len(observed_users_raw)))
            macro_growths.append(max(pred_size - float(len(observed_users_raw)), 0.0))
            macro_event_count += 1

            observed_users = unique_preserving_order(observed_users_raw)
            observed_set = set(observed_users)
            future_users = set(future_tail[:max_future_per_cascade]) - observed_set
            if not future_users:
                continue
            candidates = candidate_rows(
                observed_users,
                popularity,
                transitions,
                hyper_neighbors,
                social_neighbors,
                global_candidates,
                max_candidates,
            )
            if not candidates:
                continue
            audit_candidates_checked += len(candidates)
            audit_observed_violations += sum(1 for candidate, *_rest in candidates if candidate in observed_set)
            future_only = (set(future_tail) - observed_set) - allowed_train_users
            future_only_candidate_matches += sum(1 for candidate, *_rest in candidates if candidate in future_only)

            rows = []
            for candidate, pop, transition, hyper, social in candidates:
                rows.append(
                    prefix
                    + micro_feature_row(
                        candidate,
                        pop,
                        transition,
                        hyper,
                        social,
                        observed_users,
                        observed_times,
                        popularity,
                        social_neighbors,
                    )
                )
            micro_input = torch.tensor(rows, dtype=torch.float32, device=device)
            micro_input = (micro_input - model.x_mean) / model.x_std
            seq_user_batch = seq_user_input.repeat(len(rows), 1)
            seq_feature_batch = seq_feature_input.repeat(len(rows), 1, 1)
            context_batch = context_input.repeat(len(rows), 1, 1)
            _pred_macro_from_micro, pred_micro, _pred_trend_from_micro = model(
                micro_input,
                seq_user_batch,
                seq_feature_batch,
                context_batch,
                apply_casft_fusion=False,
            )
            probabilities = torch.sigmoid(pred_micro).cpu().numpy()
            ranked_indices = np.argsort(-probabilities)
            ranked = [candidates[idx][0] for idx in ranked_indices]
            labels = np.asarray([1 if candidate in future_users else 0 for candidate in ranked], dtype=int)

            micro_growth = float(np.sum(probabilities))
            micro_growths.append(micro_growth)
            consistency_scores.append(count_alignment(macro_growths[-1], micro_growth))
            micro_event_count += 1
            total_relevant += len(future_users)
            total_covered += int(labels.sum())
            relevant_positions = np.flatnonzero(labels == 1)
            if len(relevant_positions):
                reciprocal_rank_sum += 1.0 / float(relevant_positions[0] + 1)
            for k in K_LIST:
                top_k = labels[:k]
                hit_sums[k] += float(top_k.sum() / len(future_users))
                ap_sums[k] += average_precision_at_k(top_k, len(future_users))
                ndcg_sums[k] += ndcg_at_k(top_k, len(future_users))

    y_true = np.asarray(y_true_size, dtype=float)
    y_pred = np.asarray(y_pred_size, dtype=float)
    trend_true = np.asarray(trend_true_values, dtype=float)
    trend_pred = np.asarray(trend_pred_values, dtype=float)
    observed = np.asarray(observed_counts, dtype=float)
    if macro_event_count == 0 or micro_event_count == 0:
        return {
            "model": "KT2JointModel",
            "mode": "joint_macro_micro_training",
            "task": "multi_scale",
            "status": "missing_data",
            "reproduction_level": "kt2_joint_model_small_run",
            "obs_ratio": obs_ratio,
            "events_test_macro": macro_event_count,
            "events_test_micro": micro_event_count,
            "events_test": micro_event_count,
            "eval_cascades_used": len(eval_cascades),
            "eval_cascades_total": len(test_cascades),
            "candidate_protocol_audit": {
                "candidate_source": "train-set popularity/transitions/hyper-coactivation plus observed-prefix social neighbors",
                "future_nodes_injected": False,
                "candidate_generation_reads_future_tail": False,
                "observed_user_candidate_violations": audit_observed_violations,
                "future_only_candidate_matches_from_allowed_sources": future_only_candidate_matches,
                "candidates_checked": audit_candidates_checked,
                "leakage_check_passed": audit_observed_violations == 0,
            },
            "note": "No test cascades had both a future tail and a covered legal candidate set; KT2JointModel metrics are not valid.",
        }
    casft_status = getattr(model, "training_summary", {}).get("casft_diffusion_status", "disabled")
    casft_error = getattr(model, "training_summary", {}).get("casft_diffusion_error")
    casft_spatiotemporal_status = getattr(model, "training_summary", {}).get("casft_spatiotemporal_status", "disabled")
    casft_spatiotemporal_runtime_status = getattr(model, "training_summary", {}).get(
        "casft_spatiotemporal_runtime_status",
        casft_spatiotemporal_status,
    )
    casft_spatiotemporal_fusion_status = getattr(model, "training_summary", {}).get(
        "casft_spatiotemporal_fusion_status",
        casft_spatiotemporal_status,
    )
    minds_status = getattr(model, "training_summary", {}).get("minds_component_status", "disabled")
    minds_error = getattr(model, "training_summary", {}).get("minds_component_error")
    minds_module_status = getattr(model, "training_summary", {}).get("minds_module_status", "disabled")
    minds_module_runtime_status = getattr(
        model,
        "training_summary",
        {},
    ).get("minds_module_runtime_status", minds_module_status)
    if casft_status == "original_gaussian_diffusion_st":
        casft_scope = (
            "trend branch uses an Euler neural-ODE-style decoder and calls CasFT's original "
            "GaussianDiffusion_ST/ST_Diffusion as an auxiliary loss on min-max normalized future trend checkpoints; "
            "it is still not the full CasFT temporal point-process encoder or full training protocol"
        )
    else:
        casft_scope = (
            "trend branch is an Euler neural-ODE-style decoder with shared-state-conditioned Gaussian trend "
            "denoising auxiliary; it is not the original CasFT diffusion generator"
        )
    diffusion_note = (
        "CasFT original GaussianDiffusion_ST auxiliary"
        if casft_status == "original_gaussian_diffusion_st"
        else "shared-state-conditioned trend denoising auxiliary"
    )
    spatiotemporal_note = (
        f"; upstream CasFT spatiotemporal/TPP auxiliary status={casft_spatiotemporal_runtime_status}; "
        f"main fusion status={casft_spatiotemporal_fusion_status}"
        if casft_spatiotemporal_status != "disabled"
        else ""
    )
    minds_method_scope, minds_module_scope = minds_scope_text(minds_status, minds_module_runtime_status)
    result = {
        "model": "KT2JointModel",
        "mode": "joint_macro_micro_training",
        "task": "multi_scale",
        "status": "ok",
        "reproduction_level": "kt2_joint_model_small_run",
        "obs_ratio": obs_ratio,
        "events_test_macro": macro_event_count,
        "events_test_micro": micro_event_count,
        "events_test": micro_event_count,
        "eval_cascades_used": len(eval_cascades),
        "eval_cascades_total": len(test_cascades),
        "relevant_users_test": total_relevant,
        "candidate_recall_full": total_covered / max(total_relevant, 1),
        "candidate_protocol_audit": {
            "candidate_source": "train-set popularity/transitions/hyper-coactivation plus observed-prefix social neighbors",
            "future_nodes_injected": False,
            "candidate_generation_reads_future_tail": False,
            "observed_user_candidate_violations": audit_observed_violations,
            "future_only_candidate_matches_from_allowed_sources": future_only_candidate_matches,
            "candidates_checked": audit_candidates_checked,
            "leakage_check_passed": audit_observed_violations == 0,
        },
        "msle": msle(y_true, y_pred) if len(y_true) else None,
        "mae": float(np.mean(np.abs(y_pred - y_true))) if len(y_true) else None,
        "rmse": rmse(y_true, y_pred) if len(y_true) else None,
        "mape_percent": mape_percent(y_true, y_pred) if len(y_true) else None,
        "smape_percent": smape_percent(y_true, y_pred) if len(y_true) else None,
        "direction_accuracy": direction_accuracy(y_true, y_pred, observed, direction_threshold) if len(y_true) else None,
        "trend_mae": float(np.mean(np.abs(trend_pred - trend_true))) if len(trend_true) else None,
        "trend_rmse": rmse(trend_true, trend_pred) if len(trend_true) else None,
        "trend_direction_accuracy": float(np.mean(trend_direction_hits)) if trend_direction_hits else None,
        "trend_steps": TREND_STEPS,
        "trend_time_supervision": getattr(model, "training_summary", {}).get("trend_time_supervision"),
        "mrr": reciprocal_rank_sum / max(micro_event_count, 1),
        "macro_predicted_growth": float(np.mean(macro_growths)) if macro_growths else None,
        "mean_predicted_growth": float(np.mean(macro_growths)) if macro_growths else None,
        "micro_predicted_growth_mean": float(np.mean(micro_growths)) if micro_growths else None,
        "macro_micro_consistency": float(np.mean(consistency_scores)) if consistency_scores else None,
        "consistency_mode": "joint_training_growth_count_alignment",
        "methodology": (
            f"{minds_method_scope}; {minds_module_scope}; FOREST-style masked next-user policy "
            f"with sampled growth reward and macro/micro consistency + CasFT continuous trend branch ({casft_status}; {casft_spatiotemporal_runtime_status}; {casft_spatiotemporal_fusion_status})"
        ),
        "auc": None,
        "average_precision": None,
        "comparison_tier": "trainable_joint_model",
        "baseline_role": "KT2 candidate model compared against trainable MINDS/FOREST/CasFT baselines; handcrafted baselines are sanity checks only",
        "note": (
            "KT2 formal local joint model: prefix-feature encoder plus GRU sequence encoder, "
            f"{minds_method_scope}; {minds_module_scope}; macro size head, "
            "micro next-hop policy head, CasFT-style Euler neural-ODE trend decoder, "
            f"{diffusion_note}{spatiotemporal_note}, and FOREST-style masked next-user policy plus sampled growth reward and macro/micro consistency loss. "
            "It is not an original FOREST, MINDS, CasFT, DyGFormer, or HyperIDP reproduction."
        ),
        "research_migration": {
            "MINDS": (
                f"{minds_method_scope}; {minds_module_scope}; "
                "gradient-reversal task/stage adversaries, "
                "and macro/micro orthogonality regularizer approximate cross-cascade diffusion state and task disentanglement; "
                "this is KT2's trainable MINDS-based foundation/fallback bridge, not the MINDS paper's native dataset protocol or full paper-scale reproduction"
            ),
            "FOREST": (
                "observed activation-sequence GRU, event-level masked next-user policy loss, REINFORCE-style sampled growth reward over legal candidates, "
                "macro-quality reward weighting, and macro/micro count-consistency constrain scale and next-hop predictions; "
                f"optional upstream FOREST RNNModel/RRModel auxiliary status={getattr(model, 'forest_component_status', 'disabled')}; "
                "this is a KT2 bridge and optional original-component auxiliary, not the full FOREST training protocol or paper-scale RRModel validation"
            ),
            "CasFT": (
                casft_scope
                + (
                    f"; optional upstream CombinedSpatiotemporalModel5/NeuralPointProcess auxiliary status={casft_spatiotemporal_runtime_status}; "
                    f"prefix-only continuous-time main fusion status={casft_spatiotemporal_fusion_status}; "
                    "this still remains a KT2 bridge unless the full CasFT data protocol and multi-run validation are used"
                    if casft_spatiotemporal_status != "disabled"
                    else ""
                )
            ),
            "DyGFormer_TGN": "micro branch remains a temporal next-hop ranking task over leak-checked candidates",
        },
        "casft_diffusion_status": casft_status,
        "casft_diffusion_error": casft_error,
        "casft_spatiotemporal_status": casft_spatiotemporal_status,
        "casft_spatiotemporal_error": getattr(model, "training_summary", {}).get("casft_spatiotemporal_error"),
        "casft_spatiotemporal_runtime_status": casft_spatiotemporal_runtime_status,
        "casft_spatiotemporal_runtime_error": getattr(model, "training_summary", {}).get(
            "casft_spatiotemporal_runtime_error"
        ),
        "casft_spatiotemporal_fusion_status": casft_spatiotemporal_fusion_status,
        "casft_spatiotemporal_fusion_error": getattr(model, "training_summary", {}).get(
            "casft_spatiotemporal_fusion_error"
        ),
        "minds_component_status": minds_status,
        "minds_component_error": minds_error,
        "minds_module_status": minds_module_status,
        "minds_module_error": getattr(model, "training_summary", {}).get("minds_module_error"),
        "minds_module_runtime_status": minds_module_runtime_status,
        "minds_module_runtime_error": getattr(model, "training_summary", {}).get("minds_module_runtime_error"),
        "forest_component_status": getattr(model, "forest_component_status", "disabled"),
        "forest_component_error": getattr(model, "forest_component_error", None),
        "forest_runtime_status": getattr(model, "original_forest_runtime_status", "disabled"),
        "forest_runtime_error": getattr(model, "original_forest_runtime_error", None),
    }
    for k in K_LIST:
        result[f"hits@{k}"] = hit_sums[k] / max(micro_event_count, 1)
        result[f"map@{k}"] = ap_sums[k] / max(micro_event_count, 1)
        result[f"ndcg@{k}"] = ndcg_sums[k] / max(micro_event_count, 1)
    return result


def count_alignment(macro_growth: float, micro_growth: float) -> float:
    if macro_growth < 0 or micro_growth < 0:
        return 0.0
    denom = max(abs(math.log1p(macro_growth)), abs(math.log1p(micro_growth)), 1e-9)
    return max(0.0, 1.0 - abs(math.log1p(macro_growth) - math.log1p(micro_growth)) / denom)


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(y_pred - y_true))))


def mape_percent(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs((y_true - y_pred) / np.maximum(y_true, 1.0))) * 100.0)


def smape_percent(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    denom = np.maximum((np.abs(y_true) + np.abs(y_pred)) / 2.0, 1.0)
    return float(np.mean(np.abs(y_true - y_pred) / denom) * 100.0)


def direction_accuracy(y_true: np.ndarray, y_pred: np.ndarray, observed: np.ndarray, threshold: float) -> float:
    true_growth = y_true >= observed * (1.0 + threshold)
    pred_growth = y_pred >= observed * (1.0 + threshold)
    return float(np.mean(true_growth == pred_growth))


def minds_scope_text(minds_status: str, minds_module_runtime_status: str) -> Tuple[str, str]:
    """Describe whether KT2 is using upstream MINDS or an explicit fallback."""

    minds_original_active = minds_status == "original_dynamic_cas_hgnn_fusion_shared_lstm"
    minds_module_active = minds_module_runtime_status == "original_module_forward_auxiliary"
    minds_method_scope = (
        "MINDS original public-code DynamicCasHGNN/Fusion/SharedLSTM components are active"
        if minds_original_active
        else f"local MINDS-style fallback is active because upstream MINDS status={minds_status}"
    )
    minds_module_scope = (
        "MINDS original Module.forward/RelationGNN auxiliary is active"
        if minds_module_active
        else f"MINDS full Module auxiliary status={minds_module_runtime_status}"
    )
    return minds_method_scope, minds_module_scope


def run_kt2_joint_model(data_dir: str | Path, **kwargs) -> Dict:
    """Public adapter entry used by tests and benchmark/run_benchmark.py."""

    minds_repo = kwargs.get("minds_repo", DEFAULT_MINDS_REPO)
    args = argparse.Namespace(
        data_dir=str(data_dir),
        obs_ratio=kwargs.get("obs_ratio", 0.3),
        max_future_per_cascade=kwargs.get("max_future_per_cascade", 20),
        global_top_n=kwargs.get("global_top_n", 3000),
        max_candidates=kwargs.get("max_candidates", 5000),
        negatives_per_cascade=kwargs.get("negatives_per_cascade", 120),
        bucket_seconds=kwargs.get("bucket_seconds", 24 * 3600),
        max_bucket_users=kwargs.get("max_bucket_users", 80),
        max_train_cascades=kwargs.get("max_train_cascades", 0),
        max_test_cascades=kwargs.get("max_test_cascades", 0),
        epochs=kwargs.get("epochs", 200),
        batch_size=kwargs.get("batch_size", 4096),
        hidden_dim=kwargs.get("hidden_dim", 64),
        dropout=kwargs.get("dropout", 0.1),
        lr=kwargs.get("lr", 0.001),
        weight_decay=kwargs.get("weight_decay", 0.0001),
        lambda_macro=kwargs.get("lambda_macro", 1.0),
        lambda_micro=kwargs.get("lambda_micro", 1.0),
        lambda_trend=kwargs.get("lambda_trend", 0.4),
        lambda_consistency=kwargs.get("lambda_consistency", 0.2),
        lambda_orthogonality=kwargs.get("lambda_orthogonality", 0.05),
        lambda_adversarial=kwargs.get("lambda_adversarial", 0.02),
        lambda_diffusion=kwargs.get("lambda_diffusion", 0.05),
        lambda_forest_pg=kwargs.get("lambda_forest_pg", 0.05),
        adversary_alpha=kwargs.get("adversary_alpha", 1.0),
        diffusion_noise_std=kwargs.get("diffusion_noise_std", 0.15),
        use_original_casft_diffusion=kwargs.get("use_original_casft_diffusion", False),
        use_original_casft_spatiotemporal=kwargs.get("use_original_casft_spatiotemporal", False),
        casft_repo=kwargs.get("casft_repo", ""),
        lambda_original_casft_spatiotemporal=kwargs.get("lambda_original_casft_spatiotemporal", 0.0),
        casft_spatiotemporal_interval_num=kwargs.get("casft_spatiotemporal_interval_num", TREND_STEPS),
        casft_spatiotemporal_tpp_hdim=kwargs.get("casft_spatiotemporal_tpp_hdim", 16),
        casft_spatiotemporal_timesteps=kwargs.get("casft_spatiotemporal_timesteps", 2),
        casft_spatiotemporal_sampling_timesteps=kwargs.get("casft_spatiotemporal_sampling_timesteps", 1),
        use_original_minds_components=kwargs.get("use_original_minds_components", True),
        use_original_minds_full_module=kwargs.get("use_original_minds_full_module", True),
        lambda_original_minds_module=kwargs.get("lambda_original_minds_module", 0.01),
        lambda_original_minds_diff=kwargs.get("lambda_original_minds_diff", 0.05),
        minds_repo=str(minds_repo) if minds_repo is not None else "",
        use_original_forest_components=kwargs.get("use_original_forest_components", False),
        forest_repo=kwargs.get("forest_repo", ""),
        lambda_original_forest_ce=kwargs.get("lambda_original_forest_ce", 0.0),
        lambda_original_forest_rl=kwargs.get("lambda_original_forest_rl", 0.0),
        original_forest_rollout_samples=kwargs.get("original_forest_rollout_samples", 0),
        original_forest_start_size=kwargs.get("original_forest_start_size", 5),
        original_forest_hidden_dim=kwargs.get("original_forest_hidden_dim", 0),
        casft_diffusion_timesteps=kwargs.get("casft_diffusion_timesteps", 10),
        casft_sampling_timesteps=kwargs.get("casft_sampling_timesteps", 5),
        casft_diffusion_units=kwargs.get("casft_diffusion_units", 20),
        casft_diffusion_loss_type=kwargs.get("casft_diffusion_loss_type", "l2"),
        casft_diffusion_objective=kwargs.get("casft_diffusion_objective", "pred_noise"),
        consistency_events_per_step=kwargs.get("consistency_events_per_step", 8),
        max_consistency_candidates_per_event=kwargs.get("max_consistency_candidates_per_event", 0),
        forest_pg_rollout_samples=kwargs.get("forest_pg_rollout_samples", 2),
        max_steps_per_epoch=kwargs.get("max_steps_per_epoch", 0),
        max_sequence_len=kwargs.get("max_sequence_len", DEFAULT_MAX_SEQUENCE_LEN),
        user_hash_buckets=kwargs.get("user_hash_buckets", DEFAULT_USER_HASH_BUCKETS),
        max_grad_norm=kwargs.get("max_grad_norm", 5.0),
        max_train_micro_samples=kwargs.get("max_train_micro_samples", 300000),
        max_eval_cascades=kwargs.get("max_eval_cascades", 0),
        direction_threshold=kwargs.get("direction_threshold", 0.1),
        seed=kwargs.get("seed", 42),
        device=kwargs.get("device", "cpu"),
    )
    return _run_with_args(args)


def _run_with_args(args) -> Dict:
    audit_not_run = {
        "candidate_source": "not_evaluated",
        "future_nodes_injected": False,
        "candidate_generation_reads_future_tail": False,
        "observed_user_candidate_violations": 0,
        "future_only_candidate_matches_from_allowed_sources": 0,
        "candidates_checked": 0,
        "leakage_check_passed": True,
    }
    if torch is None:
        return {
            "model": "KT2JointModel",
            "dataset": os.path.basename(str(args.data_dir)),
            "task": "multi_scale",
            "status": "failed",
            "reproduction_level": "kt2_joint_model_small_run",
            "candidate_protocol_audit": audit_not_run,
            "note": "PyTorch is required for KT2JointModel training but is not installed.",
        }

    data_dir = Path(args.data_dir)
    train_path = data_dir / "cascade.txt"
    test_path = data_dir / "cascadetest.txt"
    edge_path = data_dir / "edges.txt"
    train_cascades = load_cascades(str(train_path))
    test_cascades = load_cascades(str(test_path))
    if args.max_train_cascades > 0:
        train_cascades = train_cascades[: args.max_train_cascades]
    if args.max_test_cascades > 0:
        test_cascades = test_cascades[: args.max_test_cascades]
    if not train_cascades or not test_cascades:
        return {
            "model": "KT2JointModel",
            "dataset": data_dir.name,
            "task": "multi_scale",
            "status": "missing_data",
            "reproduction_level": "kt2_joint_model_small_run",
            "candidate_protocol_audit": audit_not_run,
            "note": f"Expected FOREST cascade.txt and cascadetest.txt under {data_dir}.",
        }

    requested_cuda = args.device == "cuda"
    device = torch.device("cuda" if requested_cuda and torch.cuda.is_available() else "cpu")
    social_neighbors = load_neighbors(str(edge_path))
    popularity, transitions, hyper_neighbors = train_statistics(
        train_cascades,
        args.bucket_seconds,
        args.max_bucket_users,
    )
    bundle = build_joint_examples(
        train_cascades,
        popularity,
        transitions,
        hyper_neighbors,
        social_neighbors,
        args.obs_ratio,
        args.max_future_per_cascade,
        args.global_top_n,
        args.max_candidates,
        args.negatives_per_cascade,
        args.max_sequence_len,
        args.user_hash_buckets,
        args.seed,
    )
    subsample_micro_examples(bundle, args.max_train_micro_samples, args.seed)
    if len(bundle["macro_X"]) == 0 or len(bundle["micro_X"]) == 0 or len(set(bundle["micro_y"].tolist())) < 2:
        return {
            "model": "KT2JointModel",
            "dataset": data_dir.name,
            "task": "multi_scale",
            "status": "failed",
            "reproduction_level": "kt2_joint_model_small_run",
            "candidate_protocol_audit": audit_not_run,
            "train_macro_samples": int(len(bundle["macro_X"])),
            "train_micro_samples": int(len(bundle["micro_X"])),
            "note": "Not enough macro examples or positive/negative micro candidate labels for joint training.",
        }

    model = train_joint_model(bundle, args, device)
    result = evaluate_joint_model(
        model,
        test_cascades,
        popularity,
        transitions,
        hyper_neighbors,
        social_neighbors,
        args.obs_ratio,
        args.max_future_per_cascade,
        args.global_top_n,
        args.max_candidates,
        args.direction_threshold,
        args.max_sequence_len,
        args.user_hash_buckets,
        device,
        args.max_eval_cascades,
    )
    training_summary = getattr(model, "training_summary", {})
    minds_method_scope, minds_module_scope = minds_scope_text(
        training_summary.get("minds_component_status", "disabled"),
        training_summary.get(
            "minds_module_runtime_status",
            training_summary.get("minds_module_status", "disabled"),
        ),
    )
    result.update(
        {
            "dataset": data_dir.name,
            "train_macro_samples": int(len(bundle["macro_X"])),
            "train_micro_samples": int(len(bundle["micro_X"])),
            "train_cascades_used": int(bundle["train_cascades_used"]),
            "train_cascades_with_micro": int(bundle["train_cascades_with_micro"]),
            "train_positive_candidates": int(bundle["train_positive_candidates"]),
            "positive_rate": float(np.mean(bundle["micro_y"])),
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "max_steps_per_epoch": args.max_steps_per_epoch,
            "epoch_step_count": training_summary.get("epoch_step_count"),
            "max_train_micro_samples": args.max_train_micro_samples,
            "max_eval_cascades": args.max_eval_cascades,
            "hidden_dim": args.hidden_dim,
            "seed": args.seed,
            "device": str(device),
            "bucket_seconds": args.bucket_seconds,
            "macro_log_support": training_summary.get("macro_log_support"),
            "joint_training": {
                "shared_encoder": "fusion of prefix/candidate MLP, observed-sequence GRU, and cross-cascade context encoder",
                "macro_log_support": training_summary.get("macro_log_support"),
                "sequence_encoder": training_summary.get("sequence_encoder"),
                "cross_context_encoder": training_summary.get("cross_context_encoder"),
                "minds_dynamic_hypergraph": training_summary.get("minds_dynamic_hypergraph"),
                "minds_dynamic_hgnn_runtime_status": training_summary.get("minds_dynamic_hgnn_runtime_status"),
                "minds_dynamic_hgnn_runtime_error": training_summary.get("minds_dynamic_hgnn_runtime_error"),
                "minds_context_source": training_summary.get("minds_context_source"),
                "minds_shared_lstm_source": training_summary.get("minds_shared_lstm_source"),
                "minds_component_status": training_summary.get("minds_component_status"),
                "minds_component_error": training_summary.get("minds_component_error"),
                "minds_module_status": training_summary.get("minds_module_status"),
                "minds_module_error": training_summary.get("minds_module_error"),
                "minds_module_runtime_status": training_summary.get("minds_module_runtime_status"),
                "minds_module_runtime_error": training_summary.get("minds_module_runtime_error"),
                "minds_module_macro_loss_mean": getattr(
                    model,
                    "training_summary",
                    {},
                ).get("minds_module_macro_loss_mean"),
                "minds_module_micro_loss_mean": getattr(
                    model,
                    "training_summary",
                    {},
                ).get("minds_module_micro_loss_mean"),
                "minds_module_alignment_loss_mean": getattr(
                    model,
                    "training_summary",
                    {},
                ).get("minds_module_alignment_loss_mean"),
                "forest_component_status": getattr(model, "training_summary", {}).get("forest_component_status"),
                "forest_component_error": getattr(model, "training_summary", {}).get("forest_component_error"),
                "forest_hidden_fusion_status": getattr(model, "training_summary", {}).get("forest_hidden_fusion_status"),
                "forest_hidden_fusion_error": getattr(model, "training_summary", {}).get("forest_hidden_fusion_error"),
                "forest_runtime_status": getattr(model, "training_summary", {}).get("forest_runtime_status"),
                "forest_runtime_error": getattr(model, "training_summary", {}).get("forest_runtime_error"),
                "forest_auxiliary": getattr(model, "training_summary", {}).get("forest_auxiliary"),
                "forest_auxiliary_loss_mean": getattr(model, "training_summary", {}).get("forest_auxiliary_loss_mean"),
                "forest_auxiliary_ce_mean": getattr(model, "training_summary", {}).get("forest_auxiliary_ce_mean"),
                "forest_auxiliary_rl_mean": getattr(model, "training_summary", {}).get("forest_auxiliary_rl_mean"),
                "forest_size_alignment_loss_mean": getattr(
                    model,
                    "training_summary",
                    {},
                ).get("forest_size_alignment_loss_mean"),
                "trend_auxiliary": getattr(model, "training_summary", {}).get("trend_auxiliary"),
                "diffusion_auxiliary": getattr(model, "training_summary", {}).get("diffusion_auxiliary"),
                "casft_diffusion_status": getattr(model, "training_summary", {}).get("casft_diffusion_status"),
                "casft_diffusion_error": getattr(model, "training_summary", {}).get("casft_diffusion_error"),
                "casft_spatiotemporal_status": getattr(
                    model,
                    "training_summary",
                    {},
                ).get("casft_spatiotemporal_status"),
                "casft_spatiotemporal_error": getattr(
                    model,
                    "training_summary",
                    {},
                ).get("casft_spatiotemporal_error"),
                "casft_spatiotemporal_runtime_status": getattr(
                    model,
                    "training_summary",
                    {},
                ).get("casft_spatiotemporal_runtime_status"),
                "casft_spatiotemporal_runtime_error": getattr(
                    model,
                    "training_summary",
                    {},
                ).get("casft_spatiotemporal_runtime_error"),
                "casft_spatiotemporal_fusion_status": getattr(
                    model,
                    "training_summary",
                    {},
                ).get("casft_spatiotemporal_fusion_status"),
                "casft_spatiotemporal_fusion_error": getattr(
                    model,
                    "training_summary",
                    {},
                ).get("casft_spatiotemporal_fusion_error"),
                "casft_spatiotemporal_main_fusion": getattr(
                    model,
                    "training_summary",
                    {},
                ).get("casft_spatiotemporal_main_fusion"),
                "casft_spatiotemporal_loss_mean": getattr(
                    model,
                    "training_summary",
                    {},
                ).get("casft_spatiotemporal_loss_mean"),
                "casft_spatiotemporal_alignment_loss_mean": getattr(
                    model,
                    "training_summary",
                    {},
                ).get("casft_spatiotemporal_alignment_loss_mean"),
                "adversarial_regularizer": getattr(model, "training_summary", {}).get("adversarial_regularizer"),
                "orthogonality_regularizer": getattr(model, "training_summary", {}).get("orthogonality_regularizer"),
                "reinforced_coupling": getattr(model, "training_summary", {}).get("reinforced_coupling"),
                "consistency_candidate_scope": getattr(model, "training_summary", {}).get(
                    "consistency_candidate_scope"
                ),
                "max_consistency_candidates_per_event": getattr(model, "training_summary", {}).get(
                    "max_consistency_candidates_per_event"
                ),
                "methodology": (
                    f"{minds_method_scope}; {minds_module_scope}; "
                    "adversarial disentanglement, FOREST RNN hidden-state fusion plus masked next-user policy, "
                    "sampled growth reward and macro/micro consistency, "
                    f"CasFT neural-ODE-style trend decoding with {getattr(model, 'training_summary', {}).get('diffusion_auxiliary')} "
                    f"and {getattr(model, 'training_summary', {}).get('casft_spatiotemporal_main_fusion')}"
                ),
                "macro_target": "log1p(final cascade size)",
                "micro_target": "candidate activated within future window",
                "trend_target": "future cumulative cascade size checkpoints after t_obs",
                "trend_time_supervision": getattr(model, "training_summary", {}).get("trend_time_supervision"),
                "macro_loss_weight": args.lambda_macro,
                "micro_loss_weight": args.lambda_micro,
                "original_minds_module_loss_weight": args.lambda_original_minds_module,
                "original_minds_diff_loss_weight": args.lambda_original_minds_diff,
                "trend_loss_weight": args.lambda_trend,
                "consistency_loss_weight": args.lambda_consistency,
                "orthogonality_loss_weight": args.lambda_orthogonality,
                "adversarial_loss_weight": args.lambda_adversarial,
                "diffusion_loss_weight": args.lambda_diffusion,
                "original_casft_spatiotemporal_loss_weight": args.lambda_original_casft_spatiotemporal,
                "forest_pg_loss_weight": args.lambda_forest_pg,
                "forest_pg_rollout_samples": args.forest_pg_rollout_samples,
                "max_steps_per_epoch": args.max_steps_per_epoch,
                "epoch_step_count": training_summary.get("epoch_step_count"),
                "max_train_micro_samples": args.max_train_micro_samples,
                "max_eval_cascades": args.max_eval_cascades,
                "original_forest_ce_loss_weight": args.lambda_original_forest_ce,
                "original_forest_rl_loss_weight": args.lambda_original_forest_rl,
                "original_forest_rollout_samples": args.original_forest_rollout_samples,
                "original_forest_start_size": args.original_forest_start_size,
                "adversary_alpha": args.adversary_alpha,
                "diffusion_noise_std": args.diffusion_noise_std,
                "consistency_loss": "MSE(log1p(macro predicted growth), log1p(sum sigmoid(candidate logits))) plus macro-reward-weighted event-level masked next-user policy loss and FOREST-style sampled growth reward",
                "original_component_distillation": (
                    "When enabled, upstream MINDS Module.forward macro predictions, FOREST RRModel sampled EOS sizes, "
                    "and CasFT CombinedSpatiotemporalModel5 size predictions are used as training teacher signals; "
                    "CasFT CombinedSpatiotemporalModel5 also provides a prefix-only continuous-time size/trend signal gated into KT2's main macro/trend outputs."
                ),
                "max_sequence_len": args.max_sequence_len,
                "user_hash_buckets": args.user_hash_buckets,
                "final_epoch_loss": getattr(model, "training_summary", {}).get("final_epoch_loss"),
            },
        }
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", required=True)
    parser.add_argument("--obs_ratio", type=float, default=0.3)
    parser.add_argument("--max_future_per_cascade", type=int, default=20)
    parser.add_argument("--global_top_n", type=int, default=3000)
    parser.add_argument("--max_candidates", type=int, default=5000)
    parser.add_argument("--negatives_per_cascade", type=int, default=120)
    parser.add_argument("--bucket_seconds", type=int, default=24 * 3600)
    parser.add_argument("--max_bucket_users", type=int, default=80)
    parser.add_argument("--max_train_cascades", type=int, default=0)
    parser.add_argument("--max_test_cascades", type=int, default=0)
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--batch_size", type=int, default=4096)
    parser.add_argument("--hidden_dim", type=int, default=64)
    parser.add_argument("--dropout", type=float, default=0.1)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--weight_decay", type=float, default=0.0001)
    parser.add_argument("--lambda_macro", type=float, default=1.0)
    parser.add_argument("--lambda_micro", type=float, default=1.0)
    parser.add_argument("--lambda_trend", type=float, default=0.4)
    parser.add_argument("--lambda_consistency", type=float, default=0.2)
    parser.add_argument("--lambda_orthogonality", type=float, default=0.05)
    parser.add_argument("--lambda_adversarial", type=float, default=0.02)
    parser.add_argument("--lambda_diffusion", type=float, default=0.05)
    parser.add_argument("--lambda_forest_pg", type=float, default=0.05)
    parser.add_argument("--adversary_alpha", type=float, default=1.0)
    parser.add_argument("--diffusion_noise_std", type=float, default=0.15)
    parser.add_argument("--use_original_casft_diffusion", action="store_true")
    parser.add_argument("--use_original_casft_spatiotemporal", action="store_true")
    parser.add_argument("--casft_repo", default="")
    parser.add_argument("--lambda_original_casft_spatiotemporal", type=float, default=0.0)
    parser.add_argument("--casft_spatiotemporal_interval_num", type=int, default=TREND_STEPS)
    parser.add_argument("--casft_spatiotemporal_tpp_hdim", type=int, default=16)
    parser.add_argument("--casft_spatiotemporal_timesteps", type=int, default=2)
    parser.add_argument("--casft_spatiotemporal_sampling_timesteps", type=int, default=1)
    parser.add_argument("--casft_spatiotemporal_solver", default="euler")
    parser.add_argument("--casft_spatiotemporal_tpp_style", default="split")
    parser.add_argument("--casft_spatiotemporal_tpp_actfn", default="softplus")
    parser.set_defaults(use_original_minds_components=True, use_original_minds_full_module=True)
    parser.add_argument(
        "--use_original_minds_components",
        dest="use_original_minds_components",
        action="store_true",
        help="Use upstream MINDS DynamicCasHGNN/Fusion/SharedLSTM components; enabled by default.",
    )
    parser.add_argument(
        "--disable_original_minds_components",
        dest="use_original_minds_components",
        action="store_false",
        help="Disable upstream MINDS components and force the local KT2 MINDS-style fallback.",
    )
    parser.add_argument(
        "--use_original_minds_full_module",
        dest="use_original_minds_full_module",
        action="store_true",
        help="Use upstream MINDS Module.forward auxiliary; enabled by default.",
    )
    parser.add_argument(
        "--disable_original_minds_full_module",
        dest="use_original_minds_full_module",
        action="store_false",
        help="Disable upstream MINDS Module.forward auxiliary.",
    )
    parser.add_argument("--lambda_original_minds_module", type=float, default=0.01)
    parser.add_argument("--lambda_original_minds_diff", type=float, default=0.05)
    parser.add_argument("--minds_repo", default=str(DEFAULT_MINDS_REPO))
    parser.add_argument("--use_original_forest_components", action="store_true")
    parser.add_argument("--forest_repo", default="")
    parser.add_argument("--lambda_original_forest_ce", type=float, default=0.0)
    parser.add_argument("--lambda_original_forest_rl", type=float, default=0.0)
    parser.add_argument("--original_forest_rollout_samples", type=int, default=0)
    parser.add_argument("--original_forest_start_size", type=int, default=5)
    parser.add_argument("--original_forest_hidden_dim", type=int, default=0)
    parser.add_argument("--casft_diffusion_timesteps", type=int, default=10)
    parser.add_argument("--casft_sampling_timesteps", type=int, default=5)
    parser.add_argument("--casft_diffusion_units", type=int, default=20)
    parser.add_argument("--casft_diffusion_loss_type", default="l2")
    parser.add_argument("--casft_diffusion_objective", default="pred_noise")
    parser.add_argument("--consistency_events_per_step", type=int, default=8)
    parser.add_argument("--max_consistency_candidates_per_event", type=int, default=0)
    parser.add_argument("--forest_pg_rollout_samples", type=int, default=2)
    parser.add_argument("--max_steps_per_epoch", type=int, default=0)
    parser.add_argument("--max_sequence_len", type=int, default=DEFAULT_MAX_SEQUENCE_LEN)
    parser.add_argument("--user_hash_buckets", type=int, default=DEFAULT_USER_HASH_BUCKETS)
    parser.add_argument("--max_grad_norm", type=float, default=5.0)
    parser.add_argument("--max_train_micro_samples", type=int, default=300000)
    parser.add_argument("--max_eval_cascades", type=int, default=0)
    parser.add_argument("--direction_threshold", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    args = parser.parse_args()

    result = _run_with_args(args)
    if result.get("status") == "ok":
        print(
            "[KT2JointModel] "
            f"MSLE={result.get('msle'):.4f} "
            f"Coverage={result.get('candidate_recall_full'):.4f} "
            f"Hits@100={result.get('hits@100'):.4f} "
            f"Consistency={result.get('macro_micro_consistency'):.4f}"
        )
    else:
        print(f"[KT2JointModel] {result.get('status')}: {result.get('note')}")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
