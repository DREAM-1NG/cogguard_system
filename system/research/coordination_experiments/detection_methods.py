from __future__ import annotations

from typing import Any

from research.coordination_detect.contracts import DetectionFeatureSchema, DetectionTrainingCase
from research.coordination_detect.features import STAGE1_FEATURE_NAMES
from research.coordination_detect.learned import LearnedCoordinationDetector

from .baselines import LearnedDetectionImplementation as _LearnedDetectionImplementation
from .runner import (
    DetectionExecutionOutput,
    DetectionInferenceCase,
    DetectionPartitions,
    DetectionPrediction,
)


_METHOD_PROJECTIONS = {
    "coordination_only_logistic": "coordination",
    "detection_features_only_classifier": "detection",
    "learned_fused_detector": "fused",
}


def _shared_schema(partitions: DetectionPartitions) -> DetectionFeatureSchema:
    cases: tuple[Any, ...] = (
        *partitions.train_cases,
        *partitions.validation_cases,
        *partitions.test_cases,
    )
    first = cases[0]
    schema = DetectionFeatureSchema(version=first.feature_schema_version, names=first.feature_names)
    if first.feature_schema_fingerprint != schema.fingerprint:
        raise ValueError("partitions contain an invalid feature schema fingerprint")
    for case in cases[1:]:
        if (
            case.feature_schema_version != schema.version
            or case.feature_schema_fingerprint != schema.fingerprint
            or tuple(case.feature_names) != schema.names
        ):
            raise ValueError("partitions do not share one ordered feature schema")
    return schema


def _projected_names(source_schema: DetectionFeatureSchema, projection: str) -> tuple[str, ...]:
    source_names = source_schema.names
    coordination_names = tuple(name for name in STAGE1_FEATURE_NAMES if name in source_names)
    detection_names = tuple(name for name in source_names if name not in STAGE1_FEATURE_NAMES)
    if projection == "coordination":
        if not coordination_names:
            raise ValueError("Stage 1 feature group is empty")
        return coordination_names
    if projection == "detection":
        if not detection_names:
            raise ValueError("detection feature group is empty")
        return detection_names
    if projection == "fused":
        if not source_names:
            raise ValueError("fused feature group is empty")
        return source_names
    raise ValueError(f"unknown learned detection projection: {projection}")


def _projected_schema(source_schema: DetectionFeatureSchema, projection: str) -> DetectionFeatureSchema:
    return DetectionFeatureSchema(
        version=f"{source_schema.version}/stage2-{projection}",
        names=_projected_names(source_schema, projection),
    )


def _project_training_case(
    case: DetectionTrainingCase,
    source_schema: DetectionFeatureSchema,
    projected_schema: DetectionFeatureSchema,
) -> DetectionTrainingCase:
    values = dict(zip(source_schema.names, case.feature_values, strict=True))
    return DetectionTrainingCase(
        case_id=case.case_id,
        cluster_id=case.cluster_id,
        split=case.split,
        label=case.label,
        feature_schema_version=projected_schema.version,
        feature_schema_fingerprint=projected_schema.fingerprint,
        feature_names=projected_schema.names,
        feature_values=tuple(values[name] for name in projected_schema.names),
        provenance={"projection": projected_schema.version},
    )


def _project_inference_case(
    case: DetectionInferenceCase,
    source_schema: DetectionFeatureSchema,
    projected_schema: DetectionFeatureSchema,
) -> DetectionInferenceCase:
    values = dict(zip(source_schema.names, case.feature_values, strict=True))
    return DetectionInferenceCase(
        case_id=case.case_id,
        cluster_id=case.cluster_id,
        feature_schema_version=projected_schema.version,
        feature_schema_fingerprint=projected_schema.fingerprint,
        feature_names=projected_schema.names,
        feature_values=tuple(values[name] for name in projected_schema.names),
        provenance={},
    )


class LearnedDetectionImplementation(_LearnedDetectionImplementation):
    __slots__ = ("method_id", "implementation_id", "unavailable_reason", "_projection")

    def __init__(self, *, method_id: str, implementation_id: str) -> None:
        if method_id not in _METHOD_PROJECTIONS:
            raise ValueError("unknown learned detection method")
        self.method_id = method_id
        self.implementation_id = implementation_id
        self._projection = _METHOD_PROJECTIONS[method_id]
        self.unavailable_reason = None

    def execute(self, partitions: DetectionPartitions) -> DetectionExecutionOutput:
        if not isinstance(partitions, DetectionPartitions):
            raise ValueError("learned detection execution requires DetectionPartitions")
        source_schema = _shared_schema(partitions)
        projected_schema = _projected_schema(source_schema, self._projection)
        train = tuple(
            _project_training_case(case, source_schema, projected_schema)
            for case in partitions.train_cases
        )
        validation = tuple(
            _project_training_case(case, source_schema, projected_schema)
            for case in partitions.validation_cases
        )
        test = tuple(
            _project_inference_case(case, source_schema, projected_schema)
            for case in partitions.test_cases
        )
        detector = LearnedCoordinationDetector(schema=projected_schema)
        artifact = detector.fit(train, validation)
        prediction_batch = detector.predict_inference_cases(test)
        predictions = tuple(
            DetectionPrediction(
                case_id=case.case_id,
                harmful_probability=verdict.harmful_probability,
                decision=verdict.decision,
            )
            for case, verdict in zip(test, prediction_batch.verdicts, strict=True)
        )
        return DetectionExecutionOutput(model_artifact=artifact, predictions=predictions)


__all__ = ["LearnedDetectionImplementation"]
