"""Trainable Review post-level building blocks.

This module is intentionally independent from the existing rule/ablation
runtime. It provides small, reproducible PyTorch components for the Review
defense-deliverable path:

- frozen or fallback post features with trainable heads
- cross-modal adapter for meme/image views
- temporal C3D encoder for FakeSV pre-extracted video features
- claim-conditioned cross-encoder head
- uncertainty-aware gating fusion and deterministic agent review

The implementation does not claim raw-video encoding, external RAG, or full P0
benchmark validation. Those boundaries are carried in reports by the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import hashlib
import json
import math

import numpy as np

from app.core.review.review_task_schema import ATTACK_AXIS, MISINFO_AXIS, TEACHER_SILVER_SCHEMA
from app.core.review.text_features import hash_text_features, tokenize

try:  # pragma: no cover - import availability is environment dependent
    import torch
    from torch import nn
except Exception:  # pragma: no cover
    torch = None
    nn = None


POSITIVE_LABEL = "harmful"
NEGATIVE_LABEL = "non_harmful"
LABELS = (NEGATIVE_LABEL, POSITIVE_LABEL)
VIEW_ORDER = ("tweet", "meme", "img", "video", "claim")
HARM_TYPE_ORDER = (
    "misinformation",
    "hate_harassment",
    "targeted_smear",
    "incitement_mobilization",
    "manipulative_amplification",
)
STANCE_ORDER = ("support", "deny", "query", "neutral", "unlinked")
STUDENT_AXIS_ORDER = (ATTACK_AXIS, MISINFO_AXIS)
CLAIM_LINKED_DATASETS = {"PHEME", "mcfend", "FakeSV"}


@dataclass(frozen=True)
class FeatureBundle:
    matrix: np.ndarray
    backend: str
    model_name: str
    capability_boundary: str


def label_of(case: dict[str, Any]) -> str:
    return str((case.get("labels") or {}).get("harmfulness") or "unknown")


def binary_label(case: dict[str, Any]) -> int:
    return 1 if label_of(case) == POSITIVE_LABEL else 0


def text_of(case: dict[str, Any]) -> str:
    return " ".join(str(case.get("text") or "").split()).strip()


def claim_context_text(case: dict[str, Any]) -> str:
    context = case.get("claim_context") or {}
    parts = [
        str(context.get("claim_text", "")).strip(),
        str(context.get("evidence_text", "")).strip(),
    ]
    for link in context.get("evidence_links") or []:
        if isinstance(link, dict):
            parts.extend(
                [
                    str(link.get("position", "")).strip(),
                    str(link.get("mediatype", "")).strip(),
                    str(link.get("link", "")).strip(),
                ]
            )
    return " ".join(part for part in parts if part).strip()


def claim_id_of(case: dict[str, Any]) -> str:
    context = case.get("claim_context") or {}
    claim_text = str(context.get("claim_text", "")).strip()
    if claim_text:
        return hashlib.sha1(claim_text.encode("utf-8", errors="ignore")).hexdigest()[:16]
    return "unlinked"


def stance_proxy_of(case: dict[str, Any]) -> str:
    labels = case.get("labels") or {}
    raw = labels.get("raw_annotation") or {}
    if isinstance(raw, dict):
        links = raw.get("links") or []
        positions = {
            str(link.get("position", "")).lower()
            for link in links
            if isinstance(link, dict)
        }
        if "against" in positions:
            return "deny"
        if "for" in positions:
            return "support"
    veracity = str(labels.get("veracity", "")).lower()
    if veracity in {"false", "debunking"}:
        return "deny"
    if veracity == "true":
        return "support"
    return "unlinked" if not claim_context_text(case) else "neutral"


def rationale_tokens_of(case: dict[str, Any], max_tokens: int = 12) -> list[str]:
    labels = case.get("labels") or {}
    rationale = labels.get("rationale_tokens") or []
    if rationale:
        return [str(token) for token in rationale[:max_tokens]]
    tokens = tokenize(text_of(case))
    return tokens[:max_tokens]


def target_groups_of(case: dict[str, Any]) -> list[str]:
    labels = case.get("labels") or {}
    return [str(group) for group in labels.get("target_groups") or []]


def axis_supports_case(case: dict[str, Any], axis: str) -> bool:
    """Return whether a case has supervision for one of the 2+1 student axes."""
    dataset = str(case.get("dataset") or "").strip().lower()
    labels = case.get("labels") or {}
    harm_types = {str(item).strip().lower() for item in labels.get("harm_type") or []}
    raw_label = str(labels.get("raw_label") or "").strip().lower()
    if axis == ATTACK_AXIS:
        return bool(
            dataset in {"hatexplain", "multioff"}
            or harm_types.intersection({"hate", "offensive", "abusive", "toxic", "hate_harassment", "harassment"})
            or target_groups_of(case)
            or labels.get("rationale_tokens")
            or raw_label in {"hate", "offensive", "abusive", "toxic"}
        )
    if axis == MISINFO_AXIS:
        return bool(
            dataset in {"pheme", "mcfend", "fakesv"}
            or "misinformation" in harm_types
            or claim_context_text(case)
            or labels.get("veracity") is not None
            or labels.get("rumour_label") is not None
            or raw_label in {"fake", "false", "rumor", "rumour", "misinformation"}
        )
    return False


def teacher_axis_label(case: dict[str, Any], axis: str) -> int:
    if not axis_supports_case(case, axis):
        return 0
    return binary_label(case)


def teacher_axis_confidence(
    case: dict[str, Any],
    axis: str,
    *,
    teacher_confidence: float | int | None = None,
) -> float:
    if not axis_supports_case(case, axis):
        return 0.0
    try:
        base = float(teacher_confidence) if teacher_confidence is not None else 0.75
    except (TypeError, ValueError):
        base = 0.75
    if claim_context_text(case) and axis == MISINFO_AXIS:
        base = max(base, 0.8)
    if target_groups_of(case) and axis == ATTACK_AXIS:
        base = max(base, 0.8)
    return round(max(0.0, min(1.0, base)), 6)


def multitask_targets(cases: list[dict[str, Any]]) -> dict[str, np.ndarray]:
    harmfulness = np.asarray([binary_label(case) for case in cases], dtype="float32")
    harm_types = np.zeros((len(cases), len(HARM_TYPE_ORDER)), dtype="float32")
    stance = np.zeros((len(cases),), dtype="int64")
    rationale = np.zeros((len(cases),), dtype="float32")
    for row, case in enumerate(cases):
        labels = case.get("labels") or {}
        for harm_type in labels.get("harm_type") or []:
            harm_type = str(harm_type)
            if harm_type in HARM_TYPE_ORDER:
                harm_types[row, HARM_TYPE_ORDER.index(harm_type)] = 1.0
            elif harm_type in {"offensive", "toxic", "hate", "abusive"}:
                harm_types[row, HARM_TYPE_ORDER.index("hate_harassment")] = 1.0
        if harmfulness[row] and not harm_types[row].any():
            harm_types[row, HARM_TYPE_ORDER.index("manipulative_amplification")] = 1.0
        stance_label = stance_proxy_of(case)
        stance[row] = STANCE_ORDER.index(stance_label) if stance_label in STANCE_ORDER else STANCE_ORDER.index("unlinked")
        rationale[row] = 1.0 if rationale_tokens_of(case) or target_groups_of(case) else 0.0
    return {
        "harmfulness": harmfulness,
        "harm_types": harm_types,
        "stance": stance,
        "rationale": rationale,
    }


def hash_case_image_features(cases: list[dict[str, Any]], *, dim: int = 256) -> np.ndarray:
    texts = []
    for case in cases:
        img = ((case.get("views") or {}).get("img") or {})
        texts.append(
            " ".join(
                [
                    str(case.get("case_id", "")),
                    str(case.get("source_id", "")),
                    str(img.get("media_path", "")),
                ]
            )
        )
    return hash_text_features(texts, dim=dim)


def encode_clip_image_text_features(
    cases: list[dict[str, Any]],
    *,
    model_name: str = "openai/clip-vit-base-patch32",
    revision: str | None = None,
    cache_dir: str | Path | None = None,
    batch_size: int = 16,
    local_files_only: bool = True,
    fallback_dim: int = 256,
) -> tuple[FeatureBundle, FeatureBundle]:
    """Encode image/text with frozen CLIP when local weights are available.

    The fallback is deterministic and explicit in capability boundaries. It is
    meant for CPU smoke tests, not for reporting CLIP performance.
    """

    try:  # pragma: no cover - depends on optional local model cache
        from PIL import Image
        from transformers import CLIPModel, CLIPProcessor

        require_torch()
        processor = CLIPProcessor.from_pretrained(
            model_name,
            revision=revision,
            cache_dir=str(cache_dir) if cache_dir else None,
            local_files_only=local_files_only,
        )
        try:
            model = CLIPModel.from_pretrained(
                model_name,
                revision=revision,
                cache_dir=str(cache_dir) if cache_dir else None,
                local_files_only=local_files_only,
                use_safetensors=True,
            )
        except Exception:
            model = load_local_clip_safetensors_snapshot(model_name, cache_dir)
        device = resolve_torch_device()
        model.to(device)
        model.eval()
        image_rows = []
        text_rows = []
        for start in range(0, len(cases), max(1, batch_size)):
            batch_cases = cases[start : start + batch_size]
            images = []
            texts = []
            for case in batch_cases:
                image_path = str(((case.get("views") or {}).get("img") or {}).get("media_path") or "").strip()
                with Image.open(image_path) as image:
                    images.append(image.convert("RGB"))
                texts.append(text_of(case) or " ")
            image_inputs = processor(images=images, return_tensors="pt")
            text_inputs = processor(text=texts, padding=True, truncation=True, return_tensors="pt")
            image_inputs = {key: value.to(device) for key, value in image_inputs.items()}
            text_inputs = {key: value.to(device) for key, value in text_inputs.items()}
            with torch.no_grad():
                image_features = model.get_image_features(**image_inputs)
                text_features = model.get_text_features(**text_inputs)
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            image_rows.append(image_features.detach().cpu().numpy().astype("float32"))
            text_rows.append(text_features.detach().cpu().numpy().astype("float32"))
        image_matrix = np.vstack(image_rows)
        text_matrix = np.vstack(text_rows)
        image_bundle = FeatureBundle(
            matrix=image_matrix,
            backend="frozen-clip-image",
            model_name=model_name,
            capability_boundary="frozen CLIP image encoder features + trainable Review adapter",
        )
        text_bundle = FeatureBundle(
            matrix=text_matrix,
            backend="frozen-clip-text",
            model_name=model_name,
            capability_boundary="frozen CLIP text encoder features + trainable Review adapter",
        )
        return text_bundle, image_bundle
    except Exception as exc:
        text_bundle = FeatureBundle(
            matrix=hash_text_features([text_of(case) for case in cases], dim=fallback_dim),
            backend="hash-smoke-text",
            model_name=f"stable-hash-{fallback_dim}",
            capability_boundary=(
                "deterministic CPU smoke fallback for CLIP text features; "
                f"frozen CLIP unavailable: {type(exc).__name__}: {str(exc)[:160]}"
            ),
        )
        image_bundle = FeatureBundle(
            matrix=hash_case_image_features(cases, dim=fallback_dim),
            backend="hash-smoke-image",
            model_name=f"stable-hash-image-{fallback_dim}",
            capability_boundary=(
                "deterministic CPU smoke fallback for CLIP image features; "
                f"frozen CLIP unavailable: {type(exc).__name__}: {str(exc)[:160]}"
            ),
        )
        return text_bundle, image_bundle


def load_local_clip_safetensors_snapshot(model_name: str, cache_dir: str | Path | None) -> Any:
    from safetensors.torch import load_file
    from transformers import CLIPConfig, CLIPModel

    if cache_dir is None:
        raise
    model_cache = Path(cache_dir) / f"models--{model_name.replace('/', '--')}"
    config_snapshot = None
    for snapshot in sorted((model_cache / "snapshots").glob("*")):
        if (snapshot / "config.json").exists():
            config_snapshot = snapshot
            break
    for snapshot in sorted((model_cache / "snapshots").glob("*")):
        safetensors_path = snapshot / "model.safetensors"
        if not safetensors_path.exists():
            continue
        if (snapshot / "config.json").exists():
            return CLIPModel.from_pretrained(str(snapshot), local_files_only=True, use_safetensors=True)
        if config_snapshot is not None:
            config = CLIPConfig.from_pretrained(str(config_snapshot), local_files_only=True)
            model = CLIPModel(config)
            model.load_state_dict(load_file(str(safetensors_path)), strict=False)
            return model
    raise FileNotFoundError(f"no local safetensors CLIP snapshot found for {model_name} in {model_cache}")


def resolve_local_hf_snapshot(model_name: str, cache_dir: str | Path | None, *, local_files_only: bool = True) -> str:
    """Resolve a HuggingFace cache snapshot path before transformers can go online."""
    if not local_files_only:
        return model_name
    direct_path = Path(model_name)
    if direct_path.exists():
        return str(direct_path)
    if cache_dir is None:
        return model_name
    model_cache = Path(cache_dir) / f"models--{model_name.replace('/', '--')}"
    snapshots_dir = model_cache / "snapshots"
    if not snapshots_dir.exists():
        return model_name

    weight_files = {"model.safetensors", "pytorch_model.bin", "tf_model.h5", "flax_model.msgpack"}
    tokenizer_files = {
        "tokenizer.json",
        "vocab.txt",
        "sentencepiece.bpe.model",
        "spiece.model",
        "merges.txt",
    }
    snapshots = sorted(
        [snapshot for snapshot in snapshots_dir.iterdir() if snapshot.is_dir()],
        key=lambda snapshot: snapshot.stat().st_mtime,
        reverse=True,
    )
    for snapshot in snapshots:
        names = {item.name for item in snapshot.iterdir() if item.is_file()}
        if "config.json" in names and names.intersection(weight_files) and names.intersection(tokenizer_files):
            return str(snapshot)
    return model_name


def encode_text_features(
    texts: list[str],
    *,
    backend: str = "hash",
    model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    revision: str | None = None,
    cache_dir: str | Path | None = None,
    dim: int = 256,
    batch_size: int = 32,
    local_files_only: bool = True,
    max_length: int = 256,
    pooling: str = "cls",
) -> FeatureBundle:
    """Encode text with a frozen multilingual model when explicitly available.

    The hash backend is a deterministic CPU smoke fallback. Reports must not
    describe hash features as a trained transformer.
    """

    if backend in {"sentence-transformer", "auto"}:
        try:  # pragma: no cover - optional model availability
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(model_name, cache_folder=str(cache_dir) if cache_dir else None)
            matrix = model.encode(
                texts,
                batch_size=32,
                show_progress_bar=False,
                normalize_embeddings=True,
            ).astype("float32")
            return FeatureBundle(
                matrix=matrix,
                backend="sentence-transformer",
                model_name=model_name,
                capability_boundary="frozen multilingual sentence-transformer features with trainable Review heads",
            )
        except Exception:
            if backend == "sentence-transformer":
                raise
    if backend in {"hf-transformer", "auto"}:
        try:  # pragma: no cover - optional model availability
            from transformers import AutoModel, AutoTokenizer

            require_torch()
            pretrained_ref = resolve_local_hf_snapshot(model_name, cache_dir, local_files_only=local_files_only)
            tokenizer = AutoTokenizer.from_pretrained(
                pretrained_ref,
                revision=revision,
                cache_dir=str(cache_dir) if cache_dir else None,
                local_files_only=local_files_only,
                use_fast=True,
            )
            try:
                model = AutoModel.from_pretrained(
                    pretrained_ref,
                    revision=revision,
                    cache_dir=str(cache_dir) if cache_dir else None,
                    local_files_only=local_files_only,
                    use_safetensors=True,
                )
            except OSError:
                model = AutoModel.from_pretrained(
                    pretrained_ref,
                    revision=revision,
                    cache_dir=str(cache_dir) if cache_dir else None,
                    local_files_only=local_files_only,
                    use_safetensors=False,
                )
            device = resolve_torch_device()
            model.to(device)
            model.eval()
            rows = []
            safe_texts = [text if text.strip() else " " for text in texts]
            for start in range(0, len(safe_texts), max(1, batch_size)):
                batch = safe_texts[start : start + batch_size]
                encoded = tokenizer(
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=max_length,
                    return_tensors="pt",
                )
                encoded = {key: value.to(device) for key, value in encoded.items()}
                with torch.no_grad():
                    output = model(**encoded)
                    token_embeddings = output.last_hidden_state
                    if pooling == "mean":
                        mask = encoded["attention_mask"].unsqueeze(-1).float()
                        pooled = (token_embeddings * mask).sum(dim=1) / mask.sum(dim=1).clamp_min(1.0)
                    else:
                        pooled = token_embeddings[:, 0, :]
                    pooled = torch.nn.functional.normalize(pooled, dim=-1)
                rows.append(pooled.detach().cpu().numpy().astype("float32"))
            matrix = np.vstack(rows) if rows else np.zeros((0, 0), dtype="float32")
            return FeatureBundle(
                matrix=matrix,
                backend="hf-transformer",
                model_name=model_name,
                capability_boundary=(
                    f"frozen HuggingFace transformer text encoder ({model_name}) "
                    "with trainable Review multitask heads"
                ),
            )
        except Exception:
            if backend == "hf-transformer":
                raise

    matrix = hash_text_features(texts, dim=dim)
    return FeatureBundle(
        matrix=matrix,
        backend="hash-smoke",
        model_name=f"stable-hash-{dim}",
        capability_boundary="deterministic CPU smoke fallback; not a transformer encoder",
    )


def require_torch() -> None:
    if torch is None or nn is None:  # pragma: no cover
        raise RuntimeError("torch is required for Review trainable post models")


def resolve_torch_device(device: str | None = None) -> str:
    if device:
        return device
    if torch is None or not torch.cuda.is_available():
        return "cpu"
    try:
        torch.empty(1, device="cuda")
        return "cuda"
    except Exception:
        return "cpu"


class FeedForwardBinaryClassifier(nn.Module if nn is not None else object):
    def __init__(self, input_dim: int, hidden_dim: int = 128, dropout: float = 0.1):
        require_torch()
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, features: Any) -> Any:
        return self.network(features).squeeze(-1)


class MultitaskTextDetector(nn.Module if nn is not None else object):
    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = 128,
        harm_type_count: int = 5,
        stance_count: int = 5,
    ):
        require_torch()
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.1),
        )
        self.harmfulness = nn.Linear(hidden_dim, 1)
        self.harm_types = nn.Linear(hidden_dim, harm_type_count)
        self.stance = nn.Linear(hidden_dim, stance_count)
        self.rationale = nn.Linear(hidden_dim, 1)

    def forward(self, features: Any) -> dict[str, Any]:
        hidden = self.encoder(features)
        return {
            "harmfulness": self.harmfulness(hidden).squeeze(-1),
            "harm_types": self.harm_types(hidden),
            "stance": self.stance(hidden),
            "rationale": self.rationale(hidden).squeeze(-1),
        }


class CrossModalAttentionAdapter(nn.Module if nn is not None else object):
    def __init__(self, text_dim: int, image_dim: int, hidden_dim: int = 128, heads: int = 4):
        require_torch()
        super().__init__()
        self.text_proj = nn.Linear(text_dim, hidden_dim)
        self.image_proj = nn.Linear(image_dim, hidden_dim)
        self.attention = nn.MultiheadAttention(hidden_dim, heads, batch_first=True)
        self.norm = nn.LayerNorm(hidden_dim)
        self.classifier = nn.Sequential(nn.Linear(hidden_dim, hidden_dim), nn.ReLU(), nn.Linear(hidden_dim, 1))

    def forward(self, text_features: Any, image_features: Any, *, return_embedding: bool = False) -> Any:
        text_token = self.text_proj(text_features)
        image_token = self.image_proj(image_features)
        tokens = torch.stack([text_token, image_token], dim=1)
        attended, _ = self.attention(tokens, tokens, tokens, need_weights=False)
        pooled = self.norm(attended.mean(dim=1))
        logits = self.classifier(pooled).squeeze(-1)
        if return_embedding:
            return logits, pooled
        return logits


class TemporalC3DTransformer(nn.Module if nn is not None else object):
    def __init__(self, input_dim: int, hidden_dim: int = 128, heads: int = 4, layers: int = 1):
        require_torch()
        super().__init__()
        self.proj = nn.Linear(input_dim, hidden_dim)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_dim,
            nhead=heads,
            dim_feedforward=hidden_dim * 2,
            dropout=0.1,
            batch_first=True,
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=layers)
        self.classifier = nn.Linear(hidden_dim, 1)

    def forward(self, sequence_features: Any) -> Any:
        hidden = self.proj(sequence_features)
        encoded = self.encoder(hidden)
        pooled = encoded.mean(dim=1)
        return self.classifier(pooled).squeeze(-1)


class ClaimEvidenceCrossEncoder(nn.Module if nn is not None else object):
    def __init__(self, feature_dim: int, hidden_dim: int = 128, stance_count: int = 5):
        require_torch()
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(feature_dim * 4, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.1),
        )
        self.harmfulness = nn.Linear(hidden_dim, 1)
        self.stance = nn.Linear(hidden_dim, stance_count)

    def forward(self, post_features: Any, claim_features: Any) -> dict[str, Any]:
        combined = torch.cat(
            [
                post_features,
                claim_features,
                torch.abs(post_features - claim_features),
                post_features * claim_features,
            ],
            dim=-1,
        )
        hidden = self.encoder(combined)
        return {
            "harmfulness": self.harmfulness(hidden).squeeze(-1),
            "stance": self.stance(hidden),
        }


class GatingFusionModel(nn.Module if nn is not None else object):
    def __init__(self, input_dim: int, hidden_dim: int = 32):
        require_torch()
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, features: Any) -> Any:
        return self.network(features).squeeze(-1)


def _as_tensor(value: Any, device: str) -> Any:
    if isinstance(value, tuple):
        return tuple(_as_tensor(item, device) for item in value)
    if isinstance(value, list):
        return [_as_tensor(item, device) for item in value]
    if torch.is_tensor(value):
        return value.to(device)
    return torch.as_tensor(value, dtype=torch.float32, device=device)


def _slice_features(features: Any, indices: Any) -> Any:
    if isinstance(features, tuple):
        return tuple(_slice_features(item, indices) for item in features)
    return features[indices]


def _model_logits(model: Any, features: Any) -> Any:
    if isinstance(features, tuple):
        output = model(*features)
    else:
        output = model(features)
    if isinstance(output, dict):
        return output["harmfulness"]
    return output


def train_binary_torch_model(
    model: Any,
    features: Any,
    labels: np.ndarray,
    *,
    epochs: int = 5,
    lr: float = 1e-3,
    batch_size: int = 64,
    device: str | None = None,
) -> dict[str, Any]:
    require_torch()
    device = resolve_torch_device(device)
    model.to(device)
    model.train()
    x_tensor = _as_tensor(features, device)
    y_tensor = torch.as_tensor(labels.astype("float32"), device=device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
    loss_fn = nn.BCEWithLogitsLoss()
    history = []
    n = int(y_tensor.shape[0])
    for epoch in range(max(1, epochs)):
        order = torch.randperm(n, device=device)
        losses = []
        for start in range(0, n, max(1, batch_size)):
            idx = order[start : start + batch_size]
            optimizer.zero_grad()
            batch_x = _slice_features(x_tensor, idx)
            logits = _model_logits(model, batch_x)
            loss = loss_fn(logits, y_tensor[idx])
            loss.backward()
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
        history.append({"epoch": epoch + 1, "loss": round(float(np.mean(losses)), 6)})
    return {"epochs": len(history), "history": history, "device": device}


def train_multitask_text_model(
    model: Any,
    features: np.ndarray,
    targets: dict[str, np.ndarray],
    *,
    epochs: int = 5,
    lr: float = 1e-3,
    batch_size: int = 64,
    device: str | None = None,
) -> dict[str, Any]:
    require_torch()
    device = resolve_torch_device(device)
    model.to(device)
    model.train()
    x_tensor = torch.as_tensor(features, dtype=torch.float32, device=device)
    y_harm = torch.as_tensor(targets["harmfulness"].astype("float32"), device=device)
    y_types = torch.as_tensor(targets["harm_types"].astype("float32"), device=device)
    y_stance = torch.as_tensor(targets["stance"].astype("int64"), device=device)
    y_rationale = torch.as_tensor(targets["rationale"].astype("float32"), device=device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
    bce = nn.BCEWithLogitsLoss()
    ce = nn.CrossEntropyLoss()
    history = []
    n = int(y_harm.shape[0])
    for epoch in range(max(1, epochs)):
        order = torch.randperm(n, device=device)
        losses = []
        for start in range(0, n, max(1, batch_size)):
            idx = order[start : start + batch_size]
            optimizer.zero_grad()
            output = model(x_tensor[idx])
            loss = bce(output["harmfulness"], y_harm[idx])
            loss = loss + 0.2 * bce(output["harm_types"], y_types[idx])
            loss = loss + 0.1 * ce(output["stance"], y_stance[idx])
            loss = loss + 0.05 * bce(output["rationale"], y_rationale[idx])
            loss.backward()
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
        history.append({"epoch": epoch + 1, "loss": round(float(np.mean(losses)), 6)})
    return {
        "epochs": len(history),
        "history": history,
        "device": device,
        "losses": {
            "harmfulness": "BCEWithLogitsLoss",
            "harm_types": "0.2 * BCEWithLogitsLoss",
            "stance": "0.1 * CrossEntropyLoss",
            "rationale": "0.05 * BCEWithLogitsLoss",
        },
    }


def supervised_contrastive_loss(embeddings: Any, labels: Any, temperature: float = 0.2) -> Any:
    require_torch()
    if embeddings.shape[0] < 2:
        return torch.zeros((), device=embeddings.device)
    embeddings = torch.nn.functional.normalize(embeddings, dim=-1)
    logits = embeddings @ embeddings.T / temperature
    labels = labels.view(-1, 1)
    positive = labels.eq(labels.T).float()
    eye = torch.eye(labels.shape[0], device=labels.device)
    positive = positive * (1.0 - eye)
    exp_logits = torch.exp(logits) * (1.0 - eye)
    log_prob = logits - torch.log(exp_logits.sum(dim=1, keepdim=True).clamp_min(1e-8))
    positive_count = positive.sum(dim=1)
    valid = positive_count > 0
    if not bool(valid.any()):
        return torch.zeros((), device=embeddings.device)
    loss = -(positive * log_prob).sum(dim=1)[valid] / positive_count[valid]
    return loss.mean()


def train_cross_modal_torch_model(
    model: Any,
    text_features: np.ndarray,
    image_features: np.ndarray,
    labels: np.ndarray,
    *,
    epochs: int = 5,
    lr: float = 1e-3,
    batch_size: int = 64,
    contrastive_weight: float = 0.05,
    device: str | None = None,
) -> dict[str, Any]:
    require_torch()
    device = resolve_torch_device(device)
    model.to(device)
    model.train()
    text_tensor = torch.as_tensor(text_features, dtype=torch.float32, device=device)
    image_tensor = torch.as_tensor(image_features, dtype=torch.float32, device=device)
    y_tensor = torch.as_tensor(labels.astype("float32"), device=device)
    class_tensor = torch.as_tensor(labels.astype("int64"), device=device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
    loss_fn = nn.BCEWithLogitsLoss()
    n = int(y_tensor.shape[0])
    history = []
    for epoch in range(max(1, epochs)):
        order = torch.randperm(n, device=device)
        losses = []
        for start in range(0, n, max(1, batch_size)):
            idx = order[start : start + batch_size]
            optimizer.zero_grad()
            logits, embedding = model(text_tensor[idx], image_tensor[idx], return_embedding=True)
            loss = loss_fn(logits, y_tensor[idx])
            loss = loss + contrastive_weight * supervised_contrastive_loss(embedding, class_tensor[idx])
            loss.backward()
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
        history.append({"epoch": epoch + 1, "loss": round(float(np.mean(losses)), 6)})
    return {"epochs": len(history), "history": history, "device": device, "contrastive_weight": contrastive_weight}


def predict_probabilities(model: Any, features: Any, *, batch_size: int = 256, device: str | None = None) -> np.ndarray:
    require_torch()
    device = resolve_torch_device(device)
    model.to(device)
    model.eval()
    x_tensor = _as_tensor(features, device)
    n = int(x_tensor[0].shape[0] if isinstance(x_tensor, tuple) else x_tensor.shape[0])
    rows = []
    with torch.no_grad():
        for start in range(0, n, max(1, batch_size)):
            idx = slice(start, start + batch_size)
            batch_x = _slice_features(x_tensor, idx)
            logits = _model_logits(model, batch_x)
            rows.append(torch.sigmoid(logits).detach().cpu().numpy())
    return np.concatenate(rows).astype("float32")


def binary_classification_metrics(
    y_true: list[str] | np.ndarray,
    probabilities: np.ndarray,
    *,
    threshold: float = 0.5,
) -> dict[str, Any]:
    labels = np.asarray([_as_binary_value(value) for value in y_true], dtype=int)
    preds = (probabilities >= threshold).astype(int)
    accuracy = float((preds == labels).mean()) if labels.size else 0.0
    per_class = {}
    f1_values = []
    for class_id, class_name in enumerate(LABELS):
        tp = int(((preds == class_id) & (labels == class_id)).sum())
        fp = int(((preds == class_id) & (labels != class_id)).sum())
        fn = int(((preds != class_id) & (labels == class_id)).sum())
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        f1_values.append(f1)
        per_class[class_name] = {
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(f1, 6),
            "support": int((labels == class_id).sum()),
        }
    return {
        "accuracy": round(accuracy, 6),
        "macro_f1": round(float(np.mean(f1_values)), 6) if f1_values else 0.0,
        "per_class": per_class,
    }


def binary_pr_auc(y_true: list[str] | np.ndarray, probabilities: np.ndarray) -> float:
    labels = np.asarray([_as_binary_value(value) for value in y_true], dtype=int)
    scores = np.asarray(probabilities, dtype="float32")
    if labels.size == 0 or int(labels.sum()) == 0:
        return 0.0
    order = np.argsort(-scores, kind="mergesort")
    sorted_labels = labels[order]
    tp = np.cumsum(sorted_labels == 1)
    fp = np.cumsum(sorted_labels == 0)
    precision = tp / np.maximum(tp + fp, 1)
    recall = tp / max(int(labels.sum()), 1)
    precision = np.concatenate([np.asarray([1.0]), precision])
    recall = np.concatenate([np.asarray([0.0]), recall])
    trapezoid = getattr(np, "trapezoid", None) or getattr(np, "trapz")
    return round(float(trapezoid(precision, recall)), 6)


def _as_binary_value(value: Any) -> int:
    if isinstance(value, str):
        return 1 if value == POSITIVE_LABEL else 0
    return 1 if int(value) == 1 else 0


def expected_calibration_error(labels: np.ndarray, probabilities: np.ndarray, *, bins: int = 10) -> float:
    labels = labels.astype(int)
    confidence = np.maximum(probabilities, 1.0 - probabilities)
    correct = ((probabilities >= 0.5).astype(int) == labels).astype(float)
    ece = 0.0
    for bin_index in range(bins):
        low = bin_index / bins
        high = (bin_index + 1) / bins
        mask = (confidence > low) & (confidence <= high)
        if not mask.any():
            continue
        ece += float(mask.mean()) * abs(float(correct[mask].mean()) - float(confidence[mask].mean()))
    return round(ece, 6)


def coverage_risk_curve(
    labels: np.ndarray,
    probabilities: np.ndarray,
    *,
    thresholds: tuple[float, ...] = (0.5, 0.55, 0.6, 0.7, 0.8, 0.9),
) -> list[dict[str, Any]]:
    labels = labels.astype(int)
    confidence = np.maximum(probabilities, 1.0 - probabilities)
    preds = (probabilities >= 0.5).astype(int)
    rows = []
    for threshold in thresholds:
        covered = confidence >= threshold
        if covered.any():
            risk = float((preds[covered] != labels[covered]).mean())
        else:
            risk = 0.0
        rows.append(
            {
                "confidence_threshold": threshold,
                "coverage": round(float(covered.mean()), 6) if labels.size else 0.0,
                "risk": round(risk, 6),
            }
        )
    return rows


def high_risk_recall_score(
    labels: np.ndarray,
    probabilities: np.ndarray,
    *,
    threshold: float = 0.75,
) -> float:
    labels = labels.astype(int)
    positives = labels == 1
    if not positives.any():
        return 0.0
    flagged = probabilities >= threshold
    return round(float((flagged & positives).sum() / positives.sum()), 6)


def confidence_from_probability(probability: float) -> float:
    return round(float(abs(probability - 0.5) * 2.0), 6)


def standard_detector_output(
    case: dict[str, Any],
    *,
    view: str,
    probability: float,
    evidence: list[str] | None = None,
    capability_boundary: str,
    stance: str | None = None,
) -> dict[str, Any]:
    confidence = confidence_from_probability(probability)
    label = POSITIVE_LABEL if probability >= 0.5 else NEGATIVE_LABEL
    labels = case.get("labels") or {}
    return {
        "view": view,
        "label": label,
        "harm_score": round(float(probability), 6),
        "harm_types": labels.get("harm_type") or (["unspecified_harm"] if label == POSITIVE_LABEL else []),
        "confidence": confidence,
        "abstain": confidence < 0.2,
        "evidence": evidence if evidence is not None else [text_of(case)[:240]],
        "rationale_or_span": rationale_tokens_of(case),
        "target_groups": target_groups_of(case),
        "claim_id": claim_id_of(case),
        "stance": stance or stance_proxy_of(case),
        "capability_boundary": capability_boundary,
    }


def build_gating_feature_matrix(
    cases: list[dict[str, Any]],
    view_probabilities: dict[str, dict[str, float]],
    *,
    view_order: tuple[str, ...] = VIEW_ORDER,
) -> tuple[np.ndarray, list[str]]:
    rows = []
    feature_names = []
    for view in view_order:
        feature_names.extend([f"{view}_prob", f"{view}_confidence", f"{view}_available", f"{view}_abstain"])
    feature_names.extend(["cross_view_conflict", "claim_available", "language_zh"])

    for case in cases:
        case_id = str(case.get("case_id"))
        probs = []
        row = []
        for view in view_order:
            view_map = view_probabilities.get(view) or {}
            available = case_id in view_map
            prob = float(view_map.get(case_id, 0.5))
            confidence = confidence_from_probability(prob) if available else 0.0
            abstain = 1.0 if (not available or confidence < 0.2) else 0.0
            row.extend([prob, confidence, 1.0 if available else 0.0, abstain])
            if available:
                probs.append(prob)
        conflict = (max(probs) - min(probs)) if len(probs) > 1 else 0.0
        row.extend(
            [
                round(float(conflict), 6),
                1.0 if claim_context_text(case) else 0.0,
                1.0 if str(case.get("language", "")).lower().startswith("zh") else 0.0,
            ]
        )
        rows.append(row)
    return np.asarray(rows, dtype="float32"), feature_names


def fuse_detector_outputs(
    detector_outputs: list[dict[str, Any]],
    *,
    model_probability: float | None = None,
) -> dict[str, Any]:
    effective = [
        item
        for item in detector_outputs
        if item.get("label") in LABELS and not item.get("abstain")
    ]
    if model_probability is not None:
        score = float(model_probability)
        policy = "trainable_gating_fusion"
    elif effective:
        total = sum(float(item.get("confidence", 0.0)) for item in effective) or 1.0
        score = sum(float(item.get("harm_score", 0.5)) * float(item.get("confidence", 0.0)) for item in effective) / total
        policy = "confidence_weighted_fallback"
    else:
        score = 0.5
        policy = "no_effective_views"

    labels = {item.get("label") for item in effective}
    conflict = len(labels) > 1
    low_confidence = score < 0.55 and score > 0.45
    claim_unlinked = any(item.get("claim_id") == "unlinked" and item.get("stance") == "unlinked" for item in detector_outputs)
    review_reasons = []
    if conflict:
        review_reasons.append("cross_view_conflict")
    if low_confidence:
        review_reasons.append("low_confidence")
    if claim_unlinked:
        review_reasons.append("claim_unlinked")
    if not effective:
        review_reasons.append("no_effective_views")

    selected_views = [str(item.get("view")) for item in effective]
    view_weights = {}
    total_confidence = sum(float(item.get("confidence", 0.0)) for item in effective) or 1.0
    for item in effective:
        view_weights[str(item.get("view"))] = round(float(item.get("confidence", 0.0)) / total_confidence, 6)

    return {
        "final_harmfulness": POSITIVE_LABEL if score >= 0.5 else NEGATIVE_LABEL,
        "final_score": round(score, 6),
        "selected_views": selected_views,
        "view_weights": view_weights,
        "fusion_policy": policy,
        "conflict_reason": "cross_view_conflict" if conflict else "",
        "review_required": bool(review_reasons),
        "review_reason": review_reasons,
    }


def build_agent_review(detector_outputs: list[dict[str, Any]], fusion: dict[str, Any]) -> dict[str, Any]:
    reasons = list(fusion.get("review_reason") or [])
    high_risk = fusion.get("final_harmfulness") == POSITIVE_LABEL and float(fusion.get("final_score", 0.0)) >= 0.75
    if high_risk:
        reasons.append("high_risk_harm_score")
    review_required = bool(reasons)
    evidence = []
    for item in detector_outputs:
        for snippet in item.get("evidence") or []:
            if snippet and snippet not in evidence:
                evidence.append(str(snippet)[:240])
    return {
        "schema_version": "review-agent-review-v1",
        "role": "reviewer_explainer_rule_optimizer",
        "verdict": "needs_review" if review_required else "accept_fusion",
        "review_required": review_required,
        "review_reason": sorted(set(reasons)),
        "agent_outputs": [
            {
                "agent": "HarmReviewer",
                "finding": "Check harmfulness label, abstain state, and evidence sufficiency.",
            },
            {
                "agent": "EvidenceReviewer",
                "finding": "Verify claim/evidence grounding when claim_id is linked.",
            },
            {
                "agent": "RuleOptimizer",
                "finding": "Route recurring low-confidence or cross-view-conflict cases to hard-negative review.",
            },
        ],
        "evidence_summary": evidence[:5],
        "counter_narrative_draft": (
            "Prepare a neutral correction or de-amplification response after human review."
            if fusion.get("final_harmfulness") == POSITIVE_LABEL
            else ""
        ),
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def __getattr__(name: str) -> Any:
    if name in {
        "build_teacher_silver_record",
        "load_teacher_silver_index",
    }:
        from app.core.review.teacher_silver import build_teacher_silver_record, load_teacher_silver_index

        return {
            "build_teacher_silver_record": build_teacher_silver_record,
            "load_teacher_silver_index": load_teacher_silver_index,
        }[name]
    if name in {
        "SelectiveStudentEncoder",
        "build_selective_student_prediction_rows",
        "build_selective_student_targets",
        "predict_selective_student_outputs",
        "student_main_axis_metrics",
        "student_overall_probability_for_case",
        "train_selective_student_model",
    }:
        from app.core.review.selective_student import (
            SelectiveStudentEncoder,
            build_selective_student_prediction_rows,
            build_selective_student_targets,
            predict_selective_student_outputs,
            student_main_axis_metrics,
            student_overall_probability_for_case,
            train_selective_student_model,
        )

        return {
            "SelectiveStudentEncoder": SelectiveStudentEncoder,
            "build_selective_student_prediction_rows": build_selective_student_prediction_rows,
            "build_selective_student_targets": build_selective_student_targets,
            "predict_selective_student_outputs": predict_selective_student_outputs,
            "student_main_axis_metrics": student_main_axis_metrics,
            "student_overall_probability_for_case": student_overall_probability_for_case,
            "train_selective_student_model": train_selective_student_model,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
