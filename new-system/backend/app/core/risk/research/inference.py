"""研究复现模型的统一推理入口。"""

from __future__ import annotations

from pathlib import Path

from app.core.risk.research.harmful_baseline import HarmfulBaselineModel
from app.core.risk.research.stance_baseline import StanceBaselineModel
from app.core.risk.research.types import ResearchSample, RiskTask

MODEL_ROOT = Path(__file__).resolve().parent / "artifacts"
HARMFUL_MODEL_PATH = MODEL_ROOT / "harmful_baseline.pkl"
STANCE_MODEL_PATH = MODEL_ROOT / "stance_baseline.pkl"


def harmful_model_available() -> bool:
    return HARMFUL_MODEL_PATH.is_file()


def stance_model_available() -> bool:
    return STANCE_MODEL_PATH.is_file()


def predict_harmful_labels(samples: list[ResearchSample]) -> list[str]:
    if not harmful_model_available():
        raise FileNotFoundError(HARMFUL_MODEL_PATH)
    model = HarmfulBaselineModel.load(HARMFUL_MODEL_PATH)
    return model.predict(samples)


def predict_stance_labels(samples: list[ResearchSample]) -> list[str]:
    if not stance_model_available():
        raise FileNotFoundError(STANCE_MODEL_PATH)
    model = StanceBaselineModel.load(STANCE_MODEL_PATH)
    return model.predict(samples)


def build_harmful_samples(posts: list[dict]) -> list[ResearchSample]:
    return [
        ResearchSample(
            dataset="runtime",
            task=RiskTask.HARMFUL,
            text=str(post.get("content", "")),
            label="safe",
            split="unspecified",  # type: ignore[arg-type]
        )
        for post in posts
    ]


def build_stance_samples(posts: list[dict], target: str) -> list[ResearchSample]:
    return [
        ResearchSample(
            dataset="runtime",
            task=RiskTask.STANCE,
            text=str(post.get("content", "")),
            label="comment",
            target=target,
            split="unspecified",  # type: ignore[arg-type]
        )
        for post in posts
    ]
