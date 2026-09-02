"""Stage 2: Hardcase Mining Pipeline.

This script implements the active learning loop for CogGuard:
1. Loads a trained Stage 1 Student Model (XLMRReviewStudent).
2. Runs inference on an unlabeled pool to compute uncertainty (Shannon Entropy).
3. Selects hardcases (high uncertainty).
4. Invokes the high-cost Teacher (MultiAgents API) ONLY for these hardcases.
5. Saves the Teacher's JudgeRationaleBundle to teacher_silver.jsonl for Stage 3 LRKD.
"""

import argparse
import asyncio
import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List
import sys

import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from app.core.review.review_student_model import XLMRReviewStudent, ReviewStudentExample
from app.core.review.agent_review import run_manual_agent_review
from app.core.review.agent_provider import build_llm_provider_from_settings
from app.core.review.trainable_post import text_of, claim_context_text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hardcase_mining")


def _calculate_entropy(probs: torch.Tensor) -> torch.Tensor:
    """Calculate Shannon entropy for binary probabilities."""
    p = torch.clamp(probs, 1e-7, 1 - 1e-7)
    return - (p * torch.log2(p) + (1 - p) * torch.log2(1 - p))


async def mine_hardcases(args: argparse.Namespace) -> None:
    logger.info(f"Loading Student Model from: {args.student_model_path}")
    # Initialize the student model
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    student = XLMRReviewStudent(backbone=args.student_backbone).to(device)
    student.eval()
    
    # Load optional weights if provided
    if args.student_model_path and Path(args.student_model_path).exists():
        student.load_state_dict(torch.load(args.student_model_path, map_location=device))
        
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.student_backbone)

    logger.info(f"Loading unlabeled dataset from: {args.dataset_path}")
    dataset_path = Path(args.dataset_path)
    if not dataset_path.exists():
        logger.error("Dataset not found!")
        return

    cases = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            cases.append(json.loads(line))
            
    logger.info(f"Loaded {len(cases)} cases.")
    
    scored_cases = []
    
    # Run Inference
    with torch.no_grad():
        for case in cases:
            post_text = text_of(case)
            claim_text = claim_context_text(case)
            example = ReviewStudentExample(post_text=post_text)
            text_input = example.serialize_for_tokenizer()
            if claim_text:
                text_input += f" [CLAIM] {claim_text}"
                
            inputs = tokenizer(text_input, return_tensors="pt", truncation=True, max_length=512).to(device)
            outputs = student(**inputs)
            
            p_attack = torch.sigmoid(outputs["attack_hate_offense"]).item()
            p_misinfo = torch.sigmoid(outputs["misinfo_claim_risk"]).item()
            
            # Uncertainty = Average Entropy of main risk axes
            h_attack = _calculate_entropy(torch.tensor([p_attack])).item()
            h_misinfo = _calculate_entropy(torch.tensor([p_misinfo])).item()
            uncertainty_score = (h_attack + h_misinfo) / 2.0
            
            scored_cases.append({
                "case": case,
                "uncertainty_score": uncertainty_score,
                "p_attack": p_attack,
                "p_misinfo": p_misinfo
            })

    # Sort by uncertainty descending
    scored_cases.sort(key=lambda x: x["uncertainty_score"], reverse=True)
    
    top_k = int(len(cases) * args.mining_ratio)
    hardcases = scored_cases[:top_k]
    
    logger.info(f"Selected {top_k} hardcases out of {len(cases)} based on prediction entropy.")
    
    # Initialize Teacher Provider
    provider = build_llm_provider_from_settings(provider_name="openai-compatible")
    
    output_path = Path(args.output_dir) / "teacher_silver.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Invoking MultiAgents Teacher for {top_k} hardcases. Output to {output_path}")
    
    # Process hardcases via MultiAgents
    with open(output_path, "w", encoding="utf-8") as f_out:
        for i, item in enumerate(hardcases):
            case = item["case"]
            case_id = case.get("case_id", f"hardcase_{i}")
            
            logger.info(f"Processing hardcase {i+1}/{top_k}: {case_id} (Uncertainty: {item['uncertainty_score']:.3f})")
            
            # Mock a basic report structure needed for the runtime
            report_context = {
                "report_id": f"report_{case_id}",
                "post_semantics": [{"post_id": case_id, "excerpt": text_of(case)}],
                "review_harmfulness": {"global_summary": {"review_harm_risk_level": "medium"}},
                "selected_posts": [{"post_id": case_id, "excerpt": text_of(case)}]
            }
            
            try:
                # Ask HarmfulnessJudgeAgent and CountermeasureAgent (complex runtime mode)
                teacher_output = await run_manual_agent_review(
                    report=report_context,
                    agent_names=["HarmfulnessJudgeAgent"],
                    case_id=case_id,
                    selected_post_ids=[case_id],
                    provider=provider,
                    model=args.teacher_model,
                    runtime_mode="complex"
                )
                
                # Extract the final Judge report which contains the Typed Bundle
                judge_report = next((r for r in teacher_output.get("agent_reports", []) if r.get("agent_name") == "HarmfulnessJudgeAgent"), None)
                
                silver_record = {
                    "case_id": case_id,
                    "case_data": case,
                    "student_p_attack": item["p_attack"],
                    "student_p_misinfo": item["p_misinfo"],
                    "uncertainty_score": item["uncertainty_score"],
                    "teacher_bundle": judge_report.get("structured_sidecar", {}) if judge_report else {},
                    "teacher_report_text": judge_report.get("report_text", "") if judge_report else ""
                }
                f_out.write(json.dumps(silver_record, ensure_ascii=False) + "\n")
                
            except Exception as e:
                logger.error(f"Failed to process case {case_id}: {e}")
                
    logger.info("Hardcase mining completed. Teacher silver dataset generated.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-path", required=True, help="Path to unlabeled JSONL dataset")
    parser.add_argument("--student-model-path", default="", help="Path to trained Student weights")
    parser.add_argument("--student-backbone", default="xlm-roberta-base")
    parser.add_argument("--mining-ratio", type=float, default=0.1, help="Top ratio of uncertain cases to select")
    parser.add_argument("--output-dir", default="./outputs", help="Directory for teacher_silver.jsonl")
    parser.add_argument("--teacher-model", default="gpt-4", help="LLM model name for Teacher MultiAgents")
    args = parser.parse_args()
    
    asyncio.run(mine_hardcases(args))

if __name__ == "__main__":
    main()
