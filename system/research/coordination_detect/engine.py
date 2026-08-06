from __future__ import annotations

from typing import Any

from .contracts import ClusterDetectionBatch, DetectionModelArtifact
from .learned import LearnedCoordinationDetector


class CoordinationDetectionEngine:
    __slots__ = ("_detector",)

    def __init__(
        self,
        *,
        artifact: DetectionModelArtifact | None = None,
        detector: LearnedCoordinationDetector | None = None,
    ) -> None:
        if artifact is not None and detector is not None:
            raise ValueError("supply either a learned artifact or learned detector, not both")
        if artifact is not None:
            detector = LearnedCoordinationDetector(
                schema=artifact.feature_schema,
                artifact=artifact,
            )
        if detector is None:
            raise ValueError("engine requires an explicit learned artifact or detector")
        if not isinstance(detector, LearnedCoordinationDetector):
            raise ValueError("engine accepts only a learned coordination detector")
        if detector.artifact is None:
            raise ValueError("engine detector must contain an explicitly fitted learned artifact")
        self._detector = detector

    @property
    def artifact(self) -> DetectionModelArtifact:
        artifact = self._detector.artifact
        if artifact is None:
            raise ValueError("engine learned artifact is unavailable")
        return artifact

    def predict(
        self,
        batch: Any,
        detection_features: dict[str, dict[str, float]],
    ) -> ClusterDetectionBatch:
        return self._detector.predict(batch, detection_features)


__all__ = ["CoordinationDetectionEngine"]
