from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.config import PROJECT_ROOT
from app.core.analysis.coordination_runtime.group_label_cases import CoordinationGroupLabelCase
from app.services.coordination_group_label_case_service import (
    persist_coordination_group_label_cases,
    record_coordination_group_label_review,
)


def _label_case() -> dict:
    return CoordinationGroupLabelCase(
        case_id="coordination-group-case-test",
        event_id="event-1",
        snapshot_id="snapshot-1",
        source_batch_id="batch-1",
        cluster_id="cluster-1",
        member_account_ids=("weibo:u1", "xiaohongshu:u2"),
        evidence_matrix={
            "evidence_refs": ["e1", "e2"],
            "relation_types": ["url_share"],
            "window_ids": ["w1"],
            "evidence_kind_counts": {"url_share": 2},
        },
        characterization={
            "authenticity": {"source": "account_profile_bot_detection_join", "status": "pending_join"},
            "harmfulness": {"source": "coordination_detection", "status": "pending_review"},
            "orchestration": {"source": "coordination_discovery_metrics", "metrics": {"density": 1.0}},
            "time_variance": {"source": "coordination_discovery_lineage", "window_ids": ["w1"]},
        },
        model_output={
            "decision": "harmful_coordination",
            "harmful_probability": 0.82,
            "model_role": "primary_socgfm_cross_attention",
            "inference_mode": "precomputed_member_probability_cluster_aggregation",
            "claim_scope": "account_level_io_membership_to_cluster_proxy",
            "online_neural_forward": False,
            "member_probability_coverage": 1.0,
        },
    ).to_dict()


def _output_root(tmp_path: Path) -> Path:
    return PROJECT_ROOT / "output" / "pytest-coordination-group-label-cases" / hashlib.sha256(
        str(tmp_path).encode("utf-8")
    ).hexdigest()[:16]


def test_persist_coordination_group_label_cases_writes_jsonl_under_g_drive(tmp_path: Path):
    root = _output_root(tmp_path)
    case = _label_case()

    result = persist_coordination_group_label_cases(
        [case],
        snapshot_id="snapshot-1",
        source_batch_id="batch-1",
        root=root,
    )

    output_path = Path(result["output_path"])
    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]

    assert output_path.drive.upper() == "G:"
    assert result["case_count"] == 1
    assert rows[0]["review_status"] == "pending"
    assert rows[0]["cluster_harm_label"] is None
    assert rows[0]["member_account_ids"] == ["weibo:u1", "xiaohongshu:u2"]
    assert rows[0]["characterization"]["orchestration"]["source"] == "coordination_discovery_metrics"
    assert rows[0]["model_output"]["online_neural_forward"] is False


def test_record_coordination_group_label_review_appends_labeled_case(tmp_path: Path):
    root = _output_root(tmp_path)

    result = record_coordination_group_label_review(
        case=_label_case(),
        cluster_harm_label="benign_coordination",
        reviewer_id=7,
        reviewer_notes="人工核验为合法集中传播",
        root=root,
    )
    row = json.loads(Path(result["output_path"]).read_text(encoding="utf-8").splitlines()[0])

    assert result["review_status"] == "labeled"
    assert row["review_status"] == "labeled"
    assert row["cluster_harm_label"] == "benign_coordination"
    assert row["review"]["reviewer_id"] == 7
    assert row["review"]["reviewer_notes"] == "人工核验为合法集中传播"


def test_record_coordination_group_label_review_rejects_invalid_label(tmp_path: Path):
    with pytest.raises(ValueError, match="cluster_harm_label"):
        record_coordination_group_label_review(
            case=_label_case(),
            cluster_harm_label="abstain",
            reviewer_id=7,
            root=_output_root(tmp_path),
        )
