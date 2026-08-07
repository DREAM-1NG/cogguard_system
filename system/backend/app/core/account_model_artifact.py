"""Integrity primitives shared by account-model governance and runtime."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any

from app.config import PROJECT_ROOT, resolve_project_path, settings
from app.utils.exceptions import AppException

__all__ = [
    "file_sha256",
    "load_verified_chinese_social_encoder_artifact",
    "load_deployable_bundle_payloads",
    "load_deployable_bundle_manifest",
    "load_verified_bundle_manifest",
    "resolve_bundle_component",
    "verify_bundle_files",
]

_RESEARCH_PACKAGE_NAME = "_cogguard_account_model_bundle"
_DAPT_MODULE_NAME = "_cogguard_chinese_social_encoder_artifact"


def resolve_bundle_component(bundle_dir: Path, component: str) -> Path:
    """Resolve a declared bundle component or legacy checkpoint path."""

    bundle_dir = bundle_dir.resolve()
    manifest_path = bundle_dir / "manifest.json"
    if not manifest_path.is_file():
        return bundle_dir / "checkpoint.pt"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        relative = str((manifest.get("artifacts") or {})[component])
        posix = PurePosixPath(relative)
        if not relative or posix.is_absolute() or ".." in posix.parts or "\\" in relative:
            raise ValueError("invalid bundle component path")
        resolved = (bundle_dir / Path(*posix.parts)).resolve()
        resolved.relative_to(bundle_dir)
        return resolved
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as error:
        raise AppException(code=409, msg="Account model bundle manifest is invalid.") from error


def verify_bundle_files(bundle_dir: Path) -> None:
    """Apply the research package's canonical bundle verification policy."""

    load_verified_bundle_manifest(bundle_dir)


def load_verified_bundle_manifest(bundle_dir: Path) -> dict[str, Any]:
    """Return a verified manifest while translating research errors to API errors."""

    try:
        package = _load_research_package()
        manifest = package.verify_account_model_bundle(bundle_dir.resolve())
    except (AttributeError, ImportError, OSError, TypeError, ValueError) as error:
        raise AppException(code=409, msg="Account model bundle verification failed.") from error
    if not isinstance(manifest, dict):
        raise AppException(code=409, msg="Account model bundle verification returned an invalid manifest.")
    return manifest


def load_verified_chinese_social_encoder_artifact(
    artifact_uri: str | Path,
    *,
    expected_hash: str | None = None,
) -> dict[str, Any]:
    """Verify a registered DAPT encoder directory inside the artifact root."""

    root = resolve_project_path(settings.MODEL_ARTIFACT_ROOT).resolve()
    candidate = Path(artifact_uri).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise AppException(code=409, msg="Chinese social encoder artifact is outside MODEL_ARTIFACT_ROOT.") from error
    try:
        manifest = _load_dapt_module().verify_chinese_social_encoder_artifact(
            candidate,
            expected_hash=expected_hash,
        )
    except (AttributeError, OSError, TypeError, ValueError) as error:
        raise AppException(code=409, msg="Chinese social encoder artifact verification failed.") from error
    if not isinstance(manifest, dict):
        raise AppException(code=409, msg="Chinese social encoder artifact verification returned an invalid manifest.")
    return manifest


def load_deployable_bundle_manifest(bundle_dir: Path) -> dict[str, Any]:
    """Require a verified bundle that passed the research deployment protocol."""

    manifest = load_verified_bundle_manifest(bundle_dir)
    deployment = manifest.get("deployment")
    if not isinstance(deployment, dict) or deployment != {"eligible": True, "status": "eligible"}:
        raise AppException(code=409, msg="Account model bundle is not deployment eligible.")
    return manifest


def load_deployable_bundle_payloads(bundle_dir: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Read immutable bundle payloads and verify the bytes actually returned."""

    bundle_dir = bundle_dir.resolve()
    manifest = load_deployable_bundle_manifest(bundle_dir)
    artifacts = manifest.get("artifacts")
    files = manifest.get("files")
    if not isinstance(artifacts, dict) or not isinstance(files, dict):
        raise AppException(code=409, msg="Account model bundle manifest is invalid.")
    payloads: dict[str, bytes] = {}
    for role, relative_value in artifacts.items():
        relative = str(relative_value)
        path = _safe_relative_file(bundle_dir, relative)
        try:
            payload = path.read_bytes()
        except OSError as error:
            raise AppException(code=409, msg=f"Account model bundle {role} artifact is unreadable.") from error
        expected = str(files.get(relative) or "").lower()
        if not expected or hashlib.sha256(payload).hexdigest() != expected:
            raise AppException(code=409, msg=f"Account model bundle {role} artifact changed during loading.")
        payloads[str(role)] = payload
    return manifest, payloads


def _load_research_package() -> Any:
    existing = sys.modules.get(_RESEARCH_PACKAGE_NAME)
    if existing is not None:
        return existing
    package_dir = Path(__file__).resolve().parents[3] / "research" / "social_bot_detection"
    init_file = package_dir / "__init__.py"
    if not init_file.is_file():
        raise ImportError(f"internal account-model research package not found: {init_file}")
    spec = importlib.util.spec_from_file_location(
        _RESEARCH_PACKAGE_NAME,
        init_file,
        submodule_search_locations=[str(package_dir)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load internal account-model research package from {init_file}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_RESEARCH_PACKAGE_NAME] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        if sys.modules.get(_RESEARCH_PACKAGE_NAME) is module:
            sys.modules.pop(_RESEARCH_PACKAGE_NAME, None)
        raise
    return module


def _load_dapt_module() -> Any:
    existing = sys.modules.get(_DAPT_MODULE_NAME)
    if existing is not None:
        return existing
    path = PROJECT_ROOT / "research" / "social_bot_detection" / "dapt.py"
    spec = importlib.util.spec_from_file_location(_DAPT_MODULE_NAME, path)
    if spec is None or spec.loader is None:
        raise ImportError("internal Chinese social encoder artifact verifier is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_DAPT_MODULE_NAME] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        if sys.modules.get(_DAPT_MODULE_NAME) is module:
            sys.modules.pop(_DAPT_MODULE_NAME, None)
        raise
    return module


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_relative_file(bundle_dir: Path, relative: str) -> Path:
    posix = PurePosixPath(relative)
    if not relative or posix.is_absolute() or ".." in posix.parts or "\\" in relative:
        raise AppException(code=409, msg="Account model bundle contains an unsafe file path.")
    path = (bundle_dir / Path(*posix.parts)).resolve()
    try:
        path.relative_to(bundle_dir)
    except ValueError as error:
        raise AppException(code=409, msg="Account model bundle contains an unsafe file path.") from error
    return path
