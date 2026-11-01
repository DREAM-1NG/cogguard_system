from pathlib import Path

from app.core import trained_bot_detection


def test_trained_runtime_returns_none_without_verified_checkpoint(monkeypatch, tmp_path):
    monkeypatch.setattr(trained_bot_detection.settings, "BOTRHG_CHECKPOINT_PATH", str(tmp_path / "missing.pt"))
    assert trained_bot_detection.get_trained_botrhg_inference() is None


def test_internal_research_loader_targets_system_research(monkeypatch):
    package = trained_bot_detection._load_research_package()
    assert hasattr(package, "BotRHGInference")
    assert "social_bot_detection" in str(Path(package.__file__).parent)
