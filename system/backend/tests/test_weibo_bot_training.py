import pytest

from app.core.bot_training import DEFAULT_DATASET_ROOT
from app.core.bot_training import load_weibo_corpus
from app.core.bot_training import train_weibo_bot_model


pytestmark = pytest.mark.skipif(
    not DEFAULT_DATASET_ROOT.exists(),
    reason="Botection corpus is an optional external test fixture",
)


def test_weibo_corpus_loads_labeled_rows():
    rows = load_weibo_corpus(DEFAULT_DATASET_ROOT)

    assert rows
    assert {row.label for row in rows} == {0, 1}
    assert all(row.text for row in rows)
    assert all(row.post_count > 0 for row in rows)


def test_weibo_training_builds_artifact(tmp_path):
    report = train_weibo_bot_model(
        DEFAULT_DATASET_ROOT,
        output_dir=tmp_path,
        test_size=0.2,
        random_state=7,
        max_features=500,
    )

    assert report["row_count"] > 0
    assert report["train_count"] > 0
    assert report["test_count"] > 0
    assert report["metrics"]["accuracy"] >= 0.5
    assert report["metrics"]["macro_f1"] >= 0.5
    assert (tmp_path / "weibo_bot_detector.joblib").exists()
    assert (tmp_path / "weibo_bot_detector.json").exists()
