from pathlib import Path

import pytest

from research.social_bot_detection import strict_datasets


@pytest.mark.parametrize(
    ("dataset_name", "loader_name"),
    [
        ("cresci-2015", "load_strict_cresci_2015_corpus"),
        ("cresci_2017", "load_strict_cresci_2017_corpus"),
        ("midterm-2018", "load_strict_midterm_2018_corpus"),
    ],
)
def test_strict_social_loader_dispatches_supported_dataset_names(monkeypatch, tmp_path, dataset_name, loader_name):
    sentinel = object()
    calls: list[tuple[Path, int]] = []

    def fake_loader(root, *, max_posts_per_account):
        calls.append((Path(root), max_posts_per_account))
        return sentinel

    monkeypatch.setattr(strict_datasets, loader_name, fake_loader)

    result = strict_datasets.load_strict_social_corpus(dataset_name, tmp_path, max_posts_per_account=7)

    assert result is sentinel
    assert calls == [(tmp_path, 7)]


def test_strict_social_loader_rejects_unknown_dataset(tmp_path):
    with pytest.raises(ValueError, match="unsupported strict social-bot dataset"):
        strict_datasets.load_strict_social_corpus("unknown", tmp_path)


def test_dataset_categorical_features_never_include_source_or_dataset_labels():
    features = strict_datasets._categorical_features(
        {"verified": True, "lang": "en"},
        "social_spambots_1",
    )

    assert features["verified"] == "true"
    assert "source_label" not in features
    assert all("label" not in name for name in features)
