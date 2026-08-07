"""Local-only executors used by the account-training Celery worker."""

from __future__ import annotations

import importlib.util
import json
import os
from concurrent.futures import Future
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.config import PROJECT_ROOT, resolve_project_path, settings
from app.core.account_training import AccountTrainingFamily
from app.utils.exceptions import AppException

__all__ = [
    "AccountTrainingOwnership",
    "AccountTrainingOwnershipBusyError",
    "account_training_ownership_path",
    "account_training_run_is_live",
    "acquire_account_training_ownership",
    "execute_account_training_artifact",
]


class AccountTrainingOwnershipBusyError(RuntimeError):
    """A live local runtime still owns the durable run fence."""


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

    normalized_attempt = int(attempt)
    if normalized_attempt < 1:
        raise ValueError("Account training attempt must be positive.")
    path = account_training_ownership_path(run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    token = uuid4().hex
    process_identity = _process_identity(os.getpid())
    if not process_identity:
        raise RuntimeError("Cannot establish a stable process identity for account training ownership.")
    payload = json.dumps(
        {
            "attempt": normalized_attempt,
            "pid": os.getpid(),
            "process_identity": process_identity,
            "token": token,
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
                raise AccountTrainingOwnershipBusyError(
                    f"Account training run {run_id} has an unrecognized ownership fence."
                )
            if _owner_is_live(owner):
                raise AccountTrainingOwnershipBusyError(
                    f"Account training run {run_id} is still owned by live process {owner['pid']}."
                )
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

    output = _resolve_output_dir(output_dir)
    try:
        training_family = AccountTrainingFamily(family)
    except ValueError as error:
        raise AppException(code=400, msg=f"Unsupported account training family: {family}") from error
    if training_family == AccountTrainingFamily.CHINESE_SOCIAL_ENCODER:
        return _execute_dapt(config, output)
    return _execute_detector(config, output)


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
    from app.core.account_model_artifact import load_verified_chinese_social_encoder_artifact

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
    holdout_path = _required_path(config.get("frozen_holdout_manifest_path"), "frozen_holdout_manifest_path")
    try:
        frozen_holdout_manifest = json.loads(holdout_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AppException(code=409, msg="Account detector frozen holdout manifest is unreadable.") from error
    result = package.train_strict_botrhg(
        dataset_root,
        output,
        config=training_config,
        frozen_holdout_manifest=frozen_holdout_manifest,
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
    spec = importlib.util.spec_from_file_location("_cogguard_account_dapt", path)
    if spec is None or spec.loader is None:
        raise AppException(code=500, msg="Internal DAPT runtime is unavailable.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _required_path(value: Any, name: str) -> Path:
    if not value:
        raise AppException(code=409, msg=f"Account training requires {name}.")
    path = Path(str(value)).expanduser().resolve()
    if not path.exists():
        raise AppException(code=404, msg=f"Account training input {name} was not found: {path}")
    return path


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
