from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ALLOWED_CLUSTER_HARM_LABELS = frozenset({"harmful_coordination", "benign_coordination"})
ALLOWED_REVIEW_STATUSES = frozenset({"pending", "labeled", "adjudicated"})
GROUP_LABEL_CASE_SCHEMA_VERSION = "cogguard.coordination-group-label-case/v1"


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _jsonable(value: Any) -> Any:
    json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
    return value


def _stable_hash(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class CoordinationGroupLabelCase:
    case_id: str
    event_id: str
    snapshot_id: str
    source_batch_id: str
    cluster_id: str
    member_account_ids: tuple[str, ...]
    evidence_matrix: Mapping[str, Any]
    characterization: Mapping[str, Any]
    model_output: Mapping[str, Any]
    review_status: str = "pending"
    cluster_harm_label: str | None = None
    schema_version: str = GROUP_LABEL_CASE_SCHEMA_VERSION
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if self.schema_version != GROUP_LABEL_CASE_SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        for field_name in ("case_id", "event_id", "snapshot_id", "source_batch_id", "cluster_id"):
            object.__setattr__(self, field_name, _required_text(getattr(self, field_name), field_name))
        members = tuple(sorted(_required_text(member, "member_account_id") for member in self.member_account_ids))
        if not members:
            raise ValueError("member_account_ids must not be empty")
        object.__setattr__(self, "member_account_ids", members)
        if self.review_status not in ALLOWED_REVIEW_STATUSES:
            raise ValueError("review_status is invalid")
        if self.cluster_harm_label is not None and self.cluster_harm_label not in ALLOWED_CLUSTER_HARM_LABELS:
            raise ValueError("cluster_harm_label is invalid")
        _jsonable(self.evidence_matrix)
        _jsonable(self.characterization)
        _jsonable(self.model_output)
        _required_text(self.created_at, "created_at")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "case_id": self.case_id,
            "event_id": self.event_id,
            "snapshot_id": self.snapshot_id,
            "source_batch_id": self.source_batch_id,
            "cluster_id": self.cluster_id,
            "member_account_ids": list(self.member_account_ids),
            "evidence_matrix": dict(self.evidence_matrix),
            "characterization": dict(self.characterization),
            "model_output": dict(self.model_output),
            "review_status": self.review_status,
            "cluster_harm_label": self.cluster_harm_label,
            "created_at": self.created_at,
        }


def build_coordination_group_label_cases(
    *,
    snapshot: Any,
    discovery_batch: Any,
    detection_payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    verdicts = {
        str(verdict.get("cluster_id")): verdict
        for verdict in detection_payload.get("verdicts", [])
        if isinstance(verdict, Mapping) and verdict.get("cluster_id") is not None
    }
    cases: list[dict[str, Any]] = []
    for cluster in discovery_batch.candidate_clusters:
        cluster_payload = cluster.to_dict()
        cluster_id = str(cluster.cluster_id)
        verdict = dict(verdicts.get(cluster_id, {}))
        model_output = {
            "decision": verdict.get("decision"),
            "harmful_probability": verdict.get("harmful_probability"),
            "model_version": verdict.get("model_version") or detection_payload.get("model_version"),
            "model_role": verdict.get("model_role") or detection_payload.get("model_role"),
            "artifact_hash": verdict.get("artifact_hash") or detection_payload.get("model_artifact_hash"),
            "inference_mode": verdict.get("inference_mode") or detection_payload.get("inference_mode"),
            "claim_scope": verdict.get("claim_scope") or detection_payload.get("claim_scope"),
            "online_neural_forward": verdict.get("online_neural_forward", detection_payload.get("online_neural_forward")),
            "member_probability_coverage": verdict.get("member_probability_coverage"),
        }
        identity = {
            "snapshot_id": snapshot.snapshot_id,
            "source_batch_id": discovery_batch.batch_id,
            "cluster_id": cluster_id,
            "members": list(cluster.member_account_ids),
        }
        case = CoordinationGroupLabelCase(
            case_id="coordination-group-case-" + hashlib.sha256(
                json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest()[:24],
            event_id=str(snapshot.event_id),
            snapshot_id=str(snapshot.snapshot_id),
            source_batch_id=str(discovery_batch.batch_id),
            cluster_id=cluster_id,
            member_account_ids=tuple(cluster.member_account_ids),
            evidence_matrix={
                "evidence_refs": list(cluster.evidence_refs),
                "relation_types": list(cluster.relation_types),
                "window_ids": list(cluster.window_ids),
                "evidence_kind_counts": dict(cluster.evidence_kind_counts),
                "cluster_fingerprint": _stable_hash(cluster_payload),
            },
            characterization={
                "authenticity": {"source": "account_profile_bot_detection_join", "status": "pending_join"},
                "harmfulness": {"source": "coordination_detection", "status": "pending_review"},
                "orchestration": {
                    "source": "coordination_discovery_metrics",
                    "metrics": dict(cluster.coordination_metrics.to_dict()),
                },
                "time_variance": {
                    "source": "coordination_discovery_lineage",
                    "window_ids": list(cluster.window_ids),
                },
            },
            model_output=model_output,
        )
        cases.append(case.to_dict())
    return cases


def write_coordination_group_label_cases(cases: list[Mapping[str, Any]], output_path: str | Path) -> Path:
    path = Path(output_path).resolve()
    if path.drive.upper() != "G:":
        raise ValueError("coordination group label cases must be written under the G: drive")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for case in cases:
            handle.write(json.dumps(dict(case), ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
    return path


__all__ = [
    "ALLOWED_CLUSTER_HARM_LABELS",
    "ALLOWED_REVIEW_STATUSES",
    "GROUP_LABEL_CASE_SCHEMA_VERSION",
    "CoordinationGroupLabelCase",
    "build_coordination_group_label_cases",
    "write_coordination_group_label_cases",
]
