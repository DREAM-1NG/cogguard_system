from __future__ import annotations

from pathlib import Path


def test_preview_start_script_enables_backend_preview_auth() -> None:
    script = Path(__file__).resolve().parents[1].parent / "start-preview.ps1"
    source = script.read_text(encoding="utf-8")

    assert "PREVIEW_AUTH_ENABLED='true'" in source
    assert "PREVIEW_AUTH_TOKEN='cogguard-preview-token'" in source
    assert "BACKEND_DEBUG='true'" in source
    assert "$env:PREVIEW_AUTH_ENABLED" in source
    assert "$env:PREVIEW_AUTH_TOKEN" in source
