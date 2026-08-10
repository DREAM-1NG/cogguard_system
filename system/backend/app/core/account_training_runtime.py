"""Local-only executors used by the account-training Celery worker."""

from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import sys
from concurrent.futures import Future
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.config import PROJECT_ROOT, resolve_project_path, settings
from app.core.account_training import AccountTrainingFamily
from app.core.account_model_artifact import load_verified_chinese_social_encoder_artifact
from app.utils.exceptions import AppException

__all__ = [
    "AccountModelGpuOwnershipBusyError",
    "AccountModelRuntimeOwnership",
    "AccountTrainingOwnership",
    "AccountTrainingOwnershipBusyError",
    "account_model_gpu_ownership_path",
    "account_training_ownership_path",
    "account_training_run_is_live",
    "acquire_account_model_gpu_ownership",
    "acquire_account_training_ownership",
    "execute_account_training_artifact",
    "preflight_account_training_artifact",
]

_MLM_COMPATIBLE_MODEL_TYPES = frozenset(
    {
        "albert",
        "bert",
        "big_bird",
        "camembert",
        "deberta",
        "deberta-v2",
        "distilbert",
        "electra",
        "flaubert",
        "funnel",
        "longformer",
        "mobilebert",
        "modernbert",
        "roberta",
        "roformer",
        "xlm",
        "xlm-roberta",
    }
)
_MODEL_WEIGHT_FILENAMES = ("model.safetensors", "pytorch_model.bin")
_MODEL_WEIGHT_INDEX_FILENAMES = ("model.safetensors.index.json", "pytorch_model.bin.index.json")
_PRODUCTION_DATASET_NAME = "approved_account_corpus"


class AccountTrainingOwnershipBusyError(RuntimeError):
    """A live local runtime still owns the durable run fence."""


class AccountModelGpuOwnershipBusyError(AccountTrainingOwnershipBusyError):
    """Another live account-model operation owns the single-node GPU fence."""


class AccountTrainingOwnership:
    """Token-checked ownership of one local account-training runtime."""

    def __init__(self, *, path: Path, token: str, attempt: int, payload: bytes):
        self.path = path
        self.token = token
        self.attempt = attempt
        self._payload = payload
        self._released = False
        self._release_deferred = False

    @property
    def release_deferred(self) -> bool:
        return self._release_deferred

    def release_when_finished(self, execution: Future[Any]) -> None:
        """Keep the fence while a detached blocking runtime still writes files."""

        self._release_deferred = True
        execution.add_done_callback(lambda _execution: self.release())

    def release(self) -> None:
        if self._released:
            return
        with _fence_guard(self.path):
            owner = _read_owner(self.path)
            if owner and owner["payload"] == self._payload and owner["token"] == self.token:
                try:
                    self.path.unlink()
                except FileNotFoundError:
                    pass
        self._released = True


class AccountModelRuntimeOwnership:
    """Release a GPU fence and operation fence as one runtime ownership unit."""

    def __init__(self, *owners: AccountTrainingOwnership):
        if not owners:
            raise ValueError("Account model runtime ownership requires at least one fence.")
        self._owners = owners

    @property
    def release_deferred(self) -> bool:
        return any(owner.release_deferred for owner in self._owners)

    def release_when_finished(self, execution: Future[Any]) -> None:
        for owner in self._owners:
            owner.release_when_finished(execution)

    def release(self) -> None:
        for owner in reversed(self._owners):
            owner.release()


def account_model_gpu_ownership_path() -> Path:
    """Return the single-node fence shared by account training and evaluation."""

    root = resolve_project_path(settings.MODEL_ARTIFACT_ROOT)
    return root / "account_model" / "locks" / "gpu.lock"


def account_training_ownership_path(run_id: str) -> Path:
    """Return the run-local ownership record below MODEL_ARTIFACT_ROOT."""

    if not run_id or Path(run_id).name != run_id or run_id in {".", ".."}:
        raise ValueError("Account training run_id is not safe for a local ownership path.")
    root = resolve_project_path(settings.MODEL_ARTIFACT_ROOT)
    return root / "account_training" / "locks" / f"{run_id}.lock"


def account_training_run_is_live(run_id: str) -> bool:
    """Return whether a run has a live or unrecognized ownership record."""

    path = account_training_ownership_path(run_id)
    owner = _read_owner(path)
    if owner is None:
        # A legacy or malformed fence cannot prove that no runtime owns its
        # artifact directory. Leave it for an explicit operator recovery.
        return path.exists()
    return _owner_is_live(owner)


def acquire_account_training_ownership(run_id: str, attempt: int) -> AccountTrainingOwnership:
    """Create an exclusive run fence, reclaiming only records for dead owners."""

    return _acquire_ownership(
        path=account_training_ownership_path(run_id),
        attempt=attempt,
        metadata={"run_id": run_id},
        busy_error=AccountTrainingOwnershipBusyError,
        busy_message=f"Account training run {run_id}",
    )


def acquire_account_model_gpu_ownership(operation_id: str) -> AccountTrainingOwnership:
    """Acquire the process-bound GPU fence for one training or evaluation operation."""

    normalized_operation_id = str(operation_id or "").strip()
    if not normalized_operation_id or len(normalized_operation_id) > 256:
        raise ValueError("Account model GPU operation_id is invalid.")
    return _acquire_ownership(
        path=account_model_gpu_ownership_path(),
        attempt=1,
        metadata={"operation_id": normalized_operation_id},
        busy_error=AccountModelGpuOwnershipBusyError,
        busy_message="Account model GPU",
    )


def _acquire_ownership(
    *,
    path: Path,
    attempt: int,
    metadata: dict[str, Any],
    busy_error: type[AccountTrainingOwnershipBusyError],
    busy_message: str,
) -> AccountTrainingOwnership:
    normalized_attempt = int(attempt)
    if normalized_attempt < 1:
        raise ValueError("Account training attempt must be positive.")
    path.parent.mkdir(parents=True, exist_ok=True)
    token = uuid4().hex
    process_identity = _process_identity(os.getpid())
    if not process_identity:
        raise RuntimeError("Cannot establish a stable process identity for account model runtime ownership.")
    payload = json.dumps(
        {
            "attempt": normalized_attempt,
            "pid": os.getpid(),
            "process_identity": process_identity,
            "token": token,
            **metadata,
        },
        ensure_ascii=True,
        sort_keys=True,
    ).encode("utf-8")
    while True:
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            owner = _read_owner(path)
            if owner is None:
                if not path.exists():
                    continue
                raise busy_error(f"{busy_message} has an unrecognized ownership fence.")
            if _owner_is_live(owner):
                raise busy_error(f"{busy_message} is still owned by live process {owner['pid']}.")
            _reclaim_stale_owner(path, owner)
            continue
        try:
            os.write(descriptor, payload)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return AccountTrainingOwnership(path=path, token=token, attempt=normalized_attempt, payload=payload)


def _read_owner(path: Path) -> dict[str, Any] | None:
    try:
        raw_payload = path.read_bytes()
        payload = json.loads(raw_payload.decode("utf-8"))
        pid = int(payload.get("pid"))
        attempt = int(payload.get("attempt"))
        process_identity = str(payload.get("process_identity") or "")
        token = str(payload.get("token") or "")
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None
    if pid <= 0 or attempt < 1 or not process_identity or not token:
        return None
    return {
        "attempt": attempt,
        "payload": raw_payload,
        "pid": pid,
        "process_identity": process_identity,
        "token": token,
    }


def _owner_is_live(owner: dict[str, Any]) -> bool:
    current_identity = _process_identity(int(owner["pid"]))
    if current_identity is not None:
        return current_identity == owner["process_identity"]
    # A process that cannot be inspected is still treated as live. This keeps
    # access-restricted hosts and transient /proc failures fail-safe.
    return _pid_is_live(int(owner["pid"]))


def _reclaim_stale_owner(path: Path, observed: dict[str, Any]) -> None:
    """Delete only the exact stale fence observed before entering the guard."""

    with _fence_guard(path):
        current = _read_owner(path)
        if current is None or current["payload"] != observed["payload"]:
            return
        if _owner_is_live(current):
            return
        try:
            path.unlink()
        except FileNotFoundError:
            pass


@contextmanager
def _fence_guard(path: Path):
    """Serialize compare-and-delete with a kernel-released sidecar lock."""

    guard_path = path.with_name(f"{path.name}.guard")
    with guard_path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _process_identity(pid: int) -> str | None:
    if pid <= 0:
        return None
    if os.name == "nt":
        return _windows_process_identity(pid)
    return _linux_process_identity(pid)


def _linux_process_identity(pid: int) -> str | None:
    try:
        boot_id = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8").strip()
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except OSError:
        return None
    closing_parenthesis = stat.rfind(")")
    fields = stat[closing_parenthesis + 2 :].split()
    if not boot_id or closing_parenthesis < 0 or len(fields) <= 19:
        return None
    return f"linux:{boot_id}:{fields[19]}"


def _pid_is_live(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        return _windows_pid_is_live(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _windows_pid_is_live(pid: int) -> bool:
    import ctypes
    from ctypes import wintypes

    process_query_limited_information = 0x1000
    still_active = 259
    error_access_denied = 5
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    ctypes.set_last_error(0)
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return ctypes.get_last_error() == error_access_denied
    try:
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return True
        return exit_code.value == still_active
    finally:
        kernel32.CloseHandle(handle)


def _windows_process_identity(pid: int) -> str | None:
    import ctypes
    from ctypes import wintypes

    process_query_limited_information = 0x1000
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetProcessTimes.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
    ]
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return None
    try:
        created_at = wintypes.FILETIME()
        exited_at = wintypes.FILETIME()
        kernel_at = wintypes.FILETIME()
        user_at = wintypes.FILETIME()
        if not kernel32.GetProcessTimes(
            handle,
            ctypes.byref(created_at),
            ctypes.byref(exited_at),
            ctypes.byref(kernel_at),
            ctypes.byref(user_at),
        ):
            return None
        creation_ticks = (int(created_at.dwHighDateTime) << 32) | int(created_at.dwLowDateTime)
        return f"windows:{creation_ticks}"
    finally:
        kernel32.CloseHandle(handle)


def execute_account_training_artifact(
    *,
    family: str,
    config: dict[str, Any],
    output_dir: str | Path,
) -> dict[str, Any]:
    """Run one explicitly configured local training implementation.

    The worker never downloads a model or accepts an output path outside the
    configured artifact root. Missing inputs fail closed with a diagnostic
    error instead of producing a heuristic candidate.
    """

    training_family = preflight_account_training_artifact(family=family, config=config)["training_family"]
    output = _resolve_output_dir(output_dir)
    if training_family == AccountTrainingFamily.CHINESE_SOCIAL_ENCODER:
        return _execute_dapt(config, output)
    return _execute_detector(config, output)


def preflight_account_training_artifact(*, family: str, config: dict[str, Any]) -> dict[str, Any]:
    """Validate immutable local inputs before a training run is queued or executed.

    This deliberately performs only filesystem and JSON-structure checks. It
    does not create artifact directories, acquire runtime ownership, initialize
    CUDA, instantiate Transformers objects, or access the network. The worker
    still performs the final local Transformers load immediately before DAPT.
    """

    try:
        training_family = AccountTrainingFamily(family)
    except ValueError as error:
        raise AppException(code=400, msg=f"Unsupported account training family: {family}") from error
    if training_family == AccountTrainingFamily.CHINESE_SOCIAL_ENCODER:
        return _preflight_chinese_social_encoder(config, training_family)
    return _preflight_chinese_account_detector(config, training_family)


def _preflight_chinese_social_encoder(
    config: dict[str, Any],
    training_family: AccountTrainingFamily,
) -> dict[str, Any]:
    corpus_path = _required_file_path(config.get("corpus_documents_path"), "corpus_documents_path")
    documents = _read_text_jsonl(corpus_path)
    if not documents:
        raise AppException(code=409, msg="Chinese encoder training corpus must contain at least one trainable text.")
    historical_count = 0
    if config.get("historical_documents_path"):
        historical_path = _required_file_path(config.get("historical_documents_path"), "historical_documents_path")
        historical_count = len(_read_text_jsonl(historical_path))
        if not historical_count:
            raise AppException(code=409, msg="Chinese encoder historical corpus must contain at least one trainable text.")
    model_path = str(config.get("model_name_or_path") or settings.ACCOUNT_ACQUISITION_TEXT_MODEL_PATH).strip()
    if not model_path:
        raise AppException(code=409, msg="Chinese encoder training requires a local model_name_or_path.")
    _validate_local_transformers_mlm(Path(model_path).expanduser().resolve())
    return {
        "family": training_family.value,
        "training_family": training_family,
        "document_count": len(documents),
        "historical_document_count": historical_count,
    }


def _preflight_chinese_account_detector(
    config: dict[str, Any],
    training_family: AccountTrainingFamily,
) -> dict[str, Any]:
    if config.get("strict_protocol", True) is not True:
        raise AppException(code=409, msg="Account detector training requires strict_protocol=true.")
    dataset_name = str(config.get("dataset_name") or _PRODUCTION_DATASET_NAME)
    if dataset_name != _PRODUCTION_DATASET_NAME:
        raise AppException(code=409, msg="Account detector training only accepts dataset_name=approved_account_corpus.")
    dataset_root = _required_path(config.get("dataset_root"), "dataset_root")
    if not dataset_root.is_dir():
        raise AppException(code=409, msg="Account detector training dataset_root must be a directory.")
    dataset_manifest = _validate_detector_dataset_root(dataset_root)
    expected_fingerprint = str(config.get("input_fingerprint") or "").lower()
    if not _is_sha256(expected_fingerprint) or dataset_manifest["data_fingerprint"] != expected_fingerprint:
        raise AppException(code=409, msg="Account detector dataset fingerprint does not match input_fingerprint.")
    encoder_version = str(config.get("encoder_version") or "").strip()
    encoder_artifact_hash = str(config.get("encoder_artifact_hash") or "").strip().lower()
    model_path = str(config.get("text_model_path") or "").strip()
    binding_payload_path = str(config.get("encoder_binding_payload_path") or "").strip()
    if not encoder_version or not model_path or not binding_payload_path or len(encoder_artifact_hash) != 64:
        raise AppException(code=409, msg="Account detector training requires a registered encoder version.")
    try:
        verified_manifest = load_verified_chinese_social_encoder_artifact(
            model_path,
            expected_hash=encoder_artifact_hash,
        )
    except AppException:
        raise
    except (OSError, TypeError, ValueError) as error:
        raise AppException(code=409, msg="Account detector training encoder artifact verification failed.") from error
    if str(verified_manifest.get("artifact_hash") or "").lower() != encoder_artifact_hash:
        raise AppException(code=409, msg="Account detector training encoder artifact hash is invalid.")
    encoder_payload = verified_manifest.get("encoder_payload")
    if not isinstance(encoder_payload, dict) or not isinstance(encoder_payload.get("path"), str):
        raise AppException(code=409, msg="Account detector training encoder payload is invalid.")
    expected_payload_path = Path(model_path).resolve() / encoder_payload["path"]
    if Path(binding_payload_path).resolve() != expected_payload_path or not expected_payload_path.is_file():
        raise AppException(code=409, msg="Account detector training encoder binding payload is invalid.")
    return {
        "family": training_family.value,
        "training_family": training_family,
        "dataset_root": dataset_root,
    }


def _execute_dapt(config: dict[str, Any], output: Path) -> dict[str, Any]:
    model_path = str(config.get("model_name_or_path") or settings.ACCOUNT_ACQUISITION_TEXT_MODEL_PATH).strip()
    corpus_path = _required_path(config.get("corpus_documents_path"), "corpus_documents_path")
    historical_path = config.get("historical_documents_path")
    documents = _read_text_jsonl(corpus_path)
    historical = _read_text_jsonl(Path(historical_path)) if historical_path else []
    if not model_path:
        raise AppException(code=409, msg="Chinese encoder training requires a local model_name_or_path.")
    module = _load_dapt_module()
    config_keys = {
        key
        for key in (
            "mlm_probability",
            "max_length",
            "micro_batch_size",
            "gradient_accumulation_steps",
            "mixed_precision",
            "gradient_checkpointing",
            "historical_replay_ratio",
            "min_chinese_tokens",
            "learning_rate",
            "weight_decay",
        )
        if key in config
    }
    dapt_config = module.DAPTConfig(**{key: config[key] for key in config_keys})
    corpus = module.build_versioned_dapt_corpus(documents, historical, config=dapt_config)
    result = module.train_dapt(
        model_path,
        corpus,
        output_dir=output,
        config=dapt_config,
        epochs=max(1, int(config.get("epochs", 1))),
        device=str(config.get("device") or settings.ACCOUNT_ACQUISITION_DEVICE),
        resume_from=config.get("resume_checkpoint_uri") or None,
    )
    return {"family": AccountTrainingFamily.CHINESE_SOCIAL_ENCODER.value, **_jsonable(asdict(result))}


def _execute_detector(config: dict[str, Any], output: Path) -> dict[str, Any]:
    encoder_version = str(config.get("encoder_version") or "").strip()
    encoder_artifact_hash = str(config.get("encoder_artifact_hash") or "").strip().lower()
    model_path = str(config.get("text_model_path") or "").strip()
    binding_payload_path = str(config.get("encoder_binding_payload_path") or "").strip()
    if not encoder_version or not model_path or not binding_payload_path or len(encoder_artifact_hash) != 64:
        raise AppException(code=409, msg="Account detector training requires a registered encoder version.")
    verified_manifest = load_verified_chinese_social_encoder_artifact(
        model_path,
        expected_hash=encoder_artifact_hash,
    )
    encoder_payload = verified_manifest.get("encoder_payload")
    if not isinstance(encoder_payload, dict) or not isinstance(encoder_payload.get("path"), str):
        raise AppException(code=409, msg="Account detector training encoder payload is invalid.")
    expected_payload_path = (Path(model_path).resolve() / encoder_payload["path"])
    if Path(binding_payload_path).resolve() != expected_payload_path:
        raise AppException(code=409, msg="Account detector training encoder binding payload is invalid.")
    if str(verified_manifest.get("artifact_hash") or "").lower() != encoder_artifact_hash:
        raise AppException(code=409, msg="Account detector training encoder artifact hash is invalid.")
    dataset_root = _required_path(config.get("dataset_root"), "dataset_root")
    package = _load_research_package()
    model_config_payload = dict(config.get("model") or {})
    if bool(model_config_payload.get("encoder_trainable", False)):
        raise AppException(code=409, msg="Account detector training requires an immutable frozen encoder version.")
    model_config_payload["text_model_path"] = model_path
    model_config_payload["encoder_trainable"] = False
    model_config = package.ModelConfig(**{key: value for key, value in model_config_payload.items() if key in package.ModelConfig.__dataclass_fields__})
    training_payload = {
        key: value
        for key, value in config.items()
        if key in package.TrainingConfig.__dataclass_fields__ and key != "model"
    }
    training_payload["dataset_name"] = str(config.get("dataset_name") or "approved_account_corpus")
    training_payload["model"] = model_config
    training_config = package.TrainingConfig(**training_payload)
    # Production training must produce a record-derived evaluation protocol.
    # The older two-stage helper remains available for research comparison but
    # is intentionally not a system worker default.
    if not bool(config.get("strict_protocol", True)):
        raise AppException(code=409, msg="Account detector workers require strict_protocol=true.")
    result = package.train_strict_botrhg(
        dataset_root,
        output,
        config=training_config,
        deployment_schema="cogguard.botrhg.account.v3",
        encoder_binding_payload_path=expected_payload_path,
    )
    return {
        "family": AccountTrainingFamily.CHINESE_ACCOUNT_DETECTOR.value,
        "encoder_version": encoder_version,
        "encoder_artifact_hash": encoder_artifact_hash,
        **_jsonable(result),
    }


def _load_research_package() -> Any:
    package_dir = PROJECT_ROOT / "research" / "social_bot_detection"
    init_file = package_dir / "__init__.py"
    name = "_cogguard_account_training_research"
    existing = __import__("sys").modules.get(name)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(name, init_file, submodule_search_locations=[str(package_dir)])
    if spec is None or spec.loader is None:
        raise AppException(code=500, msg="Internal account-detection research package is unavailable.")
    module = importlib.util.module_from_spec(spec)
    __import__("sys").modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_dapt_module() -> Any:
    path = PROJECT_ROOT / "research" / "social_bot_detection" / "dapt.py"
    name = "_cogguard_account_dapt"
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AppException(code=500, msg="Internal DAPT runtime is unavailable.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def _required_path(value: Any, name: str) -> Path:
    if not value:
        raise AppException(code=409, msg=f"Account training requires {name}.")
    path = Path(str(value)).expanduser().resolve()
    if not path.exists():
        raise AppException(code=404, msg=f"Account training input {name} was not found: {path}")
    return path


def _required_file_path(value: Any, name: str) -> Path:
    path = _required_path(value, name)
    if not path.is_file():
        raise AppException(code=409, msg=f"Account training input {name} must be a file.")
    return path


def _validate_detector_dataset_root(dataset_root: Path) -> dict[str, Any]:
    labels_path = dataset_root / "approved_account_labels.jsonl"
    manifest_path = dataset_root / "dataset_manifest.json"
    _required_file_path(labels_path, "dataset_root/approved_account_labels.jsonl")
    manifest = _read_json_object(manifest_path, "Account detector dataset_manifest.json")
    _validate_detector_dataset_manifest(manifest)
    try:
        lines = labels_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise AppException(code=409, msg="Account detector approved_account_labels.jsonl is unreadable.") from error
    observed_class_counts: dict[str, int] = {}
    fingerprint = hashlib.sha256()
    record_count = 0
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            raise AppException(code=409, msg=f"Account detector dataset has invalid record at line {line_number}.") from None
        if not isinstance(record, dict):
            raise AppException(code=409, msg=f"Account detector dataset has invalid record at line {line_number}.")
        target = str(record.get("training_target") or "").strip()
        text = str(record.get("text") or "").strip()
        identity = str(record.get("account_id") or record.get("case_id") or "").strip()
        if target not in {"bot", "non_bot", "abstain"} or not text or not identity:
            raise AppException(code=409, msg=f"Account detector dataset has invalid record at line {line_number}.")
        fingerprint.update(json.dumps(record, ensure_ascii=False, sort_keys=True).encode("utf-8"))
        fingerprint.update(b"\n")
        observed_class_counts[target] = observed_class_counts.get(target, 0) + 1
        record_count += 1
    if not record_count:
        raise AppException(code=409, msg="Account detector approved_account_labels.jsonl must contain trainable records.")
    if record_count != manifest["record_count"]:
        raise AppException(code=409, msg="Account detector dataset_manifest.json record_count does not match records.")
    if observed_class_counts != manifest["class_counts"]:
        raise AppException(code=409, msg="Account detector dataset_manifest.json class_counts do not match records.")
    if fingerprint.hexdigest() != manifest["data_fingerprint"]:
        raise AppException(code=409, msg="Account detector dataset_manifest.json data_fingerprint does not match records.")
    if observed_class_counts.get("bot", 0) < 1 or observed_class_counts.get("non_bot", 0) < 1:
        raise AppException(code=409, msg="Account detector dataset requires at least one bot and one non_bot record.")
    return manifest


def _validate_detector_dataset_manifest(manifest: dict[str, Any]) -> None:
    data_fingerprint = str(manifest.get("data_fingerprint") or "").lower()
    record_count = manifest.get("record_count")
    class_counts = manifest.get("class_counts")
    if (
        not _is_sha256(data_fingerprint)
        or not isinstance(record_count, int)
        or isinstance(record_count, bool)
        or record_count <= 0
        or not isinstance(class_counts, dict)
        or not class_counts
        or not all(
            isinstance(target, str)
            and target in {"bot", "non_bot", "abstain"}
            and isinstance(count, int)
            and not isinstance(count, bool)
            and count >= 0
            for target, count in class_counts.items()
        )
        or sum(class_counts.values()) != record_count
    ):
        raise AppException(code=409, msg="Account detector dataset_manifest.json structure is invalid.")
    manifest["data_fingerprint"] = data_fingerprint


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value.lower())


def _validate_local_transformers_mlm(model_path: Path) -> None:
    """Cheap offline validation for a local MLM directory before queuing work."""

    if not model_path.is_dir():
        raise AppException(code=404, msg=f"Chinese encoder local model directory was not found: {model_path}")
    config = _read_json_object(model_path / "config.json", "Chinese encoder local model config")
    architectures = config.get("architectures")
    model_type = str(config.get("model_type") or "").strip().lower()
    has_mlm_architecture = isinstance(architectures, list) and any(
        isinstance(item, str) and item.endswith("ForMaskedLM") for item in architectures
    )
    if not has_mlm_architecture and model_type not in _MLM_COMPATIBLE_MODEL_TYPES:
        raise AppException(code=409, msg="Chinese encoder local model config is not MLM compatible.")
    tokenizer_json = model_path / "tokenizer.json"
    if tokenizer_json.is_file():
        _read_json_object(tokenizer_json, "Chinese encoder tokenizer.json")
    else:
        tokenizer_config = model_path / "tokenizer_config.json"
        vocab_files = (model_path / "vocab.txt", model_path / "vocab.json", model_path / "spiece.model")
        if not tokenizer_config.is_file() or not any(path.is_file() and path.stat().st_size > 0 for path in vocab_files):
            raise AppException(
                code=409,
                msg="Chinese encoder local model requires readable tokenizer.json or tokenizer_config.json with vocabulary.",
            )
        _read_json_object(tokenizer_config, "Chinese encoder tokenizer config")
    if any((model_path / filename).is_file() and (model_path / filename).stat().st_size > 0 for filename in _MODEL_WEIGHT_FILENAMES):
        return
    for index_name in _MODEL_WEIGHT_INDEX_FILENAMES:
        index_path = model_path / index_name
        if not index_path.is_file():
            continue
        index = _read_json_object(index_path, "Chinese encoder model shard index")
        weight_map = index.get("weight_map")
        if not isinstance(weight_map, dict) or not weight_map:
            raise AppException(code=409, msg="Chinese encoder local model shard index has no weights.")
        raw_shard_names = list(weight_map.values())
        if not all(isinstance(value, str) and value.strip() for value in raw_shard_names):
            raise AppException(code=409, msg="Chinese encoder local model shard index contains an invalid weight path.")
        shard_names = {value for value in raw_shard_names}
        if any(
            not _safe_model_file(model_path, shard_name).is_file()
            or _safe_model_file(model_path, shard_name).stat().st_size <= 0
            for shard_name in shard_names
        ):
            raise AppException(code=409, msg="Chinese encoder local model shard index references missing weights.")
        return
    raise AppException(code=409, msg="Chinese encoder local model weights are missing or empty.")


def _read_json_object(path: Path, description: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AppException(code=409, msg=f"{description} is unreadable.") from error
    if not isinstance(payload, dict):
        raise AppException(code=409, msg=f"{description} must be a JSON object.")
    return payload


def _safe_model_file(model_path: Path, relative: str) -> Path:
    candidate = (model_path / relative).resolve()
    try:
        candidate.relative_to(model_path)
    except ValueError as error:
        raise AppException(code=409, msg="Chinese encoder local model shard index contains an unsafe path.") from error
    return candidate


def _resolve_output_dir(value: str | Path) -> Path:
    root = resolve_project_path(settings.MODEL_ARTIFACT_ROOT)
    candidate = Path(value)
    if candidate.is_absolute() or candidate.drive or ".." in candidate.parts:
        raise AppException(code=400, msg="Account training output_dir must be relative to MODEL_ARTIFACT_ROOT.")
    output = (root / candidate).resolve()
    try:
        output.relative_to(root)
    except ValueError as error:
        raise AppException(code=400, msg="Account training output_dir escapes MODEL_ARTIFACT_ROOT.") from error
    output.mkdir(parents=True, exist_ok=True)
    return output


def _read_text_jsonl(path: Path) -> list[str]:
    if not path.is_file():
        raise AppException(code=404, msg=f"Account training text corpus was not found: {path}")
    rows: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            payload = line
        if isinstance(payload, str):
            text = payload
        elif isinstance(payload, dict):
            text = payload.get("text") or payload.get("content") or ""
        else:
            text = ""
        if str(text).strip():
            rows.append(str(text))
    return rows


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value
