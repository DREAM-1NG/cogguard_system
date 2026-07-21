from __future__ import annotations

import base64

from app.core.risk.kt3_agent_media import agent_requires_vision
from app.core.risk.kt3_agent_media import build_media_inputs_for_post
from app.core.risk.kt3_agent_media import build_provider_input_bundle_for_agent
from app.core.risk.kt3_agent_media import build_vision_input_status
from app.core.risk.kt3_agent_media import infer_media_type
from app.core.risk.kt3_agent_media import maybe_data_url
from app.core.risk.kt3_agent_media import provider_should_receive_media


def test_build_media_inputs_preserves_platform_neutral_media_and_derived_text():
    post = {
        "post_id": "p-1",
        "media_urls": ["G:/media/a.jpg", "G:/media/b.mp4", "G:/media/c.bin"],
        "raw_data": {"ocr_text": " OCR text ", "asr_text": " ASR text "},
        "evidence": {"caption": "caption text"},
    }

    rows = build_media_inputs_for_post(post, include_media_base64=False, max_keyframes=2)

    assert [row["media_type"] for row in rows] == ["image", "video_keyframe_reference"]
    assert [row["media_index"] for row in rows] == [0, 1]
    assert rows[0]["post_id"] == "p-1"
    assert rows[0]["ocr_text"] == "OCR text"
    assert rows[0]["asr_text"] == "ASR text"
    assert rows[0]["caption"] == "caption text"
    assert "data_url" not in rows[0]

    derived = build_media_inputs_for_post(
        {"post_id": "p-2", "raw_data": {"caption": "derived caption"}},
        include_media_base64=False,
        max_keyframes=2,
    )
    assert derived == [
        {
            "post_id": "p-2",
            "media_index": 0,
            "media_type": "derived_text_only",
            "uri": "",
            "selection_policy": "no_media_file_reference_available",
            "ocr_text": "",
            "asr_text": "",
            "caption": "derived caption",
        }
    ]


def test_maybe_data_url_only_embeds_supported_local_images(tmp_path):
    image = tmp_path / "fixture.png"
    payload = b"\x89PNG\r\n\x1a\nfixture"
    image.write_bytes(payload)
    unsupported = tmp_path / "fixture.txt"
    unsupported.write_text("not image", encoding="utf-8")

    assert maybe_data_url(str(image)) == f"data:image/png;base64,{base64.b64encode(payload).decode('ascii')}"
    assert maybe_data_url(str(unsupported)) is None
    assert maybe_data_url(str(tmp_path / "missing.png")) is None


def test_media_type_and_vision_gate_are_agent_scoped():
    assert infer_media_type("a.jpeg") == "image"
    assert infer_media_type("a.webm") == "video_keyframe_reference"
    assert infer_media_type("a.bin") == "media_reference"

    state = {"require_vision": True}
    assert agent_requires_vision("MultimodalConsistencyAgent", context={}, state=state) is True
    assert agent_requires_vision("HarmfulnessJudgeAgent", context={}, state=state) is False
    assert agent_requires_vision("MultimodalConsistencyAgent", context={}, state={}) is False


def test_provider_bundle_keeps_media_only_for_visual_review_agents():
    context = {"media_inputs": [{"media_type": "image", "data_url": "data:image/png;base64,AAAA"}], "claim": "x"}

    multimodal = build_provider_input_bundle_for_agent("MultimodalConsistencyAgent", context=context)
    debate = build_provider_input_bundle_for_agent("FullDebate:MultimodalConsistencyAgent", context=context)
    text_only = build_provider_input_bundle_for_agent("ClaimEvidenceAgent", context=context)

    assert multimodal is context
    assert debate is context
    assert text_only is not context
    assert text_only["media_inputs"] == []
    assert context["media_inputs"]
    assert provider_should_receive_media("MultimodalConsistencyAgent") is True
    assert provider_should_receive_media("FullDebate:HarmfulnessJudgeAgent") is True
    assert provider_should_receive_media("ClaimEvidenceAgent") is False


def test_vision_input_status_reports_payload_availability():
    status = build_vision_input_status(
        {
            "media_inputs": [
                {"media_type": "image", "data_url": "data:image/png;base64,AAAA"},
                {"media_type": "video_keyframe_reference"},
                "ignored",
            ]
        }
    )

    assert status == {
        "has_vision_input": True,
        "media_input_count": 2,
        "data_url_count": 1,
        "media_types": ["image", "video_keyframe_reference"],
        "requires_base64_or_accessible_image_url": True,
    }
