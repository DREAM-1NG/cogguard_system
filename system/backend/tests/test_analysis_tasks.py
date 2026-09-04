from app.celery_app import celery_app


def test_analysis_teacher_task_is_registered_in_celery_app():
    assert "analysis.teacher_review" in celery_app.tasks
    assert celery_app.tasks["analysis.teacher_review"].name == "analysis.teacher_review"
