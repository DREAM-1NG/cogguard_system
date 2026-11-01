"""Review Gate labelled dataset contract.

The Gate Suite is an offline evaluation harness. This module keeps its labelled
inputs explicit so runtime risk reports never invent gold labels from their own
predictions.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any


DATASET_CONTRACT_VERSION = "review-gate-dataset-v1"

REQUIRED_METADATA_FIELDS = [
    "dataset_id",
    "version",
    "source",
    "label_policy",
    "control_set_notes",
]

OPTIONAL_METADATA_FIELDS = [
    "split",
    "annotator_protocol",
    "label_version",
    "leakage_policy",
    "threshold_policy",
]

FORMAL_ACCEPTANCE_METADATA_FIELDS = [
    "control_set_notes",
    "split",
    "leakage_policy",
    "threshold_policy",
]

REQUIRED_GATE_LAYERS = [
    "post_gate",
    "user_gate",
    "community_gate",
]

GATE_DATASET_USAGE_POLICY = {
    "uses_gold_for_training": False,
    "runtime_gold_generation": False,
    "default_persistence": False,
    "online_llm_or_rag_required": False,
    "description": (
        "Review Gate Dataset is an explicit labelled gold/control contract for offline "
        "evaluation only. It must not be inferred from runtime predictions and must "
        "not update model weights, thresholds, or calibration state."
    ),
}

GATE_DATASET_LEAKAGE_POLICY = {
    "no_runtime_derived_gold": True,
    "no_training_or_calibration_from_gate_gold": True,
    "control_set_required_for_formal_acceptance": True,
    "same_event_runtime_outputs_must_not_be_used_as_gold": True,
    "description": (
        "Formal acceptance requires labels prepared outside the current runtime "
        "report path, preferably with same-topic, same-window, and same-platform "
        "or comparable control samples."
    ),
}

Review_GATE_DATASET_CONTRACT = {
    "contract_version": DATASET_CONTRACT_VERSION,
    "artifact_type": "gate_dataset_contract",
    "purpose": "Explicit gold/control set contract for Review Post/User/Community Gate Suite.",
    "request_field": "gate_dataset",
    "entrypoints": {
        "evaluate": "POST /api/v1/risk/review/gate-suite",
        "contract": "GET /api/v1/risk/review/gate-dataset/contract",
        "validate": "POST /api/v1/risk/review/gate-dataset/validate",
    },
    "required_metadata_fields": REQUIRED_METADATA_FIELDS,
    "optional_metadata_fields": OPTIONAL_METADATA_FIELDS,
    "top_level_fields": {
        "contract_version": {
            "type": "string",
            "required": False,
            "default": DATASET_CONTRACT_VERSION,
            "description": "Stable contract version used by external evaluation scripts.",
        },
        "metadata": {
            "type": "object",
            "required": True,
            "required_fields": REQUIRED_METADATA_FIELDS,
            "optional_fields": OPTIONAL_METADATA_FIELDS,
            "description": "Dataset provenance, label policy, and control-set notes.",
        },
        "post_cases": {
            "type": "array<object>",
            "required_for_layer": "post_gate",
            "description": "Fixed post-level labelled cases with posts, propagation context, and gold labels.",
        },
        "user_gold": {
            "type": "object | array<object>",
            "required_for_layer": "user_gate",
            "description": "Fixed account-level gold labels keyed by account_id or provided as rows.",
        },
        "community_gold": {
            "type": "object | array<object>",
            "required_for_layer": "community_gate",
            "description": "Fixed community-level gold labels keyed by community_id or provided as rows.",
        },
        "thresholds": {
            "type": "object",
            "required": False,
            "description": "Optional per-layer acceptance thresholds. They are read-only evaluation criteria.",
        },
        "prefer_embeddings": {
            "type": "boolean",
            "required": False,
            "description": "Optional post scorer preference; defaults to the offline-safe deterministic path.",
        },
    },
    "layer_contracts": {
        "post_gate": {
            "input_field": "post_cases",
            "minimum_usable_shape": {
                "case_id": "string",
                "posts": "array<object>",
                "propagation": "object",
                "gold": {
                    "post_id": {
                        "claim_id": "string",
                        "stance": "support|deny|query|neutral|uncertain|...",
                        "harm_label": "harmful|non_harmful|uncertain",
                        "harm_types": "array<string>",
                        "must_have_modalities": "array<string>",
                        "evidence_required": "boolean",
                    }
                },
            },
            "metrics": [
                "claim_link_accuracy",
                "stance_accuracy",
                "harm_label_accuracy",
                "harm_type_micro_precision",
                "harm_type_micro_recall",
                "harm_type_micro_f1",
                "evidence_presence_rate",
                "abstain_rate",
                "evaluated_posts",
            ],
            "default_thresholds": {
                "claim_link_accuracy": 0.7,
                "stance_accuracy": 0.7,
                "harm_label_accuracy": 0.7,
                "harm_type_micro_f1": 0.5,
                "evidence_presence_rate": 0.9,
            },
        },
        "user_gate": {
            "input_field": "user_gold",
            "minimum_usable_shape": {
                "account_id": "string",
                "harmful": "boolean",
                "persistence_label": "low|medium|high",
                "trajectory": "string",
                "roles": "array<string>",
                "needs_representative_evidence": "boolean",
            },
            "metrics": [
                "harmful_flag_accuracy",
                "persistence_label_accuracy",
                "trajectory_accuracy",
                "role_micro_precision",
                "role_micro_recall",
                "role_micro_f1",
                "representative_evidence_rate",
                "runtime_needs_review_rate",
                "evaluated_accounts",
            ],
            "default_thresholds": {
                "harmful_flag_accuracy": 0.7,
                "persistence_label_accuracy": 0.7,
                "trajectory_accuracy": 0.6,
                "role_micro_f1": 0.5,
                "representative_evidence_rate": 0.8,
            },
        },
        "community_gate": {
            "input_field": "community_gold",
            "minimum_usable_shape": {
                "community_id": "string",
                "collective_harm": "boolean",
                "amplification": "boolean",
                "harm_types": "array<string>",
                "roles": "array<string>",
                "claims": "array<string>",
                "key_accounts": "array<string>",
                "needs_claim_coverage": "boolean",
                "needs_key_account_evidence": "boolean",
            },
            "metrics": [
                "collective_harm_accuracy",
                "amplification_label_accuracy",
                "harm_type_micro_precision",
                "harm_type_micro_recall",
                "harm_type_micro_f1",
                "role_micro_precision",
                "role_micro_recall",
                "role_micro_f1",
                "claim_coverage_rate",
                "key_account_evidence_rate",
                "runtime_needs_review_rate",
                "graph_export_ready_rate",
                "evaluated_communities",
            ],
            "default_thresholds": {
                "collective_harm_accuracy": 0.7,
                "amplification_label_accuracy": 0.7,
                "harm_type_micro_f1": 0.5,
                "role_micro_f1": 0.5,
                "claim_coverage_rate": 0.7,
                "key_account_evidence_rate": 0.8,
            },
        },
    },
    "usage_policy": GATE_DATASET_USAGE_POLICY,
    "leakage_policy": GATE_DATASET_LEAKAGE_POLICY,
    "persistence_policy": {
        "default_persistence": False,
        "reason": "Gate Suite outputs may include gold labels, failed samples, and review evidence.",
    },
    "manifest_policy": {
        "artifact_type": "gate_dataset_manifest",
        "contains_gold_payload": False,
        "fingerprint_algorithm": "sha256-canonical-json",
        "description": (
            "A report-safe reproducibility manifest may expose dataset metadata, "
            "layer coverage, counts, threshold layers, and stable fingerprints, "
            "but never copies the raw labelled examples."
        ),
    },
    "readiness_policy": {
        "valid_for_execution": (
            "At least one layer has usable labelled inputs and required "
            "metadata is present; this is enough to run a layer gate."
        ),
        "formal_acceptance_ready": (
            "All three Review layers are covered and the dataset declares control "
            "notes, split, leakage policy, and threshold policy. This is still "
            "an offline evaluation contract, not model training evidence."
        ),
        "formal_acceptance_metadata_fields": FORMAL_ACCEPTANCE_METADATA_FIELDS,
        "required_gate_layers": REQUIRED_GATE_LAYERS,
    },
    "validation_warning_codes": {
        "dataset_missing_usable_layers": "Dataset was provided but no layer contains usable labelled inputs.",
        "metadata_ignored_non_object": "metadata exists but is not an object.",
        "metadata_missing_<field>": "A recommended provenance field is missing or blank.",
        "readiness_dataset_not_provided": "No explicit Gate Dataset was provided.",
        "readiness_missing_required_metadata": "One or more required metadata fields are missing.",
        "readiness_missing_control_set_notes": "Formal acceptance needs explicit control-set notes.",
        "readiness_missing_split": "Formal acceptance needs an explicit train/dev/eval or evaluation split declaration.",
        "readiness_missing_leakage_policy": "Formal acceptance needs an explicit leakage-isolation policy.",
        "readiness_missing_threshold_policy": "Formal acceptance needs a threshold-freezing policy.",
        "readiness_missing_full_layer_coverage": "Formal Review acceptance needs post, user, and community layer gold coverage.",
        "readiness_contract_warnings_present": "Formal Review acceptance is blocked while contract-shape warnings remain.",
        "post_cases_ignored_non_list": "post_cases exists but is not a list.",
        "post_cases_dropped_non_object_items": "post_cases contains non-object rows.",
        "post_cases_<index>_missing_<field>": "A post case is missing a minimum field.",
        "post_cases_<index>_missing_gold": "A post case has no usable gold labels.",
        "user_gold_ignored_invalid_type": "user_gold is neither an object nor a list.",
        "user_gold_missing_ids": "At least one user gold row is missing account_id.",
        "community_gold_ignored_invalid_type": "community_gold is neither an object nor a list.",
        "community_gold_missing_ids": "At least one community gold row is missing community_id.",
        "thresholds_<layer>_ignored_non_object": "A threshold layer exists but is not an object.",
        "thresholds_<layer>_<metric>_ignored_non_numeric": "A threshold value is not numeric.",
        "prefer_embeddings_ignored_non_bool": "prefer_embeddings exists but is not boolean.",
    },
    "example_skeleton": {
        "contract_version": DATASET_CONTRACT_VERSION,
        "metadata": {
            "dataset_id": "review-example-eval",
            "version": "v1",
            "source": "expert_labelled_project_sample",
            "label_policy": "independent expert labels; no runtime-derived gold",
            "control_set_notes": "same-topic, same-window benign/control communities included",
            "split": "eval",
            "annotator_protocol": "two-pass expert annotation with disagreement resolution",
            "label_version": "review-harm-taxonomy-v1",
            "leakage_policy": "labels prepared outside the current runtime report path",
            "threshold_policy": "thresholds fixed before evaluation; gate gold is never used for calibration",
        },
        "prefer_embeddings": False,
        "post_cases": [
            {
                "case_id": "event_a_posts",
                "posts": [],
                "propagation": {},
                "gold": {
                    "post_id": {
                        "claim_id": "claim_1",
                        "stance": "support",
                        "harm_label": "harmful",
                        "harm_types": ["misinformation"],
                        "must_have_modalities": ["text"],
                        "evidence_required": True,
                    }
                },
            }
        ],
        "user_gold": {
            "account_id": {
                "harmful": True,
                "persistence_label": "high",
                "trajectory": "stable",
                "roles": ["amplifier"],
                "needs_representative_evidence": True,
            }
        },
        "community_gold": {
            "community_id": {
                "collective_harm": True,
                "amplification": True,
                "harm_types": ["misinformation"],
                "roles": ["amplifier"],
                "claims": ["claim_1"],
                "key_accounts": ["account_id"],
                "needs_claim_coverage": True,
                "needs_key_account_evidence": True,
            }
        },
        "thresholds": {
            "post": {"stance_accuracy": 0.7},
            "user": {"role_micro_f1": 0.5},
            "community": {"claim_coverage_rate": 0.7},
        },
    },
}


def get_gate_dataset_contract_spec() -> dict[str, Any]:
    """Return the machine-readable Review Gate Dataset contract."""
    return deepcopy(Review_GATE_DATASET_CONTRACT)


def normalize_gate_dataset(dataset: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize an optional Review Gate dataset into Suite-ready inputs.

    Accepted dataset shape:

    {
        "metadata": {
            "dataset_id": "...",
            "version": "...",
            "source": "...",
            "label_policy": "...",
            "control_set_notes": "..."
        },
        "post_cases": [...],
        "user_gold": {...} | [...],
        "community_gold": {...} | [...],
        "thresholds": {"post": {...}, "user": {...}, "community": {...}},
        "prefer_embeddings": false
    }
    """
    if not isinstance(dataset, dict):
        return _empty_contract(provided=False)

    warnings: list[str] = []
    metadata = dataset.get("metadata") if isinstance(dataset.get("metadata"), dict) else {}
    if dataset.get("metadata") is not None and not isinstance(dataset.get("metadata"), dict):
        warnings.append("metadata_ignored_non_object")

    post_cases = _optional_list(dataset.get("post_cases"), "post_cases", warnings)
    user_gold = _optional_gold(dataset.get("user_gold"), "user_gold", warnings)
    community_gold = _optional_gold(dataset.get("community_gold"), "community_gold", warnings)
    thresholds = _optional_thresholds(dataset.get("thresholds"), warnings)
    prefer_embeddings = dataset.get("prefer_embeddings")

    if prefer_embeddings is not None and not isinstance(prefer_embeddings, bool):
        warnings.append("prefer_embeddings_ignored_non_bool")
        prefer_embeddings = None

    layer_coverage = {
        "post_gate": bool(post_cases),
        "user_gate": bool(user_gold),
        "community_gate": bool(community_gold),
    }
    warnings.extend(_strict_contract_warnings(dataset, post_cases, user_gold, community_gold))
    normalized_metadata = _normalize_metadata(metadata)
    readiness = _evaluate_readiness(
        provided=True,
        metadata=normalized_metadata,
        layer_coverage=layer_coverage,
        validation_warnings=warnings,
    )
    warnings.extend(readiness["readiness_warnings"])
    if not any(layer_coverage.values()):
        warnings.append("dataset_missing_usable_layers")
    warnings = _unique_sorted(warnings)

    return {
        "provided": True,
        "contract_version": _text(dataset.get("contract_version")) or DATASET_CONTRACT_VERSION,
        "metadata": normalized_metadata,
        "post_cases": post_cases,
        "user_gold": user_gold,
        "community_gold": community_gold,
        "thresholds": thresholds,
        "prefer_embeddings": prefer_embeddings,
        "evaluation_readiness": readiness,
        "validation": {
            "valid": any(layer_coverage.values()),
            "warnings": warnings,
            "layer_coverage": layer_coverage,
        },
    }


def gate_dataset_contract_view(normalized: dict[str, Any]) -> dict[str, Any]:
    """Return a report-safe summary without copying full labelled examples."""
    metadata = normalized.get("metadata") if isinstance(normalized.get("metadata"), dict) else {}
    validation = normalized.get("validation") if isinstance(normalized.get("validation"), dict) else {}
    readiness = (
        normalized.get("evaluation_readiness")
        if isinstance(normalized.get("evaluation_readiness"), dict)
        else _evaluate_readiness(
            provided=bool(normalized.get("provided")),
            metadata=metadata,
            layer_coverage=validation.get("layer_coverage") or {},
            validation_warnings=_as_list(validation.get("warnings")),
        )
    )
    return {
        "provided": bool(normalized.get("provided")),
        "contract_version": _text(normalized.get("contract_version")) or DATASET_CONTRACT_VERSION,
        "metadata": metadata,
        "validation": validation,
        "evaluation_readiness": readiness,
        "counts": {
            "post_cases": len(_as_list(normalized.get("post_cases"))),
            "user_gold": _gold_count(normalized.get("user_gold")),
            "community_gold": _gold_count(normalized.get("community_gold")),
        },
        "threshold_layers": sorted(
            (normalized.get("thresholds") or {}).keys()
            if isinstance(normalized.get("thresholds"), dict)
            else []
        ),
        "usage_policy": GATE_DATASET_USAGE_POLICY,
        "leakage_policy": GATE_DATASET_LEAKAGE_POLICY,
        "manifest": build_gate_dataset_manifest(normalized),
    }


def build_gate_dataset_manifest(normalized: dict[str, Any]) -> dict[str, Any]:
    """Return a gold-safe manifest for reproducible offline Gate Suite runs."""
    metadata = normalized.get("metadata") if isinstance(normalized.get("metadata"), dict) else {}
    validation = normalized.get("validation") if isinstance(normalized.get("validation"), dict) else {}
    readiness = (
        normalized.get("evaluation_readiness")
        if isinstance(normalized.get("evaluation_readiness"), dict)
        else _evaluate_readiness(
            provided=bool(normalized.get("provided")),
            metadata=metadata,
            layer_coverage=validation.get("layer_coverage") or {},
            validation_warnings=_as_list(validation.get("warnings")),
        )
    )
    post_cases = _as_list(normalized.get("post_cases"))
    user_gold = normalized.get("user_gold")
    community_gold = normalized.get("community_gold")
    thresholds = normalized.get("thresholds") if isinstance(normalized.get("thresholds"), dict) else None
    manifest_subject = {
        "contract_version": _text(normalized.get("contract_version")) or DATASET_CONTRACT_VERSION,
        "metadata": metadata,
        "post_cases": post_cases,
        "user_gold": user_gold,
        "community_gold": community_gold,
        "thresholds": thresholds,
        "prefer_embeddings": normalized.get("prefer_embeddings"),
    }
    return {
        "artifact_type": "gate_dataset_manifest",
        "contract_version": DATASET_CONTRACT_VERSION,
        "contains_gold_payload": False,
        "fingerprint_algorithm": "sha256-canonical-json",
        "dataset_fingerprint": _fingerprint(manifest_subject),
        "layer_fingerprints": {
            "post_gate": _fingerprint(post_cases),
            "user_gate": _fingerprint(user_gold),
            "community_gate": _fingerprint(community_gold),
            "thresholds": _fingerprint(thresholds),
        },
        "metadata": metadata,
        "layer_coverage": validation.get("layer_coverage"),
        "evaluation_readiness": readiness,
        "counts": {
            "post_cases": len(post_cases),
            "user_gold": _gold_count(user_gold),
            "community_gold": _gold_count(community_gold),
        },
        "threshold_layers": sorted(thresholds.keys()) if isinstance(thresholds, dict) else [],
        "warning_count": len(_as_list(validation.get("warnings"))),
        "valid_for_execution": bool(validation.get("valid")),
        "formal_acceptance_ready": bool(readiness.get("formal_acceptance_ready")),
        "persistence": {
            "default_persistence": False,
            "reason": "Manifest is report-safe, but Gate Suite gold/control payloads remain non-persistent by default.",
        },
    }


def validate_gate_dataset_contract(dataset: dict[str, Any] | None) -> dict[str, Any]:
    """Return a machine-readable validation report for an external Gate Dataset."""
    normalized = normalize_gate_dataset(dataset)
    contract_view = gate_dataset_contract_view(normalized)
    validation = contract_view.get("validation") or {}
    warnings = sorted(set(_as_list(validation.get("warnings"))))
    readiness = contract_view.get("evaluation_readiness") or {}
    missing_metadata = [
        field
        for field in REQUIRED_METADATA_FIELDS
        if _text((normalized.get("metadata") or {}).get(field)) == "unspecified"
    ]
    return {
        "contract_version": DATASET_CONTRACT_VERSION,
        "valid": bool(validation.get("valid")) and not missing_metadata,
        "layer_coverage": validation.get("layer_coverage"),
        "warnings": warnings,
        "missing_metadata_fields": missing_metadata,
        "evaluation_readiness": readiness,
        "formal_acceptance_ready": bool(readiness.get("formal_acceptance_ready")),
        "readiness_warnings": readiness.get("readiness_warnings") or [],
        "counts": contract_view.get("counts"),
        "threshold_layers": contract_view.get("threshold_layers"),
        "usage_policy": GATE_DATASET_USAGE_POLICY,
        "leakage_policy": GATE_DATASET_LEAKAGE_POLICY,
        "manifest": contract_view.get("manifest"),
        "normalized_contract": contract_view,
    }


def _empty_contract(*, provided: bool) -> dict[str, Any]:
    return {
        "provided": provided,
        "contract_version": DATASET_CONTRACT_VERSION,
        "metadata": _normalize_metadata({}),
        "post_cases": None,
        "user_gold": None,
        "community_gold": None,
        "thresholds": None,
        "prefer_embeddings": None,
        "evaluation_readiness": _evaluate_readiness(
            provided=provided,
            metadata=_normalize_metadata({}),
            layer_coverage={
                "post_gate": False,
                "user_gate": False,
                "community_gate": False,
            },
            validation_warnings=[] if not provided else ["dataset_missing_usable_layers"],
        ),
        "validation": {
            "valid": False,
            "warnings": [] if not provided else ["dataset_missing_usable_layers"],
            "layer_coverage": {
                "post_gate": False,
                "user_gate": False,
                "community_gate": False,
            },
        },
    }


def _normalize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "dataset_id": _text(metadata.get("dataset_id")) or "unspecified",
        "version": _text(metadata.get("version")) or "unspecified",
        "source": _text(metadata.get("source")) or "unspecified",
        "label_policy": _text(metadata.get("label_policy")) or "unspecified",
        "control_set_notes": _text(metadata.get("control_set_notes")) or "unspecified",
    }
    for field in OPTIONAL_METADATA_FIELDS:
        value = _text(metadata.get(field))
        if value:
            normalized[field] = value
    return normalized


def _optional_list(value: Any, field_name: str, warnings: list[str]) -> list[dict[str, Any]] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        warnings.append(f"{field_name}_ignored_non_list")
        return None
    rows = [row for row in value if isinstance(row, dict)]
    if len(rows) != len(value):
        warnings.append(f"{field_name}_dropped_non_object_items")
    return rows or None


def _optional_gold(value: Any, field_name: str, warnings: list[str]) -> dict[str, Any] | list[dict[str, Any]] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value or None
    if isinstance(value, list):
        rows = [row for row in value if isinstance(row, dict)]
        if len(rows) != len(value):
            warnings.append(f"{field_name}_dropped_non_object_items")
        return rows or None
    warnings.append(f"{field_name}_ignored_invalid_type")
    return None


def _optional_thresholds(value: Any, warnings: list[str]) -> dict[str, dict[str, float]] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        warnings.append("thresholds_ignored_non_object")
        return None

    normalized: dict[str, dict[str, float]] = {}
    for layer in ("post", "user", "community"):
        raw_layer = value.get(layer)
        if raw_layer is None:
            continue
        if not isinstance(raw_layer, dict):
            warnings.append(f"thresholds_{layer}_ignored_non_object")
            continue
        layer_thresholds: dict[str, float] = {}
        for metric, threshold in raw_layer.items():
            try:
                layer_thresholds[_text(metric)] = float(threshold)
            except (TypeError, ValueError):
                warnings.append(f"thresholds_{layer}_{metric}_ignored_non_numeric")
        if layer_thresholds:
            normalized[layer] = layer_thresholds
    return normalized or None


def _strict_contract_warnings(
    dataset: dict[str, Any],
    post_cases: list[dict[str, Any]] | None,
    user_gold: dict[str, Any] | list[dict[str, Any]] | None,
    community_gold: dict[str, Any] | list[dict[str, Any]] | None,
) -> list[str]:
    warnings: list[str] = []
    metadata = dataset.get("metadata") if isinstance(dataset.get("metadata"), dict) else {}
    for field in REQUIRED_METADATA_FIELDS:
        if not _text(metadata.get(field)):
            warnings.append(f"metadata_missing_{field}")

    warnings.extend(_post_case_contract_warnings(post_cases))
    warnings.extend(_gold_id_warnings(user_gold, "user_gold", "account_id"))
    warnings.extend(_gold_id_warnings(community_gold, "community_gold", "community_id"))
    return warnings


def _evaluate_readiness(
    *,
    provided: bool,
    metadata: dict[str, Any],
    layer_coverage: dict[str, Any],
    validation_warnings: list[Any],
) -> dict[str, Any]:
    missing_metadata = [
        field
        for field in REQUIRED_METADATA_FIELDS
        if not _metadata_has_value(metadata.get(field))
    ]
    readiness_warnings: list[str] = []
    if not provided:
        readiness_warnings.append("readiness_dataset_not_provided")
    if missing_metadata:
        readiness_warnings.append("readiness_missing_required_metadata")

    for field in FORMAL_ACCEPTANCE_METADATA_FIELDS:
        if not _metadata_has_value(metadata.get(field)):
            readiness_warnings.append(f"readiness_missing_{field}")

    missing_layers = [
        layer
        for layer in REQUIRED_GATE_LAYERS
        if not bool(layer_coverage.get(layer))
    ]
    if missing_layers:
        readiness_warnings.append("readiness_missing_full_layer_coverage")
    shape_warnings = [
        str(warning)
        for warning in validation_warnings
        if str(warning) and not str(warning).startswith("readiness_")
    ]
    if shape_warnings:
        readiness_warnings.append("readiness_contract_warnings_present")

    has_required_metadata = provided and not missing_metadata
    has_full_layer_coverage = provided and not missing_layers
    has_control_notes = _metadata_has_value(metadata.get("control_set_notes"))
    has_split = _metadata_has_value(metadata.get("split"))
    has_leakage_policy = _metadata_has_value(metadata.get("leakage_policy"))
    has_threshold_policy = _metadata_has_value(metadata.get("threshold_policy"))
    formal_acceptance_ready = all(
        [
            has_required_metadata,
            has_control_notes,
            has_split,
            has_leakage_policy,
            has_threshold_policy,
            has_full_layer_coverage,
            not shape_warnings,
        ]
    )
    return {
        "has_required_metadata": has_required_metadata,
        "has_control_notes": has_control_notes,
        "has_split": has_split,
        "has_leakage_policy": has_leakage_policy,
        "has_threshold_policy": has_threshold_policy,
        "has_full_layer_coverage": has_full_layer_coverage,
        "covered_layers": sorted(
            layer
            for layer in REQUIRED_GATE_LAYERS
            if bool(layer_coverage.get(layer))
        ),
        "missing_layers": missing_layers,
        "missing_metadata_fields": missing_metadata,
        "formal_acceptance_ready": formal_acceptance_ready,
        "readiness_warnings": _unique_sorted(readiness_warnings),
        "acceptance_note": (
            "ready_for_formal_offline_acceptance"
            if formal_acceptance_ready
            else "executable_gate_dataset_but_not_formal_acceptance_ready"
        ),
    }


def _post_case_contract_warnings(post_cases: list[dict[str, Any]] | None) -> list[str]:
    warnings: list[str] = []
    for index, case in enumerate(post_cases or []):
        for field in ("case_id", "posts", "gold"):
            if field not in case:
                warnings.append(f"post_cases_{index}_missing_{field}")
        if "posts" in case and not isinstance(case.get("posts"), list):
            warnings.append(f"post_cases_{index}_posts_not_list")
        gold = case.get("gold", case.get("labels"))
        if not _gold_rows(gold):
            warnings.append(f"post_cases_{index}_missing_gold")
    return warnings


def _gold_id_warnings(
    gold: dict[str, Any] | list[dict[str, Any]] | None,
    field_name: str,
    id_field: str,
) -> list[str]:
    if not gold:
        return []
    missing_ids = 0
    if isinstance(gold, dict):
        missing_ids = sum(1 for key, value in gold.items() if not _text(key) or not isinstance(value, dict))
    elif isinstance(gold, list):
        missing_ids = sum(1 for row in gold if not isinstance(row, dict) or not _text(row.get(id_field)))
    if missing_ids:
        return [f"{field_name}_missing_ids"]
    return []


def _gold_rows(raw_gold: Any) -> list[dict[str, Any]]:
    if isinstance(raw_gold, dict):
        return [value for value in raw_gold.values() if isinstance(value, dict)]
    if isinstance(raw_gold, list):
        return [row for row in raw_gold if isinstance(row, dict)]
    return []


def _gold_count(value: Any) -> int:
    if isinstance(value, dict):
        return len(value)
    if isinstance(value, list):
        return len(value)
    return 0


def _fingerprint(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _unique_sorted(values: list[Any]) -> list[str]:
    return sorted({str(value) for value in values if str(value)})


def _metadata_has_value(value: Any) -> bool:
    text = _text(value)
    return bool(text) and text != "unspecified"


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()
