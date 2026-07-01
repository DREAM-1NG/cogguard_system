"""Post-level multimodal, claim-conditioned semantic assessment for KT3.

This module implements a practical inference scaffold aligned with the
literature direction already adopted in the KT3 documents:

- multimodal normalization over text, emoji, OCR, ASR, and media metadata
- claim-conditioned stance inference inspired by rumor / claim verification work
- representation-based harmfulness scoring via semantic prototypes rather than
  keyword-only matching

The online path stays lightweight and explainable. Richer LLM / agent layers are
still expected to act as teacher, reviewer, or explainer components around this
deployable core.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any
import re
from urllib.parse import unquote, urlparse

import numpy as np

try:
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover - dependency/runtime fallback
    SentenceTransformer = None


EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MAX_EVIDENCE_POSTS = 20
TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+")

IMAGE_EXTENSIONS = {".bmp", ".gif", ".jpg", ".jpeg", ".png", ".svg", ".webp"}
VIDEO_EXTENSIONS = {".avi", ".mkv", ".mov", ".mp4", ".m3u8", ".webm"}

EMOJI_TEXT = {
    "😂": "mocking laughter",
    "🤣": "mocking laughter",
    "😡": "anger outrage",
    "🤬": "abusive anger",
    "😭": "distress",
    "🔥": "intensification",
    "💥": "explosive emphasis",
    "👍": "approval support",
    "👎": "rejection disapproval",
    "🙏": "appeal pleading",
    "❓": "question uncertainty",
    "❗": "strong emphasis",
}

STANCE_PROTOTYPES = {
    "support": (
        "The post endorses, repeats, legitimizes, or amplifies the referenced claim."
    ),
    "deny": (
        "The post refutes, corrects, debunks, or disputes the referenced claim."
    ),
    "query": (
        "The post questions, doubts, or asks whether the referenced claim is true."
    ),
    "neutral": (
        "The post mentions the referenced claim without a clear stance or judgment."
    ),
}

HARM_TYPE_PROTOTYPES = {
    "misinformation": (
        "The post spreads, amplifies, or legitimizes misleading, false, deceptive, "
        "or unverified claims and narratives."
    ),
    "hate_harassment": (
        "The post attacks, humiliates, threatens, or dehumanizes a person or group, "
        "including dogwhistles, abuse, or targeted ridicule."
    ),
    "targeted_smear": (
        "The post uses insinuation, selective framing, reputational attack, or "
        "delegitimizing narratives against a person, institution, or community."
    ),
    "incitement_mobilization": (
        "The post encourages harassment, brigading, exclusion, intimidation, or "
        "collective action against a target."
    ),
    "manipulative_amplification": (
        "The post seeks strategic amplification, mass reposting, synthetic virality, "
        "or coordinated attention shaping."
    ),
}

NON_HARMFUL_PROTOTYPE = (
    "The post is benign discussion, ordinary reporting, neutral commentary, or "
    "constructive correction without abusive or manipulative intent."
)

MULTIMODAL_METHOD_TRACE = [
    {
        "paper": "RGCL, ACL 2024",
        "transfer": "retrieval-aware multimodal harmfulness: keep per-modality evidence and nearest claim context explicit",
    },
    {
        "paper": "MOCHEG, SIGIR 2023",
        "transfer": "claim-conditioned multimodal fact-checking with evidence and explanation fields",
    },
    {
        "paper": "FACTIFY3M, EMNLP 2023",
        "transfer": "5W-style explainability cues are represented as evidence fields rather than hidden features",
    },
    {
        "paper": "FakeSV, AAAI 2023",
        "transfer": "short-video support uses ASR/OCR/caption/social context before full video encoders are available",
    },
]

MODALITY_FUSION_WEIGHTS = {
    "text": 1.0,
    "ocr": 0.9,
    "asr": 0.85,
    "caption_media": 0.75,
    "emoji_hashtag": 0.55,
}

POST_VIEW_ORDER = ("tweet", "meme", "img", "video")

POST_VIEW_DETECTORS = {
    "tweet": "D_tweet",
    "meme": "D_meme",
    "img": "D_img",
    "video": "D_video",
}

POST_VIEW_FUSION_WEIGHTS = {
    "tweet": 1.0,
    "meme": 1.15,
    "img": 0.9,
    "video": 1.1,
}

POST_VIEW_THRESHOLDS = {
    "harmful": 0.58,
    "non_harmful": 0.48,
}


@dataclass(slots=True)
class NormalizedPost:
    post_id: str
    author_id: str
    author_name: str
    platform: str
    event_id: str | None
    text: str
    hashtags: list[str] = field(default_factory=list)
    media_urls: list[str] = field(default_factory=list)
    emoji_text: str = ""
    ocr_text: str = ""
    asr_text: str = ""
    media_text: str = ""
    media_context_text: str = ""
    media_metadata_text: str = ""
    modalities: list[str] = field(default_factory=list)
    semantic_text: str = ""


@dataclass(slots=True)
class ClaimCandidate:
    claim_id: str
    claim_text: str
    share_count: int = 0
    account_count: int = 0
    first_share: str = ""
    source: str = "propagation"


@lru_cache(maxsize=1)
def _load_embedding_model() -> Any | None:
    if SentenceTransformer is None:
        return None
    try:
        return SentenceTransformer(EMBEDDING_MODEL_NAME)
    except Exception:
        return None


class SimilarityEngine:
    """Semantic similarity with embedding-first and lexical fallback behavior."""

    def __init__(self, prefer_embeddings: bool = True) -> None:
        self.model = _load_embedding_model() if prefer_embeddings else None
        self.backend = EMBEDDING_MODEL_NAME if self.model is not None else "lexical-fallback"
        self._cache: dict[str, np.ndarray] = {}

    def _encode(self, text: str) -> np.ndarray:
        if text not in self._cache:
            vector = self.model.encode(text, normalize_embeddings=True)
            self._cache[text] = np.asarray(vector, dtype=float)
        return self._cache[text]

    def score(self, left: str, right: str) -> float:
        if not left or not right:
            return 0.0
        if self.model is not None:
            try:
                raw = float(np.dot(self._encode(left), self._encode(right)))
                return round(max(0.0, min(1.0, (raw + 1.0) / 2.0)), 4)
            except Exception:
                self.model = None
                self.backend = "lexical-fallback"
        return round(_lexical_similarity(left, right), 4)


def normalize_multimodal_post(post: dict[str, Any]) -> NormalizedPost:
    """Fuse crawled multimodal fields into one post-level semantic representation."""
    content = _clean_text(post.get("content", ""))
    hashtags = [str(tag).strip() for tag in (post.get("hashtags") or []) if str(tag).strip()]
    media_urls = [str(url).strip() for url in (post.get("media_urls") or []) if str(url).strip()]
    raw_data = post.get("raw_data") or {}

    emoji_text = _extract_emoji_text(content)
    ocr_text = " ".join(_collect_raw_text_values(raw_data, {"ocr", "image_text", "screen_text"}))
    asr_text = " ".join(_collect_raw_text_values(raw_data, {"asr", "speech", "transcript", "subtitle"}))
    media_context_parts = _collect_raw_text_values(
        raw_data,
        {"caption", "summary", "description", "alt", "frame"},
    )
    media_metadata_parts = _describe_media_urls(media_urls)
    media_text = " ".join(_dedupe_strings([*media_context_parts, *media_metadata_parts]))

    modalities = ["text"]
    if hashtags:
        modalities.append("hashtags")
    if emoji_text:
        modalities.append("emoji")
    if ocr_text:
        modalities.append("ocr")
    if asr_text:
        modalities.append("asr")
    if media_text:
        modalities.append("media")

    parts = [content]
    if hashtags:
        parts.append("hashtags: " + " ".join(hashtags))
    if emoji_text:
        parts.append("emoji cues: " + emoji_text)
    if ocr_text:
        parts.append("ocr text: " + ocr_text)
    if asr_text:
        parts.append("asr text: " + asr_text)
    if media_text:
        parts.append("media context: " + media_text)

    return NormalizedPost(
        post_id=str(post.get("post_id", "") or ""),
        author_id=str(post.get("author_id", "") or ""),
        author_name=str(post.get("author_name", "") or ""),
        platform=str(post.get("platform", "") or ""),
        event_id=post.get("event_id"),
        text=content,
        hashtags=hashtags,
        media_urls=media_urls,
        emoji_text=emoji_text,
        ocr_text=ocr_text,
        asr_text=asr_text,
        media_text=media_text,
        media_context_text=" ".join(_dedupe_strings(media_context_parts)),
        media_metadata_text=" ".join(_dedupe_strings(media_metadata_parts)),
        modalities=modalities,
        semantic_text=" ".join(part for part in parts if part).strip(),
    )


def build_claim_candidates(prop_data: dict[str, Any]) -> list[ClaimCandidate]:
    """Build claim candidates from propagation outputs plus supporting snippets."""
    evidence_map = {
        str(chain.get("claim_id", "")): chain
        for chain in (prop_data.get("evidence_chains") or [])
        if str(chain.get("claim_id", "")).strip()
    }
    claim_candidates: list[ClaimCandidate] = []
    for claim in prop_data.get("claims") or []:
        claim_id = str(claim.get("object_id") or claim.get("claim_id") or "").strip()
        if not claim_id:
            continue
        chain = evidence_map.get(claim_id, {})
        supporting_posts = chain.get("supporting_posts") or []
        support_snippets = [
            _clean_text(post.get("content", ""))[:160]
            for post in supporting_posts[:3]
            if _clean_text(post.get("content", ""))
        ]
        claim_text_parts = [_describe_claim_anchor(claim_id), *support_snippets]
        claim_candidates.append(
            ClaimCandidate(
                claim_id=claim_id,
                claim_text=" ".join(part for part in claim_text_parts if part).strip(),
                share_count=int(claim.get("share_count", 0) or 0),
                account_count=int(claim.get("account_count", 0) or 0),
                first_share=str(claim.get("first_share", "") or ""),
            )
        )
    return claim_candidates


def assess_post_semantics(
    posts: list[dict[str, Any]],
    prop_data: dict[str, Any],
    *,
    prefer_embeddings: bool = True,
    max_output_posts: int = MAX_EVIDENCE_POSTS,
) -> dict[str, Any]:
    """Run KT3 post-level multimodal, claim-conditioned assessment."""
    engine = SimilarityEngine(prefer_embeddings=prefer_embeddings)
    normalized_posts = [
        normalize_multimodal_post(post)
        for post in posts
        if _clean_text(post.get("content", "")) or (post.get("raw_data") or post.get("media_urls"))
    ]
    claim_candidates = build_claim_candidates(prop_data)

    results = [
        _assess_single_post(post, claim_candidates, engine)
        for post in normalized_posts
    ]
    summary = _summarize_post_results(results, claim_candidates, engine.backend, len(posts))

    representative_posts = sorted(
        results,
        key=lambda item: (
            item["harmfulness"]["score"],
            item["stance"]["confidence"],
            item["primary_claim"]["score"] if item["primary_claim"] else 0.0,
        ),
        reverse=True,
    )[:max_output_posts]

    return {
        "analysis_scope": {
            "input_posts": len(posts),
            "normalized_posts": len(normalized_posts),
            "claim_candidates": len(claim_candidates),
        },
        "modeling": {
            "encoder_backend": engine.backend,
            "claim_conditioned": True,
            "multimodal_fields": ["text", "emoji", "ocr", "asr", "media_metadata"],
            "multimodal_fusion": "modality-aware late fusion over normalized text/OCR/ASR/caption/media channels",
            "method_trace": MULTIMODAL_METHOD_TRACE,
            "design_note": (
                "Representation-based KT3 scaffold aligned with multimodal harmfulness "
                "and claim-conditioned stance literature."
            ),
        },
        "claim_candidates": [
            {
                "claim_id": claim.claim_id,
                "claim_text": claim.claim_text[:240],
                "share_count": claim.share_count,
                "account_count": claim.account_count,
            }
            for claim in claim_candidates[:10]
        ],
        "summary": summary,
        "posts": representative_posts,
        "aggregation_posts": results,
    }


def _assess_single_post(
    post: NormalizedPost,
    claim_candidates: list[ClaimCandidate],
    engine: SimilarityEngine,
) -> dict[str, Any]:
    linked_claims = _link_claims(post, claim_candidates, engine)
    primary_claim = linked_claims[0] if linked_claims else None
    stance = _infer_stance(post, primary_claim, engine)
    harmfulness = _infer_harmfulness(post, primary_claim, stance, engine)
    multimodal_detection = _infer_multimodal_detection(post, primary_claim, stance, engine)
    post_view_detection = _infer_post_view_detection(post, primary_claim, stance, engine)

    return {
        "post_id": post.post_id,
        "author_id": post.author_id,
        "author_name": post.author_name,
        "platform": post.platform,
        "event_id": post.event_id,
        "excerpt": post.text[:240],
        "hashtags": post.hashtags,
        "media_urls": post.media_urls,
        "modalities": post.modalities,
        "linked_claims": linked_claims,
        "primary_claim": primary_claim,
        "stance": stance,
        "harmfulness": harmfulness,
        "multimodal_detection": multimodal_detection,
        "post_view_detection": post_view_detection,
        "evidence": {
            "text": post.text[:240],
            "ocr_text": post.ocr_text[:240],
            "asr_text": post.asr_text[:240],
            "media_text": post.media_text[:240],
        },
    }


def _link_claims(
    post: NormalizedPost,
    claim_candidates: list[ClaimCandidate],
    engine: SimilarityEngine,
) -> list[dict[str, Any]]:
    if not claim_candidates or not post.semantic_text:
        return []

    scored = []
    for claim in claim_candidates:
        score = engine.score(post.semantic_text, claim.claim_text)
        scored.append(
            {
                "claim_id": claim.claim_id,
                "claim_text": claim.claim_text[:240],
                "score": score,
                "share_count": claim.share_count,
                "account_count": claim.account_count,
            }
        )

    scored.sort(key=lambda item: item["score"], reverse=True)
    top_score = scored[0]["score"]
    if top_score < 0.35:
        return []

    threshold = max(0.3, top_score - 0.08)
    return [item for item in scored[:2] if item["score"] >= threshold]


def _infer_stance(
    post: NormalizedPost,
    primary_claim: dict[str, Any] | None,
    engine: SimilarityEngine,
) -> dict[str, Any]:
    if primary_claim is None:
        return {
            "label": "unlinked",
            "confidence": 0.0,
            "abstain": True,
            "scores": {},
        }

    claim_text = primary_claim["claim_text"]
    scores = {
        label: engine.score(
            post.semantic_text,
            f"{prototype} Claim: {claim_text}",
        )
        for label, prototype in STANCE_PROTOTYPES.items()
    }
    sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    top_label, top_score = sorted_scores[0]
    second_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0.0
    abstain = top_score < 0.45 or (top_score - second_score) < 0.03
    return {
        "label": "uncertain" if abstain else top_label,
        "confidence": round(top_score, 4),
        "abstain": abstain,
        "scores": {label: round(score, 4) for label, score in scores.items()},
    }


def _infer_harmfulness(
    post: NormalizedPost,
    primary_claim: dict[str, Any] | None,
    stance: dict[str, Any],
    engine: SimilarityEngine,
) -> dict[str, Any]:
    scores = {
        label: engine.score(post.semantic_text, prototype)
        for label, prototype in HARM_TYPE_PROTOTYPES.items()
    }
    benign_score = engine.score(post.semantic_text, NON_HARMFUL_PROTOTYPE)

    if primary_claim is not None:
        claim_text = primary_claim["claim_text"]
        rumor_hypothesis = (
            "The post amplifies or legitimizes the following disputed narrative or claim: "
            + claim_text
        )
        rumor_boost = engine.score(post.semantic_text, rumor_hypothesis)
        if stance["label"] == "support":
            scores["misinformation"] = max(scores["misinformation"], rumor_boost)
        elif stance["label"] == "deny":
            scores["misinformation"] = round(scores["misinformation"] * 0.7, 4)

    top_label, top_score = max(scores.items(), key=lambda item: item[1])
    selected_types = [
        label
        for label, score in scores.items()
        if score >= max(0.52, top_score - 0.05)
    ]

    harmful_margin = top_score - benign_score
    if top_score >= 0.58 and harmful_margin >= 0.04:
        label = "harmful"
        abstain = False
    elif top_score >= 0.5 and harmful_margin >= 0.0:
        label = "uncertain"
        abstain = True
    else:
        label = "non_harmful"
        abstain = False
        selected_types = []

    return {
        "label": label,
        "score": round(top_score, 4),
        "abstain": abstain,
        "primary_type": top_label if selected_types else None,
        "types": selected_types,
        "type_scores": {name: round(score, 4) for name, score in scores.items()},
        "benign_score": round(benign_score, 4),
    }


def _infer_multimodal_detection(
    post: NormalizedPost,
    primary_claim: dict[str, Any] | None,
    stance: dict[str, Any],
    engine: SimilarityEngine,
) -> dict[str, Any]:
    modality_texts = _modality_texts(post)
    channel_results: list[dict[str, Any]] = []
    for modality, text in modality_texts.items():
        if not text:
            continue
        type_scores = {
            label: engine.score(text, prototype)
            for label, prototype in HARM_TYPE_PROTOTYPES.items()
        }
        benign_score = engine.score(text, NON_HARMFUL_PROTOTYPE)
        primary_type, score = max(type_scores.items(), key=lambda item: item[1])
        channel_results.append(
            {
                "modality": modality,
                "weight": MODALITY_FUSION_WEIGHTS.get(modality, 0.5),
                "primary_type": primary_type,
                "harm_score": round(score, 4),
                "benign_score": round(benign_score, 4),
                "evidence_excerpt": text[:180],
                "type_scores": {key: round(value, 4) for key, value in type_scores.items()},
            }
        )

    if not channel_results:
        return {
            "status": "no_multimodal_evidence",
            "fusion_method": "modality-aware-late-fusion",
            "fused_harm_score": 0.0,
            "label": "uncertain",
            "evidence_modalities": [],
            "channel_results": [],
            "cross_modal_conflict": 0.0,
            "claim_grounded": primary_claim is not None,
            "capability_boundary": _multimodal_capability_boundary(),
            "method_trace": MULTIMODAL_METHOD_TRACE,
        }

    total_weight = sum(item["weight"] for item in channel_results) or 1.0
    fused_score = sum(item["harm_score"] * item["weight"] for item in channel_results) / total_weight
    score_values = [item["harm_score"] for item in channel_results]
    type_vote = Counter()
    for item in channel_results:
        type_vote[item["primary_type"]] += item["harm_score"] * item["weight"]
    primary_type, _ = type_vote.most_common(1)[0]
    conflict = max(score_values) - min(score_values) if len(score_values) > 1 else 0.0
    stance_support_boost = 0.03 if stance.get("label") == "support" and primary_claim else 0.0
    fused_score = min(1.0, fused_score + stance_support_boost)
    if fused_score >= 0.58:
        label = "harmful"
    elif fused_score >= 0.48 or conflict >= 0.18:
        label = "uncertain"
    else:
        label = "non_harmful"

    return {
        "status": "executed",
        "fusion_method": "modality-aware-late-fusion",
        "fused_harm_score": round(fused_score, 4),
        "label": label,
        "primary_type": primary_type if label != "non_harmful" else None,
        "evidence_modalities": [item["modality"] for item in channel_results],
        "channel_results": channel_results,
        "cross_modal_conflict": round(conflict, 4),
        "claim_grounded": primary_claim is not None,
        "capability_boundary": _multimodal_capability_boundary(),
        "method_trace": MULTIMODAL_METHOD_TRACE,
    }


def _infer_post_view_detection(
    post: NormalizedPost,
    primary_claim: dict[str, Any] | None,
    stance: dict[str, Any],
    engine: SimilarityEngine,
) -> dict[str, Any]:
    """Detect tweet/meme/img/video views, then fuse them at post level."""
    view_payloads = _post_view_payloads(post)
    view_results = {
        view_name: _detect_single_post_view(
            view_name,
            view_payloads[view_name],
            primary_claim,
            stance,
            engine,
        )
        for view_name in POST_VIEW_ORDER
    }
    majority_vote = _majority_vote_post_views(view_results)
    weighted_fusion = _weighted_fuse_post_views(view_results)
    final_decision = _select_post_view_final_decision(majority_vote, weighted_fusion)
    conflict = _post_view_conflict(view_results)
    review_reason = _post_view_review_reasons(view_results, majority_vote, weighted_fusion, conflict)
    final_label = final_decision["label"]
    return {
        "schema_version": "kt3-post-view-detection-v1",
        "status": "executed",
        "view_order": list(POST_VIEW_ORDER),
        "view_results": view_results,
        "fusion": {
            "majority_vote": majority_vote,
            "weighted_fusion": weighted_fusion,
        },
        "fusion_policy": final_decision["policy"],
        "final_harmfulness": final_label,
        "harm_score": final_decision["score"],
        "harm_types": _merge_post_view_harm_types(view_results) if final_label != "non_harmful" else [],
        "primary_claim": {
            "claim_id": primary_claim.get("claim_id"),
            "score": _safe_float(primary_claim.get("score")),
        }
        if primary_claim
        else None,
        "stance": {
            "label": stance.get("label", "unknown"),
            "confidence": _safe_float(stance.get("confidence")),
            "abstain": bool(stance.get("abstain")),
        },
        "conflict": conflict,
        "review_reason": review_reason,
        "capability_boundary": _post_view_capability_boundary(),
        "method_trace": MULTIMODAL_METHOD_TRACE,
    }


def _post_view_payloads(post: NormalizedPost) -> dict[str, dict[str, Any]]:
    media_kind_counts = _media_kind_counts(post.media_urls)
    image_decodable_text = " ".join([post.ocr_text, post.media_context_text]).strip()
    video_decodable_text = " ".join([post.asr_text, post.ocr_text, post.media_context_text]).strip()
    tweet_text = " ".join([post.text, " ".join(post.hashtags), post.emoji_text]).strip()
    meme_text = (
        " ".join([post.text, post.ocr_text, post.media_context_text, " ".join(post.hashtags)]).strip()
        if image_decodable_text
        else ""
    )
    img_text = image_decodable_text
    video_text = (
        " ".join([video_decodable_text, post.text]).strip()
        if video_decodable_text and (media_kind_counts["video"] or post.asr_text)
        else ""
    )
    return {
        "tweet": {
            "semantic_text": tweet_text,
            "evidence_modalities": [
                name
                for name, value in {
                    "text": post.text,
                    "hashtags": " ".join(post.hashtags),
                    "emoji": post.emoji_text,
                }.items()
                if value
            ],
            "media_kind_count": 0,
            "metadata_only": False,
        },
        "meme": {
            "semantic_text": meme_text,
            "evidence_modalities": [
                name
                for name, value in {
                    "text": post.text,
                    "ocr": post.ocr_text,
                    "caption": post.media_context_text,
                    "hashtags": " ".join(post.hashtags),
                }.items()
                if value
            ],
            "media_kind_count": media_kind_counts["image"],
            "metadata_only": bool(media_kind_counts["image"] and not image_decodable_text),
        },
        "img": {
            "semantic_text": img_text,
            "evidence_modalities": [
                name
                for name, value in {
                    "ocr": post.ocr_text,
                    "caption": post.media_context_text,
                }.items()
                if value
            ],
            "media_kind_count": media_kind_counts["image"],
            "metadata_only": bool(media_kind_counts["image"] and not img_text),
        },
        "video": {
            "semantic_text": video_text,
            "evidence_modalities": [
                name
                for name, value in {
                    "asr": post.asr_text,
                    "ocr": post.ocr_text,
                    "caption": post.media_context_text,
                    "text": post.text,
                }.items()
                if value
            ],
            "media_kind_count": media_kind_counts["video"],
            "metadata_only": bool(media_kind_counts["video"] and not video_decodable_text),
        },
    }


def _detect_single_post_view(
    view_name: str,
    payload: dict[str, Any],
    primary_claim: dict[str, Any] | None,
    stance: dict[str, Any],
    engine: SimilarityEngine,
) -> dict[str, Any]:
    semantic_text = _clean_text(payload.get("semantic_text"))
    available = bool(semantic_text)
    media_kind_count = _safe_int(payload.get("media_kind_count"))
    metadata_only = bool(payload.get("metadata_only"))
    if not available:
        return {
            "detector": POST_VIEW_DETECTORS[view_name],
            "available": False,
            "abstain": True,
            "label": "uncertain",
            "score": 0.0,
            "confidence": 0.0,
            "primary_type": None,
            "harm_types": [],
            "type_scores": {},
            "benign_score": 0.0,
            "evidence": [],
            "evidence_modalities": [],
            "media_kind_count": media_kind_count,
            "reason": "view_unavailable" if not metadata_only else "media_without_decodable_content",
        }

    type_scores = {
        label: engine.score(semantic_text, prototype)
        for label, prototype in HARM_TYPE_PROTOTYPES.items()
    }
    benign_score = engine.score(semantic_text, NON_HARMFUL_PROTOTYPE)
    if primary_claim is not None and view_name in {"tweet", "meme", "video"}:
        claim_text = primary_claim["claim_text"]
        claim_score = engine.score(
            semantic_text,
            "The view amplifies or legitimizes the referenced disputed claim: " + claim_text,
        )
        if stance.get("label") == "support":
            type_scores["misinformation"] = max(type_scores["misinformation"], claim_score)
        elif stance.get("label") == "deny":
            type_scores["misinformation"] = round(type_scores["misinformation"] * 0.7, 4)

    primary_type, score = max(type_scores.items(), key=lambda item: item[1])
    margin = score - benign_score
    if score >= POST_VIEW_THRESHOLDS["harmful"] and margin >= 0.04:
        label = "harmful"
        abstain = False
    elif score <= POST_VIEW_THRESHOLDS["non_harmful"] and margin < 0.02:
        label = "non_harmful"
        abstain = False
    else:
        label = "uncertain"
        abstain = True

    harm_types = [
        label_name
        for label_name, label_score in type_scores.items()
        if label_score >= max(0.52, score - 0.05)
    ]
    if label == "non_harmful":
        harm_types = []

    confidence = _view_confidence(score, benign_score, label, metadata_only)
    return {
        "detector": POST_VIEW_DETECTORS[view_name],
        "available": True,
        "abstain": abstain,
        "label": label,
        "score": round(score, 4),
        "confidence": confidence,
        "primary_type": primary_type if label != "non_harmful" else None,
        "harm_types": harm_types,
        "type_scores": {key: round(value, 4) for key, value in type_scores.items()},
        "benign_score": round(benign_score, 4),
        "evidence": [semantic_text[:180]],
        "evidence_modalities": _as_text_list(payload.get("evidence_modalities")),
        "media_kind_count": media_kind_count,
        "reason": "view_detected_with_media_metadata_only" if metadata_only else "view_detected",
    }


def _majority_vote_post_views(view_results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    eligible = {
        name: result
        for name, result in view_results.items()
        if result.get("available") and not result.get("abstain") and result.get("label") in {"harmful", "non_harmful"}
    }
    votes = Counter(result["label"] for result in eligible.values())
    if not eligible:
        label = "uncertain"
        reason = "no_confident_view_votes"
    elif votes["harmful"] > len(eligible) / 2:
        label = "harmful"
        reason = "harmful_majority"
    elif votes["non_harmful"] > len(eligible) / 2:
        label = "non_harmful"
        reason = "non_harmful_majority"
    else:
        label = "uncertain"
        reason = "tied_or_no_majority"
    harmful_vote_strength = sum(
        _safe_float(result.get("confidence"))
        for result in eligible.values()
        if result.get("label") == "harmful"
    )
    total_vote_strength = sum(_safe_float(result.get("confidence")) for result in eligible.values()) or 1.0
    return {
        "label": label,
        "harm_score": round(harmful_vote_strength / total_vote_strength, 4) if eligible else 0.0,
        "vote_counts": dict(votes),
        "eligible_views": sorted(eligible),
        "abstained_views": sorted(
            name
            for name, result in view_results.items()
            if not result.get("available") or result.get("abstain")
        ),
        "reason": reason,
    }


def _weighted_fuse_post_views(view_results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    weighted_sum = 0.0
    total_weight = 0.0
    contributors = []
    for view_name, result in view_results.items():
        if not result.get("available"):
            continue
        if result.get("abstain"):
            continue
        confidence = _safe_float(result.get("confidence"))
        if confidence <= 0:
            continue
        base_weight = POST_VIEW_FUSION_WEIGHTS.get(view_name, 0.8)
        weight = base_weight * confidence
        weighted_sum += weight * _safe_float(result.get("score"))
        total_weight += weight
        contributors.append(
            {
                "view": view_name,
                "weight": round(weight, 4),
                "label": result.get("label", "uncertain"),
                "score": _safe_float(result.get("score")),
                "confidence": confidence,
            }
        )

    if not contributors or total_weight <= 0:
        return {
            "label": "uncertain",
            "harm_score": 0.0,
            "contributors": [],
            "reason": "no_available_view_scores",
        }

    harm_score = weighted_sum / total_weight
    if harm_score >= POST_VIEW_THRESHOLDS["harmful"]:
        label = "harmful"
    elif harm_score <= POST_VIEW_THRESHOLDS["non_harmful"]:
        label = "non_harmful"
    else:
        label = "uncertain"
    return {
        "label": label,
        "harm_score": round(harm_score, 4),
        "contributors": contributors,
        "reason": "confidence_weighted_late_fusion",
    }


def _select_post_view_final_decision(
    majority_vote: dict[str, Any],
    weighted_fusion: dict[str, Any],
) -> dict[str, Any]:
    majority_label = majority_vote.get("label", "uncertain")
    weighted_label = weighted_fusion.get("label", "uncertain")
    if majority_label == weighted_label and majority_label != "uncertain":
        return {
            "label": majority_label,
            "score": _safe_float(weighted_fusion.get("harm_score")),
            "policy": "majority_vote_confirmed_by_weighted_fusion",
        }
    if majority_label != "uncertain":
        return {
            "label": majority_label,
            "score": _safe_float(majority_vote.get("harm_score")),
            "policy": "majority_vote",
        }
    return {
        "label": weighted_label,
        "score": _safe_float(weighted_fusion.get("harm_score")),
        "policy": "weighted_fusion_fallback",
    }


def _post_view_conflict(view_results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    confident_labels = {
        name: result.get("label")
        for name, result in view_results.items()
        if result.get("available") and not result.get("abstain") and result.get("label") in {"harmful", "non_harmful"}
    }
    score_values = [
        _safe_float(result.get("score"))
        for result in view_results.values()
        if result.get("available") and not result.get("abstain")
    ]
    has_label_conflict = "harmful" in confident_labels.values() and "non_harmful" in confident_labels.values()
    score_gap = max(score_values) - min(score_values) if len(score_values) > 1 else 0.0
    conflict_type = None
    if has_label_conflict:
        conflict_type = "cross_view_label_conflict"
    elif score_gap >= 0.18:
        conflict_type = "cross_view_score_divergence"
    return {
        "has_conflict": bool(conflict_type),
        "type": conflict_type,
        "score_gap": round(score_gap, 4),
        "conflicting_views": confident_labels,
    }


def _post_view_review_reasons(
    view_results: dict[str, dict[str, Any]],
    majority_vote: dict[str, Any],
    weighted_fusion: dict[str, Any],
    conflict: dict[str, Any],
) -> list[str]:
    reasons = []
    if majority_vote.get("label") == "uncertain":
        reasons.append("majority_vote_uncertain")
    if weighted_fusion.get("label") == "uncertain":
        reasons.append("weighted_fusion_uncertain")
    if conflict.get("has_conflict"):
        reasons.append(str(conflict.get("type") or "cross_view_conflict"))
    unavailable = [
        name
        for name, result in view_results.items()
        if not result.get("available")
    ]
    if unavailable:
        reasons.append("view_unavailable:" + ",".join(unavailable))
    metadata_only = [
        name
        for name, result in view_results.items()
        if str(result.get("reason", "")).startswith("media_without_decodable_content")
        or str(result.get("reason", "")).endswith("media_metadata_only")
    ]
    if metadata_only:
        reasons.append("media_without_decodable_content:" + ",".join(metadata_only))
    return reasons


def _merge_post_view_harm_types(view_results: dict[str, dict[str, Any]]) -> list[str]:
    weighted = Counter()
    for view_name, result in view_results.items():
        if not result.get("available") or result.get("abstain") or result.get("label") == "non_harmful":
            continue
        weight = POST_VIEW_FUSION_WEIGHTS.get(view_name, 0.8) * max(0.1, _safe_float(result.get("confidence")))
        for harm_type in _as_text_list(result.get("harm_types")):
            weighted[harm_type] += weight
    return [
        harm_type
        for harm_type, _ in weighted.most_common()
    ]


def _view_confidence(score: float, benign_score: float, label: str, metadata_only: bool) -> float:
    margin = abs(score - benign_score)
    if label == "uncertain":
        base = 0.35 + min(0.25, margin)
    else:
        base = 0.55 + min(0.4, margin)
    if metadata_only:
        base *= 0.35
    return round(max(0.0, min(1.0, base)), 4)


def _media_kind_counts(media_urls: list[str]) -> dict[str, int]:
    counts = {"image": 0, "video": 0, "linked": 0}
    for url in media_urls:
        parsed = urlparse(url)
        filename = unquote(parsed.path.rsplit("/", 1)[-1]) if parsed.path else ""
        suffix = ""
        if "." in filename:
            suffix = "." + filename.rsplit(".", 1)[-1].lower()
        if suffix in VIDEO_EXTENSIONS:
            counts["video"] += 1
        elif suffix in IMAGE_EXTENSIONS:
            counts["image"] += 1
        else:
            counts["linked"] += 1
    return counts


def _post_view_capability_boundary() -> dict[str, Any]:
    return {
        "status": "implemented_four_view_runtime_fusion_scaffold",
        "view_detectors": list(POST_VIEW_DETECTORS.values()),
        "majority_vote": True,
        "weighted_late_fusion": True,
        "effective_views_only": True,
        "media_url_is_not_decodable_evidence": True,
        "learned_fusion": False,
        "true_image_encoder": False,
        "true_video_encoder": False,
        "trained_view_detectors": False,
        "description": (
            "Runs tweet/meme/img/video view-level detection over normalized text, OCR, ASR, "
            "caption and media context, then fuses view decisions. Image/video views abstain "
            "when media exists but no decodable OCR/ASR/caption content is available; abstained "
            "views are excluded from majority vote and weighted fusion."
        ),
    }


def _multimodal_capability_boundary() -> dict[str, Any]:
    return {
        "status": "implemented_normalized_multimodal_late_fusion",
        "true_image_encoder": False,
        "true_video_encoder": False,
        "trained_multimodal_model": False,
        "uses_runtime_gold": False,
        "description": (
            "Uses normalized text, OCR, ASR, captions, emoji, hashtags, and media "
            "metadata as modality channels. It is not yet an end-to-end image/video "
            "encoder or trained multimodal transformer."
        ),
    }


def _modality_texts(post: NormalizedPost) -> dict[str, str]:
    return {
        "text": post.text,
        "ocr": post.ocr_text,
        "asr": post.asr_text,
        "caption_media": post.media_text,
        "emoji_hashtag": " ".join([post.emoji_text, " ".join(post.hashtags)]).strip(),
    }


def _summarize_post_results(
    results: list[dict[str, Any]],
    claim_candidates: list[ClaimCandidate],
    backend: str,
    input_posts: int,
) -> dict[str, Any]:
    harm_counter: Counter[str] = Counter()
    stance_counter: Counter[str] = Counter()
    claim_counter: dict[str, dict[str, Any]] = {}

    harmful_posts = 0
    linked_posts = 0

    for result in results:
        harm = result["harmfulness"]
        stance = result["stance"]
        primary_claim = result["primary_claim"]

        if harm["label"] == "harmful":
            harmful_posts += 1
            for harm_type in harm["types"]:
                harm_counter[harm_type] += 1

        if stance["label"] not in {"unlinked", "uncertain"}:
            stance_counter[stance["label"]] += 1

        if primary_claim is not None:
            linked_posts += 1
            claim_entry = claim_counter.setdefault(
                primary_claim["claim_id"],
                {
                    "claim_id": primary_claim["claim_id"],
                    "claim_text": primary_claim["claim_text"],
                    "linked_posts": 0,
                    "harmful_posts": 0,
                    "support": 0,
                    "deny": 0,
                    "query": 0,
                    "neutral": 0,
                },
            )
            claim_entry["linked_posts"] += 1
            if harm["label"] == "harmful":
                claim_entry["harmful_posts"] += 1
            if stance["label"] in {"support", "deny", "query", "neutral"}:
                claim_entry[stance["label"]] += 1

    top_claims = sorted(
        claim_counter.values(),
        key=lambda item: (item["harmful_posts"], item["linked_posts"]),
        reverse=True,
    )[:10]

    return {
        "input_posts": input_posts,
        "analyzed_posts": len(results),
        "linked_posts": linked_posts,
        "harmful_posts": harmful_posts,
        "harmful_ratio": round(harmful_posts / len(results), 4) if results else 0.0,
        "harm_types": dict(harm_counter),
        "stance_distribution": dict(stance_counter),
        "top_claims": top_claims,
        "available_claims": len(claim_candidates),
        "backend": backend,
    }


def _collect_raw_text_values(
    raw_data: Any,
    key_markers: set[str],
    *,
    limit: int = 5,
) -> list[str]:
    results: list[str] = []

    def walk(node: Any, parent_key: str = "") -> None:
        if len(results) >= limit:
            return
        if isinstance(node, str):
            if any(marker in parent_key.lower() for marker in key_markers):
                cleaned = _clean_text(node)
                if cleaned:
                    results.append(cleaned[:240])
            return
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, str(key))
            return
        if isinstance(node, list):
            for item in node:
                walk(item, parent_key)

    walk(raw_data)
    return _dedupe_strings(results)


def _extract_emoji_text(text: str) -> str:
    hints = [label for emoji, label in EMOJI_TEXT.items() if emoji in text]
    return " ".join(_dedupe_strings(hints))


def _describe_media_urls(media_urls: list[str]) -> list[str]:
    descriptions = []
    for url in media_urls[:4]:
        parsed = urlparse(url)
        filename = unquote(parsed.path.rsplit("/", 1)[-1]) if parsed.path else ""
        suffix = ""
        if "." in filename:
            suffix = "." + filename.rsplit(".", 1)[-1].lower()
        if suffix in VIDEO_EXTENSIONS:
            media_type = "video"
        elif suffix in IMAGE_EXTENSIONS:
            media_type = "image"
        else:
            media_type = "linked media"
        domain = parsed.netloc.lower()
        details = " ".join(part for part in [media_type, domain, filename[:60]] if part)
        descriptions.append(details.strip())
    return descriptions


def _describe_claim_anchor(claim_id: str) -> str:
    if claim_id.startswith("#"):
        return f"hashtag narrative {claim_id}"
    if claim_id.startswith("http://") or claim_id.startswith("https://"):
        parsed = urlparse(claim_id)
        filename = unquote(parsed.path.rsplit("/", 1)[-1]) if parsed.path else ""
        parts = ["shared link", parsed.netloc.lower(), filename]
        return " ".join(part for part in parts if part).strip()
    return claim_id


def _lexical_similarity(left: str, right: str) -> float:
    left_tokens = _tokenize(left)
    right_tokens = _tokenize(right)
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = left_tokens & right_tokens
    if not overlap:
        return 0.0
    jaccard = len(overlap) / len(left_tokens | right_tokens)
    containment = len(overlap) / min(len(left_tokens), len(right_tokens))
    return max(0.0, min(1.0, 0.6 * containment + 0.4 * jaccard))


def _tokenize(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_PATTERN.findall(text or "")}


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped = []
    for value in values:
        normalized = _clean_text(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _as_text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item or "").strip()]


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
