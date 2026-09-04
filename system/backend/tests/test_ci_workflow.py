from __future__ import annotations

from pathlib import Path


def test_release_workflow_declares_all_required_cross_platform_gates():
    root = Path(__file__).resolve().parents[3]
    workflow = root / ".github" / "workflows" / "release-gates.yml"
    assert workflow.exists(), workflow
    text = workflow.read_text(encoding="utf-8")
    for job in (
        "backend-unit",
        "backend-integration",
        "migration-roundtrip",
        "frontend-unit-component",
        "frontend-build-smoke",
        "release-security",
        "source-deployment-smoke",
    ):
        assert f"{job}:" in text
    assert "windows-latest" in text
    assert "ubuntu-latest" in text
    assert "COGGUARD_REQUIRE_EXTERNAL_SERVICES: \"1\"" in text
    assert "concurrency:" in text
    assert "CREATE DATABASE IF NOT EXISTS cogguard_test" in text
    assert "pytest tests -q" not in text
