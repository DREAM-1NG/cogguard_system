import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Mocking the actual import of run_manual_agent_review since it requires the full CogGuard Agent setup
# In a real environment, this would import from app.core.review.agent_review
# from app.core.review.agent_review import run_manual_agent_review

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent_worker")

TEACHER_SILVER_PATH = ROOT / ".tmp" / "production_teacher_silver.jsonl"

async def mock_run_manual_agent_review(text: str, metadata: dict) -> dict:
    """
    Simulates the expensive MultiAgent RAG pipeline.
    In reality, this takes 5-10 seconds and consumes API quota.
    """
    await asyncio.sleep(2.0)  # Simulate LLM latency
    
    # Mocking a detailed JudgeRationaleBundle
    return {
        "status": "success",
        "rationale": f"Based on multi-agent analysis and policy matching, this content is highly ambiguous. It contains sarcasm regarding {metadata.get('topic', 'unknown')} which skirts community guidelines.",
        "final_decision": "violation_detected",
        "confidence": 0.85
    }

async def process_hardcase_offline(post_id: str, text: str, metadata: Optional[Dict[str, Any]] = None):
    """
    Background worker function called by the FastAPI Gateway.
    In a distributed setup, this is the Celery task.
    """
    logger.info(f"[Worker] Starting offline MultiAgent review for Post: {post_id}")
    
    try:
        # Here we would call the actual `run_manual_agent_review`
        # result = await run_manual_agent_review(text, metadata or {})
        result = await mock_run_manual_agent_review(text, metadata or {})
        
        # Save the result to teacher_silver.jsonl for Phase 3 Distillation
        save_teacher_silver_record(post_id, text, result)
        
        logger.info(f"[Worker] Successfully processed Post: {post_id}. Appended to silver dataset.")
        
    except Exception as e:
        logger.error(f"[Worker] Failed to process Post {post_id}: {str(e)}")

def save_teacher_silver_record(post_id: str, text: str, agent_result: dict):
    """Appends the Agent's reasoning into the distillation dataset."""
    TEACHER_SILVER_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    record = {
        "post_id": post_id,
        "text": text,
        "explanation": agent_result.get("rationale", ""),
        "teacher_label": agent_result.get("final_decision"),
        "timestamp": "2026-08-13T16:35:00Z" # Mock timestamp
    }
    
    with open(TEACHER_SILVER_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
