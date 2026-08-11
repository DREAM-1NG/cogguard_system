from __future__ import annotations

import csv
import importlib.util
import sys
import types
import uuid
from pathlib import Path

import pytest

from app.config import PROJECT_ROOT


def _load_experiments():
    research_name = "research"
    research_dir = PROJECT_ROOT / "research"
    if research_name not in sys.modules:
        research_package = types.ModuleType(research_name)
        research_package.__path__ = [str(research_dir)]
        sys.modules[research_name] = research_package

    package_name = "research.coordination_experiments"
    cached = sys.modules.get(package_name)
    if cached is not None:
        return cached
    package_dir = research_dir / "coordination_experiments"
    spec = importlib.util.spec_from_file_location(
        package_name,
        package_dir / "__init__.py",
        submodule_search_locations=[str(package_dir)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = module
    spec.loader.exec_module(module)
    return module


def _write_russian_fixture(root: Path) -> Path:
    root.mkdir()
    path = root / "IRAhandle_tweets_1.csv"
    rows = [
        ("a", "A", "first #x https://a.test", "1/1/2020 00:00", "1"),
        ("b", "B", "second #x https://a.test", "1/1/2020 00:30", "2"),
        ("c", "C", "third #solo https://c.test", "1/1/2020 00:40", "3"),
        ("a", "A", "later #y https://b.test", "1/2/2020 00:00", "4"),
        ("b", "B", "later #y https://b.test", "1/2/2020 00:10", "5"),
        ("c", "C", "later #z https://z.test", "1/2/2020 00:20", "6"),
        ("d", "D", "later #z https://z.test", "1/2/2020 00:30", "7"),
        ("e", "E", "later #q https://q.test", "1/2/2020 00:40", "8"),
        ("f", "F", "later #q https://q.test", "1/2/2020 00:50", "9"),
        ("g", "G", "later #r https://r.test", "1/2/2020 01:00", "10"),
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "external_author_id",
                "author",
                "content",
                "publish_date",
                "tweet_id",
                "retweet",
            ]
        )
        writer.writerows(rows)
    return root


def test_public_proxy_runner_builds_future_pair_recovery_manifest(tmp_path):
    module = _load_experiments()
    fixture = _write_russian_fixture(tmp_path / "russian")
    output = module.CANONICAL_REPRODUCTION_OUTPUT_ROOT / f"pytest-public-proxy-{uuid.uuid4().hex}"
    config = module.PublicProxyDatasetConfig(
        dataset_id="fixture_russian",
        kind="russian_troll_csv_dir",
        path=str(fixture),
        limit_rows=100,
    )

    manifest = module.run_public_proxy_comparison(
        (config,),
        output,
        train_fraction=0.3,
        window_seconds=3600,
        negative_multiplier=2,
        seed=7,
    )

    assert manifest["schema_version"] == module.PUBLIC_PROXY_SCHEMA_VERSION
    assert manifest["rows"][0]["dataset_id"] == "fixture_russian"
    assert manifest["rows"][0]["test_positive_pair_count"] >= 1
    assert set(manifest["rows"][0]["methods"]) == set(module.PUBLIC_PROXY_METHODS)
    assert (output / "public_proxy_manifest.json").exists()
    assert (output / "public_proxy_table.csv").exists()


def test_public_proxy_output_dir_must_stay_on_g_drive(tmp_path):
    module = _load_experiments()

    with pytest.raises(ValueError, match="absolute descendant"):
        module.validate_public_proxy_output_dir("relative/path")
    with pytest.raises(ValueError, match="G:"):
        module.validate_public_proxy_output_dir(tmp_path / "outside")
