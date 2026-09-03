"""Checkpoint-gated XLM-R runtime for Student Review."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Protocol

import torch
from torch import nn
from transformers import AutoModel, AutoTokenizer


STUDENT_MODEL_VERSION = "review-student-xlmr-v3"
STANCE_LABELS = ("support", "deny", "query")
ARCHITECTURE = {
    "post_encoder": "xlm-roberta-base",
    "input": "post_text_claim_context_decodable_evidence",
    "prediction_heads": ["attack_hate_offense", "misinfo_claim_risk", "stance"],
    "distillation_head": "rationale_proj",
    "hardcase_routing": "external_uncertainty_and_governance_policy",
    "distillation_losses": ["gold_bce", "teacher_soft_bce", "stance_ce", "latent_cosine"],
}


@dataclass(frozen=True, slots=True)
class ReviewStudentInput:
    post_text: str = ""
    claim_context: str = ""
    hashtags: str = ""
    ocr_text: str = ""
    asr_transcript: str = ""
    caption: str = ""

    @classmethod
    def from_post(cls, post: Mapping[str, Any]) -> "ReviewStudentInput":
        return cls(
            post_text=_first_text(post, ("content", "text", "title")),
            claim_context=_flatten_text(post.get("claim_context") or post.get("claim")),
            hashtags=_flatten_text(post.get("hashtags")),
            ocr_text=_flatten_text(post.get("ocr_text") or post.get("ocr")),
            asr_transcript=_flatten_text(post.get("asr_transcript") or post.get("asr")),
            caption=_flatten_text(post.get("caption") or post.get("alt_text")),
        )

    def serialize(self) -> str:
        parts = (
            ("TEXT", self.post_text),
            ("CLAIM", self.claim_context),
            ("HASHTAGS", self.hashtags),
            ("OCR", self.ocr_text),
            ("ASR", self.asr_transcript),
            ("CAPTION", self.caption),
        )
        return " ".join(f"[{label}] {value}" for label, value in parts if value)


class XLMRReviewStudent(nn.Module):
    """Shared encoder with three prediction heads and one distillation head."""

    def __init__(
        self,
        *,
        backbone: str = "xlm-roberta-base",
        encoder: nn.Module | None = None,
        hidden_size: int | None = None,
        stance_count: int = len(STANCE_LABELS),
        rationale_dim: int = 768,
    ) -> None:
        super().__init__()
        self.encoder = encoder or AutoModel.from_pretrained(backbone)
        resolved_hidden_size = hidden_size or int(getattr(self.encoder.config, "hidden_size"))
        self.attack_hate_offense = nn.Linear(resolved_hidden_size, 1)
        self.misinfo_claim_risk = nn.Linear(resolved_hidden_size, 1)
        self.stance = nn.Linear(resolved_hidden_size, stance_count)
        self.rationale_proj = nn.Linear(resolved_hidden_size, rationale_dim)

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> dict[str, torch.Tensor]:
        encoded = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        pooled = encoded.last_hidden_state[:, 0, :]
        return {
            "attack_hate_offense": self.attack_hate_offense(pooled).squeeze(-1),
            "misinfo_claim_risk": self.misinfo_claim_risk(pooled).squeeze(-1),
            "stance": self.stance(pooled),
            "rationale_proj": self.rationale_proj(pooled),
        }


@dataclass(frozen=True, slots=True)
class StudentCheckpoint:
    checkpoint_path: Path
    manifest_path: Path
    manifest: dict[str, Any]
    sha256: str
    version: str


class StudentPredictor(Protocol):
    def predict(self, inputs: Sequence[ReviewStudentInput]) -> list[dict[str, Any]]: ...


class TorchStudentPredictor:
    def __init__(self, descriptor: StudentCheckpoint) -> None:
        manifest = descriptor.manifest
        backbone = str(manifest.get("backbone") or "xlm-roberta-base")
        self._device = torch.device(str(manifest.get("device") or "cpu"))
        self._tokenizer = AutoTokenizer.from_pretrained(backbone)
        self._model = XLMRReviewStudent(
            backbone=backbone,
            stance_count=int(manifest.get("stance_count") or len(STANCE_LABELS)),
            rationale_dim=int(manifest.get("rationale_dim") or 768),
        ).to(self._device)
        payload = torch.load(descriptor.checkpoint_path, map_location=self._device, weights_only=True)
        state_dict = payload.get("state_dict") if isinstance(payload, Mapping) else payload
        if not isinstance(state_dict, Mapping):
            raise ValueError("Student checkpoint does not contain a state_dict")
        self._model.load_state_dict(state_dict, strict=True)
        self._model.eval()

    def predict(self, inputs: Sequence[ReviewStudentInput]) -> list[dict[str, Any]]:
        if not inputs:
            return []
        encoded = self._tokenizer(
            [item.serialize() for item in inputs],
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        ).to(self._device)
        with torch.no_grad():
            outputs = self._model(
                input_ids=encoded["input_ids"],
                attention_mask=encoded["attention_mask"],
            )
        attack = torch.sigmoid(outputs["attack_hate_offense"]).cpu().tolist()
        misinfo = torch.sigmoid(outputs["misinfo_claim_risk"]).cpu().tolist()
        stance = torch.softmax(outputs["stance"], dim=-1).cpu().tolist()
        return [
            {
                "attack_hate_offense": float(attack[index]),
                "misinfo_claim_risk": float(misinfo[index]),
                "stance": [float(value) for value in stance[index]],
            }
            for index in range(len(inputs))
        ]


class StudentRuntime:
    """Synchronous Student Review interface used by the Analysis Run adapter."""

    def __init__(
        self,
        *,
        predictor_factory: Callable[[StudentCheckpoint], StudentPredictor] = TorchStudentPredictor,
    ) -> None:
        self._predictor_factory = predictor_factory

    def predict_sync(self, case: dict[str, Any]) -> dict[str, Any]:
        normalized = _normalize_case(case)
        if not normalized["posts"]:
            return _shadow_verdict(normalized, model_status="shadow_untrained", reason="No posts are available.")

        active_model = normalized["options"].get("active_model")
        try:
            checkpoint = _resolve_active_checkpoint(active_model)
        except ValueError as exc:
            status = "shadow_untrained" if not active_model else "checkpoint_incompatible"
            return _shadow_verdict(normalized, model_status=status, reason=str(exc))

        inputs = [ReviewStudentInput.from_post(post) for post in normalized["posts"]]
        try:
            predictions = self._predictor_factory(checkpoint).predict(inputs)
            result = _aggregate_predictions(predictions)
        except Exception as exc:
            return _shadow_verdict(
                normalized,
                model_status="checkpoint_incompatible",
                reason=f"Student checkpoint inference failed: {exc}",
            )

        score = result["score"]
        confidence = result["confidence"]
        label = _label(score, confidence)
        active_learning = build_active_learning_signal(
            score=score,
            confidence=confidence,
            case=normalized,
            teacher_reference=normalized["options"].get("teacher_reference"),
        )
        return _verdict(
            normalized,
            model_status="checkpoint_active",
            label=label,
            score=score,
            confidence=confidence,
            abstain=label == "uncertain",
            active_learning=active_learning,
            checkpoint={
                "status": "active",
                "path": str(checkpoint.checkpoint_path),
                "manifest_path": str(checkpoint.manifest_path),
                "sha256": checkpoint.sha256,
                "version": checkpoint.version,
            },
            signals={
                "axes": result["axes"],
                "stance": result["stance"],
                "input_count": len(inputs),
            },
        )


def build_active_learning_signal(
    *,
    score: float,
    confidence: float,
    case: Mapping[str, Any],
    teacher_reference: Any = None,
) -> dict[str, Any]:
    reasons: list[str] = []
    uncertainty = 1.0 - abs(float(score) - 0.5) * 2.0
    if uncertainty >= 0.45:
        reasons.append("uncertainty")
    teacher_disagreement = 0.0
    if isinstance(teacher_reference, Mapping):
        teacher_label = str(teacher_reference.get("label") or teacher_reference.get("decision") or "")
        if teacher_label and teacher_label not in {_label(score, confidence), "uncertain"}:
            teacher_disagreement = 1.0
            reasons.append("teacher_student_disagreement")
    if len(list(case.get("platforms") or [])) > 1:
        reasons.append("diversity")
    ood = _ood_score(case)
    drift = _drift_score(case)
    if ood >= 0.5:
        reasons.append("ood")
    if drift >= 0.5:
        reasons.append("drift")
    if _random_audit_bucket(case) == 0:
        reasons.append("random_audit")
    priority = min(
        1.0,
        0.38 * uncertainty
        + 0.25 * teacher_disagreement
        + 0.15 * ood
        + 0.12 * drift
        + (0.1 if "diversity" in reasons else 0.0)
        + (0.03 if "random_audit" in reasons else 0.0),
    )
    return {
        "priority": round(priority, 6),
        "reasons": sorted(set(reasons)),
        "policy": {
            "feedback_threshold": 200,
            "minimum_retrain_interval_days": 7,
            "random_audit_rate": 0.01,
            "activation_requires_dual_approval": True,
        },
    }


def build_distillation_plan(*, teacher_traces: list[Any], approved_verdicts: list[Any]) -> dict[str, Any]:
    trace_count = sum(isinstance(row, Mapping) for row in teacher_traces)
    approved_count = sum(isinstance(row, Mapping) for row in approved_verdicts)
    return {
        "status": "ready_for_candidate_training" if approved_count >= 200 else "insufficient_approved_feedback",
        "teacher_trace_count": trace_count,
        "approved_verdict_count": approved_count,
        "losses": ARCHITECTURE["distillation_losses"],
        "student_deploy_gate": {
            "teacher_macro_f1_gap_max": 0.03,
            "ece_max": 0.08,
            "single_post_p95_seconds_on_8gb_gpu": 2.0,
        },
    }


def _resolve_active_checkpoint(value: Any) -> StudentCheckpoint:
    if not isinstance(value, Mapping) or str(value.get("status") or "") != "active":
        raise ValueError("No approved active Student checkpoint is configured")
    if str(value.get("technology") or "review_student") != "review_student":
        raise ValueError("Active model technology is not review_student")

    artifact_path = Path(str(value.get("artifact_uri") or "")).expanduser()
    checkpoint_value = value.get("checkpoint_path")
    checkpoint_path = Path(str(checkpoint_value)).expanduser() if checkpoint_value else artifact_path
    if artifact_path.is_dir() and not checkpoint_value:
        checkpoint_path = artifact_path / "checkpoint.pt"
    manifest_path = artifact_path / "manifest.json" if artifact_path.is_dir() else checkpoint_path.parent / "manifest.json"
    if not checkpoint_path.is_file() or not manifest_path.is_file():
        raise ValueError("Active Student checkpoint or manifest is missing")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Student checkpoint manifest is invalid") from exc
    if not isinstance(manifest, dict) or str(manifest.get("technology") or "") != "review_student":
        raise ValueError("Student checkpoint manifest technology is incompatible")
    expected = str(value.get("artifact_hash") or "").strip().lower()
    actual = _sha256_file(checkpoint_path)
    if len(expected) != 64 or expected != actual:
        raise ValueError("Student checkpoint SHA-256 does not match the active model")
    return StudentCheckpoint(
        checkpoint_path=checkpoint_path.resolve(),
        manifest_path=manifest_path.resolve(),
        manifest=manifest,
        sha256=actual,
        version=str(value.get("version") or manifest.get("version") or "unknown"),
    )


def _aggregate_predictions(predictions: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not predictions:
        raise ValueError("Student predictor returned no outputs")
    attack = [_probability(row.get("attack_hate_offense")) for row in predictions]
    misinfo = [_probability(row.get("misinfo_claim_risk")) for row in predictions]
    stance_rows = [row.get("stance") for row in predictions]
    if any(not isinstance(row, Sequence) or isinstance(row, (str, bytes)) for row in stance_rows):
        raise ValueError("Student predictor returned an invalid stance output")
    stance_width = len(stance_rows[0])
    if stance_width != len(STANCE_LABELS) or any(len(row) != stance_width for row in stance_rows):
        raise ValueError("Student predictor returned incompatible stance dimensions")
    stance = [mean(_probability(row[index]) for row in stance_rows) for index in range(stance_width)]
    attack_score = mean(attack)
    misinfo_score = mean(misinfo)
    score = max(attack_score, misinfo_score)
    return {
        "score": round(score, 6),
        "confidence": round(max(score, 1.0 - score), 6),
        "axes": {
            "attack_hate_offense": round(attack_score, 6),
            "misinfo_claim_risk": round(misinfo_score, 6),
        },
        "stance": {label: round(stance[index], 6) for index, label in enumerate(STANCE_LABELS)},
    }


def _shadow_verdict(case: Mapping[str, Any], *, model_status: str, reason: str) -> dict[str, Any]:
    active_learning = build_active_learning_signal(score=0.5, confidence=0.0, case=case)
    return _verdict(
        case,
        model_status=model_status,
        label="uncertain",
        score=0.5,
        confidence=0.0,
        abstain=True,
        active_learning=active_learning,
        checkpoint={"status": model_status, "path": ""},
        signals={"axes": {}, "stance": {}, "input_count": len(case.get("posts") or [])},
        reason=reason,
    )


def _verdict(
    case: Mapping[str, Any],
    *,
    model_status: str,
    label: str,
    score: float,
    confidence: float,
    abstain: bool,
    active_learning: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    signals: Mapping[str, Any],
    reason: str | None = None,
) -> dict[str, Any]:
    review_required = bool(abstain or active_learning.get("priority", 0.0) >= 0.35)
    result = {
        "technology": "student",
        "schema": "cogguard.review.review_verdict.v2",
        "status": "ok",
        "verdict_type": "preliminary",
        "verdict_id": _verdict_id(case),
        "snapshot_id": case.get("snapshot_id"),
        "event_id": case.get("event_id"),
        "platforms": list(case.get("platforms") or []),
        "model_version": STUDENT_MODEL_VERSION,
        "model_status": model_status,
        "label": label,
        "score": score,
        "confidence": confidence,
        "risk_level": "unknown" if abstain else ("high" if score >= 0.72 else "medium" if score >= 0.5 else "low"),
        "abstain": abstain,
        "review_required": review_required,
        "review_reason": sorted(set(active_learning.get("reasons") or []) | ({"student_checkpoint_not_active"} if model_status != "checkpoint_active" else set())),
        "architecture": ARCHITECTURE,
        "checkpoint": dict(checkpoint),
        "distillation": build_distillation_plan(
            teacher_traces=list(case.get("options", {}).get("teacher_traces") or []),
            approved_verdicts=list(case.get("options", {}).get("approved_verdicts") or []),
        ),
        "signals": {**dict(signals), "active_learning": dict(active_learning)},
        "evidence": {
            "capability_boundary": {
                "runtime": "system/runtimes/review_student",
                "model_status": model_status,
                "canonical_allowed": False,
                "reason": "Only an analyst-confirmed decision can become canonical.",
            }
        },
    }
    if reason:
        result["reason"] = reason
    return result


def _normalize_case(case: Mapping[str, Any]) -> dict[str, Any]:
    posts = [dict(row) for row in case.get("posts") or [] if isinstance(row, Mapping)]
    comments = [dict(row) for row in case.get("comments") or [] if isinstance(row, Mapping)]
    platforms = [str(value) for value in case.get("platforms") or [] if str(value).strip()]
    if not platforms:
        platforms = sorted(
            {
                str(row.get("platform") or "").strip()
                for row in posts + comments
                if str(row.get("platform") or "").strip()
            }
        )
    return {
        "snapshot_id": str(case.get("snapshot_id") or ""),
        "event_id": str(case.get("event_id") or ""),
        "platforms": platforms,
        "posts": posts,
        "comments": comments,
        "relationships": [dict(row) for row in case.get("relationships") or [] if isinstance(row, Mapping)],
        "quality_report": dict(case.get("quality_report") or {}),
        "options": dict(case.get("options") or {}),
    }


def _label(score: float, confidence: float) -> str:
    if confidence < 0.58:
        return "uncertain"
    return "harmful" if score >= 0.5 else "non_harmful"


def _probability(value: Any) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise ValueError("Student predictor probabilities must be finite values in [0, 1]")
    return number


def _ood_score(case: Mapping[str, Any]) -> float:
    platforms = list(case.get("platforms") or [])
    unknown = [platform for platform in platforms if platform not in {"weibo", "douyin", "xhs", "news"}]
    return min(1.0, len(unknown) / max(len(platforms), 1))


def _drift_score(case: Mapping[str, Any]) -> float:
    quality = dict(case.get("quality_report") or {})
    issues = list(quality.get("issues") or [])
    missing = int(quality.get("missing_timestamps") or 0) + int(quality.get("missing_authors") or 0)
    return min(1.0, 0.1 * len(issues) + 0.02 * missing)


def _random_audit_bucket(case: Mapping[str, Any]) -> int:
    digest = hashlib.sha256(_json(case).encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


def _verdict_id(case: Mapping[str, Any]) -> str:
    return f"student_{hashlib.sha256(_json(case).encode('utf-8')).hexdigest()[:24]}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _first_text(row: Mapping[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        value = _flatten_text(row.get(key))
        if value:
            return value
    return ""


def _flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return " ".join(value.split()).strip()
    if isinstance(value, Mapping):
        return " ".join(filter(None, (_flatten_text(item) for item in value.values())))
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return " ".join(filter(None, (_flatten_text(item) for item in value)))
    return " ".join(str(value).split()).strip()


__all__ = [
    "ReviewStudentInput",
    "STUDENT_MODEL_VERSION",
    "StudentCheckpoint",
    "StudentRuntime",
    "TorchStudentPredictor",
    "XLMRReviewStudent",
    "build_active_learning_signal",
    "build_distillation_plan",
]
