from __future__ import annotations

from pathlib import Path


def test_preview_start_script_uses_standard_login_boundary() -> None:
    script = Path(__file__).resolve().parents[1].parent / "start-preview.ps1"
    source = script.read_text(encoding="utf-8")

    assert "PREVIEW_AUTH_ENABLED" not in source
    assert "PREVIEW_AUTH_TOKEN" not in source
    assert "BACKEND_DEBUG='true'" in source
    assert "uvicorn app.main:app" in source


def test_preview_start_script_supports_frontend_port_fallback() -> None:
    script = Path(__file__).resolve().parents[1].parent / "start-preview.ps1"
    source = script.read_text(encoding="utf-8")

    assert "Get-FreePort" in source
    assert "5173" in source
    assert "Frontend preview:" in source
