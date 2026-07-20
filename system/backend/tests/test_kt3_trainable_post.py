from __future__ import annotations

import importlib.util

import numpy as np
import pytest

from app.core.risk.kt3_trainable_post import (
    CrossModalAttentionAdapter,
    GatingFusionModel,
    MultitaskTextDetector,
    binary_classification_metrics,
    build_agent_review,
    build_gating_feature_matrix,
    coverage_risk_curve,
    encode_text_features,
    encode_clip_image_text_features,
    expected_calibration_error,
    fuse_detector_outputs,
    hash_case_image_features,
    predict_probabilities,
    standard_detector_output,
    train_binary_torch_model,
    train_cross_modal_torch_model,
    train_multitask_text_model,
    multitask_targets,
)
from app.core.risk.kt3_selective_student import (
    ATTACK_AXIS,
    SelectiveStudentEncoder,
    build_selective_student_targets,
    load_teacher_silver_index,
    predict_selective_student_outputs,
    student_main_axis_metrics,
    train_selective_student_model,
)
from app.core.risk.kt3_teacher_silver import build_teacher_silver_record
from app.core.risk.kt3_rag import LocalHashRag, augment_context_with_rag


def _case(case_id: str, text: str, label: str = "harmful") -> dict:
    return {
        "case_id": case_id,
        "dataset": "unit",
        "split": "test",
        "source_id": case_id,
        "language": "zh" if any("\u4e00" <= char <= "\u9fff" for char in text) else "en",
        "text": text,
        "labels": {
            "harmfulness": label,
            "harm_type": ["misinformation"] if label == "harmful" else [],
            "rationale_tokens": ["claim", "target"] if label == "harmful" else [],
            "target_groups": ["public"] if label == "harmful" else [],
        },
        "views": {
            "tweet": {"available": True},
            "meme": {"available": True},
            "img": {"available": True, "media_path": f"G:/fake/{case_id}.png"},
            "video": {"available": False},
        },
        "claim_context": {
            "available": True,
            "claim_text": "public claim",
            "evidence_text": "local evidence",
        },
    }


def test_hash_features_and_standard_detector_contract():
    cases = [_case("a", "harmful claim"), _case("b", "benign note", "non_harmful")]
    bundle = encode_text_features([case["text"] for case in cases], backend="hash", dim=32)
    image_features = hash_case_image_features(cases, dim=32)

    assert bundle.backend == "hash-smoke"
    assert bundle.matrix.shape == (2, 32)
    assert image_features.shape == (2, 32)

    output = standard_detector_output(
        cases[0],
        view="tweet",
        probability=0.82,
        capability_boundary="unit boundary",
    )
    assert output["label"] == "harmful"
    assert output["harm_score"] == 0.82
    assert output["confidence"] > 0.6
    assert output["abstain"] is False
    assert output["claim_id"] != "unlinked"
    assert output["rationale_or_span"]


def test_multitask_targets_and_clip_fallback_contract():
    cases = [_case("a", "harmful claim"), _case("b", "benign note", "non_harmful")]
    targets = multitask_targets(cases)
    transformer_fallback = encode_text_features(
        ["中文谣言检测", "benign note"],
        backend="auto",
        model_name="definitely-not-a-local-hf-model",
        local_files_only=True,
        dim=16,
    )
    text_bundle, image_bundle = encode_clip_image_text_features(
        cases,
        model_name="definitely-not-a-local-clip-model",
        local_files_only=True,
        fallback_dim=16,
    )

    assert targets["harmfulness"].tolist() == [1.0, 0.0]
    assert targets["harm_types"].shape[0] == 2
    assert targets["stance"].shape == (2,)
    assert transformer_fallback.backend == "hash-smoke"
    assert transformer_fallback.matrix.shape == (2, 16)
    assert text_bundle.backend == "hash-smoke-text"
    assert image_bundle.backend == "hash-smoke-image"
    assert text_bundle.matrix.shape == (2, 16)
    assert image_bundle.matrix.shape == (2, 16)


def test_teacher_silver_and_selective_target_contract():
    case = _case("a", "harmful claim")
    case["dataset"] = "HateXplain"
    review_result = {
        "summary": {
            "requested_agents": 7,
            "completed": 7,
            "runtime_reasons": ["claim_retrieval_tasks_present"],
            "candidate_rule_hints": ["low_confidence"],
            "reflection_response_reports": 1,
        },
        "audit": {
            "failure_mode_tags": ["cross_view_conflict"],
        },
        "input_bundle": {
            "selected_posts": [
                {
                    "post_id": "p1",
                    "excerpt": "claim snippet",
                    "content": "claim snippet",
                }
            ]
        },
        "agent_reports": [
            {
                "review_id": "judge-1",
                "agent_name": "HarmfulnessJudgeAgent",
                "report_role": "judge_final",
                "status": "completed",
                "structured_sidecar": {
                    "confidence": 0.84,
                    "review_required": True,
                    "evidence_refs": [{"text": "evidence snippet"}],
                    "uncertainties": ["low_confidence"],
                    "debate_trace_refs": ["debate:1"],
                },
            }
        ],
    }

    teacher = build_teacher_silver_record(case, review_result)
    index = load_teacher_silver_index([teacher])
    targets = build_selective_student_targets([case], index)

    assert teacher["schema_version"] == "kt3-teacher-silver-v1"
    assert teacher["main_axes"][ATTACK_AXIS]["available"] is True
    assert teacher["main_axes"][ATTACK_AXIS]["label"] in {"harmful", "non_harmful"}
    assert teacher["sample_mode"] == "hard_case"
    assert teacher["trace_refs"]
    assert targets["attack"].shape == (1,)
    assert targets["attack_mask"][0] == 1.0
    assert targets["defer"][0] == 1.0


@pytest.mark.skipif(importlib.util.find_spec("torch") is None, reason="torch not installed")
def test_selective_student_smoke_train():
    cases = [_case("a", "harmful claim"), _case("b", "benign note", "non_harmful")]
    for case in cases:
        case["dataset"] = "HateXplain"
    hard_review = {
        "summary": {
            "requested_agents": 7,
            "completed": 7,
            "runtime_reasons": ["claim_retrieval_tasks_present"],
            "candidate_rule_hints": ["low_confidence"],
            "reflection_response_reports": 1,
        },
        "audit": {"failure_mode_tags": ["cross_view_conflict"]},
        "input_bundle": {"selected_posts": [{"post_id": "p1", "excerpt": "claim snippet", "content": "claim snippet"}]},
        "agent_reports": [
            {
                "review_id": "judge-1",
                "agent_name": "HarmfulnessJudgeAgent",
                "report_role": "judge_final",
                "status": "completed",
                "structured_sidecar": {
                    "confidence": 0.84,
                    "review_required": True,
                    "evidence_refs": [{"text": "evidence snippet"}],
                    "uncertainties": ["low_confidence"],
                    "debate_trace_refs": ["debate:1"],
                },
            }
        ],
    }
    easy_review = {
        "summary": {
            "requested_agents": 7,
            "completed": 7,
            "runtime_reasons": [],
            "candidate_rule_hints": [],
            "reflection_response_reports": 0,
        },
        "audit": {"failure_mode_tags": []},
        "input_bundle": {"selected_posts": [{"post_id": "p2", "excerpt": "benign snippet", "content": "benign snippet"}]},
        "agent_reports": [
            {
                "review_id": "judge-2",
                "agent_name": "HarmfulnessJudgeAgent",
                "report_role": "judge_final",
                "status": "completed",
                "structured_sidecar": {
                    "confidence": 0.62,
                    "review_required": False,
                    "evidence_refs": [{"text": "support snippet"}],
                    "uncertainties": [],
                    "debate_trace_refs": [],
                },
            }
        ],
    }
    teacher_index = load_teacher_silver_index(
        [
            build_teacher_silver_record(cases[0], hard_review),
            build_teacher_silver_record(cases[1], easy_review),
        ]
    )
    post_features = encode_text_features([case["text"] for case in cases], backend="hash", dim=16).matrix
    claim_features = encode_text_features([case["claim_context"]["claim_text"] for case in cases], backend="hash", dim=16).matrix
    features = np.concatenate([post_features, claim_features], axis=-1)
    targets = build_selective_student_targets(cases, teacher_index)

    model = SelectiveStudentEncoder(input_dim=32, hidden_dim=8)
    train_info = train_selective_student_model(model, features, targets, epochs=1, batch_size=2, device="cpu")
    predictions = predict_selective_student_outputs(model, features, device="cpu")
    metrics = student_main_axis_metrics(cases, predictions, teacher_silver_index=teacher_index)

    assert train_info["epochs"] == 1
    assert predictions[ATTACK_AXIS].shape == (2,)
    assert predictions["defer"].shape == (2,)
    assert metrics["overall"]["support_cases"] == 2
    assert 0.0 <= metrics["macro_f1"] <= 1.0


def test_local_hash_rag_retrieval_and_context_augmentation(tmp_path):
    corpus_path = tmp_path / "disarm_corpus.jsonl"
    corpus_path.write_text(
        "\n".join(
            [
                '{"doc_id":"D1","source":"DISARM","title":"Amplify","text":"coordinated amplification and manipulation"}',
                '{"doc_id":"D2","source":"DISARM","title":"Benign","text":"ordinary conversation"}',
            ]
        ),
        encoding="utf-8",
    )
    rag = LocalHashRag.from_jsonl(corpus_path, dim=32)
    evidence = rag.retrieve("coordinated manipulation campaign", top_k=1)
    augmented = augment_context_with_rag("claim context", evidence)

    assert evidence
    assert evidence[0]["doc_id"] == "D1"
    assert "claim context" in augmented
    assert "coordinated amplification" in augmented


def test_gating_features_fusion_and_agent_review_contract():
    cases = [_case("a", "harmful claim"), _case("b", "benign note", "non_harmful")]
    matrix, names = build_gating_feature_matrix(
        cases,
        {
            "tweet": {"a": 0.9, "b": 0.2},
            "meme": {"a": 0.1, "b": 0.25},
        },
    )
    assert matrix.shape[0] == 2
    assert "cross_view_conflict" in names
    assert matrix[0, names.index("cross_view_conflict")] == pytest.approx(0.8)

    tweet = standard_detector_output(cases[0], view="tweet", probability=0.9, capability_boundary="tweet")
    meme = standard_detector_output(cases[0], view="meme", probability=0.1, capability_boundary="meme")
    fusion = fuse_detector_outputs([tweet, meme], model_probability=0.55)
    review = build_agent_review([tweet, meme], fusion)

    assert fusion["fusion_policy"] == "trainable_gating_fusion"
    assert fusion["review_required"] is True
    assert "cross_view_conflict" in fusion["review_reason"]
    assert review["role"] == "reviewer_explainer_rule_optimizer"
    assert review["review_required"] is True


def test_metrics_include_calibration_and_coverage():
    labels = np.asarray([1, 0, 1, 0])
    probabilities = np.asarray([0.9, 0.2, 0.55, 0.7], dtype="float32")
    metrics = binary_classification_metrics(labels, probabilities)
    ece = expected_calibration_error(labels, probabilities)
    curve = coverage_risk_curve(labels, probabilities)

    assert 0.0 <= metrics["macro_f1"] <= 1.0
    assert 0.0 <= ece <= 1.0
    assert curve
    assert {"coverage", "risk", "confidence_threshold"} <= set(curve[0])


@pytest.mark.skipif(importlib.util.find_spec("torch") is None, reason="torch not installed")
def test_torch_text_and_gating_smoke_train():
    cases = [_case("a", "harmful claim"), _case("b", "benign note", "non_harmful")]
    features = encode_text_features([case["text"] for case in cases], backend="hash", dim=16).matrix
    labels = np.asarray([1, 0], dtype=int)

    model = MultitaskTextDetector(input_dim=16, hidden_dim=8)
    train_info = train_multitask_text_model(model, features, multitask_targets(cases), epochs=1, batch_size=2, device="cpu")
    probs = predict_probabilities(model, features, device="cpu")
    assert train_info["epochs"] == 1
    assert probs.shape == (2,)

    gating = GatingFusionModel(input_dim=4, hidden_dim=4)
    gate_features = np.asarray([[0.9, 0.8, 1.0, 0.0], [0.2, 0.6, 1.0, 0.0]], dtype="float32")
    train_binary_torch_model(gating, gate_features, labels, epochs=1, batch_size=2, device="cpu")
    gate_probs = predict_probabilities(gating, gate_features, device="cpu")
    assert gate_probs.shape == (2,)


@pytest.mark.skipif(importlib.util.find_spec("torch") is None, reason="torch not installed")
def test_cross_modal_adapter_smoke_train():
    labels = np.asarray([1, 0, 1, 0], dtype=int)
    text = np.asarray(
        [
            [1.0, 0.0, 0.2, 0.1],
            [0.0, 1.0, 0.1, 0.2],
            [0.9, 0.0, 0.3, 0.1],
            [0.0, 0.8, 0.1, 0.3],
        ],
        dtype="float32",
    )
    image = np.asarray(
        [
            [0.9, 0.1, 0.2, 0.0],
            [0.1, 0.9, 0.0, 0.2],
            [0.8, 0.1, 0.3, 0.0],
            [0.2, 0.8, 0.0, 0.3],
        ],
        dtype="float32",
    )
    model = CrossModalAttentionAdapter(text_dim=4, image_dim=4, hidden_dim=8, heads=2)
    info = train_cross_modal_torch_model(model, text, image, labels, epochs=1, batch_size=4, device="cpu")
    probs = predict_probabilities(model, (text, image), device="cpu")

    assert info["epochs"] == 1
    assert info["contrastive_weight"] > 0
    assert probs.shape == (4,)
