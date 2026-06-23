"""Stance 研究复现 baseline。

阶段 3 先落地一个可重复、可评估、CPU 友好的 baseline：
TF-IDF(text + target prompt) + LogisticRegression。
后续如需更强模型，可在不改变训练/推理接口的前提下替换。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import pickle

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from app.core.risk.research.metrics import evaluate_classification
from app.core.risk.research.types import ResearchSample, RiskTask


@dataclass(frozen=True)
class StanceTrainResult:
    train_size: int
    eval_size: int
    labels: tuple[str, ...]
    metrics: dict[str, object]


class StanceBaselineModel:
    def __init__(self, pipeline: Pipeline):
        self.pipeline = pipeline

    @staticmethod
    def _compose_text(sample: ResearchSample) -> str:
        target = sample.target or "当前话题"
        return f"target: {target} [SEP] text: {sample.text}"

    @classmethod
    def train(cls, train_samples: Iterable[ResearchSample]) -> "StanceBaselineModel":
        samples = list(train_samples)
        if not samples:
            raise ValueError("train_samples 不能为空")
        if any(sample.task != RiskTask.STANCE for sample in samples):
            raise ValueError("StanceBaselineModel 仅支持 stance 任务样本")

        texts = [cls._compose_text(sample) for sample in samples]
        labels = [sample.label for sample in samples]
        pipeline = Pipeline(
            steps=[
                ("tfidf", TfidfVectorizer(max_features=8000, ngram_range=(1, 2))),
                ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
            ]
        )
        pipeline.fit(texts, labels)
        return cls(pipeline)

    def predict(self, samples: Iterable[ResearchSample]) -> list[str]:
        sample_list = list(samples)
        if not sample_list:
            return []
        texts = [self._compose_text(sample) for sample in sample_list]
        return list(self.pipeline.predict(texts))

    def evaluate(self, samples: Iterable[ResearchSample]) -> dict[str, object]:
        sample_list = list(samples)
        predictions = self.predict(sample_list)
        return evaluate_classification([sample.label for sample in sample_list], predictions)

    def save(self, path: str | Path) -> None:
        with Path(path).open("wb") as fh:
            pickle.dump(self.pipeline, fh)

    @classmethod
    def load(cls, path: str | Path) -> "StanceBaselineModel":
        with Path(path).open("rb") as fh:
            pipeline = pickle.load(fh)
        return cls(pipeline)


def train_and_evaluate_stance_baseline(
    train_samples: Iterable[ResearchSample],
    eval_samples: Iterable[ResearchSample],
) -> StanceTrainResult:
    train_list = list(train_samples)
    eval_list = list(eval_samples)
    model = StanceBaselineModel.train(train_list)
    metrics = model.evaluate(eval_list or train_list)
    labels = tuple(sorted(set(sample.label for sample in train_list + eval_list)))
    return StanceTrainResult(
        train_size=len(train_list),
        eval_size=len(eval_list),
        labels=labels,
        metrics=metrics,
    )
