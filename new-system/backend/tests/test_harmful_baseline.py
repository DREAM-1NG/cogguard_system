"""阶段 2：Harmful baseline 研究复现测试。"""

from __future__ import annotations

from app.core.risk.research.harmful_baseline import HarmfulBaselineModel, train_and_evaluate_harmful_baseline
from app.core.risk.research.types import ResearchSample, RiskSplit, RiskTask


def _sample(text: str, label: str) -> ResearchSample:
    return ResearchSample(
        dataset="cold",
        task=RiskTask.HARMFUL,
        text=text,
        label=label,
        split=RiskSplit.TRAIN,
    )


def test_harmful_baseline_train_and_predict(tmp_path):
    train_samples = [
        _sample("kill them all right now", "harmful"),
        _sample("violent toxic message", "harmful"),
        _sample("have a nice peaceful day", "safe"),
        _sample("friendly neutral greeting", "safe"),
    ]
    eval_samples = [
        _sample("this is a violent message", "harmful"),
        _sample("peace and kindness for everyone", "safe"),
    ]

    model = HarmfulBaselineModel.train(train_samples)
    predictions = model.predict(eval_samples)
    assert len(predictions) == 2
    assert set(predictions).issubset({"harmful", "safe"})

    save_path = tmp_path / "harmful.joblib"
    model.save(save_path)
    loaded = HarmfulBaselineModel.load(save_path)
    assert loaded.predict(eval_samples) == predictions


def test_harmful_baseline_train_and_evaluate_returns_metrics():
    train_samples = [
        _sample("kill them all right now", "harmful"),
        _sample("violent toxic message", "harmful"),
        _sample("have a nice peaceful day", "safe"),
        _sample("friendly neutral greeting", "safe"),
    ]
    eval_samples = [
        _sample("violent attack now", "harmful"),
        _sample("friendly peaceful message", "safe"),
    ]

    result = train_and_evaluate_harmful_baseline(train_samples, eval_samples)
    assert result.train_size == 4
    assert result.eval_size == 2
    assert set(result.labels) == {"harmful", "safe"}
    assert result.metrics["accuracy"] >= 0.5
    assert "macro_f1" in result.metrics
