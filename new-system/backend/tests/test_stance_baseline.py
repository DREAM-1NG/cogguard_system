"""阶段 3：Stance baseline 研究复现测试。"""

from __future__ import annotations

from app.core.risk.research.stance_baseline import StanceBaselineModel, train_and_evaluate_stance_baseline
from app.core.risk.research.types import ResearchSample, RiskSplit, RiskTask


def _sample(text: str, label: str, target: str = "热点事件A") -> ResearchSample:
    return ResearchSample(
        dataset="cstance",
        task=RiskTask.STANCE,
        text=text,
        label=label,
        target=target,
        split=RiskSplit.TRAIN,
    )


def test_stance_baseline_train_and_predict(tmp_path):
    train_samples = [
        _sample("我支持这个说法", "support"),
        _sample("这完全是假的", "deny"),
        _sample("有证据吗", "query"),
        _sample("我先围观一下", "comment"),
    ]
    eval_samples = [
        _sample("我同意这个观点", "support"),
        _sample("这不是真的", "deny"),
    ]

    model = StanceBaselineModel.train(train_samples)
    predictions = model.predict(eval_samples)
    assert len(predictions) == 2
    assert set(predictions).issubset({"support", "deny", "query", "comment"})

    save_path = tmp_path / "stance.pkl"
    model.save(save_path)
    loaded = StanceBaselineModel.load(save_path)
    assert loaded.predict(eval_samples) == predictions


def test_stance_baseline_train_and_evaluate_returns_metrics():
    train_samples = [
        _sample("我支持这个说法", "support"),
        _sample("我赞成这个观点", "support"),
        _sample("这个观点值得转发", "support"),
        _sample("这完全是假的", "deny"),
        _sample("这不可信，是谣言", "deny"),
        _sample("这是谣言", "deny"),
        _sample("有证据吗", "query"),
        _sample("真的吗？有来源吗", "query"),
        _sample("我先围观一下", "comment"),
        _sample("路过围观，暂不表态", "comment"),
    ]
    eval_samples = [
        _sample("我赞成这个看法", "support"),
        _sample("这不可信", "deny"),
        _sample("真的吗？", "query"),
        _sample("路过围观", "comment"),
    ]

    result = train_and_evaluate_stance_baseline(train_samples, eval_samples)
    assert result.train_size == 10
    assert result.eval_size == 4
    assert set(result.labels) == {"comment", "deny", "query", "support"}
    assert result.metrics["accuracy"] >= 0.5
    assert "macro_f1" in result.metrics
