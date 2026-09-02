import logging
import math
from typing import Dict, Any, Optional
import sys
from pathlib import Path

from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.review.review_student_model import XLMRReviewStudent, ReviewStudentExample
from app.api.agent_worker import process_hardcase_offline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("student_gateway")

app = FastAPI(title="CogGuard Student Triage Gateway", version="1.0")

# Global variables for model and tokenizer
MODEL = None
TOKENIZER = None
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
ENTROPY_THRESHOLD = 0.6  # Configurable threshold

class ReviewRequest(BaseModel):
    post_id: str
    text: str
    metadata: Optional[Dict[str, Any]] = None

class ReviewResponse(BaseModel):
    post_id: str
    attack_hate_prob: float
    misinfo_prob: float
    entropy: float
    decision: str  # "blocked", "allowed", "pending_agent_review"

def calculate_entropy(prob: float) -> float:
    """Calculates Binary Shannon Entropy."""
    if prob <= 0.0 or prob >= 1.0:
        return 0.0
    return -(prob * math.log2(prob) + (1 - prob) * math.log2(1 - prob))

@app.on_event("startup")
async def startup_event():
    global MODEL, TOKENIZER
    logger.info("Loading XLMRReviewStudent Distilled Model...")
    # Assuming phase3 distilled weights exist, otherwise falls back to random init for testing
    backbone_name = "xlm-roberta-base"
    TOKENIZER = AutoTokenizer.from_pretrained(backbone_name)
    MODEL = XLMRReviewStudent(backbone=backbone_name).to(DEVICE)
    MODEL.eval()
    logger.info("Model loaded successfully.")

@app.post("/review", response_model=ReviewResponse)
async def review_content(request: ReviewRequest, background_tasks: BackgroundTasks):
    """
    High-concurrency triage endpoint.
    Runs the lightweight student model and routes based on entropy.
    """
    if not MODEL or not TOKENIZER:
        raise HTTPException(status_code=503, detail="Model not loaded")

    # 1. Prepare input
    example = ReviewStudentExample(post_text=request.text)
    text_input = example.serialize_for_tokenizer()
    
    encoding = TOKENIZER(
        text_input,
        truncation=True,
        padding="max_length",
        max_length=256,
        return_tensors="pt"
    ).to(DEVICE)
    
    # 2. Forward pass (No RAG, No LLM API calls here)
    with torch.no_grad():
        outputs = MODEL(input_ids=encoding["input_ids"], attention_mask=encoding["attention_mask"])
        # Sigmoid for binary classification probability
        hate_prob = torch.sigmoid(outputs["attack_hate_offense"]).item()
        misinfo_prob = torch.sigmoid(outputs["misinfo_claim_risk"]).item()
        
    # 3. Calculate Uncertainty (Entropy)
    hate_entropy = calculate_entropy(hate_prob)
    misinfo_entropy = calculate_entropy(misinfo_prob)
    max_entropy = max(hate_entropy, misinfo_entropy)
    
    # 4. Triage Routing
    if max_entropy >= ENTROPY_THRESHOLD:
        decision = "pending_agent_review"
        # Push to async queue (BackgroundTasks simulates Celery in this PoC)
        logger.info(f"[{request.post_id}] High entropy ({max_entropy:.4f}) detected. Routing to Agent Worker.")
        background_tasks.add_task(process_hardcase_offline, request.post_id, request.text, request.metadata)
    else:
        # Simple thresholding logic for fast-path
        is_violation = (hate_prob > 0.8) or (misinfo_prob > 0.8)
        decision = "blocked" if is_violation else "allowed"
        logger.info(f"[{request.post_id}] Low entropy ({max_entropy:.4f}). Fast-path decision: {decision}")

    return ReviewResponse(
        post_id=request.post_id,
        attack_hate_prob=hate_prob,
        misinfo_prob=misinfo_prob,
        entropy=max_entropy,
        decision=decision
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
