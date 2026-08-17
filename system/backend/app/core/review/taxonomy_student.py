"""Taxonomy-first textified Review Student.

This module is the stage-1 Student path for social-media content moderation.
It follows harmful-content taxonomy practice by learning orthogonal risk axes
instead of a flat harmful/non-harmful label. Raw images or videos are not
consumed here; OCR, ASR, captions, hashtags, and post text are serialized as
text evidence with explicit field markers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

try:  # pragma: no cover - torch is optional in lightweight API tests
    import torch
    from torch import nn
except Exception:  # pragma: no cover
    torch = None  # type: ignore[assignment]
    nn = None  # type: ignore[assignment]


TEXTIFIED_STUDENT_SCHEMA = "kt3-textified-student-v1"

INTERPERSONAL_AXIS = "interpersonal_aggression"
DECEPTION_AXIS = "ideological_deception"
STANCE_AXIS = "stance"

MAIN_AXIS_ORDER = (INTERPERSONAL_AXIS, DECEPTION_AXIS)
STANCE_ORDER = ("support", "deny", "query", "neutral", "unlinked")

INTERPERSONAL_FINE_LABELS = (
    "identity_attack",
    "identity_misrepresentation",
    "insult",
    "harassment",
    "threat_of_violence",
    "sexual_aggression",
    "doxing",
)
DECEPTION_FINE_LABELS = (
    "misinformation",
    "rumor",
    "false_claim",
    "conspiracy_narrative",
    "manipulative_context",
    "impersonation_or_source_misuse",
)
FINE_LABEL_ORDER = INTERPERSONAL_FINE_LABELS + DECEPTION_FINE_LABELS

PROTOCOL_HEAD_DIMS = {
    "hatexplain_3way": 3,
    "latent_hate_3way": 3,
    "hatecheck_binary": 2,
    "hatecot_universal_3way": 3,
}

INTERPERSONAL_DATASETS = {"hatexplain", "hatecot", "multioff"}
DECEPTION_DATASETS = {"pheme", "mcfend", "fakesv", "weibo21"}
CLAIM_LINKED_DATASETS = {"pheme", "mcfend", "fakesv", "weibo21"}

POSITIVE_LABELS = {
    "harmful",
    "hate",
    "hateful",
    "offensive",
    "abusive",
    "toxic",
    "fake",
    "false",
    "rumor",
    "rumour",
    "misinformation",
}
NEGATIVE_LABELS = {
    "non_harmful",
    "normal",
    "benign",
    "neutral",
    "non-offensive",
    "real",
    "true",
    "non-rumor",
    "non-rumour",
}

PRIMARY_FIELD_ORDER = ("text", "hashtags")
DERIVED_TEXT_FIELD_ORDER = ("ocr", "asr", "caption")
FIELD_ORDER = PRIMARY_FIELD_ORDER + DERIVED_TEXT_FIELD_ORDER
RATIONALE_FIELDS = ("explain", "explanation", "rationale", "rationale_text")


@dataclass(frozen=True)
class TextifiedStudentExample:
    case_id: str
    dataset: str
    split: str
    input_text: str
    labels: dict[str, float | int]
    task_mask: dict[str, float]
    fine_labels: dict[str, float]
    rationale_text: str
    metadata: dict[str, Any]


def require_torch() -> None:
    if torch is None or nn is None:  # pragma: no cover
        raise RuntimeError("torch is required for taxonomy Review Student models")


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return " ".join(_clean_text(item) for item in value if _clean_text(item))
    return " ".join(str(value).split()).strip()


def _labels(case: Mapping[str, Any]) -> Mapping[str, Any]:
    labels = case.get("labels") or {}
    return labels if isinstance(labels, Mapping) else {}


def _raw_label(case: Mapping[str, Any]) -> str:
    labels = _labels(case)
    candidates = [
        labels.get("harmfulness"),
        labels.get("raw_label"),
        labels.get("label"),
        labels.get("veracity"),
        labels.get("rumour_label"),
        labels.get("rumor_label"),
    ]
    for candidate in candidates:
        text = _clean_text(candidate).lower()
        if text:
            return text
    return ""


def _harm_types(case: Mapping[str, Any]) -> set[str]:
    labels = _labels(case)
    raw = labels.get("harm_type") or labels.get("harm_types") or []
    if isinstance(raw, str):
        raw = [raw]
    return {_clean_text(item).lower() for item in raw if _clean_text(item)}


def _target_groups(case: Mapping[str, Any]) -> list[str]:
    labels = _labels(case)
    raw = labels.get("target_groups") or labels.get("targets") or []
    if isinstance(raw, str):
        raw = [raw]
    return [_clean_text(item) for item in raw if _clean_text(item)]


def _claim_context(case: Mapping[str, Any]) -> Mapping[str, Any]:
    context = case.get("claim_context") or {}
    return context if isinstance(context, Mapping) else {}


def claim_context_text(case: Mapping[str, Any]) -> str:
    context = _claim_context(case)
    parts = [
        _clean_text(context.get("claim_text")),
        _clean_text(context.get("evidence_text")),
    ]
    for link in context.get("evidence_links") or []:
        if isinstance(link, Mapping):
            parts.extend(
                [
                    _clean_text(link.get("position")),
                    _clean_text(link.get("mediatype")),
                    _clean_text(link.get("link")),
                ]
            )
    return " ".join(part for part in parts if part)


def _field_value(case: Mapping[str, Any], field: str) -> str:
    if field == "hashtags":
        labels = _labels(case)
        return _clean_text(case.get("hashtags") or labels.get("hashtags"))
    media = case.get("media") or {}
    media = media if isinstance(media, Mapping) else {}
    if field in {"ocr", "asr", "caption"}:
        return _clean_text(case.get(field) or media.get(field) or media.get(f"{field}_text"))
    return _clean_text(case.get(field))


def build_textified_input(
    case: Mapping[str, Any],
    *,
    include_derived_text: bool = True,
) -> str:
    """Serialize social-media evidence fields for a text-only encoder.

    The Student path uses only primary text fields. Derived media text remains
    available to legacy callers behind an explicit compatibility option.
    """

    segments = []
    field_order = FIELD_ORDER if include_derived_text else PRIMARY_FIELD_ORDER
    for field in field_order:
        value = _field_value(case, field)
        if value:
            segments.append(f"[{field.upper()}] {value}")
    claim_text = claim_context_text(case)
    if claim_text:
        segments.append(f"[CLAIM_CONTEXT] {claim_text}")
    return "\n".join(segments) if segments else "[TEXT] "


def rationale_text_of(case: Mapping[str, Any]) -> str:
    """Return dataset-provided rationale/explanation text when it exists.

    This is for supervised LRKD on explanation-bearing datasets such as
    HateCoT. It must not be filled by the current hard-case mining pipeline.
    """

    labels = _labels(case)
    for field in RATIONALE_FIELDS:
        text = _clean_text(case.get(field) or labels.get(field))
        if text:
            return text
    tokens = labels.get("rationale_tokens") or []
    if tokens:
        return _clean_text(tokens)
    return ""


def dataset_supports_axis(dataset: str, axis: str) -> bool:
    name = dataset.strip().lower()
    if axis == INTERPERSONAL_AXIS:
        return name in INTERPERSONAL_DATASETS
    if axis == DECEPTION_AXIS:
        return name in DECEPTION_DATASETS
    if axis == STANCE_AXIS:
        return name in CLAIM_LINKED_DATASETS
    return False


def case_supports_axis(case: Mapping[str, Any], axis: str) -> bool:
    dataset = _clean_text(case.get("dataset")).lower()
    harm_types = _harm_types(case)
    labels = _labels(case)
    if axis == INTERPERSONAL_AXIS:
        return bool(
            dataset_supports_axis(dataset, axis)
            or harm_types.intersection(
                {
                    "hate",
                    "hateful",
                    "offensive",
                    "abusive",
                    "toxic",
                    "hate_harassment",
                    "harassment",
                    "identity_attack",
                    "insult",
                    "threat_of_violence",
                }
            )
            or _target_groups(case)
            or labels.get("rationale_tokens")
        )
    if axis == DECEPTION_AXIS:
        return bool(
            dataset_supports_axis(dataset, axis)
            or harm_types.intersection(
                {
                    "misinformation",
                    "false_claim",
                    "rumor",
                    "rumour",
                    "fake_news",
                    "manipulative_context",
                }
            )
            or claim_context_text(case)
            or labels.get("veracity") is not None
            or labels.get("rumour_label") is not None
            or labels.get("rumor_label") is not None
        )
    if axis == STANCE_AXIS:
        return bool(dataset_supports_axis(dataset, axis) and claim_context_text(case))
    return False


def _binary_from_label(raw_label: str) -> float:
    label = raw_label.strip().lower()
    if label in POSITIVE_LABELS:
        return 1.0
    if label in NEGATIVE_LABELS:
        return 0.0
    return 0.0


def _stance_label(case: Mapping[str, Any]) -> int:
    labels = _labels(case)
    raw = labels.get("raw_annotation") or {}
    if isinstance(raw, Mapping):
        positions = {
            _clean_text(link.get("position")).lower()
            for link in raw.get("links") or []
            if isinstance(link, Mapping)
        }
        if "against" in positions:
            return STANCE_ORDER.index("deny")
        if "for" in positions:
            return STANCE_ORDER.index("support")
    stance = _clean_text(labels.get("stance")).lower()
    if stance in STANCE_ORDER:
        return STANCE_ORDER.index(stance)
    veracity = _clean_text(labels.get("veracity")).lower()
    if veracity in {"false", "fake", "debunking"}:
        return STANCE_ORDER.index("deny")
    if veracity in {"true", "real"}:
        return STANCE_ORDER.index("support")
    return STANCE_ORDER.index("neutral" if claim_context_text(case) else "unlinked")


def fine_label_targets(case: Mapping[str, Any]) -> dict[str, float]:
    raw = _raw_label(case)
    harm_types = _harm_types(case)
    targets = {label: 0.0 for label in FINE_LABEL_ORDER}
    for label in FINE_LABEL_ORDER:
        if label in harm_types:
            targets[label] = 1.0
    if raw in {"hate", "hateful", "abusive"}:
        targets["identity_attack"] = 1.0
    if raw in {"offensive", "toxic"}:
        targets["insult"] = 1.0
    if raw in {"fake", "false", "misinformation"}:
        targets["misinformation"] = 1.0
    if raw in {"rumor", "rumour"}:
        targets["rumor"] = 1.0
    return targets


def build_textified_student_example(case: Mapping[str, Any]) -> TextifiedStudentExample:
    dataset = _clean_text(case.get("dataset")) or "unknown"
    raw_label = _raw_label(case)
    rationale_text = rationale_text_of(case)
    task_mask = {
        INTERPERSONAL_AXIS: 1.0 if case_supports_axis(case, INTERPERSONAL_AXIS) else 0.0,
        DECEPTION_AXIS: 1.0 if case_supports_axis(case, DECEPTION_AXIS) else 0.0,
        STANCE_AXIS: 1.0 if case_supports_axis(case, STANCE_AXIS) else 0.0,
        "rationale": 1.0 if dataset.strip().lower() == "hatecot" and rationale_text else 0.0,
    }
    binary = _binary_from_label(raw_label)
    labels: dict[str, float | int] = {
        INTERPERSONAL_AXIS: binary if task_mask[INTERPERSONAL_AXIS] else 0.0,
        DECEPTION_AXIS: binary if task_mask[DECEPTION_AXIS] else 0.0,
        STANCE_AXIS: _stance_label(case),
    }
    return TextifiedStudentExample(
        case_id=_clean_text(case.get("case_id") or case.get("id")) or "unknown",
        dataset=dataset,
        split=_clean_text(case.get("split") or case.get("protocol_split")) or "unknown",
        input_text=build_textified_input(case, include_derived_text=False),
        labels=labels,
        task_mask=task_mask,
        fine_labels=fine_label_targets(case),
        rationale_text=rationale_text,
        metadata={
            "schema": TEXTIFIED_STUDENT_SCHEMA,
            "raw_label": raw_label,
            "taxonomy_scope": "interpersonal_aggression + ideological_deception",
            "excluded_scope": "exploitation_self_harm and raw vision/video understanding",
        },
    )


def build_textified_student_batch(cases: list[Mapping[str, Any]]) -> dict[str, Any]:
    examples = [build_textified_student_example(case) for case in cases]
    return {
        "schema": TEXTIFIED_STUDENT_SCHEMA,
        "examples": examples,
        "texts": [example.input_text for example in examples],
        "rationale_texts": [example.rationale_text for example in examples],
        "labels": {
            INTERPERSONAL_AXIS: np.asarray([example.labels[INTERPERSONAL_AXIS] for example in examples], dtype="float32"),
            DECEPTION_AXIS: np.asarray([example.labels[DECEPTION_AXIS] for example in examples], dtype="float32"),
            STANCE_AXIS: np.asarray([example.labels[STANCE_AXIS] for example in examples], dtype="int64"),
            "fine_labels": np.asarray(
                [[example.fine_labels[label] for label in FINE_LABEL_ORDER] for example in examples],
                dtype="float32",
            ),
        },
        "task_mask": {
            INTERPERSONAL_AXIS: np.asarray([example.task_mask[INTERPERSONAL_AXIS] for example in examples], dtype="float32"),
            DECEPTION_AXIS: np.asarray([example.task_mask[DECEPTION_AXIS] for example in examples], dtype="float32"),
            STANCE_AXIS: np.asarray([example.task_mask[STANCE_AXIS] for example in examples], dtype="float32"),
            "rationale": np.asarray([example.task_mask.get("rationale", 0.0) for example in examples], dtype="float32"),
            "fine_labels": np.asarray(
                [
                    1.0
                    if example.task_mask[INTERPERSONAL_AXIS] or example.task_mask[DECEPTION_AXIS]
                    else 0.0
                    for example in examples
                ],
                dtype="float32",
            ),
        },
    }


class XLMRTextifiedReviewStudent(nn.Module if nn is not None else object):
    """End-to-end XLM-R text encoder with taxonomy-first heads."""

    def __init__(
        self,
        model_name: str = "xlm-roberta-base",
        *,
        fine_label_count: int = len(FINE_LABEL_ORDER),
        stance_count: int = len(STANCE_ORDER),
        rationale_dim: int = 768,
        dropout: float = 0.1,
        protocol_head_dims: Mapping[str, int] | None = None,
        local_files_only: bool = False,
        cache_dir: str | None = None,
    ):
        require_torch()
        super().__init__()
        from transformers import AutoModel

        self.backbone = AutoModel.from_pretrained(
            model_name,
            local_files_only=local_files_only,
            cache_dir=cache_dir,
        )
        hidden_size = int(self.backbone.config.hidden_size)
        self.dropout = nn.Dropout(dropout)
        self.interpersonal_aggression = nn.Linear(hidden_size, 1)
        self.ideological_deception = nn.Linear(hidden_size, 1)
        self.stance = nn.Linear(hidden_size, stance_count)
        self.fine_labels = nn.Linear(hidden_size, fine_label_count)
        self.rationale_proj = nn.Linear(hidden_size, rationale_dim)
        self.harm_rationale_proj = nn.Linear(hidden_size, rationale_dim)
        self.evidence_rationale_proj = nn.Linear(hidden_size, rationale_dim)
        self.policy_rationale_proj = nn.Linear(hidden_size, rationale_dim)
        protocol_dims = dict(PROTOCOL_HEAD_DIMS)
        if protocol_head_dims:
            protocol_dims.update({str(name): int(size) for name, size in protocol_head_dims.items()})
        self.protocol_heads = nn.ModuleDict({
            name: nn.Linear(hidden_size, size) for name, size in protocol_dims.items()
        })

    def forward(self, input_ids: Any, attention_mask: Any, **kwargs: Any) -> dict[str, Any]:
        output = self.backbone(input_ids=input_ids, attention_mask=attention_mask, **kwargs)
        token_embeddings = output.last_hidden_state
        mask = attention_mask.unsqueeze(-1).float()
        pooled = (token_embeddings * mask).sum(dim=1) / mask.sum(dim=1).clamp_min(1.0)
        pooled = self.dropout(pooled)
        rationale_projection = self.rationale_proj(pooled)
        return {
            INTERPERSONAL_AXIS: self.interpersonal_aggression(pooled).squeeze(-1),
            DECEPTION_AXIS: self.ideological_deception(pooled).squeeze(-1),
            STANCE_AXIS: self.stance(pooled),
            "fine_labels": self.fine_labels(pooled),
            "rationale_proj": rationale_projection,
            "harm_rationale_proj": getattr(self, "harm_rationale_proj", self.rationale_proj)(pooled),
            "evidence_rationale_proj": getattr(self, "evidence_rationale_proj", self.rationale_proj)(pooled),
            "policy_rationale_proj": getattr(self, "policy_rationale_proj", self.rationale_proj)(pooled),
            "protocol_logits": {
                name: head(pooled) for name, head in self.protocol_heads.items()
            },
            "pooled": pooled,
        }


def normalize_rationale_projection(value: Any) -> Any:
    """L2-normalize projected rationale vectors for cosine retrieval."""

    require_torch()
    return torch.nn.functional.normalize(value, dim=-1)


def predict_rationale_projection(
    model: Any,
    tokenizer: Any,
    texts: list[str],
    *,
    batch_size: int = 16,
    max_length: int = 256,
    device: str | None = None,
) -> np.ndarray:
    """Return normalized Student rationale projections for a list of texts."""

    require_torch()
    resolved_device = device or next(model.parameters()).device
    model.to(resolved_device)
    model.eval()
    rows = []
    safe_texts = [text if str(text).strip() else " " for text in texts]
    with torch.no_grad():
        for start in range(0, len(safe_texts), max(1, batch_size)):
            encoded = tokenizer(
                safe_texts[start : start + batch_size],
                padding=True,
                truncation=True,
                max_length=max_length,
                return_tensors="pt",
            )
            encoded = {key: value.to(resolved_device) for key, value in encoded.items()}
            projected = normalize_rationale_projection(model(**encoded)["rationale_proj"])
            rows.append(projected.detach().cpu().numpy().astype("float32"))
    return np.vstack(rows) if rows else np.zeros((0, 0), dtype="float32")


def masked_mean(losses: Any, mask: Any) -> Any:
    require_torch()
    mask = mask.float()
    return (losses * mask).sum() / mask.sum().clamp_min(1.0)


class TextifiedStudentLoss(nn.Module if nn is not None else object):
    """Task-masked SFT loss for the first-stage taxonomy Student."""

    def __init__(
        self,
        *,
        stance_weight: float = 0.1,
        fine_label_weight: float = 0.2,
        lrkd_weight: float = 0.0,
        harm_rationale_weight: float = 0.0,
        evidence_rationale_weight: float = 0.0,
        policy_rationale_weight: float = 0.0,
    ):
        require_torch()
        super().__init__()
        self.bce = nn.BCEWithLogitsLoss(reduction="none")
        self.ce = nn.CrossEntropyLoss(reduction="none")
        self.cosine = nn.CosineEmbeddingLoss(reduction="none")
        self.stance_weight = stance_weight
        self.fine_label_weight = fine_label_weight
        self.lrkd_weight = lrkd_weight
        self.harm_rationale_weight = harm_rationale_weight
        self.evidence_rationale_weight = evidence_rationale_weight
        self.policy_rationale_weight = policy_rationale_weight

    def forward(self, outputs: Mapping[str, Any], targets: Mapping[str, Any]) -> dict[str, Any]:
        interpersonal_loss = masked_mean(
            self.bce(outputs[INTERPERSONAL_AXIS], targets[INTERPERSONAL_AXIS]),
            targets[f"{INTERPERSONAL_AXIS}_mask"],
        )
        deception_loss = masked_mean(
            self.bce(outputs[DECEPTION_AXIS], targets[DECEPTION_AXIS]),
            targets[f"{DECEPTION_AXIS}_mask"],
        )
        stance_loss = masked_mean(
            self.ce(outputs[STANCE_AXIS], targets[STANCE_AXIS]),
            targets[f"{STANCE_AXIS}_mask"],
        )
        fine_loss_by_label = self.bce(outputs["fine_labels"], targets["fine_labels"]).mean(dim=1)
        fine_loss = masked_mean(fine_loss_by_label, targets["fine_labels_mask"])
        total = (
            interpersonal_loss
            + deception_loss
            + self.stance_weight * stance_loss
            + self.fine_label_weight * fine_loss
        )
        lrkd_loss = torch.zeros((), device=total.device)
        if (
            self.lrkd_weight > 0.0
            and "rationale_proj" in outputs
            and "teacher_vector" in targets
            and "teacher_vector_mask" in targets
        ):
            target_similarity = torch.ones(
                outputs["rationale_proj"].shape[0],
                device=outputs["rationale_proj"].device,
            )
            per_row_lrkd = self.cosine(
                outputs["rationale_proj"],
                targets["teacher_vector"],
                target_similarity,
            )
            lrkd_loss = masked_mean(per_row_lrkd, targets["teacher_vector_mask"])
            total = total + self.lrkd_weight * lrkd_loss
        rationale_losses: dict[str, Any] = {}
        rationale_specs = (
            ("harm_rationale_proj", "harm_teacher_vector", "harm_teacher_vector_mask", self.harm_rationale_weight),
            ("evidence_rationale_proj", "evidence_teacher_vector", "evidence_teacher_vector_mask", self.evidence_rationale_weight),
            ("policy_rationale_proj", "policy_teacher_vector", "policy_teacher_vector_mask", self.policy_rationale_weight),
        )
        for output_key, target_key, mask_key, weight in rationale_specs:
            loss = torch.zeros((), device=total.device)
            if weight > 0.0 and output_key in outputs and target_key in targets and mask_key in targets:
                target_similarity = torch.ones(
                    outputs[output_key].shape[0],
                    device=outputs[output_key].device,
                )
                per_row = self.cosine(outputs[output_key], targets[target_key], target_similarity)
                loss = masked_mean(per_row, targets[mask_key])
                total = total + weight * loss
            rationale_losses[output_key] = loss
        return {
            "total_loss": total,
            INTERPERSONAL_AXIS: interpersonal_loss,
            DECEPTION_AXIS: deception_loss,
            STANCE_AXIS: stance_loss,
            "fine_labels": fine_loss,
            "lrkd": lrkd_loss,
            **rationale_losses,
        }
