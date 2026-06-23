"""阶段 5：研究复现训练流水线测试。"""

from __future__ import annotations

from app.core.risk.research.trainers import train_harmful_pipeline, train_stance_pipeline
from app.core.risk.research.types import ResearchSample, RiskSplit, RiskTask


def _harmful_sample(text: str, label: str) -> ResearchSample:
    return ResearchSample(
        dataset="cold",
        task=RiskTask.HARMFUL,
        text=text,
        label=label,
        split=RiskSplit.TRAIN,
    )


def _stance_sample(text: str, label: str, target: str = "热点事件A") -> ResearchSample:
    return ResearchSample(
        dataset="cstance",
        task=RiskTask.STANCE,
        text=text,
        label=label,
        target=target,
        split=RiskSplit.TRAIN,
    )


def test_train_harmful_pipeline_saves_artifact(tmp_path):
    train_samples = [
        _harmful_sample("kill them all right now", "harmful"),
        _harmful_sample("violent toxic message", "harmful"),
        _harmful_sample("have a nice peaceful day", "safe"),
        _harmful_sample("friendly neutral greeting", "safe"),
    ]
    eval_samples = [
        _harmful_sample("violent attack now", "harmful"),
        _harmful_sample("peace and kindness for everyone", "safe"),
    ]

    output = tmp_path / "harmful.pkl"
    result = train_harmful_pipeline(train_samples, eval_samples, output)
    assert result.task == RiskTask.HARMFUL
    assert output.is_file()
    assert result.metrics["accuracy"] >= 0.5


def test_train_stance_pipeline_saves_artifact(tmp_path):
    train_samples = [
        _stance_sample("我支持这个说法", "support"),
        _stance_sample("我赞成这个观点", "support"),
        _stance_sample("这完全是假的", "deny"),
        _stance_sample("这是谣言", "deny"),
        _stance_sample("有证据吗", "query"),
        _stance_sample("真的吗？有来源吗", "query"),
        _stance_sample("我先围观一下", "comment"),
        _stance_sample("路过围观，暂不表态", "comment"),
    ]
    eval_samples = [
        _stance_sample("我赞成这个看法", "support"),
        _stance_sample("这不可信", "deny"),
        _stance_sample("真的吗？", "query"),
        _stance_sample("路过围观", "comment"),
    ]

    output = tmp_path / "stance.pkl"
    result = train_stance_pipeline(train_samples, eval_samples, output)
    assert result.task == RiskTask.STANCE
    assert output.is_file()
    assert result.metrics["accuracy"] >= 0.5
