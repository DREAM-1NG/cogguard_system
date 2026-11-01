"""Selective 2+1 Review Student model and evaluation helpers."""

from __future__ import annotations

from typing import Any

import numpy as np

from app.core.review.trainable_post import (
    ATTACK_AXIS,
    MISINFO_AXIS,
    NEGATIVE_LABEL,
    POSITIVE_LABEL,
    STANCE_ORDER,
    axis_supports_case,
    binary_classification_metrics,
    binary_label,
    binary_pr_auc,
    claim_context_text,
    coverage_risk_curve,
    expected_calibration_error,
    high_risk_recall_score,
    label_of,
    require_torch,
    resolve_torch_device,
    stance_proxy_of,
    text_of,
    torch,
    nn,
)
from app.core.review.teacher_silver import load_teacher_silver_index

__all__ = [
    "LegacySmokeAdapter",
    "build_legacy_smoke_adapter_prediction_rows",
    "build_legacy_smoke_adapter_targets",
    "load_teacher_silver_index",
    "predict_legacy_smoke_adapter_outputs",
    "student_main_axis_metrics",
    "student_overall_probability_for_case",
    "train_legacy_smoke_adapter_model",
]


def build_legacy_smoke_adapter_targets(
    cases: list[dict[str, Any]],
    teacher_silver_by_case: dict[str, dict[str, Any]] | None = None,
) -> dict[str, np.ndarray]:
    teacher_silver_by_case = teacher_silver_by_case or {}
    n = len(cases)
    attack = np.zeros(n, dtype="float32")
    attack_mask = np.zeros(n, dtype="float32")
    misinfo = np.zeros(n, dtype="float32")
    misinfo_mask = np.zeros(n, dtype="float32")
    stance = np.full(n, STANCE_ORDER.index("unlinked"), dtype="int64")
    stance_mask = np.zeros(n, dtype="float32")
    defer = np.zeros(n, dtype="float32")
    defer_mask = np.ones(n, dtype="float32")
    sample_weight = np.ones(n, dtype="float32")
    for index, case in enumerate(cases):
        case_id = str(case.get("case_id") or "")
        teacher = teacher_silver_by_case.get(case_id) or {}
        if teacher:
            sample_weight[index] = float(max(0.25, min(1.0, 0.5 + 0.5 * float(teacher.get("confidence", 0.5)))))
            defer[index] = 1.0 if str(teacher.get("sample_mode") or "") == "hard_case" else 0.0
            main_axes = teacher.get("main_axes") or {}
            attack_axis = main_axes.get(ATTACK_AXIS) or {}
            if bool(attack_axis.get("available")):
                attack_mask[index] = 1.0
                attack[index] = 1.0 if str(attack_axis.get("label")) == "harmful" else 0.0
            misinfo_axis = main_axes.get(MISINFO_AXIS) or {}
            if bool(misinfo_axis.get("available")):
                misinfo_mask[index] = 1.0
                misinfo[index] = 1.0 if str(misinfo_axis.get("label")) == "harmful" else 0.0
            stance_record = teacher.get("stance") or {}
            stance_label = str(stance_record.get("label") or stance_proxy_of(case))
            if bool(stance_record.get("available")) and stance_label in STANCE_ORDER:
                stance_mask[index] = 1.0
                stance[index] = STANCE_ORDER.index(stance_label)
        else:
            if axis_supports_case(case, ATTACK_AXIS):
                attack_mask[index] = 1.0
                attack[index] = float(binary_label(case))
            if axis_supports_case(case, MISINFO_AXIS):
                misinfo_mask[index] = 1.0
                misinfo[index] = float(binary_label(case))
            stance_label = stance_proxy_of(case)
            if claim_context_text(case) and stance_label in STANCE_ORDER:
                stance_mask[index] = 1.0
                stance[index] = STANCE_ORDER.index(stance_label)
            defer[index] = 0.0
    return {
        "attack": attack,
        "attack_mask": attack_mask,
        "misinfo": misinfo,
        "misinfo_mask": misinfo_mask,
        "stance": stance,
        "stance_mask": stance_mask,
        "defer": defer,
        "defer_mask": defer_mask,
        "sample_weight": sample_weight,
    }


class LegacySmokeAdapter(nn.Module if nn is not None else object):
    def __init__(self, input_dim: int, hidden_dim: int = 128, stance_count: int = len(STANCE_ORDER)):
        require_torch()
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.1),
        )
        self.attack_hate_offense = nn.Linear(hidden_dim, 1)
        self.misinfo_claim_risk = nn.Linear(hidden_dim, 1)
        self.stance = nn.Linear(hidden_dim, stance_count)
        self.defer = nn.Linear(hidden_dim, 1)

    def forward(self, features: Any) -> dict[str, Any]:
        hidden = self.encoder(features)
        return {
            ATTACK_AXIS: self.attack_hate_offense(hidden).squeeze(-1),
            MISINFO_AXIS: self.misinfo_claim_risk(hidden).squeeze(-1),
            "stance": self.stance(hidden),
            "defer": self.defer(hidden).squeeze(-1),
        }


def _masked_weighted_mean(losses: Any, mask: Any, sample_weight: Any | None = None) -> Any:
    weighted_mask = mask.float()
    if sample_weight is not None:
        weighted_mask = weighted_mask * sample_weight.float()
    total = weighted_mask.sum().clamp_min(1.0)
    return (losses * weighted_mask).sum() / total


def train_legacy_smoke_adapter_model(
    model: Any,
    features: np.ndarray,
    targets: dict[str, np.ndarray],
    *,
    epochs: int = 5,
    lr: float = 1e-3,
    batch_size: int = 64,
    stance_weight: float = 0.2,
    defer_weight: float = 0.15,
    device: str | None = None,
) -> dict[str, Any]:
    require_torch()
    device = resolve_torch_device(device)
    model.to(device)
    model.train()
    x_tensor = torch.as_tensor(features, dtype=torch.float32, device=device)
    y_attack = torch.as_tensor(targets["attack"].astype("float32"), device=device)
    y_attack_mask = torch.as_tensor(targets["attack_mask"].astype("float32"), device=device)
    y_misinfo = torch.as_tensor(targets["misinfo"].astype("float32"), device=device)
    y_misinfo_mask = torch.as_tensor(targets["misinfo_mask"].astype("float32"), device=device)
    y_stance = torch.as_tensor(targets["stance"].astype("int64"), device=device)
    y_stance_mask = torch.as_tensor(targets["stance_mask"].astype("float32"), device=device)
    y_defer = torch.as_tensor(targets["defer"].astype("float32"), device=device)
    y_defer_mask = torch.as_tensor(targets["defer_mask"].astype("float32"), device=device)
    sample_weight = torch.as_tensor(targets["sample_weight"].astype("float32"), device=device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
    bce = nn.BCEWithLogitsLoss(reduction="none")
    ce = nn.CrossEntropyLoss(reduction="none")
    history = []
    n = int(y_attack.shape[0])
    for epoch in range(max(1, epochs)):
        order = torch.randperm(n, device=device)
        losses = []
        for start in range(0, n, max(1, batch_size)):
            idx = order[start : start + batch_size]
            optimizer.zero_grad()
            output = model(x_tensor[idx])
            attack_loss = _masked_weighted_mean(bce(output[ATTACK_AXIS], y_attack[idx]), y_attack_mask[idx], sample_weight[idx])
            misinfo_loss = _masked_weighted_mean(
                bce(output[MISINFO_AXIS], y_misinfo[idx]),
                y_misinfo_mask[idx],
                sample_weight[idx],
            )
            stance_loss = _masked_weighted_mean(
                ce(output["stance"], y_stance[idx]),
                y_stance_mask[idx],
                sample_weight[idx],
            )
            defer_loss = _masked_weighted_mean(
                bce(output["defer"], y_defer[idx]),
                y_defer_mask[idx],
                sample_weight[idx],
            )
            loss = attack_loss + misinfo_loss + stance_weight * stance_loss + defer_weight * defer_loss
            loss.backward()
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
        history.append({"epoch": epoch + 1, "loss": round(float(np.mean(losses)), 6)})
    return {
        "epochs": len(history),
        "history": history,
        "device": device,
        "losses": {
            ATTACK_AXIS: "masked BCEWithLogitsLoss",
            MISINFO_AXIS: "masked BCEWithLogitsLoss",
            "stance": f"{stance_weight} * masked CrossEntropyLoss",
            "defer": f"{defer_weight} * masked BCEWithLogitsLoss",
        },
    }


def predict_legacy_smoke_adapter_outputs(
    model: Any,
    features: np.ndarray,
    *,
    batch_size: int = 256,
    device: str | None = None,
) -> dict[str, np.ndarray]:
    require_torch()
    device = resolve_torch_device(device)
    model.to(device)
    model.eval()
    x_tensor = torch.as_tensor(features, dtype=torch.float32, device=device)
    n = int(x_tensor.shape[0])
    rows: dict[str, list[np.ndarray]] = {ATTACK_AXIS: [], MISINFO_AXIS: [], "stance": [], "defer": []}
    with torch.no_grad():
        for start in range(0, n, max(1, batch_size)):
            idx = slice(start, start + batch_size)
            output = model(x_tensor[idx])
            rows[ATTACK_AXIS].append(torch.sigmoid(output[ATTACK_AXIS]).detach().cpu().numpy())
            rows[MISINFO_AXIS].append(torch.sigmoid(output[MISINFO_AXIS]).detach().cpu().numpy())
            rows["stance"].append(torch.softmax(output["stance"], dim=-1).detach().cpu().numpy())
            rows["defer"].append(torch.sigmoid(output["defer"]).detach().cpu().numpy())
    return {
        ATTACK_AXIS: np.concatenate(rows[ATTACK_AXIS]).astype("float32"),
        MISINFO_AXIS: np.concatenate(rows[MISINFO_AXIS]).astype("float32"),
        "stance": np.concatenate(rows["stance"]).astype("float32"),
        "defer": np.concatenate(rows["defer"]).astype("float32"),
    }


def student_overall_probability_for_case(case: dict[str, Any], attack_probability: float, misinfo_probability: float) -> float:
    supported = []
    if axis_supports_case(case, ATTACK_AXIS):
        supported.append(float(attack_probability))
    if axis_supports_case(case, MISINFO_AXIS):
        supported.append(float(misinfo_probability))
    if not supported:
        supported = [float(attack_probability), float(misinfo_probability)]
    safe_probs = [max(0.0, min(1.0, prob)) for prob in supported]
    product = 1.0
    for prob in safe_probs:
        product *= 1.0 - prob
    return 1.0 - product


def build_legacy_smoke_adapter_prediction_rows(
    cases: list[dict[str, Any]],
    predictions: dict[str, np.ndarray],
    *,
    teacher_silver_index: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    teacher_silver_index = teacher_silver_index or {}
    for index, case in enumerate(cases):
        case_id = str(case.get("case_id"))
        teacher = teacher_silver_index.get(case_id) or {}
        attack_prob = float(predictions[ATTACK_AXIS][index])
        misinfo_prob = float(predictions[MISINFO_AXIS][index])
        defer_prob = float(predictions["defer"][index])
        stance_probs = predictions["stance"][index]
        stance_idx = int(np.argmax(stance_probs))
        stance_label = STANCE_ORDER[stance_idx] if 0 <= stance_idx < len(STANCE_ORDER) else "unlinked"
        overall_prob = student_overall_probability_for_case(case, attack_prob, misinfo_prob)
        rows.append(
            {
                "case_id": case_id,
                "dataset": case.get("dataset"),
                "split": case.get("split"),
                "source_id": case.get("source_id"),
                "y_true": label_of(case),
                "teacher_sample_mode": teacher.get("sample_mode"),
                "teacher_confidence": teacher.get("confidence"),
                "teacher_main_axes": teacher.get("main_axes") or {},
                "teacher_review_reason": teacher.get("review_reason") or [],
                "teacher_trace_refs": teacher.get("trace_refs") or [],
                "student": {
                    ATTACK_AXIS: round(attack_prob, 6),
                    MISINFO_AXIS: round(misinfo_prob, 6),
                    "stance": {
                        "label": stance_label,
                        "probability": round(float(stance_probs[stance_idx]), 6),
                    },
                    "defer_probability": round(defer_prob, 6),
                    "abstain": bool(defer_prob >= 0.5),
                },
                "overall_harmful_probability": round(overall_prob, 6),
                "predicted_label": POSITIVE_LABEL if overall_prob >= 0.5 else NEGATIVE_LABEL,
                "text_excerpt": text_of(case)[:240],
            }
        )
    return rows


def student_main_axis_metrics(
    cases: list[dict[str, Any]],
    predictions: dict[str, np.ndarray],
    *,
    teacher_silver_index: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    teacher_silver_index = teacher_silver_index or {}
    attack_labels = np.asarray([binary_label(case) for case in cases if axis_supports_case(case, ATTACK_AXIS)], dtype=int)
    misinfo_labels = np.asarray([binary_label(case) for case in cases if axis_supports_case(case, MISINFO_AXIS)], dtype=int)
    attack_scores = np.asarray(
        [float(predictions[ATTACK_AXIS][index]) for index, case in enumerate(cases) if axis_supports_case(case, ATTACK_AXIS)],
        dtype="float32",
    )
    misinfo_scores = np.asarray(
        [float(predictions[MISINFO_AXIS][index]) for index, case in enumerate(cases) if axis_supports_case(case, MISINFO_AXIS)],
        dtype="float32",
    )
    overall_labels = np.asarray([binary_label(case) for case in cases], dtype=int)
    overall_scores = np.asarray(
        [
            student_overall_probability_for_case(
                cases[index],
                float(predictions[ATTACK_AXIS][index]),
                float(predictions[MISINFO_AXIS][index]),
            )
            for index in range(len(cases))
        ],
        dtype="float32",
    )
    defer_scores = np.asarray([float(predictions["defer"][index]) for index in range(len(cases))], dtype="float32")
    stance_indices = [index for index, case in enumerate(cases) if claim_context_text(case)]
    stance_labels = np.asarray([STANCE_ORDER.index(stance_proxy_of(cases[index])) for index in stance_indices], dtype=int)
    stance_scores = np.asarray([predictions["stance"][index] for index in stance_indices], dtype="float32")
    attack_metrics = binary_classification_metrics(attack_labels, attack_scores) if attack_labels.size else {}
    misinfo_metrics = binary_classification_metrics(misinfo_labels, misinfo_scores) if misinfo_labels.size else {}
    overall_metrics = binary_classification_metrics(overall_labels, overall_scores)
    attack_pr_auc = binary_pr_auc(attack_labels, attack_scores) if attack_labels.size else 0.0
    misinfo_pr_auc = binary_pr_auc(misinfo_labels, misinfo_scores) if misinfo_labels.size else 0.0
    overall_pr_auc = binary_pr_auc(overall_labels, overall_scores)
    stance_accuracy = float((np.argmax(stance_scores, axis=-1) == stance_labels).mean()) if stance_indices else 0.0
    abstain_rate = float((defer_scores >= 0.5).mean()) if len(cases) else 0.0
    high_risk_recall = high_risk_recall_score(overall_labels, overall_scores)
    return {
        "attack": {
            **attack_metrics,
            "pr_auc": round(float(attack_pr_auc), 6),
            "support_cases": int(attack_labels.size),
        },
        "misinfo": {
            **misinfo_metrics,
            "pr_auc": round(float(misinfo_pr_auc), 6),
            "support_cases": int(misinfo_labels.size),
        },
        "overall": {
            **overall_metrics,
            "pr_auc": round(float(overall_pr_auc), 6),
            "support_cases": len(cases),
            "abstain_rate": round(abstain_rate, 6),
            "high_risk_recall": round(float(high_risk_recall), 6),
            "stance_accuracy": round(stance_accuracy, 6),
            "coverage_risk_curve": coverage_risk_curve(overall_labels, overall_scores),
            "ece": expected_calibration_error(overall_labels, overall_scores),
        },
        "macro_f1": round(
            float(
                np.mean(
                    [
                        value
                        for value in [
                            attack_metrics.get("macro_f1") if attack_metrics else None,
                            misinfo_metrics.get("macro_f1") if misinfo_metrics else None,
                        ]
                        if value is not None
                    ]
                )
            )
            if (attack_metrics or misinfo_metrics)
            else 0.0,
            6,
        ),
        "accuracy": round(float(overall_metrics.get("accuracy", 0.0)), 6),
        "pr_auc": round(float(overall_pr_auc), 6),
        "ece": round(float(expected_calibration_error(overall_labels, overall_scores)), 6),
        "coverage_risk_curve": coverage_risk_curve(overall_labels, overall_scores),
        "abstain_rate": round(abstain_rate, 6),
        "high_risk_recall": round(float(high_risk_recall), 6),
    }
