"""Runtime primitives for Chinese social-encoder DAPT experiments."""

from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, Mapping
from uuid import uuid4


_ENCODER_ARTIFACT_SCHEMA = "cogguard.chinese-social-encoder.v1"
_ENCODER_ARTIFACT_DIRNAME = "chinese_social_encoder"
_ENCODER_MANIFEST_NAME = "encoder_manifest.json"
_ENCODER_PAYLOAD_NAME = "encoder_state.pt"
_ENCODER_PAYLOAD_SCHEMA = "cogguard.botrhg.account.v3"


@dataclass(frozen=True, slots=True)
class DAPTConfig:
    """Configuration for domain-adaptive masked-language-model training."""

    mlm_probability: float = 0.15
    max_length: int = 128
    micro_batch_size: int = 2
    gradient_accumulation_steps: int = 32
    mixed_precision: bool = True
    gradient_checkpointing: bool = True
    historical_replay_ratio: float = 0.20
    min_chinese_tokens: int = 4
    learning_rate: float = 5e-5
    weight_decay: float = 0.01


@dataclass(frozen=True, slots=True)
class DAPTCorpusManifest:
    """Reproducible provenance for a DAPT text-only corpus version."""

    schema: str
    version_id: str
    input_fingerprint: str
    corpus_fingerprint: str
    eligible_chinese_token_count: int
    current_document_count: int
    replay_document_count: int
    exact_duplicate_count: int
    rejected_document_count: int
    historical_replay_ratio: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DAPTCorpusVersion:
    """Prepared documents plus the manifest required to reproduce them."""

    documents: tuple[str, ...]
    manifest: DAPTCorpusManifest


@dataclass(frozen=True, slots=True)
class DAPTTrainingState:
    """Position of a recoverable DAPT run."""

    epoch: int
    global_step: int
    data_cursor: int


@dataclass(frozen=True, slots=True)
class DAPTTrainingResult:
    """Stable summary returned by a completed or resumed DAPT run."""

    completed_epochs: int
    global_step: int
    checkpoint_path: Path
    input_fingerprint: str
    runtime_precision: str
    encoder_artifact_dir: Path
    encoder_manifest_path: Path
    encoder_payload_path: Path
    encoder_artifact_hash: str


def build_versioned_dapt_corpus(
    current_documents: Iterable[str],
    historical_documents: Iterable[str] = (),
    *,
    config: DAPTConfig | None = None,
) -> DAPTCorpusVersion:
    """Filter, exactly deduplicate, and deterministically mix DAPT text.

    Documents retain their original bytes-as-text semantics for exact
    de-duplication. Chinese token eligibility is counted as CJK Unified
    Ideographs, which keeps the policy inspectable without a tokenizer.
    """

    effective_config = config or DAPTConfig()
    _validate_config(effective_config)
    current_source = tuple(current_documents)
    historical_source = tuple(historical_documents)
    current, current_duplicates, current_rejected = _eligible_unique_documents(
        current_source, effective_config.min_chinese_tokens
    )
    historical, historical_duplicates, historical_rejected = _eligible_unique_documents(
        historical_source, effective_config.min_chinese_tokens, excluded=set(current)
    )
    replay_count = min(len(historical), round(len(current) * effective_config.historical_replay_ratio / (1 - effective_config.historical_replay_ratio)))
    replay = tuple(sorted(historical, key=_document_sort_key)[:replay_count])
    documents = tuple(current) + replay
    input_payload = {
        "current_source": sorted(current_source),
        "historical_source": sorted(historical_source),
        "current": list(current),
        "historical": list(historical),
        "config": {
            "min_chinese_tokens": effective_config.min_chinese_tokens,
            "historical_replay_ratio": effective_config.historical_replay_ratio,
        },
    }
    input_fingerprint = _fingerprint(input_payload)
    corpus_fingerprint = _fingerprint({"documents": list(documents)})
    manifest = DAPTCorpusManifest(
        schema="cogguard.dapt.corpus.v1",
        version_id=f"dapt-corpus-v1-{input_fingerprint[:12]}",
        input_fingerprint=input_fingerprint,
        corpus_fingerprint=corpus_fingerprint,
        eligible_chinese_token_count=sum(_chinese_token_count(document) for document in documents),
        current_document_count=len(current),
        replay_document_count=len(replay),
        exact_duplicate_count=current_duplicates + historical_duplicates,
        rejected_document_count=current_rejected + historical_rejected,
        historical_replay_ratio=effective_config.historical_replay_ratio,
    )
    return DAPTCorpusVersion(documents=documents, manifest=manifest)


def save_dapt_checkpoint(
    path: str | Path,
    *,
    model: object,
    optimizer: object,
    scheduler: object,
    scaler: object,
    epoch: int,
    global_step: int,
    data_cursor: int,
    corpus: DAPTCorpusVersion,
    config: DAPTConfig,
) -> Path:
    """Atomically persist all state needed for an idempotent DAPT resume."""

    torch = _require_torch()
    checkpoint_path = Path(path)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "cogguard.dapt.checkpoint.v1",
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "scheduler_state_dict": scheduler.state_dict(),
        "scaler_state_dict": scaler.state_dict(),
        "epoch": epoch,
        "global_step": global_step,
        "data_cursor": data_cursor,
        "rng_state": _capture_rng_state(torch),
        "input_fingerprint": corpus.manifest.input_fingerprint,
        "config_hash": dapt_config_hash(config),
    }
    temporary_path = checkpoint_path.with_suffix(checkpoint_path.suffix + ".tmp")
    torch.save(payload, temporary_path)
    os.replace(temporary_path, checkpoint_path)
    return checkpoint_path


def load_dapt_checkpoint(
    path: str | Path,
    *,
    model: object | None = None,
    optimizer: object | None = None,
    scheduler: object | None = None,
    scaler: object | None = None,
    corpus: DAPTCorpusVersion,
    config: DAPTConfig,
) -> DAPTTrainingState:
    """Load a trusted local checkpoint after verifying its run identity."""

    torch = _require_torch()
    payload = torch.load(Path(path), map_location="cpu", weights_only=False)
    if not isinstance(payload, dict) or payload.get("schema") != "cogguard.dapt.checkpoint.v1":
        raise ValueError(f"unsupported DAPT checkpoint: {path}")
    if payload.get("input_fingerprint") != corpus.manifest.input_fingerprint:
        raise ValueError("DAPT checkpoint input fingerprint does not match the supplied corpus")
    if payload.get("config_hash") != dapt_config_hash(config):
        raise ValueError("DAPT checkpoint config hash does not match the supplied configuration")
    for key in (
        "model_state_dict",
        "optimizer_state_dict",
        "scheduler_state_dict",
        "scaler_state_dict",
        "epoch",
        "global_step",
        "data_cursor",
        "rng_state",
        "input_fingerprint",
        "config_hash",
    ):
        if key not in payload:
            raise ValueError(f"DAPT checkpoint is missing required field: {key}")
    if model is not None:
        model.load_state_dict(payload["model_state_dict"])
    if optimizer is not None:
        optimizer.load_state_dict(payload["optimizer_state_dict"])
    if scheduler is not None:
        scheduler.load_state_dict(payload["scheduler_state_dict"])
    if scaler is not None:
        scaler.load_state_dict(payload["scaler_state_dict"])
    _restore_rng_state(payload["rng_state"], torch)
    return DAPTTrainingState(
        epoch=int(payload["epoch"]),
        global_step=int(payload["global_step"]),
        data_cursor=int(payload["data_cursor"]),
    )


def dapt_config_hash(config: DAPTConfig) -> str:
    """Return the stable configuration identity stored in a checkpoint."""

    return _fingerprint(asdict(config))


def train_dapt(
    model_name_or_path: str | Path,
    corpus: DAPTCorpusVersion,
    *,
    output_dir: str | Path,
    config: DAPTConfig | None = None,
    tokenizer: object | None = None,
    model: object | None = None,
    optimizer: object | None = None,
    scheduler: object | None = None,
    epochs: int = 1,
    device: str = "cpu",
    checkpoint_path: str | Path | None = None,
    resume_from: str | Path | None = None,
) -> DAPTTrainingResult:
    """Train a full ``AutoModelForMaskedLM`` on a prepared DAPT corpus.

    The default loading path is local-only so a research run can never
    silently download or substitute a different pretrained model. Tests and
    controlled runtimes can inject tokenizer and model instances directly.
    """

    effective_config = config or DAPTConfig()
    _validate_training_inputs(effective_config, corpus, epochs)
    torch = _require_torch()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    runtime_device = torch.device(device)
    if (tokenizer is None) != (model is None):
        raise ValueError("tokenizer and model must be injected together")
    if tokenizer is None:
        tokenizer, model = _load_local_transformers_model(model_name_or_path)
    assert model is not None
    for parameter in model.parameters():
        parameter.requires_grad_(True)
    if effective_config.gradient_checkpointing and hasattr(model, "gradient_checkpointing_enable"):
        model.gradient_checkpointing_enable()
    model.to(runtime_device)
    model.train()
    optimizer = optimizer or torch.optim.AdamW(
        model.parameters(), lr=effective_config.learning_rate, weight_decay=effective_config.weight_decay
    )
    scheduler = scheduler or torch.optim.lr_scheduler.LambdaLR(optimizer, lambda _: 1.0)
    runtime_precision, autocast_dtype, scaler_enabled = _resolve_runtime_precision(
        torch,
        runtime_device,
        mixed_precision=effective_config.mixed_precision,
    )
    amp_enabled = runtime_precision != "float32"
    scaler = torch.amp.GradScaler("cuda", enabled=scaler_enabled)
    target_checkpoint = Path(checkpoint_path) if checkpoint_path is not None else output / "dapt_checkpoint.pt"
    state = DAPTTrainingState(epoch=0, global_step=0, data_cursor=0)
    if resume_from is not None:
        state = load_dapt_checkpoint(
            resume_from,
            model=model,
            optimizer=optimizer,
            scheduler=scheduler,
            scaler=scaler,
            corpus=corpus,
            config=effective_config,
        )
    _write_runtime_metadata(output, corpus, effective_config)
    for epoch in range(state.epoch, epochs):
        windows = _optimizer_windows(corpus.documents, effective_config.micro_batch_size, effective_config.gradient_accumulation_steps)
        start_cursor = state.data_cursor if epoch == state.epoch else 0
        for cursor in range(start_cursor, len(windows)):
            optimizer.zero_grad(set_to_none=True)
            window = windows[cursor]
            for texts in window:
                batch = _tokenize_for_mlm(tokenizer, texts, effective_config.max_length, runtime_device)
                masked_inputs, labels = _mask_tokens(batch, tokenizer, effective_config.mlm_probability, torch)
                with torch.autocast(
                    device_type=runtime_device.type,
                    enabled=amp_enabled,
                    dtype=autocast_dtype,
                ):
                    loss = model(**masked_inputs, labels=labels).loss / len(window)
                scaler.scale(loss).backward()
            scale_before_step = float(scaler.get_scale())
            scaler.step(optimizer)
            scaler.update()
            optimizer_step_completed = _amp_optimizer_step_completed(
                enabled=scaler_enabled,
                scale_before=scale_before_step,
                scale_after=float(scaler.get_scale()),
            )
            if optimizer_step_completed:
                scheduler.step()
            state = DAPTTrainingState(
                epoch=epoch,
                global_step=state.global_step + int(optimizer_step_completed),
                data_cursor=cursor + 1,
            )
            save_dapt_checkpoint(
                target_checkpoint,
                model=model,
                optimizer=optimizer,
                scheduler=scheduler,
                scaler=scaler,
                epoch=state.epoch,
                global_step=state.global_step,
                data_cursor=state.data_cursor,
                corpus=corpus,
                config=effective_config,
            )
        state = DAPTTrainingState(epoch=epoch + 1, global_step=state.global_step, data_cursor=0)
        save_dapt_checkpoint(
            target_checkpoint,
            model=model,
            optimizer=optimizer,
            scheduler=scheduler,
            scaler=scaler,
            epoch=state.epoch,
            global_step=state.global_step,
            data_cursor=state.data_cursor,
            corpus=corpus,
            config=effective_config,
        )
    result = DAPTTrainingResult(
        completed_epochs=state.epoch,
        global_step=state.global_step,
        checkpoint_path=target_checkpoint,
        input_fingerprint=corpus.manifest.input_fingerprint,
        runtime_precision=runtime_precision,
        **_export_chinese_social_encoder_artifact(
            output,
            model=model,
            tokenizer=tokenizer,
            corpus=corpus,
            config=effective_config,
            base_model_identity=str(model_name_or_path),
            runtime_precision=runtime_precision,
        ),
    )
    (output / "dapt_report.json").write_text(
        json.dumps(
            {
                "completed_epochs": result.completed_epochs,
                "global_step": result.global_step,
                "checkpoint_path": str(result.checkpoint_path),
                "input_fingerprint": result.input_fingerprint,
                "runtime_precision": result.runtime_precision,
                "encoder_artifact_dir": str(result.encoder_artifact_dir),
                "encoder_manifest_path": str(result.encoder_manifest_path),
                "encoder_payload_path": str(result.encoder_payload_path),
                "encoder_artifact_hash": result.encoder_artifact_hash,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return result


def verify_chinese_social_encoder_artifact(
    artifact_dir: str | Path,
    *,
    expected_hash: str | None = None,
) -> dict[str, object]:
    """Verify a portable Chinese social encoder directory without loading it."""

    root = Path(artifact_dir).resolve()
    manifest_path = root / _ENCODER_MANIFEST_NAME
    if not root.is_dir() or not manifest_path.is_file():
        raise ValueError("Chinese social encoder artifact manifest is missing")
    try:
        raw_manifest = manifest_path.read_bytes()
        manifest = json.loads(raw_manifest.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Chinese social encoder artifact manifest is unreadable") from error
    if not isinstance(manifest, dict) or raw_manifest != _canonical_json(manifest).encode("utf-8"):
        raise ValueError("Chinese social encoder artifact manifest is not canonical")
    if (
        manifest.get("schema") != _ENCODER_ARTIFACT_SCHEMA
        or manifest.get("status") != "completed"
        or not isinstance(manifest.get("base_model_identity"), str)
        or not manifest["base_model_identity"].strip()
        or not isinstance(manifest.get("provenance"), dict)
        or not isinstance(manifest.get("files"), dict)
        or not manifest["files"]
    ):
        raise ValueError("Chinese social encoder artifact manifest is invalid")
    provenance = manifest["provenance"]
    if not isinstance(provenance.get("corpus"), dict) or not isinstance(provenance.get("dapt_config"), dict):
        raise ValueError("Chinese social encoder artifact provenance is invalid")
    if not _is_sha256(provenance.get("dapt_config_hash")):
        raise ValueError("Chinese social encoder artifact configuration fingerprint is invalid")

    declared = manifest["files"]
    for relative, digest in declared.items():
        path = _safe_artifact_file(root, relative)
        if not _is_sha256(digest):
            raise ValueError("Chinese social encoder artifact SHA-256 is invalid")
        if not path.is_file():
            raise ValueError(f"Chinese social encoder artifact file is missing: {relative}")
        if _file_sha256(path) != digest:
            raise ValueError(f"Chinese social encoder artifact SHA-256 mismatch: {relative}")
    found = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path != manifest_path
    }
    if found != set(declared):
        raise ValueError("Chinese social encoder artifact contains unlisted or missing files")
    payload = manifest.get("encoder_payload")
    if not isinstance(payload, dict) or set(payload) != {"path", "schema", "sha256"}:
        raise ValueError("Chinese social encoder artifact encoder payload is invalid")
    payload_path = _safe_artifact_file(root, payload["path"])
    payload_hash = str(payload["sha256"] or "").lower()
    if (
        payload.get("schema") != _ENCODER_PAYLOAD_SCHEMA
        or declared.get(str(payload["path"])) != payload_hash
        or not _is_sha256(payload_hash)
        or _file_sha256(payload_path) != payload_hash
    ):
        raise ValueError("Chinese social encoder artifact encoder payload SHA-256 mismatch")
    try:
        payload_value = _require_torch().load(payload_path, map_location="cpu", weights_only=True)
    except (EOFError, OSError, RuntimeError, TypeError, ValueError) as error:
        raise ValueError("Chinese social encoder artifact encoder payload is unreadable") from error
    if (
        not isinstance(payload_value, Mapping)
        or payload_value.get("schema") != _ENCODER_PAYLOAD_SCHEMA
        or payload_value.get("component") != "encoder"
        or not isinstance(payload_value.get("state_dict"), Mapping)
        or not payload_value["state_dict"]
    ):
        raise ValueError("Chinese social encoder artifact encoder payload is invalid")
    artifact_hash = payload_hash
    if expected_hash is not None and artifact_hash != str(expected_hash).strip().lower():
        raise ValueError("Chinese social encoder artifact hash does not match the registered version")
    return {**manifest, "artifact_hash": artifact_hash}


def _export_chinese_social_encoder_artifact(
    output: Path,
    *,
    model: object,
    tokenizer: object,
    corpus: DAPTCorpusVersion,
    config: DAPTConfig,
    base_model_identity: str,
    runtime_precision: str,
) -> dict[str, Path | str]:
    """Persist the completed encoder once; resume verifies instead of overwriting it."""

    artifact_dir = output / _ENCODER_ARTIFACT_DIRNAME
    provenance = {
        "corpus": corpus.manifest.to_dict(),
        "dapt_config": asdict(config),
        "dapt_config_hash": dapt_config_hash(config),
        "runtime_precision": runtime_precision,
    }
    if artifact_dir.exists():
        manifest = verify_chinese_social_encoder_artifact(artifact_dir)
        if (
            manifest["base_model_identity"] != base_model_identity
            or manifest["provenance"] != provenance
        ):
            raise ValueError("Chinese social encoder artifact already exists with different immutable provenance")
        return {
            "encoder_artifact_dir": artifact_dir,
            "encoder_manifest_path": artifact_dir / _ENCODER_MANIFEST_NAME,
            "encoder_payload_path": artifact_dir / str(manifest["encoder_payload"]["path"]),
            "encoder_artifact_hash": str(manifest["artifact_hash"]),
        }

    temporary_dir = output / f".{_ENCODER_ARTIFACT_DIRNAME}-{uuid4().hex}.tmp"
    try:
        temporary_dir.mkdir(parents=False, exist_ok=False)
        try:
            portable_encoder = _portable_encoder_model(model)
            portable_encoder.save_pretrained(temporary_dir)
            tokenizer.save_pretrained(temporary_dir)
        except AttributeError as error:
            raise ValueError("DAPT model and tokenizer must support save_pretrained") from error
        payload_path = temporary_dir / _ENCODER_PAYLOAD_NAME
        _require_torch().save(
            {
                "schema": _ENCODER_PAYLOAD_SCHEMA,
                "component": "encoder",
                "state_dict": _frozen_encoder_state_dict(portable_encoder),
            },
            payload_path,
        )
        files = _artifact_file_hashes(temporary_dir)
        manifest = {
            "base_model_identity": base_model_identity,
            "encoder_payload": {
                "path": _ENCODER_PAYLOAD_NAME,
                "schema": _ENCODER_PAYLOAD_SCHEMA,
                "sha256": files[_ENCODER_PAYLOAD_NAME],
            },
            "files": files,
            "provenance": provenance,
            "schema": _ENCODER_ARTIFACT_SCHEMA,
            "status": "completed",
        }
        manifest_path = temporary_dir / _ENCODER_MANIFEST_NAME
        manifest_path.write_text(_canonical_json(manifest), encoding="utf-8")
        os.replace(temporary_dir, artifact_dir)
    except BaseException:
        shutil.rmtree(temporary_dir, ignore_errors=True)
        raise
    verified = verify_chinese_social_encoder_artifact(artifact_dir)
    return {
        "encoder_artifact_dir": artifact_dir,
        "encoder_manifest_path": artifact_dir / _ENCODER_MANIFEST_NAME,
        "encoder_payload_path": artifact_dir / str(verified["encoder_payload"]["path"]),
        "encoder_artifact_hash": str(verified["artifact_hash"]),
    }


def _frozen_encoder_state_dict(model: object) -> Mapping[str, object]:
    state_dict = model.state_dict()
    if not isinstance(state_dict, Mapping) or not state_dict:
        raise ValueError("DAPT model has no exportable encoder state_dict")
    return state_dict


def _portable_encoder_model(model: object) -> object:
    """Materialize the AutoModel state that detector training will later load."""

    base_model = getattr(model, "base_model", None)
    encoder = base_model if base_model is not None and base_model is not model else model
    config = getattr(encoder, "config", None)
    if config is None:
        return encoder
    try:
        from transformers import AutoModel

        portable = AutoModel.from_config(config)
    except ImportError as error:
        raise RuntimeError("DAPT portable encoder export requires transformers.") from error
    incompatible = portable.load_state_dict(encoder.state_dict(), strict=False)
    missing = set(incompatible.missing_keys)
    unexpected = set(incompatible.unexpected_keys)
    if unexpected or any(not key.startswith("pooler.") for key in missing):
        raise ValueError("DAPT model state cannot be exported as a portable base encoder")
    return portable


def _artifact_file_hashes(root: Path) -> dict[str, str]:
    files = {
        path.relative_to(root).as_posix(): _file_sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != _ENCODER_MANIFEST_NAME
    }
    if not files:
        raise ValueError("DAPT save_pretrained produced no encoder files")
    return dict(sorted(files.items()))


def _safe_artifact_file(root: Path, relative: object) -> Path:
    normalized = str(relative)
    posix = PurePosixPath(normalized)
    if (
        not normalized
        or posix.is_absolute()
        or ".." in posix.parts
        or "." in posix.parts
        or "\\" in normalized
        or normalized == _ENCODER_MANIFEST_NAME
    ):
        raise ValueError("Chinese social encoder artifact contains an unsafe file path")
    path = (root / Path(*posix.parts)).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ValueError("Chinese social encoder artifact contains an unsafe file path") from error
    return path


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_sha256(value: object) -> bool:
    normalized = str(value or "").lower()
    return len(normalized) == 64 and all(character in "0123456789abcdef" for character in normalized)


def _eligible_unique_documents(
    documents: Iterable[str], min_chinese_tokens: int, *, excluded: set[str] | None = None
) -> tuple[tuple[str, ...], int, int]:
    seen = set(excluded or ())
    accepted: list[str] = []
    duplicates = 0
    rejected = 0
    for document in documents:
        if not isinstance(document, str) or _chinese_token_count(document) < min_chinese_tokens:
            rejected += 1
        elif document in seen:
            duplicates += 1
        else:
            seen.add(document)
            accepted.append(document)
    return tuple(sorted(accepted, key=_document_sort_key)), duplicates, rejected


def _chinese_token_count(document: str) -> int:
    return sum("\u4e00" <= character <= "\u9fff" for character in document)


def _document_sort_key(document: str) -> tuple[str, str]:
    return hashlib.sha256(document.encode("utf-8")).hexdigest(), document


def _fingerprint(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _capture_rng_state(torch: object) -> dict[str, object]:
    state: dict[str, object] = {"python": random.getstate(), "torch_cpu": torch.get_rng_state()}
    try:
        import numpy as np

        state["numpy"] = np.random.get_state()
    except ImportError:
        state["numpy"] = None
    if torch.cuda.is_available():
        state["torch_cuda"] = torch.cuda.get_rng_state_all()
    return state


def _restore_rng_state(state: dict[str, object], torch: object) -> None:
    random.setstate(state["python"])
    if state.get("numpy") is not None:
        import numpy as np

        np.random.set_state(state["numpy"])
    torch.set_rng_state(state["torch_cpu"])
    if state.get("torch_cuda") is not None and torch.cuda.is_available():
        torch.cuda.set_rng_state_all(state["torch_cuda"])


def _require_torch():
    try:
        import torch
    except ImportError as error:
        raise RuntimeError("DAPT checkpoint and training require the optional dependency 'torch'.") from error
    return torch


def _validate_config(config: DAPTConfig) -> None:
    if not 0 <= config.historical_replay_ratio < 1:
        raise ValueError("historical_replay_ratio must be in [0, 1)")
    if config.min_chinese_tokens < 1:
        raise ValueError("min_chinese_tokens must be at least 1")


def _validate_training_inputs(config: DAPTConfig, corpus: DAPTCorpusVersion, epochs: int) -> None:
    _validate_config(config)
    if not corpus.documents:
        raise ValueError("DAPT training requires at least one eligible document")
    if config.micro_batch_size < 1:
        raise ValueError("micro_batch_size must be at least 1")
    if config.gradient_accumulation_steps < 1:
        raise ValueError("gradient_accumulation_steps must be at least 1")
    if not 0 < config.mlm_probability <= 1:
        raise ValueError("mlm_probability must be in (0, 1]")
    if epochs < 0:
        raise ValueError("epochs must be non-negative")


def _amp_optimizer_step_completed(*, enabled: bool, scale_before: float, scale_after: float) -> bool:
    """Return false when GradScaler skipped an optimizer update after overflow."""

    return not enabled or scale_after >= scale_before


def _resolve_runtime_precision(torch: object, device: object, *, mixed_precision: bool) -> tuple[str, object, bool]:
    """Resolve one explicit precision policy for the current training device."""

    if not mixed_precision or getattr(device, "type", "") != "cuda":
        return "float32", torch.float32, False
    if torch.cuda.is_bf16_supported():
        return "bfloat16", torch.bfloat16, False
    return "float16", torch.float16, True


def _load_local_transformers_model(model_name_or_path: str | Path) -> tuple[object, object]:
    if not str(model_name_or_path):
        raise ValueError("model_name_or_path is required for DAPT training")
    try:
        from transformers import AutoModelForMaskedLM, AutoTokenizer
    except ImportError as error:
        raise RuntimeError("DAPT model loading requires the optional dependency 'transformers'.") from error
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name_or_path, local_files_only=True)
        model = AutoModelForMaskedLM.from_pretrained(model_name_or_path, local_files_only=True)
    except OSError as error:
        raise RuntimeError(f"DAPT requires a local Transformers model at: {model_name_or_path}") from error
    return tokenizer, model


def _optimizer_windows(documents: tuple[str, ...], micro_batch_size: int, accumulation_steps: int) -> list[list[tuple[str, ...]]]:
    micro_batches = [tuple(documents[index : index + micro_batch_size]) for index in range(0, len(documents), micro_batch_size)]
    return [micro_batches[index : index + accumulation_steps] for index in range(0, len(micro_batches), accumulation_steps)]


def _tokenize_for_mlm(tokenizer: object, documents: tuple[str, ...], max_length: int, device: object) -> dict[str, object]:
    encoded = tokenizer(
        list(documents),
        padding=True,
        truncation=True,
        max_length=max_length,
        return_tensors="pt",
        return_special_tokens_mask=True,
    )
    return {key: value.to(device) for key, value in encoded.items()}


def _mask_tokens(batch: dict[str, object], tokenizer: object, probability: float, torch: object) -> tuple[dict[str, object], object]:
    input_ids = batch["input_ids"].clone()
    labels = input_ids.clone()
    candidates = batch["attention_mask"].bool()
    special_tokens = batch.get("special_tokens_mask")
    if special_tokens is not None:
        candidates &= ~special_tokens.bool()
    selected = torch.rand(input_ids.shape, device=input_ids.device) < probability
    selected &= candidates
    if not selected.any() and candidates.any():
        first_candidate = candidates.nonzero(as_tuple=False)[0]
        selected[first_candidate[0], first_candidate[1]] = True
    labels[~selected] = -100
    masked = input_ids.clone()
    replacement = torch.rand(input_ids.shape, device=input_ids.device)
    masked[selected & (replacement < 0.8)] = tokenizer.mask_token_id
    random_tokens = torch.randint(tokenizer.vocab_size, input_ids.shape, device=input_ids.device)
    masked[selected & (replacement >= 0.8) & (replacement < 0.9)] = random_tokens[selected & (replacement >= 0.8) & (replacement < 0.9)]
    model_inputs = {key: value for key, value in batch.items() if key != "special_tokens_mask"}
    model_inputs["input_ids"] = masked
    return model_inputs, labels


def _write_runtime_metadata(output: Path, corpus: DAPTCorpusVersion, config: DAPTConfig) -> None:
    (output / "dapt_manifest.json").write_text(json.dumps(corpus.manifest.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "dapt_config.json").write_text(json.dumps(asdict(config), ensure_ascii=False, indent=2), encoding="utf-8")
