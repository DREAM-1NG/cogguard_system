from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping as MappingABC, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from .baselines import default_baseline_registry
from .compact_discovery_methods import default_compact_discovery_registry
from .iohunter_compact import (
    CompactIOHunterMemoryBudgetExceeded,
    compact_fold_fingerprint,
    load_compact_iohunter,
)
from .runner import CANONICAL_REPRODUCTION_OUTPUT_ROOT


IOHUNTER_PREFLIGHT_CAMPAIGNS = ("china", "cuba", "iran", "russia", "UAE", "venezuela")
IOHUNTER_OFFICIAL_SEEDS = (42, 43, 44, 45, 46)
CANONICAL_IOHUNTER_PROCESSED_ROOT = Path("G:/CISCN/dataset/iohunter/data/processed").resolve(strict=False)
IOHUNTER_PREFLIGHT_SCHEMA_VERSION = "cogguard.iohunter-matrix-preflight/v1"
IOHUNTER_PREFLIGHT_RUN_SCHEMA_VERSION = "cogguard.iohunter-preflight-run/v1"
IOHUNTER_PREFLIGHT_STATUS = "preflight_only_no_models_executed"
IOHUNTER_EVALUATION_SCOPE = (
    "IOHunter account labels support external account-recovery evaluation; "
    "they are not ground-truth coordination edges, campaign communities, or causal coordination claims."
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def _text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{field_name} must be non-empty canonical text")
    return value


def _sha(value: str, field_name: str) -> str:
    value = _text(value, field_name).lower()
    if len(value) != 71 or not value.startswith("sha256:"):
        raise ValueError(f"{field_name} must be sha256:<64 hex>")
    int(value[7:], 16)
    return value


def validate_iohunter_preflight_output_dir(output_dir: str | Path) -> Path:
    if not isinstance(output_dir, (str, Path)):
        raise ValueError("output_dir must be a filesystem path")
    candidate = Path(output_dir)
    if not candidate.is_absolute():
        raise ValueError("output_dir must be absolute under the canonical G-drive reproduction output root")
    if any(part == ".." for part in candidate.parts):
        raise ValueError("output_dir must not use traversal outside the canonical G-drive reproduction output root")
    resolved = candidate.resolve(strict=False)
    root = CANONICAL_REPRODUCTION_OUTPUT_ROOT.resolve(strict=False)
    if root.drive.upper() != "G:" or resolved.drive.upper() != "G:":
        raise ValueError("output_dir must be on the canonical G-drive reproduction output root")
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            "output_dir must resolve under the canonical G-drive reproduction output root"
        ) from exc
    if resolved == root:
        raise ValueError("output_dir must be a descendant of the canonical G-drive reproduction output root")
    return resolved


@dataclass(frozen=True, slots=True)
class IOHunterPreflightRow:
    run_id: str
    execution_id: str
    stage: str
    campaign: str
    seed: int
    fold_id: str
    split_policy: str
    method_id: str
    method_version: str
    model_role: str
    implementation_id: str
    dependencies: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    input_fingerprints: Mapping[str, str]
    evaluation_fingerprints: Mapping[str, str]
    expected_output_path: str
    run_manifest_path: str
    status: str
    reason: str | None
    memory_profile: Mapping[str, Any] | None = None
    resume_action: str = "write_preflight_manifest"

    def __post_init__(self) -> None:
        for field_name in (
            "run_id",
            "execution_id",
            "campaign",
            "fold_id",
            "split_policy",
            "method_id",
            "method_version",
            "model_role",
            "implementation_id",
            "expected_output_path",
            "run_manifest_path",
            "resume_action",
        ):
            object.__setattr__(self, field_name, _text(getattr(self, field_name), field_name))
        if self.stage not in {"discovery", "detection"}:
            raise ValueError("stage must be discovery or detection")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise ValueError("seed must be an integer")
        if self.status not in {"ready", "blocked"}:
            raise ValueError("status must be ready or blocked")
        if (self.status == "blocked") != bool(self.reason):
            raise ValueError("blocked rows require a reason and ready rows do not")
        object.__setattr__(self, "dependencies", tuple(_text(value, "dependency") for value in self.dependencies))
        object.__setattr__(
            self,
            "required_capabilities",
            tuple(_text(value, "required_capability") for value in self.required_capabilities),
        )
        expected_inputs = (
            {"discovery"}
            if self.stage == "discovery"
            else {"discovery", "evaluator", "fold"}
        )
        if set(self.input_fingerprints) != expected_inputs:
            raise ValueError(
                f"{self.stage} input_fingerprints must contain {sorted(expected_inputs)}"
            )
        object.__setattr__(
            self,
            "input_fingerprints",
            MappingProxyType(
                {
                    key: _sha(value, f"input_fingerprints[{key}]")
                    for key, value in sorted(self.input_fingerprints.items())
                }
            ),
        )
        if set(self.evaluation_fingerprints) != {"evaluator", "fold"}:
            raise ValueError(
                "evaluation_fingerprints must contain evaluator and fold"
            )
        object.__setattr__(
            self,
            "evaluation_fingerprints",
            MappingProxyType(
                {
                    key: _sha(value, f"evaluation_fingerprints[{key}]")
                    for key, value in sorted(self.evaluation_fingerprints.items())
                }
            ),
        )
        if self.memory_profile is not None:
            if not isinstance(self.memory_profile, MappingABC):
                raise ValueError("memory_profile must be a mapping when provided")
            object.__setattr__(
                self,
                "memory_profile",
                MappingProxyType({str(key): value for key, value in sorted(self.memory_profile.items())}),
            )

    def _identity_payload(self, *, include_resume: bool) -> dict[str, Any]:
        payload = {
            "run_id": self.run_id,
            "execution_id": self.execution_id,
            "stage": self.stage,
            "campaign": self.campaign,
            "seed": self.seed,
            "fold_id": self.fold_id,
            "split_policy": self.split_policy,
            "method_id": self.method_id,
            "method_version": self.method_version,
            "model_role": self.model_role,
            "implementation_id": self.implementation_id,
            "dependencies": list(self.dependencies),
            "required_capabilities": list(self.required_capabilities),
            "input_fingerprints": dict(self.input_fingerprints),
            "evaluation_fingerprints": dict(self.evaluation_fingerprints),
            "expected_output_path": self.expected_output_path,
            "run_manifest_path": self.run_manifest_path,
            "status": self.status,
            "reason": self.reason,
        }
        if include_resume:
            payload["resume_action"] = self.resume_action
            payload["memory_profile"] = None if self.memory_profile is None else dict(self.memory_profile)
        return payload

    @property
    def row_fingerprint(self) -> str:
        return _fingerprint(self._identity_payload(include_resume=False))

    def to_dict(self) -> dict[str, Any]:
        payload = self._identity_payload(include_resume=True)
        payload["row_fingerprint"] = self.row_fingerprint
        return payload


@dataclass(frozen=True, slots=True)
class IOHunterPreflightMatrix:
    output_dir: str
    dataset_root: str
    rows: tuple[IOHunterPreflightRow, ...]
    matrix_fingerprint: str
    campaign_memory_profiles: Mapping[str, Any] | None = None
    evaluation_scope: str = IOHUNTER_EVALUATION_SCOPE
    model_execution_started: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": IOHUNTER_PREFLIGHT_SCHEMA_VERSION,
            "status": IOHUNTER_PREFLIGHT_STATUS,
            "output_dir": self.output_dir,
            "dataset_root": self.dataset_root,
            "matrix_fingerprint": self.matrix_fingerprint,
            "evaluation_scope": self.evaluation_scope,
            "model_execution_started": self.model_execution_started,
            "campaign_memory_profiles": (
                None if self.campaign_memory_profiles is None else dict(self.campaign_memory_profiles)
            ),
            "rows": [row.to_dict() for row in self.rows],
        }


def _run_id(payload: Mapping[str, Any]) -> str:
    return "iohunter-" + hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()[:24]


def _execution_id(payload: Mapping[str, Any]) -> str:
    return (
        "iohunter-execution-"
        + hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()[:24]
    )


def _run_paths(output_dir: Path, row_key: Mapping[str, Any], run_id: str) -> tuple[Path, Path]:
    method_id = str(row_key["method_id"])
    filename = f"{method_id}-{run_id}.json"
    expected = output_dir / "expected_outputs" / filename
    manifest = output_dir / "run_manifests" / filename
    return expected.resolve(strict=False), manifest.resolve(strict=False)


def _blocked_reason(method_id: str, split_policy: str, unavailable_reason: str | None) -> str | None:
    if split_policy == "observed_time_holdout":
        return "blocked: IOHunter processed graphs lack observed timestamps for observed_time_holdout"
    if method_id == "tgn_style_memory_prior":
        return "blocked: tgn_style_memory_prior requires observed timestamps unavailable in IOHunter"
    if unavailable_reason is not None:
        return f"blocked: {unavailable_reason}"
    return None


def _row(
    *,
    output_dir: Path,
    campaign: str,
    seed: int,
    fold_id: str,
    split_policy: str,
    spec: Any,
    fingerprints: Mapping[str, str],
    status: str,
    reason: str | None,
    memory_profile: Mapping[str, Any] | None,
) -> IOHunterPreflightRow:
    execution_inputs = (
        {"discovery": fingerprints["discovery"]}
        if spec.stage == "discovery"
        else dict(fingerprints)
    )
    evaluation_fingerprints = {
        "evaluator": fingerprints["evaluator"],
        "fold": fingerprints["fold"],
    }
    execution_id = _execution_id(
        {
            "campaign": campaign,
            "seed": seed,
            "split_policy": split_policy,
            "method_id": spec.method_id,
            "method_version": spec.method_version,
            "implementation_id": spec.implementation_id,
            "input_fingerprints": execution_inputs,
        }
    )
    evaluation_key = {
        "execution_id": execution_id,
        "fold_id": fold_id,
        "evaluation_fingerprints": evaluation_fingerprints,
    }
    run_id = _run_id(evaluation_key)
    key = {
        "campaign": campaign,
        "seed": seed,
        "fold_id": fold_id,
        "split_policy": split_policy,
        "method_id": spec.method_id,
    }
    expected, manifest = _run_paths(output_dir, key, run_id)
    expected.relative_to(output_dir)
    manifest.relative_to(output_dir)
    return IOHunterPreflightRow(
        run_id=run_id,
        execution_id=execution_id,
        stage=spec.stage,
        campaign=campaign,
        seed=seed,
        fold_id=fold_id,
        split_policy=split_policy,
        method_id=spec.method_id,
        method_version=spec.method_version,
        model_role=spec.model_role,
        implementation_id=spec.implementation_id,
        dependencies=spec.optional_dependencies,
        required_capabilities=spec.required_capabilities,
        input_fingerprints=execution_inputs,
        evaluation_fingerprints=evaluation_fingerprints,
        expected_output_path=str(expected),
        run_manifest_path=str(manifest),
        status=status,
        reason=reason,
        memory_profile=memory_profile,
    )


def _campaign_load_failure_rows(
    *,
    output_dir: Path,
    campaign: str,
    source: Path,
    reason: str,
    memory_profile: Mapping[str, Any] | None = None,
) -> list[IOHunterPreflightRow]:
    registry = default_baseline_registry()
    fingerprints = {
        "discovery": "sha256:" + "0" * 64,
        "evaluator": "sha256:" + "0" * 64,
        "fold": "sha256:" + "0" * 64,
    }
    rows: list[IOHunterPreflightRow] = []
    for seed_index, seed in enumerate(IOHUNTER_OFFICIAL_SEEDS):
        fold_id = f"fold-{seed_index:03d}"
        for spec in registry.specs():
            for split_policy in ("official_fold", "observed_time_holdout"):
                rows.append(
                    _row(
                        output_dir=output_dir,
                        campaign=campaign,
                        seed=seed,
                        fold_id=fold_id,
                        split_policy=split_policy,
                        spec=spec,
                        fingerprints=fingerprints,
                        status="blocked",
                        reason=f"blocked: compact IOHunter load failed for {source}: {reason}",
                        memory_profile=memory_profile,
                    )
                )
    return rows


def _build_campaign_rows(
    *,
    dataset_root: Path,
    output_dir: Path,
    campaign: str,
    memory_budget_bytes: int,
) -> list[IOHunterPreflightRow]:
    source = dataset_root / campaign / "0.7_datasets.pkl"
    try:
        compact = load_compact_iohunter(
            source,
            campaign=campaign,
            trusted_local=True,
            memory_budget_bytes=memory_budget_bytes,
        )
    except CompactIOHunterMemoryBudgetExceeded as exc:
        return _campaign_load_failure_rows(
            output_dir=output_dir,
            campaign=campaign,
            source=source,
            reason=str(exc),
            memory_profile=exc.memory_profile.to_dict(),
        )
    except Exception as exc:
        return _campaign_load_failure_rows(
            output_dir=output_dir,
            campaign=campaign,
            source=source,
            reason=f"{type(exc).__name__}: {exc}",
        )

    registry = default_baseline_registry()
    compact_registry = default_compact_discovery_registry()
    rows: list[IOHunterPreflightRow] = []
    for seed, fold in zip(IOHUNTER_OFFICIAL_SEEDS, compact.evaluator.official_folds, strict=True):
        fingerprints = {
            "discovery": compact.discovery_view.source_layer_fingerprint,
            "evaluator": compact.evaluator.content_fingerprint,
            "fold": compact_fold_fingerprint(fold),
        }
        for spec in registry.specs():
            if spec.method_id in compact_registry.method_ids():
                unavailable = compact_registry.implementation(spec.method_id).unavailable_reason
            else:
                unavailable = registry.implementation(spec.method_id).unavailable_reason
            for split_policy in ("official_fold", "observed_time_holdout"):
                reason = _blocked_reason(spec.method_id, split_policy, unavailable)
                status = "blocked" if reason else "ready"
                rows.append(
                    _row(
                        output_dir=output_dir,
                        campaign=campaign,
                        seed=seed,
                        fold_id=fold.fold_id,
                        split_policy=split_policy,
                        spec=spec,
                        fingerprints=fingerprints,
                        status=status,
                        reason=reason,
                        memory_profile=compact.memory_profile.to_dict(),
                    )
                )
    return rows


def _resume_action(path: Path, row: IOHunterPreflightRow) -> str:
    if not path.exists():
        return "write_preflight_manifest"
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "rewrite_preflight_manifest"
    if (
        existing.get("schema_version") == IOHUNTER_PREFLIGHT_RUN_SCHEMA_VERSION
        and existing.get("run_id") == row.run_id
        and existing.get("row_fingerprint") == row.row_fingerprint
    ):
        if existing.get("execution_status") == "complete":
            return "skip_complete"
        if existing.get("execution_status") == "not_started_preflight_only":
            return "skip_preflight"
    return "rewrite_preflight_manifest"


def _write_run_manifest(row: IOHunterPreflightRow) -> IOHunterPreflightRow:
    path = Path(row.run_manifest_path)
    action = _resume_action(path, row)
    row = IOHunterPreflightRow(
        **{
            **row._identity_payload(include_resume=False),
            "memory_profile": row.memory_profile,
            "resume_action": action,
        }
    )
    if action in {"skip_complete", "skip_preflight"}:
        return row
    _atomic_write_json(
        path,
        {
            "schema_version": IOHUNTER_PREFLIGHT_RUN_SCHEMA_VERSION,
            "run_id": row.run_id,
            "row_fingerprint": row.row_fingerprint,
            "execution_status": "not_started_preflight_only",
            "model_execution_started": False,
            "memory_profile": None if row.memory_profile is None else dict(row.memory_profile),
            "row": row.to_dict(),
        },
    )
    return row


def _matrix_fingerprint(rows: Sequence[IOHunterPreflightRow], dataset_root: Path) -> str:
    return _fingerprint(
        {
            "schema_version": IOHUNTER_PREFLIGHT_SCHEMA_VERSION,
            "dataset_root": str(dataset_root),
            "evaluation_scope": IOHUNTER_EVALUATION_SCOPE,
            "model_execution_started": False,
            "rows": [row._identity_payload(include_resume=False) for row in rows],
        }
    )


def preflight_iohunter_matrix(
    dataset_root: str | Path = CANONICAL_IOHUNTER_PROCESSED_ROOT,
    output_dir: str | Path = CANONICAL_REPRODUCTION_OUTPUT_ROOT / "preflight",
    *,
    memory_budget_bytes: int = 16 * 1024**3,
) -> IOHunterPreflightMatrix:
    if isinstance(memory_budget_bytes, bool) or not isinstance(memory_budget_bytes, int) or memory_budget_bytes <= 0:
        raise ValueError("memory_budget_bytes must be a positive integer")
    dataset = Path(dataset_root).resolve(strict=False)
    output = validate_iohunter_preflight_output_dir(output_dir)
    rows: list[IOHunterPreflightRow] = []
    for campaign in IOHUNTER_PREFLIGHT_CAMPAIGNS:
        rows.extend(
            _build_campaign_rows(
                dataset_root=dataset,
                output_dir=output,
                campaign=campaign,
                memory_budget_bytes=memory_budget_bytes,
            )
        )
    rows = sorted(rows, key=lambda row: (row.campaign, row.seed, row.fold_id, row.method_id, row.split_policy))
    rows = [_write_run_manifest(row) for row in rows]
    memory_profiles: dict[str, Any] = {}
    for row in rows:
        if row.memory_profile is not None and row.campaign not in memory_profiles:
            memory_profiles[row.campaign] = dict(row.memory_profile)
    fingerprint = _matrix_fingerprint(rows, dataset)
    matrix = IOHunterPreflightMatrix(
        output_dir=str(output),
        dataset_root=str(dataset),
        rows=tuple(rows),
        matrix_fingerprint=fingerprint,
        campaign_memory_profiles=memory_profiles,
    )
    _atomic_write_json(output / "matrix_manifest.json", matrix.to_dict())
    return matrix


__all__ = [
    "CANONICAL_IOHUNTER_PROCESSED_ROOT",
    "IOHUNTER_EVALUATION_SCOPE",
    "IOHUNTER_OFFICIAL_SEEDS",
    "IOHUNTER_PREFLIGHT_CAMPAIGNS",
    "IOHUNTER_PREFLIGHT_SCHEMA_VERSION",
    "IOHUNTER_PREFLIGHT_STATUS",
    "IOHunterPreflightMatrix",
    "IOHunterPreflightRow",
    "preflight_iohunter_matrix",
    "validate_iohunter_preflight_output_dir",
]
