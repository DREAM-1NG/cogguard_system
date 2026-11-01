"""Celery registration contract for propagation monitoring."""


def test_celery_registers_due_propagation_monitoring_task_on_analysis_queue():
    from app.celery_app import celery_app

    assert "propagation.monitor_due_profiles" in celery_app.tasks
    assert celery_app.conf.task_routes["propagation.*"] == {"queue": "analysis"}
    schedule = celery_app.conf.beat_schedule["propagation-monitor-due-profiles"]
    assert schedule["task"] == "propagation.monitor_due_profiles"
