from __future__ import annotations

import pytest

from research.social_bot_detection import cli


def test_default_cli_benchmark_is_cresci_2017(monkeypatch, tmp_path):
    observed = {}

    def fake_train(dataset_root, output_dir, *, config):
        observed["dataset_root"] = dataset_root
        observed["output_dir"] = output_dir
        observed["dataset_name"] = config.dataset_name
        return {"status": "ok"}

    monkeypatch.setattr(cli, "train_botrhg", fake_train)

    result = cli.main(
        [
            "--dataset-root",
            str(tmp_path / "dataset"),
            "--output-dir",
            str(tmp_path / "output"),
            "--text-model-path",
            "fixture",
        ]
    )

    assert result == 0
    assert observed["dataset_name"] == "cresci_2017"


def test_cli_rejects_legacy_botection_benchmark(tmp_path):
    with pytest.raises(SystemExit):
        cli.main(
            [
                "--dataset-name",
                "botection",
                "--dataset-root",
                str(tmp_path / "dataset"),
                "--output-dir",
                str(tmp_path / "output"),
                "--text-model-path",
                "fixture",
            ]
        )
