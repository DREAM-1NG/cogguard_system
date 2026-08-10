from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.config import Settings, settings
from app.core.account_training import (
    AccountTrainingFamily,
    AccountTrainingPolicy,
    AccountTrainingState,
    TrainingTriggerContext,
    evaluate_training_trigger,
    is_training_heartbeat_stale,
    recovery_attempt_allowed,
    require_training_transition,
)


NOW = datetime(2026, 8, 5, tzinfo=timezone.utc)


def test_encoder_training_requires_500000_new_tokens_and_seven_day_cooldown():
    blocked = evaluate_training_trigger(
        TrainingTriggerContext(
            family=AccountTrainingFamily.CHINESE_SOCIAL_ENCODER,
            eligible_item_count=499_999,
            last_dispatched_at=NOW - timedelta(days=8),
            now=NOW,
        )
    )
    assert blocked.allowed is False
    assert blocked.reason == "eligible_item_threshold_not_met"

    cooling_down = evaluate_training_trigger(
        TrainingTriggerContext(
            family=AccountTrainingFamily.CHINESE_SOCIAL_ENCODER,
            eligible_item_count=500_000,
            last_dispatched_at=NOW - timedelta(days=6),
            now=NOW,
        )
    )
    assert cooling_down.allowed is False
    assert cooling_down.reason == "cooldown_active"


def test_detector_training_requires_200_approved_binary_labels():
    decision = evaluate_training_trigger(
        TrainingTriggerContext(
            family=AccountTrainingFamily.CHINESE_ACCOUNT_DETECTOR,
            eligible_item_count=200,
            last_dispatched_at=NOW - timedelta(days=7),
            now=NOW,
        )
    )
    assert decision.allowed is True
    assert decision.threshold == 200


def test_trigger_policy_can_be_configured_by_the_deployment():
    decision = evaluate_training_trigger(
        TrainingTriggerContext(
            family=AccountTrainingFamily.CHINESE_SOCIAL_ENCODER,
            eligible_item_count=12,
            last_dispatched_at=NOW - timedelta(days=2),
            now=NOW,
        ),
        policy=AccountTrainingPolicy(
            dapt_token_threshold=12,
            supervised_label_threshold=5,
            cooldown_days=1,
            heartbeat_timeout_seconds=90,
            max_resumes=2,
        ),
    )
    assert decision.allowed is True
    assert decision.threshold == 12


def test_manual_trigger_only_bypasses_quantity_threshold():
    allowed = evaluate_training_trigger(
        TrainingTriggerContext(
            family=AccountTrainingFamily.CHINESE_ACCOUNT_DETECTOR,
            eligible_item_count=0,
            last_dispatched_at=NOW - timedelta(days=8),
            now=NOW,
            manual=True,
            input_ready=True,
        )
    )
    assert allowed.allowed is True
    assert allowed.quantity_bypassed is True

    blocked = evaluate_training_trigger(
        TrainingTriggerContext(
            family=AccountTrainingFamily.CHINESE_ACCOUNT_DETECTOR,
            eligible_item_count=0,
            last_dispatched_at=NOW - timedelta(days=1),
            now=NOW,
            manual=True,
            input_ready=True,
        )
    )
    assert blocked.allowed is False
    assert blocked.reason == "cooldown_active"

    missing_input = evaluate_training_trigger(
        TrainingTriggerContext(
            family=AccountTrainingFamily.CHINESE_ACCOUNT_DETECTOR,
            eligible_item_count=0,
            last_dispatched_at=None,
            now=NOW,
            manual=True,
            input_ready=False,
        )
    )
    assert missing_input.allowed is False
    assert missing_input.reason == "training_input_not_ready"


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (AccountTrainingState.QUEUED, AccountTrainingState.PREPARING),
        (AccountTrainingState.PREPARING, AccountTrainingState.RUNNING),
        (AccountTrainingState.RUNNING, AccountTrainingState.EVALUATING),
        (AccountTrainingState.EVALUATING, AccountTrainingState.COMPLETED),
        (AccountTrainingState.RUNNING, AccountTrainingState.INTERRUPTED),
        (AccountTrainingState.INTERRUPTED, AccountTrainingState.QUEUED),
        (AccountTrainingState.QUEUED, AccountTrainingState.CANCELLED),
    ],
)
def test_training_state_machine_accepts_governed_transitions(current, target):
    require_training_transition(current, target)


def test_training_state_machine_rejects_skipped_or_terminal_transitions():
    with pytest.raises(ValueError, match="Invalid account training transition"):
        require_training_transition(AccountTrainingState.QUEUED, AccountTrainingState.COMPLETED)
    with pytest.raises(ValueError, match="Invalid account training transition"):
        require_training_transition(AccountTrainingState.COMPLETED, AccountTrainingState.RUNNING)


def test_active_run_heartbeat_lease_expires_but_terminal_runs_do_not():
    assert is_training_heartbeat_stale(
        state=AccountTrainingState.RUNNING,
        heartbeat_at=NOW - timedelta(seconds=301),
        now=NOW,
        timeout_seconds=300,
    )
    assert not is_training_heartbeat_stale(
        state=AccountTrainingState.COMPLETED,
        heartbeat_at=NOW - timedelta(days=1),
        now=NOW,
        timeout_seconds=300,
    )


def test_recovery_attempts_are_bounded_by_the_persisted_limit():
    assert recovery_attempt_allowed(attempt=1, max_attempts=3)
    assert recovery_attempt_allowed(attempt=2, max_attempts=3)
    assert not recovery_attempt_allowed(attempt=3, max_attempts=3)


@pytest.mark.parametrize(
    "field_name",
    [
        "ACCOUNT_TRAINING_OUTBOX_CLAIM_LEASE_SECONDS",
        "ACCOUNT_TRAINING_OUTBOX_PUBLISH_TIMEOUT_SECONDS",
    ],
)
def test_outbox_claim_lease_and_publish_timeout_must_be_positive(field_name):
    with pytest.raises(ValueError, match=f"{field_name} must be positive"):
        Settings(_env_file=None, **{field_name: 0})


def test_celery_broker_timeouts_and_publish_retry_follow_outbox_configuration():
    from app.celery_app import celery_app

    assert celery_app.conf.task_publish_retry is False
    assert celery_app.conf.broker_connection_timeout == settings.ACCOUNT_TRAINING_OUTBOX_PUBLISH_TIMEOUT_SECONDS
    assert celery_app.conf.broker_transport_options == {
        "socket_connect_timeout": settings.ACCOUNT_TRAINING_OUTBOX_PUBLISH_TIMEOUT_SECONDS,
        "socket_timeout": settings.ACCOUNT_TRAINING_OUTBOX_PUBLISH_TIMEOUT_SECONDS,
        "retry_on_timeout": False,
    }


def test_celery_beat_owns_training_reconciliation_and_model_monitoring_cadence():
    from app.celery_app import celery_app

    schedule = celery_app.conf.beat_schedule
    assert schedule["account-training-heartbeat-reconciliation"]["task"] == "account_training.reconcile_heartbeats"
    assert schedule["account-training-heartbeat-reconciliation"]["options"] == {"queue": "account_training"}
    assert schedule["account-model-monitoring-snapshot"]["task"] == "account_training.monitor_active_model"
    assert schedule["account-model-monitoring-snapshot"]["options"] == {"queue": "account_training"}
    assert schedule["account-evaluation-dispatch-reconciliation"]["task"] == "account_evaluation.reconcile_dispatches"
    assert schedule["account-evaluation-dispatch-reconciliation"]["options"] == {"queue": "account_evaluation"}
    assert schedule["account-training-heartbeat-reconciliation"]["schedule"] > 0
    assert schedule["account-model-monitoring-snapshot"]["schedule"] > 0
    assert schedule["account-evaluation-dispatch-reconciliation"]["schedule"] > 0


def test_start_script_launches_a_dedicated_celery_beat_scheduler():
    script = (Path(__file__).resolve().parents[2] / "start-system.ps1").read_text(encoding="utf-8")

    assert "'beat', '--loglevel=info'" in script
    assert "account-training-beat" in script


def test_start_script_serializes_training_and_evaluation_on_one_gpu_worker():
    script = (Path(__file__).resolve().parents[2] / "start-system.ps1").read_text(encoding="utf-8")

    assert "'--queues', 'account_training,account_evaluation'" in script
    assert "'--concurrency', '1', '--pool', 'solo'" in script
    assert "account_training|account_evaluation|account-training@|account-model@" in script
    assert "Stop-StaleAccountModelWorkers" in script


def test_start_script_binds_the_backend_for_static_frontend_delivery():
    script = (Path(__file__).resolve().parents[2] / "start-system.ps1").read_text(encoding="utf-8")

    assert "'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000'" in script
    assert "Get-NetTCPConnection -LocalPort $Port -State Listen" in script
