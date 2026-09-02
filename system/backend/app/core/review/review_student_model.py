"""Multilingual Task-Masked Content Risk Classification Student Model."""

from typing import Any, Dict, Optional
import torch
import torch.nn as nn
from transformers import AutoModel, AutoTokenizer

class XLMRReviewStudent(nn.Module):
    def __init__(self, backbone: str = "xlm-roberta-base", stance_count: int = 3, hidden_size: int = 768):
        super().__init__()
        # Backbone shared multilingual encoder
        self.encoder = AutoModel.from_pretrained(backbone)
        
        # Multi-task Explicit Risk Classification Heads
        self.attack_hate_offense = nn.Linear(hidden_size, 1)
        self.misinfo_claim_risk = nn.Linear(hidden_size, 1)
        self.stance = nn.Linear(hidden_size, stance_count)
        
        # Latent Rationale Distillation Head (projects CLS to Teacher's SBERT space)
        self.rationale_proj = nn.Linear(hidden_size, 768)
        
    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> Dict[str, torch.Tensor]:
        outputs = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        # Using [CLS] token representation for downstream heads
        cls_rep = outputs.last_hidden_state[:, 0, :]
        
        return {
            "attack_hate_offense": self.attack_hate_offense(cls_rep).squeeze(-1),
            "misinfo_claim_risk": self.misinfo_claim_risk(cls_rep).squeeze(-1),
            "stance": self.stance(cls_rep),
            "rationale_proj": self.rationale_proj(cls_rep)
        }

class ReviewStudentExample:
    """Standardized serialized input structure for the student model."""
    def __init__(
        self,
        post_text: str = "",
        hashtags: str = "",
        ocr_text: str = "",
        asr_transcript: str = "",
        caption: str = ""
    ):
        self.post_text = post_text
        self.hashtags = hashtags
        self.ocr_text = ocr_text
        self.asr_transcript = asr_transcript
        self.caption = caption
        
    def serialize_for_tokenizer(self) -> str:
        """Serializes multimodal text fields into a single sequence."""
        parts = []
        if self.post_text:
            parts.append(f"[TEXT] {self.post_text}")
        if self.hashtags:
            parts.append(f"[HASHTAGS] {self.hashtags}")
        if self.ocr_text:
            parts.append(f"[OCR] {self.ocr_text}")
        if self.asr_transcript:
            parts.append(f"[ASR] {self.asr_transcript}")
        if self.caption:
            parts.append(f"[CAPTION] {self.caption}")
        return " ".join(parts)
