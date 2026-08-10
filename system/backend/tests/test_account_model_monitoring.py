from __future__ import annotations

import asyncio
import json
from datetime import datetime

import pytest

from app.core.account_model_monitoring import (
    MonitoringThresholds,
    population_stability_index,
    summarize_account_predictions,
)
from app.models.account_labeling import (
    AccountDetectionModelActivation,
    AccountDetectionModelVersion,
    AccountMonitorSnapshot,
    AccountPredictionAudit,
)
from app.services.account_model_monitoring_service import (
    create_account_monitor_snapshot,
    list_account_monitor_snapshots,
)
from app.utils.exceptions import AppException


class _Result:
    def __init__(self, *, scalar=None, rows=()):
        self.scalar = scalar
        self.rows = list(rows)

    def scalar_one_or_none(self):
        return self.scalar

    def scalars(self):
        return self

    def all(self):
        return self.rows


class _MonitoringSession:
    def __init__(self, *, activation=None, model=None, current_rows=(), reference_rows=(), snapshots=()):
        self.activation = activation
        self.model = model
        self.current_rows = list(current_rows)
        self.reference_rows = list(reference_rows)
        self.snapshots = list(snapshots)
        self.added = []
        self.audit_queries = 0
        self.snapshot_missing_created_at_on_flush = False

    async def execute(self, statement):
        entity = statement.column_descriptions[0].get("entity")
        if entity is AccountDetectionModelActivation:
            return _Result(scalar=self.activation)
        if entity is AccountDetectionModelVersion:
            return _Result(scalar=self.model)
        if entity is AccountPredictionAudit:
            self.audit_queries += 1
            rows = self.current_rows if self.audit_queries == 1 else self.reference_rows
            return _Result(rows=rows)
        if entity is AccountMonitorSnapshot:
            return _Result(rows=self.snapshots)
        raise AssertionError(f"Unexpected entity: {entity}")

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        for value in self.added:
            if isinstance(value, AccountMonitorSnapshot) and value.created_at is None:
                self.snapshot_missing_created_at_on_flush = True
                value.created_at = datetime(2026, 8, 5, 12, 0, 0)


def test_prediction_monitor_reports_calibration_coverage_latency_and_false_positive_burden():
    summary = summarize_account_predictions(
        [
            {"probability": 0.9, "target": 1, "abstained": False, "latency_ms": 100.0, "hard_error": False},
            {"probability": 0.8, "target": 0, "abstained": False, "latency_ms": 200.0, "hard_error": False},
            {"probability": 0.4, "target": 0, "abstained": True, "latency_ms": 300.0, "hard_error": False},
        ],
        reference_probabilities=[0.1, 0.2, 0.4, 0.8, 0.9],
        thresholds=MonitoringThresholds(daily_prediction_volume=300, daily_review_capacity=100),
    )

    assert summary["prediction_count"] == 3
    assert summary["labeled_prediction_count"] == 3
    assert summary["coverage"] == pytest.approx(2 / 3)
    assert summary["false_positive_count"] == 1
    assert summary["estimated_daily_false_positives"] == 100
    assert summary["latency_ms"]["p95"] == pytest.approx(290.0)
    assert 0 <= summary["ece"] <= 1


def test_hard_error_budget_can_request_automatic_rollback_but_drift_cannot():
    hard_error = summarize_account_predictions(
        [
            {"probability": 0.5, "target": None, "abstained": True, "latency_ms": 50, "hard_error": True},
            {"probability": 0.5, "target": None, "abstained": True, "latency_ms": 50, "hard_error": False},
        ],
        thresholds=MonitoringThresholds(max_hard_error_rate=0.1),
    )
    assert hard_error["status"] == "hard_failure"
    assert hard_error["automatic_rollback_allowed"] is True

    drift = summarize_account_predictions(
        [
            {"probability": 0.99, "target": None, "abstained": False, "latency_ms": 50, "hard_error": False}
            for _ in range(10)
        ],
        reference_probabilities=[0.01] * 10,
        thresholds=MonitoringThresholds(max_population_stability_index=0.1),
    )
    assert drift["status"] == "drift_alert"
    assert drift["automatic_rollback_allowed"] is False


def test_hard_error_summary_keeps_bounded_reason_categories_without_raw_error_text():
    summary = summarize_account_predictions(
        [
            {
                "probability": 0.5,
                "target": None,
                "abstained": True,
                "latency_ms": 50,
                "hard_error": True,
                "hard_error_reason": "active_model_bundle_invalid",
            },
            {
                "probability": 0.5,
                "target": None,
                "abstained": True,
                "latency_ms": 50,
                "hard_error": True,
                "hard_error_reason": "database password in raw exception text",
            },
        ],
        thresholds=MonitoringThresholds(max_hard_error_rate=0.1),
    )

    assert summary["hard_error_reason_counts"] == {
        "active_model_bundle_invalid": 1,
        "other_runtime_failure": 1,
    }


def test_population_stability_index_requires_probabilities_in_unit_interval():
    assert population_stability_index([0.1, 0.9], [0.1, 0.9]) == pytest.approx(0.0)
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        population_stability_index([1.1], [0.5])


def test_snapshot_rejects_summary_without_a_pointer_bound_model():
    session = _MonitoringSession()
    with pytest.raises(AppException, match="active model pointer"):
        asyncio.run(
            create_account_monitor_snapshot(
                session,
                window_started_at=datetime(2026, 8, 5, 10, 0, 0),
                window_finished_at=datetime(2026, 8, 5, 11, 0, 0),
            )
        )
    assert session.added == []


def test_snapshot_persists_model_identity_from_the_active_pointer():
    artifact_hash = "a" * 64
    activation = AccountDetectionModelActivation(
        model_family="chinese_account_detection",
        model_version="detector-20260805",
        pointer_revision=7,
    )
    model = AccountDetectionModelVersion(
        model_version="detector-20260805",
        dataset_version_id="dataset-1",
        artifact_uri="artifacts/detector-20260805",
        artifact_hash=artifact_hash,
    )
    current = AccountPredictionAudit(
        audit_id="audit-current",
        case_id="case-1",
        account_id="account-1",
        platform="weibo",
        family="chinese_account_detection",
        model_version="detector-20260805",
        pointer_revision=7,
        input_fingerprint="b" * 64,
        prediction_json=json.dumps({"calibrated_probability": 0.9, "latency_ms": 12.0}),
    )
    reference = AccountPredictionAudit(
        audit_id="audit-reference",
        case_id="case-0",
        account_id="account-0",
        platform="weibo",
        family="chinese_account_detection",
        model_version="detector-20260805",
        pointer_revision=7,
        input_fingerprint="c" * 64,
        prediction_json=json.dumps({"calibrated_probability": 0.2, "latency_ms": 10.0}),
    )
    session = _MonitoringSession(
        activation=activation,
        model=model,
        current_rows=[current],
        reference_rows=[reference],
    )

    snapshot = asyncio.run(
        create_account_monitor_snapshot(
            session,
            window_started_at=datetime(2026, 8, 5, 10, 0, 0),
            window_finished_at=datetime(2026, 8, 5, 11, 0, 0),
        )
    )

    persisted = session.added[0]
    assert isinstance(persisted, AccountMonitorSnapshot)
    assert persisted.model_version == "detector-20260805"
    assert persisted.pointer_revision == 7
    assert session.snapshot_missing_created_at_on_flush is False
    assert snapshot["created_at"] is not None
    assert snapshot["artifact_hash"] == artifact_hash
    assert snapshot["metrics"]["model_identity"] == {
        "family": "chinese_account_detection",
        "model_version": "detector-20260805",
        "artifact_hash": artifact_hash,
        "pointer_revision": 7,
    }


def test_snapshot_query_returns_persisted_pointer_identity():
    snapshot = AccountMonitorSnapshot(
        snapshot_id="account-monitor-1",
        family="chinese_account_detection",
        model_version="detector-1",
        pointer_revision=2,
        window_started_at=datetime(2026, 8, 5, 10, 0, 0),
        window_finished_at=datetime(2026, 8, 5, 11, 0, 0),
        status="healthy",
        metrics_json=json.dumps({"model_identity": {"artifact_hash": "d" * 64}}),
        created_at=datetime(2026, 8, 5, 11, 5, 0),
    )
    rows = asyncio.run(list_account_monitor_snapshots(_MonitoringSession(snapshots=[snapshot])))
    assert rows == [
        {
            "snapshot_id": "account-monitor-1",
            "family": "chinese_account_detection",
            "model_version": "detector-1",
            "artifact_hash": "d" * 64,
            "pointer_revision": 2,
            "window_started_at": "2026-08-05T10:00:00",
            "window_finished_at": "2026-08-05T11:00:00",
            "status": "healthy",
            "metrics": {"model_identity": {"artifact_hash": "d" * 64}},
            "created_at": "2026-08-05T11:05:00",
        }
    ]
