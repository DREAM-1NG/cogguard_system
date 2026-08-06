from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from typing import Any

import numpy as np

from .contracts import (
    ClusterDetectionBatch,
    ClusterDetectionVerdict,
    DetectionFeatureSchema,
    DetectionModelArtifact,
    DetectionTrainingCase,
    case_id_fingerprint,
)
from .features import build_detection_feature_rows


_THRESHOLD_OBJECTIVE = "maximize_covered_macro_f1_times_coverage"


def _sigmoid(values: np.ndarray) -> np.ndarray:
    result = np.empty_like(values, dtype=np.float64)
    positive = values >= 0.0
    result[positive] = 1.0 / (1.0 + np.exp(-values[positive]))
    exponent = np.exp(values[~positive])
    result[~positive] = exponent / (1.0 + exponent)
    return result


def _objective(
    design: np.ndarray,
    labels: np.ndarray,
    parameters: np.ndarray,
    sample_weights: np.ndarray,
    regularization: float,
) -> float:
    logits = design @ parameters
    losses = np.logaddexp(0.0, logits) - labels * logits
    penalty = 0.5 * regularization * float(parameters[:-1] @ parameters[:-1])
    return float(np.sum(sample_weights * losses) / np.sum(sample_weights) + penalty)


def _fit_full_batch_logistic(
    features: np.ndarray,
    labels: np.ndarray,
    *,
    sample_weights: np.ndarray,
    regularization: float,
    max_iterations: int,
    tolerance: float,
) -> tuple[np.ndarray, float, int]:
    rows = features.shape[0]
    design = np.column_stack((features, np.ones(rows, dtype=np.float64)))
    parameters = np.zeros(design.shape[1], dtype=np.float64)
    weight_total = float(np.sum(sample_weights))
    regularizer = np.diag(
        np.concatenate((np.full(features.shape[1], regularization), np.zeros(1)))
    )
    converged = False
    for iteration in range(1, max_iterations + 1):
        probabilities = _sigmoid(design @ parameters)
        gradient = design.T @ (sample_weights * (probabilities - labels)) / weight_total
        gradient[:-1] += regularization * parameters[:-1]
        curvature = sample_weights * probabilities * (1.0 - probabilities)
        hessian = (design.T * curvature) @ design / weight_total + regularizer
        if not np.all(np.isfinite(gradient)) or not np.all(np.isfinite(hessian)):
            raise ValueError("non-finite model optimizer state")
        try:
            step = np.linalg.solve(hessian, gradient)
        except np.linalg.LinAlgError as exc:
            raise ValueError("model optimizer Hessian is singular") from exc
        current = _objective(design, labels, parameters, sample_weights, regularization)
        step_scale = 1.0
        while step_scale > np.finfo(np.float64).eps:
            candidate = parameters - step_scale * step
            if _objective(design, labels, candidate, sample_weights, regularization) <= current:
                parameters = candidate
                break
            step_scale *= 0.5
        else:
            raise ValueError("model optimizer line search failed")
        if float(np.max(np.abs(step_scale * step))) <= tolerance:
            converged = True
            break
    if not converged or not np.all(np.isfinite(parameters)):
        raise ValueError("model optimizer failed to converge to finite parameters")
    return parameters[:-1], float(parameters[-1]), iteration


def _fit_platt(
    logits: np.ndarray,
    labels: np.ndarray,
    *,
    regularization: float,
    max_iterations: int,
    tolerance: float,
) -> tuple[float, float, int]:
    features = logits.reshape(-1, 1)
    parameters, intercept, iterations = _fit_full_batch_logistic(
        features,
        labels,
        sample_weights=np.ones(labels.shape[0], dtype=np.float64),
        regularization=regularization,
        max_iterations=max_iterations,
        tolerance=tolerance,
    )
    return float(parameters[0]), intercept, iterations


def _binary_f1(true: np.ndarray, predicted: np.ndarray, positive_label: int) -> float:
    true_positive = int(np.sum((true == positive_label) & (predicted == positive_label)))
    false_positive = int(np.sum((true != positive_label) & (predicted == positive_label)))
    false_negative = int(np.sum((true == positive_label) & (predicted != positive_label)))
    denominator = 2 * true_positive + false_positive + false_negative
    return 0.0 if denominator == 0 else (2.0 * true_positive) / denominator


def _select_thresholds(probabilities: np.ndarray, labels: np.ndarray) -> tuple[float, float]:
    candidates = tuple(sorted({0.0, 1.0, *(float(value) for value in probabilities)}))
    ranked: list[tuple[tuple[float, ...], tuple[float, float]]] = []
    for lower in candidates:
        for upper in candidates:
            if lower >= upper:
                continue
            covered = (probabilities <= lower) | (probabilities >= upper)
            if not np.any(covered & (labels == 0)) or not np.any(covered & (labels == 1)):
                continue
            covered_labels = labels[covered]
            predictions = (probabilities[covered] >= upper).astype(np.int64)
            macro_f1 = (
                _binary_f1(covered_labels, predictions, 0)
                + _binary_f1(covered_labels, predictions, 1)
            ) / 2.0
            coverage = float(np.mean(covered))
            score = macro_f1 * coverage
            rank = (score, macro_f1, coverage, upper - lower, -lower, -upper)
            ranked.append((rank, (lower, upper)))
    if not ranked:
        raise ValueError("validation rows cannot produce selective thresholds with both classes covered")
    return max(ranked, key=lambda item: item[0])[1]


def _validate_partition(
    cases: Sequence[DetectionTrainingCase],
    expected_split: str,
    schema: DetectionFeatureSchema,
) -> tuple[DetectionTrainingCase, ...]:
    normalized = tuple(cases)
    if not normalized:
        raise ValueError(f"{expected_split} cases must not be empty")
    if not all(isinstance(case, DetectionTrainingCase) for case in normalized):
        raise ValueError(f"{expected_split} cases must contain DetectionTrainingCase values")
    ids = [case.case_id for case in normalized]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{expected_split} cases contain duplicate case IDs")
    cluster_ids = [case.cluster_id for case in normalized]
    if len(cluster_ids) != len(set(cluster_ids)):
        raise ValueError(f"{expected_split} cases contain duplicate cluster IDs")
    for case in normalized:
        if case.split != expected_split:
            raise ValueError(f"{expected_split} partition contains case with split {case.split!r}")
        schema.validate_case(case)
    if {case.label for case in normalized} != {0, 1}:
        raise ValueError(f"{expected_split} cases must contain both classes")
    return normalized


def _matrix(cases: Sequence[DetectionTrainingCase]) -> tuple[np.ndarray, np.ndarray]:
    features = np.asarray([case.feature_values for case in cases], dtype=np.float64)
    labels = np.asarray([case.label for case in cases], dtype=np.float64)
    if features.ndim != 2 or not np.all(np.isfinite(features)):
        raise ValueError("case features must form a finite matrix")
    return features, labels


class LearnedCoordinationDetector:
    __slots__ = (
        "schema", "regularization", "max_iterations", "tolerance",
        "calibration_regularization", "calibration_max_iterations", "_artifact",
    )

    def __init__(
        self,
        *,
        schema: DetectionFeatureSchema,
        artifact: DetectionModelArtifact | None = None,
        regularization: float = 0.01,
        max_iterations: int = 256,
        tolerance: float = 1e-10,
        calibration_regularization: float = 0.001,
        calibration_max_iterations: int = 256,
    ) -> None:
        if not isinstance(schema, DetectionFeatureSchema):
            raise ValueError("schema must be a DetectionFeatureSchema")
        self.schema = schema
        self.regularization = float(regularization)
        self.max_iterations = int(max_iterations)
        self.tolerance = float(tolerance)
        self.calibration_regularization = float(calibration_regularization)
        self.calibration_max_iterations = int(calibration_max_iterations)
        if (
            not math.isfinite(self.regularization) or self.regularization <= 0.0
            or not math.isfinite(self.calibration_regularization)
            or self.calibration_regularization <= 0.0
            or not math.isfinite(self.tolerance) or self.tolerance <= 0.0
            or self.max_iterations <= 0 or self.calibration_max_iterations <= 0
        ):
            raise ValueError("optimizer configuration must be finite and positive")
        if artifact is not None and artifact.feature_schema != schema:
            raise ValueError("artifact feature schema does not match detector schema")
        self._artifact = artifact

    @property
    def artifact(self) -> DetectionModelArtifact | None:
        return self._artifact

    def fit(
        self,
        train_cases: Sequence[DetectionTrainingCase],
        validation_cases: Sequence[DetectionTrainingCase],
    ) -> DetectionModelArtifact:
        train = _validate_partition(train_cases, "train", self.schema)
        validation = _validate_partition(validation_cases, "validation", self.schema)
        train_ids = {case.case_id for case in train}
        validation_ids = {case.case_id for case in validation}
        if train_ids & validation_ids:
            raise ValueError("train and validation case IDs must be disjoint")
        train_cluster_ids = {case.cluster_id for case in train}
        validation_cluster_ids = {case.cluster_id for case in validation}
        if train_cluster_ids & validation_cluster_ids:
            raise ValueError("train and validation cluster IDs must be disjoint")

        train_features, train_labels = _matrix(train)
        validation_features, validation_labels = _matrix(validation)
        scaler_mean = np.mean(train_features, axis=0)
        scaler_scale = np.std(train_features, axis=0)
        scaler_scale = np.where(scaler_scale == 0.0, 1.0, scaler_scale)
        standardized_train = (train_features - scaler_mean) / scaler_scale
        class_zero = int(np.sum(train_labels == 0))
        class_one = int(np.sum(train_labels == 1))
        row_count = train_labels.shape[0]
        class_weight_zero = row_count / (2.0 * class_zero)
        class_weight_one = row_count / (2.0 * class_one)
        sample_weights = np.where(train_labels == 0, class_weight_zero, class_weight_one)
        coefficients, intercept, model_iterations = _fit_full_batch_logistic(
            standardized_train,
            train_labels,
            sample_weights=sample_weights,
            regularization=self.regularization,
            max_iterations=self.max_iterations,
            tolerance=self.tolerance,
        )

        standardized_validation = (validation_features - scaler_mean) / scaler_scale
        validation_logits = standardized_validation @ coefficients + intercept
        slope, calibration_intercept, calibration_iterations = _fit_platt(
            validation_logits,
            validation_labels,
            regularization=self.calibration_regularization,
            max_iterations=self.calibration_max_iterations,
            tolerance=self.tolerance,
        )
        calibrated = _sigmoid(slope * validation_logits + calibration_intercept)
        if not np.all(np.isfinite(calibrated)):
            raise ValueError("calibrator produced non-finite validation probabilities")
        lower, upper = _select_thresholds(calibrated, validation_labels.astype(np.int64))
        validation_fingerprint = case_id_fingerprint(case.case_id for case in validation)
        artifact = DetectionModelArtifact(
            feature_schema=self.schema,
            scaler_mean=tuple(float(value) for value in scaler_mean),
            scaler_scale=tuple(float(value) for value in scaler_scale),
            coefficients=tuple(float(value) for value in coefficients),
            intercept=intercept,
            calibrator_slope=slope,
            calibrator_intercept=calibration_intercept,
            lower_decision_threshold=lower,
            upper_decision_threshold=upper,
            validation_ood_min=tuple(float(value) for value in np.min(validation_features, axis=0)),
            validation_ood_max=tuple(float(value) for value in np.max(validation_features, axis=0)),
            optimizer_config={
                "algorithm": "full_batch_l2_logistic_regression",
                "optimizer": "newton_with_backtracking",
                "regularization": self.regularization,
                "max_iterations": self.max_iterations,
                "tolerance": self.tolerance,
                "iterations": model_iterations,
                "class_weight_0": class_weight_zero,
                "class_weight_1": class_weight_one,
                "seed": 0,
            },
            calibrator_config={
                "algorithm": "one_dimensional_platt_scaling",
                "regularization": self.calibration_regularization,
                "max_iterations": self.calibration_max_iterations,
                "tolerance": self.tolerance,
                "iterations": calibration_iterations,
            },
            threshold_objective=_THRESHOLD_OBJECTIVE,
            train_fit_case_ids_fingerprint=case_id_fingerprint(case.case_id for case in train),
            validation_calibration_case_ids_fingerprint=validation_fingerprint,
            validation_threshold_case_ids_fingerprint=validation_fingerprint,
            validation_ood_case_ids_fingerprint=validation_fingerprint,
        )
        self._artifact = artifact
        return artifact

    def _require_artifact(self) -> DetectionModelArtifact:
        if self._artifact is None:
            raise ValueError("detector requires an explicitly fitted learned artifact")
        return self._artifact

    def _predict_vectors(
        self,
        cluster_ids: Sequence[str],
        feature_rows: np.ndarray,
        *,
        source_batch_id: str,
        source_batch_fingerprint: str,
    ) -> ClusterDetectionBatch:
        artifact = self._require_artifact()
        if feature_rows.shape != (len(cluster_ids), len(self.schema.names)):
            raise ValueError("prediction features do not match schema shape")
        if not np.all(np.isfinite(feature_rows)):
            raise ValueError("prediction features must be finite")
        standardized = (
            feature_rows - np.asarray(artifact.scaler_mean)
        ) / np.asarray(artifact.scaler_scale)
        logits = standardized @ np.asarray(artifact.coefficients) + artifact.intercept
        probabilities = _sigmoid(
            artifact.calibrator_slope * logits + artifact.calibrator_intercept
        )
        verdicts: list[ClusterDetectionVerdict] = []
        for row_index, cluster_id in enumerate(cluster_ids):
            values = feature_rows[row_index]
            ood_features = tuple(
                name
                for name, value, low, high in zip(
                    self.schema.names,
                    values,
                    artifact.validation_ood_min,
                    artifact.validation_ood_max,
                    strict=True,
                )
                if value < low or value > high
            )
            probability = float(probabilities[row_index])
            if ood_features:
                decision = "abstain"
                reason = "out_of_distribution"
            elif probability <= artifact.lower_decision_threshold:
                decision = "benign_coordination"
                reason = None
            elif probability >= artifact.upper_decision_threshold:
                decision = "harmful_coordination"
                reason = None
            else:
                decision = "abstain"
                reason = "selective_threshold"
            verdicts.append(
                ClusterDetectionVerdict(
                    cluster_id=cluster_id,
                    decision=decision,
                    harmful_probability=probability,
                    model_version=artifact.model_version,
                    model_role=artifact.model_role,
                    artifact_hash=artifact.artifact_hash,
                    abstain_reason=reason,
                    ood_features=ood_features,
                )
            )
        digest = hashlib.sha256(
            json.dumps(
                {"source": source_batch_fingerprint, "artifact": artifact.artifact_hash},
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return ClusterDetectionBatch(
            batch_id=f"detection-{digest[:24]}",
            source_batch_id=source_batch_id,
            source_batch_fingerprint=source_batch_fingerprint,
            model_artifact_hash=artifact.artifact_hash,
            verdicts=tuple(verdicts),
        )

    def predict_feature_rows(
        self, cases: Sequence[DetectionTrainingCase]
    ) -> ClusterDetectionBatch:
        rows = tuple(cases)
        if not rows:
            raise ValueError("prediction cases must not be empty")
        ids = [case.case_id for case in rows]
        if len(ids) != len(set(ids)):
            raise ValueError("prediction cases contain duplicate case IDs")
        for case in rows:
            self.schema.validate_case(case)
        source_fingerprint = case_id_fingerprint(ids)
        return self._predict_vectors(
            [case.cluster_id for case in rows],
            np.asarray([case.feature_values for case in rows], dtype=np.float64),
            source_batch_id="feature-rows",
            source_batch_fingerprint=source_fingerprint,
        )

    def predict(self, batch: Any, detection_features: dict[str, dict[str, float]]) -> ClusterDetectionBatch:
        rows = build_detection_feature_rows(batch, self.schema, detection_features)
        cluster_ids = [cluster.cluster_id for cluster in batch.candidate_clusters]
        return self._predict_vectors(
            cluster_ids,
            np.asarray([rows[cluster_id] for cluster_id in cluster_ids], dtype=np.float64),
            source_batch_id=batch.batch_id,
            source_batch_fingerprint=batch.batch_fingerprint,
        )


__all__ = ["LearnedCoordinationDetector"]
