"""Local Transformer text representation for account-level posts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import torch
from torch import Tensor, nn

__all__ = ["TextEncoder", "TextEncoderConfig"]


@dataclass(frozen=True, slots=True)
class TextEncoderConfig:
    model_path: str
    max_length: int = 256
    batch_size: int = 8
    max_chunks_per_account: int = 8
    trainable: bool = False
    initialize_from_config: bool = False


class TextEncoder(nn.Module):
    """Encode complete account text using a local Hugging Face checkpoint.

    The encoder is frozen by default, which makes the transfer experiment
    practical on CPU while still using learned language representations. A
    fine-tuning run must opt in explicitly through ``trainable``.
    """

    def __init__(self, config: TextEncoderConfig) -> None:
        super().__init__()
        if not config.model_path:
            raise ValueError("text_model_path is required; no implicit TF-IDF fallback is allowed")
        model_path = Path(config.model_path)
        if not model_path.exists():
            raise FileNotFoundError(f"local text model does not exist: {model_path}")
        from transformers import AutoConfig, AutoModel, AutoTokenizer

        self.config = config
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
        if config.initialize_from_config:
            model_config = AutoConfig.from_pretrained(model_path, local_files_only=True)
            self.encoder = AutoModel.from_config(model_config)
        else:
            self.encoder = AutoModel.from_pretrained(model_path, local_files_only=True)
        self.hidden_size = int(self.encoder.config.hidden_size)
        if not config.trainable:
            for parameter in self.encoder.parameters():
                parameter.requires_grad_(False)
            self.encoder.eval()

    def forward(self, texts: list[str], *, device: torch.device) -> Tensor:
        """Return mean-pooled CLS representations for a batch of accounts."""

        if not texts:
            return torch.empty((0, self.hidden_size), device=device)
        encoded = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=self.config.max_length,
            return_tensors="pt",
        )
        encoded = {key: value.to(device) for key, value in encoded.items()}
        context = torch.enable_grad() if self.config.trainable else torch.no_grad()
        with context:
            output = self.encoder(**encoded)
            mask = encoded["attention_mask"].unsqueeze(-1).to(output.last_hidden_state.dtype)
            pooled = (output.last_hidden_state * mask).sum(dim=1) / mask.sum(dim=1).clamp_min(1.0)
        return pooled

    def encode_all(self, texts: list[str], *, device: torch.device) -> Tensor:
        """Encode accounts by aggregating evenly sampled token chunks."""

        prepared: list[dict[str, list[int]]] = []
        owners: list[int] = []
        chunk_size = max(1, self.config.max_length - self.tokenizer.num_special_tokens_to_add(pair=False))
        for owner, text in enumerate(texts):
            token_ids = self.tokenizer(text, add_special_tokens=False, truncation=False)["input_ids"]
            chunks = [token_ids[start : start + chunk_size] for start in range(0, len(token_ids), chunk_size)]
            if not chunks:
                chunks = [[self.tokenizer.unk_token_id or 0]]
            chunks = _sample_chunks(chunks, self.config.max_chunks_per_account)
            for chunk in chunks:
                prepared.append(self.tokenizer.prepare_for_model(chunk, add_special_tokens=True, return_attention_mask=True))
                owners.append(owner)
        chunk_embeddings = []
        for start in range(0, len(prepared), self.config.batch_size):
            batch = self.tokenizer.pad(prepared[start : start + self.config.batch_size], padding=True, return_tensors="pt")
            batch = {key: value.to(device) for key, value in batch.items()}
            context = torch.enable_grad() if self.config.trainable else torch.no_grad()
            with context:
                output = self.encoder(**batch)
                mask = batch["attention_mask"].unsqueeze(-1).to(output.last_hidden_state.dtype)
                chunk_embeddings.append((output.last_hidden_state * mask).sum(dim=1) / mask.sum(dim=1).clamp_min(1.0))
        stacked = torch.cat(chunk_embeddings, dim=0)
        result = torch.zeros((len(texts), self.hidden_size), device=device)
        counts = torch.zeros((len(texts), 1), device=device)
        for index, owner in enumerate(owners):
            result[owner] += stacked[index]
            counts[owner] += 1
        return result / counts.clamp_min(1.0)


def _sample_chunks(chunks: list[list[int]], limit: int) -> list[list[int]]:
    """Keep deterministic coverage from the beginning, middle, and end."""

    if limit <= 0 or len(chunks) <= limit:
        return chunks
    positions = sorted({round(index * (len(chunks) - 1) / max(limit - 1, 1)) for index in range(limit)})
    return [chunks[position] for position in positions]
