"""Public API registration contract for propagation monitoring."""


def test_propagation_monitoring_alert_routes_are_registered():
    from app.main import app

    paths = app.openapi()["paths"]

    assert "/api/v1/propagation/monitor-profiles" in paths
    assert "/api/v1/propagation/alerts" in paths
    assert "/api/v1/propagation/alerts/unresolved-count" in paths
    assert "/api/v1/propagation/alerts/{alert_id}" in paths
    assert "/api/v1/propagation/alerts/{alert_id}/actions" in paths
