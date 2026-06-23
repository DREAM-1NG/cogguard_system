"""研究复现训练/评估流水线。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.core.risk.research.harmful_baseline import (
    HarmfulBaselineModel,
    HarmfulTrainResult,
    train_and_evaluate_harmful_baseline,
)
from app.core.risk.research.inference import HARMFUL_MODEL_PATH, STANCE_MODEL_PATH
from app.core.risk.research.stance_baseline import (
    StanceBaselineModel,
    StanceTrainResult,
    train_and_evaluate_stance_baseline,
)
from app.core.risk.research.types import ResearchSample, RiskTask


@dataclass(frozen=True)
class TrainingArtifactResult:
    task: RiskTask
    model_path: str
    train_size: int
    eval_size: int
    metrics: dict[str, object]


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def train_harmful_pipeline(
    train_samples: Iterable[ResearchSample],
    eval_samples: Iterable[ResearchSample],
    model_path: str | Path | None = None,
) -> TrainingArtifactResult:
    train_list = list(train_samples)
    eval_list = list(eval_samples)
    result: HarmfulTrainResult = train_and_evaluate_harmful_baseline(train_list, eval_list)
    model = HarmfulBaselineModel.train(train_list)
    output_path = Path(model_path or HARMFUL_MODEL_PATH)
    _ensure_parent(output_path)
    model.save(output_path)
    return TrainingArtifactResult(
        task=RiskTask.HARMFUL,
        model_path=str(output_path),
        train_size=result.train_size,
        eval_size=result.eval_size,
        metrics=result.metrics,
    )


def train_stance_pipeline(
    train_samples: Iterable[ResearchSample],
    eval_samples: Iterable[ResearchSample],
    model_path: str | Path | None = None,
) -> TrainingArtifactResult:
    train_list = list(train_samples)
    eval_list = list(eval_samples)
    result: StanceTrainResult = train_and_evaluate_stance_baseline(train_list, eval_list)
    model = StanceBaselineModel.train(train_list)
    output_path = Path(model_path or STANCE_MODEL_PATH)
    _ensure_parent(output_path)
    model.save(output_path)
    return TrainingArtifactResult(
        task=RiskTask.STANCE,
        model_path=str(output_path),
        train_size=result.train_size,
        eval_size=result.eval_size,
        metrics=result.metrics,
    )
