import hashlib
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core import trained_bot_detection


def test_trained_runtime_returns_none_without_verified_checkpoint(monkeypatch, tmp_path):
    monkeypatch.setattr(trained_bot_detection.settings, "BOTRHG_CHECKPOINT_PATH", str(tmp_path / "missing.pt"))
    assert trained_bot_detection.get_trained_botrhg_inference() is None


def test_core_runtime_rejects_implicit_legacy_loading_when_bootstrap_is_disabled(monkeypatch, tmp_path):
    checkpoint = tmp_path / "checkpoint.pt"
    checkpoint.write_bytes(b"checkpoint")
    monkeypatch.setattr(trained_bot_detection.settings, "BOTRHG_CHECKPOINT_PATH", str(checkpoint))
    monkeypatch.setattr(trained_bot_detection.settings, "ACCOUNT_MODEL_BOOTSTRAP_MODE", "disabled", raising=False)
    monkeypatch.setattr(
        trained_bot_detection,
        "_load_research_package",
        lambda: pytest.fail("disabled bootstrap must fail before loading the research runtime"),
    )

    assert trained_bot_detection.get_trained_botrhg_inference() is None


def test_internal_research_loader_targets_system_research(monkeypatch):
    package = trained_bot_detection._load_research_package()
    assert hasattr(package, "BotRHGInference")
    assert "social_bot_detection" in str(Path(package.__file__).parent)


def test_governed_runtime_uses_bundle_components_and_bounds_the_cache(monkeypatch, tmp_path):
    checkpoint = tmp_path / "detector.pt"
    checkpoint.write_bytes(b"detector")
    component_paths = {
        "encoder_path": str(tmp_path / "encoder.pt"),
        "feature_schema_path": str(tmp_path / "feature_schema.json"),
        "calibration_path": str(tmp_path / "calibration.json"),
    }
    component_bytes = {
        "encoder_bytes": b"encoder",
        "feature_schema_bytes": b'{"schema":"features"}',
        "calibration_bytes": b'{"method":"temperature"}',
    }
    Path(component_paths["encoder_path"]).write_bytes(component_bytes["encoder_bytes"])
    Path(component_paths["feature_schema_path"]).write_bytes(component_bytes["feature_schema_bytes"])
    Path(component_paths["calibration_path"]).write_bytes(component_bytes["calibration_bytes"])
    calls = []

    class Runtime:
        pass

    def factory(path, **kwargs):
        calls.append((path, kwargs))
        return Runtime()

    package = SimpleNamespace(create_botrhg_inference=factory, BotRHGInference=factory)
    monkeypatch.setattr(trained_bot_detection, "_load_research_package", lambda: package)
    monkeypatch.setattr(trained_bot_detection.settings, "BOTRHG_DATA_FINGERPRINT", "")
    trained_bot_detection._INFERENCE_CACHE.clear()

    def source(revision):
        return SimpleNamespace(
            checkpoint_path=str(checkpoint),
            model_version=f"model-{revision}",
            artifact_hash=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
            pointer_revision=revision,
            data_fingerprint="",
            source_schema="cogguard.botrhg.account.v3",
            **component_paths,
        )

    trained_bot_detection.get_trained_botrhg_inference(source(1), allow_legacy_fallback=False)
    trained_bot_detection.get_trained_botrhg_inference(source(2), allow_legacy_fallback=False)

    assert len(trained_bot_detection._INFERENCE_CACHE) == 1
    assert calls[-1][1] == {
        "device": trained_bot_detection.settings.BOTRHG_DEVICE,
        "checkpoint_bytes": b"detector",
        "encoder_path": component_paths["encoder_path"],
        "feature_schema_path": component_paths["feature_schema_path"],
        "calibration_path": component_paths["calibration_path"],
        **component_bytes,
        "expected_source_schema": "cogguard.botrhg.account.v3",
    }


def test_concurrent_cold_start_creates_one_runtime(monkeypatch, tmp_path):
    checkpoint = tmp_path / "detector.pt"
    checkpoint.write_bytes(b"detector")
    calls = []
    runtime = object()

    def factory(_path, **_kwargs):
        calls.append(1)
        time.sleep(0.05)
        return runtime

    package = SimpleNamespace(create_botrhg_inference=factory, BotRHGInference=factory)
    source = SimpleNamespace(
        checkpoint_path=str(checkpoint),
        model_version="model-concurrent",
        artifact_hash=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        pointer_revision=1,
        data_fingerprint="",
        source_schema="",
        encoder_path=None,
        feature_schema_path=None,
        calibration_path=None,
    )
    monkeypatch.setattr(trained_bot_detection, "_load_research_package", lambda: package)
    monkeypatch.setattr(trained_bot_detection.settings, "BOTRHG_DATA_FINGERPRINT", "")
    trained_bot_detection._INFERENCE_CACHE.clear()

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(
            executor.map(
                lambda _index: trained_bot_detection.get_trained_botrhg_inference(
                    source,
                    allow_legacy_fallback=False,
                ),
                range(4),
            )
        )

    assert results == [runtime] * 4
    assert calls == [1]


def test_runtime_deserializes_the_exact_bytes_that_passed_hash_verification(monkeypatch, tmp_path):
    checkpoint = tmp_path / "detector.pt"
    verified_bytes = b"verified-detector"
    checkpoint.write_bytes(verified_bytes)
    observed = {}

    def factory(path, **kwargs):
        Path(path).write_bytes(b"replacement-after-verification")
        observed.update(kwargs)
        return object()

    package = SimpleNamespace(create_botrhg_inference=factory)
    source = SimpleNamespace(
        checkpoint_path=str(checkpoint),
        model_version="model-bytes",
        artifact_hash=hashlib.sha256(verified_bytes).hexdigest(),
        pointer_revision=1,
        data_fingerprint="",
        source_schema="",
        encoder_path=None,
        feature_schema_path=None,
        calibration_path=None,
    )
    monkeypatch.setattr(trained_bot_detection, "_load_research_package", lambda: package)
    monkeypatch.setattr(trained_bot_detection.settings, "BOTRHG_DATA_FINGERPRINT", "")
    trained_bot_detection._INFERENCE_CACHE.clear()

    assert trained_bot_detection.get_trained_botrhg_inference(source, allow_legacy_fallback=False) is not None
    assert observed["checkpoint_bytes"] == verified_bytes


def test_partial_research_package_fails_closed_on_repeated_requests(monkeypatch, tmp_path):
    checkpoint = tmp_path / "detector.pt"
    checkpoint.write_bytes(b"detector")
    source = SimpleNamespace(
        checkpoint_path=str(checkpoint),
        model_version="model-partial-import",
        artifact_hash=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        pointer_revision=1,
        data_fingerprint="",
        source_schema="",
        encoder_path=None,
        feature_schema_path=None,
        calibration_path=None,
    )
    monkeypatch.setattr(trained_bot_detection.settings, "BOTRHG_DATA_FINGERPRINT", "")
    monkeypatch.setitem(sys.modules, trained_bot_detection._PACKAGE_NAME, SimpleNamespace())

    assert trained_bot_detection.get_trained_botrhg_inference(source, allow_legacy_fallback=False) is None
    assert trained_bot_detection.get_trained_botrhg_inference(source, allow_legacy_fallback=False) is None


def test_legacy_cache_identity_includes_the_checkpoint_bytes(monkeypatch, tmp_path):
    first = tmp_path / "first.pt"
    second = tmp_path / "second.pt"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    observed = []

    def factory(_path, **kwargs):
        observed.append(kwargs["checkpoint_bytes"])
        return object()

    monkeypatch.setattr(
        trained_bot_detection,
        "_load_research_package",
        lambda: SimpleNamespace(create_botrhg_inference=factory),
    )
    monkeypatch.setattr(trained_bot_detection.settings, "BOTRHG_DATA_FINGERPRINT", "")
    monkeypatch.setattr(
        trained_bot_detection.settings,
        "ACCOUNT_MODEL_BOOTSTRAP_MODE",
        "local_legacy",
    )
    trained_bot_detection._INFERENCE_CACHE.clear()

    monkeypatch.setattr(trained_bot_detection.settings, "BOTRHG_CHECKPOINT_PATH", str(first))
    trained_bot_detection.get_trained_botrhg_inference()
    monkeypatch.setattr(trained_bot_detection.settings, "BOTRHG_CHECKPOINT_PATH", str(second))
    trained_bot_detection.get_trained_botrhg_inference()

    assert observed == [b"first", b"second"]


def test_public_runtime_cache_invalidation_clears_cached_inference():
    trained_bot_detection._INFERENCE_CACHE.clear()
    trained_bot_detection._INFERENCE_CACHE[("model", "hash", "1", "cpu")] = object()

    invalidate = getattr(trained_bot_detection, "invalidate_trained_botrhg_runtime_cache", None)
    assert invalidate is not None, "automatic rollback needs a public cache invalidation boundary"

    invalidate()

    assert trained_bot_detection._INFERENCE_CACHE == {}
