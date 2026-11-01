"""Approved dual-axis Student bundle runtime for analyst-facing review."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


STUDENT_BUNDLE_SCHEMA = "cogguard.review.student_bundle.v1"
HARM_AXIS = "interpersonal_harm"
CLAIM_AXIS = "claim_deception"

__all__ = [
    "CLAIM_AXIS",
    "HARM_AXIS",
    "STUDENT_BUNDLE_SCHEMA",
    "build_student_bundle_verdict",
]


@dataclass(frozen=True, slots=True)
class _LoadedHarmModel:
    model: Any
    tokenizer: Any
    threshold: float
    max_length: int
    device: str


_HARM_MODEL_CACHE: dict[str, _LoadedHarmModel] = {}


def build_student_bundle_verdict(case: Mapping[str, Any]) -> dict[str, Any]:
    """Run only approved bundle artifacts; never substitute a heuristic verdict."""

    normalized = _normalize_case(case)
    active_model = normalized["active_model"]
    bundle = _bundle_config(active_model)
    if bundle is None:
        return _unconfigured_verdict(
            normalized,
            reason="No approved dual-axis Student bundle is active.",
        )

    harm = _harm_axis(normalized, bundle)
    claim = _claim_axis(bundle)
    status = "completed" if harm["status"] == "completed" else harm["status"]
    return {
        "technology": "student",
        "schema": STUDENT_BUNDLE_SCHEMA,
        "status": status,
        "verdict_type": "preliminary",
        "verdict_id": _verdict_id(normalized),
        "snapshot_id": normalized["snapshot_id"],
        "event_id": normalized["event_id"],
        "axes": {HARM_AXIS: harm, CLAIM_AXIS: claim},
        # Legacy review-case projection consumes this top-level preliminary
        # conclusion. Product clients read the explicit axes above instead.
        "label": harm.get("conclusion"),
        "score": harm.get("risk_score"),
        "risk_level": _risk_level(harm.get("risk_score")),
        "abstain": harm["status"] != "completed",
        "review_required": harm["status"] != "completed",
        "claimability": "claimable" if status == "completed" else "non_claimable",
        "fallback": False,
        "capability_boundary": {
            "canonical_allowed": False,
            "analyst_approval_required": True,
            "claim_axis_state": claim["status"],
            "raw_media_understanding": False,
        },
    }


def _harm_axis(case: dict[str, Any], bundle: dict[str, Any]) -> dict[str, Any]:
    config = bundle.get(HARM_AXIS)
    if not isinstance(config, Mapping) or str(config.get("status") or "configured") != "configured":
        return _unconfigured_axis("The harm Student artifact is not configured in the active bundle.")
    texts = _case_texts(case)
    if not texts:
        return _failed_axis("No text is available in this EventSnapshot.")
    try:
        loaded = _load_harm_model(config)
        probability = _predict_harm_probability(loaded, texts)
    except Exception as exc:  # Runtime failures must remain visible to analysts.
        return _failed_axis(f"The approved harm Student could not run: {type(exc).__name__}.")
    conclusion = "harmful" if probability >= loaded.threshold else "non_harmful"
    return {
        "task": HARM_AXIS,
        "status": "completed",
        "conclusion": conclusion,
        "risk_score": round(probability, 6),
        "threshold": round(loaded.threshold, 6),
        "rationale": _harm_rationale(conclusion, probability),
    }


def _claim_axis(bundle: dict[str, Any]) -> dict[str, Any]:
    config = bundle.get(CLAIM_AXIS)
    if not isinstance(config, Mapping) or str(config.get("status") or "unconfigured") != "configured":
        reason = "The claim-deception Student is awaiting a trained, calibrated, approved Weibo21 artifact."
        if isinstance(config, Mapping) and str(config.get("reason") or "").strip():
            reason = str(config["reason"]).strip()[:400]
        return {
            "task": CLAIM_AXIS,
            "status": "unconfigured",
            "conclusion": None,
            "risk_score": None,
            "threshold": None,
            "rationale": reason,
        }
    return _failed_axis("Configured claim-deception execution is not available in this deployment.", task=CLAIM_AXIS)


def _load_harm_model(config: Mapping[str, Any]) -> _LoadedHarmModel:
    checkpoint_path = Path(str(config.get("checkpoint_path") or "").strip())
    if not checkpoint_path.is_file():
        raise FileNotFoundError("approved checkpoint is unavailable")
    cache_key = str(checkpoint_path.resolve())
    cached = _HARM_MODEL_CACHE.get(cache_key)
    if cached is not None:
        return cached

    import torch
    from transformers import AutoTokenizer

    from app.core.review.taxonomy_student import XLMRTextifiedReviewStudent

    payload = torch.load(checkpoint_path, map_location="cpu")
    if not isinstance(payload, dict) or payload.get("schema") != "hatecot-lrkd-student-checkpoint-v1":
        raise ValueError("unsupported Student checkpoint schema")
    model_config = payload.get("model_config") if isinstance(payload.get("model_config"), dict) else {}
    model_name = str(config.get("model_name") or model_config.get("backbone") or "").strip()
    if not model_name:
        raise ValueError("approved bundle is missing the XLM-R backbone name")
    cache_dir = str(config.get("hf_cache_dir") or model_config.get("hf_cache_dir") or "").strip() or None
    local_files_only = not bool(config.get("allow_model_download", False))
    device = _device_name(config)
    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        local_files_only=local_files_only,
        cache_dir=cache_dir,
    )
    model = XLMRTextifiedReviewStudent(
        model_name=model_name,
        rationale_dim=int(model_config.get("rationale_dim") or 768),
        local_files_only=local_files_only,
        cache_dir=cache_dir,
    )
    model.load_state_dict(payload["model_state_dict"], strict=True)
    model.to(device)
    model.eval()
    loaded = _LoadedHarmModel(
        model=model,
        tokenizer=tokenizer,
        threshold=float(config.get("threshold") or payload.get("decision_threshold") or 0.5),
        max_length=int(config.get("max_length") or model_config.get("max_length") or 128),
        device=device,
    )
    _HARM_MODEL_CACHE[cache_key] = loaded
    return loaded


def _predict_harm_probability(loaded: _LoadedHarmModel, texts: list[str]) -> float:
    import torch

    encoded = loaded.tokenizer(
        texts,
        padding=True,
        truncation=True,
        max_length=loaded.max_length,
        return_tensors="pt",
    )
    encoded = {key: value.to(loaded.device) for key, value in encoded.items()}
    with torch.no_grad():
        logits = loaded.model(**encoded)["interpersonal_aggression"]
        probabilities = torch.sigmoid(logits).detach().cpu().tolist()
    return float(sum(float(value) for value in probabilities) / max(len(probabilities), 1))


def _bundle_config(active_model: Mapping[str, Any]) -> dict[str, Any] | None:
    if str(active_model.get("status") or "") != "active":
        return None
    config = active_model.get("config")
    if not isinstance(config, Mapping) or config.get("schema") != STUDENT_BUNDLE_SCHEMA:
        return None
    return dict(config)


def _normalize_case(case: Mapping[str, Any]) -> dict[str, Any]:
    options = case.get("options") if isinstance(case.get("options"), Mapping) else {}
    active_model = options.get("active_model") if isinstance(options.get("active_model"), Mapping) else {}
    return {
        "snapshot_id": str(case.get("snapshot_id") or ""),
        "event_id": str(case.get("event_id") or ""),
        "posts": [dict(row) for row in case.get("posts") or [] if isinstance(row, Mapping)],
        "comments": [dict(row) for row in case.get("comments") or [] if isinstance(row, Mapping)],
        "active_model": dict(active_model),
    }


def _case_texts(case: Mapping[str, Any]) -> list[str]:
    texts: list[str] = []
    for row in [*case["posts"], *case["comments"]]:
        value = next((row.get(key) for key in ("content", "text", "title") if str(row.get(key) or "").strip()), "")
        text = str(value).strip()
        if text:
            texts.append(text)
    return texts[:64]


def _unconfigured_verdict(case: Mapping[str, Any], *, reason: str) -> dict[str, Any]:
    harm = _unconfigured_axis(reason)
    return {
        "technology": "student",
        "schema": STUDENT_BUNDLE_SCHEMA,
        "status": "unconfigured",
        "verdict_type": "preliminary",
        "verdict_id": _verdict_id(case),
        "snapshot_id": case["snapshot_id"],
        "event_id": case["event_id"],
        "axes": {HARM_AXIS: harm, CLAIM_AXIS: _claim_axis({})},
        "label": None,
        "score": None,
        "abstain": True,
        "review_required": True,
        "claimability": "non_claimable",
        "fallback": False,
        "capability_boundary": {"canonical_allowed": False, "analyst_approval_required": True},
    }


def _unconfigured_axis(reason: str) -> dict[str, Any]:
    return {
        "task": HARM_AXIS,
        "status": "unconfigured",
        "conclusion": None,
        "risk_score": None,
        "threshold": None,
        "rationale": reason[:400],
    }


def _failed_axis(reason: str, *, task: str = HARM_AXIS) -> dict[str, Any]:
    return {
        "task": task,
        "status": "failed",
        "conclusion": None,
        "risk_score": None,
        "threshold": None,
        "rationale": reason[:400],
    }


def _device_name(config: Mapping[str, Any]) -> str:
    preferred = str(config.get("device") or "auto").strip().lower()
    if preferred not in {"", "auto"}:
        return preferred
    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


def _harm_rationale(conclusion: str, probability: float) -> str:
    if conclusion == "harmful":
        return "内容文本与已批准的危害识别模型模式一致，建议结合人工审计确认处置。"
    return "当前文本未达到已批准危害识别模型的风险阈值，仍不替代人工复核。"


def _risk_level(score: Any) -> str:
    if not isinstance(score, (float, int)):
        return ""
    if score >= 0.8:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def _verdict_id(case: Mapping[str, Any]) -> str:
    return f"student_bundle_{str(case.get('snapshot_id') or 'unknown')[:96]}"
