from pathlib import Path


def test_preview_startup_cleans_any_backend_port_owner():
    script = Path(__file__).parents[2] / "start-preview.ps1"
    source = script.read_text(encoding="utf-8")

    assert "Get-NetTCPConnection -LocalPort $Port -State Listen" in source
    assert "-LocalAddress '127.0.0.1'" not in source
