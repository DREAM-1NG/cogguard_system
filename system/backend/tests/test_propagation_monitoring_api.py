"""Route contract for the propagation monitoring workbench."""


def test_propagation_monitoring_routes_share_the_release_api_surface():
    """The delivered frontend requires both alert and timeline endpoints."""
    from app.main import app

    paths = app.openapi()["paths"]

    assert "/api/v1/propagation/model-event-timeline" in paths
    assert "/api/v1/propagation/monitor-profiles" in paths
    assert "/api/v1/propagation/alerts" in paths
    assert "/api/v1/propagation/alerts/unresolved-count" in paths
    assert "/api/v1/propagation/alerts/{alert_id}" in paths
    assert "/api/v1/propagation/alerts/{alert_id}/actions" in paths
