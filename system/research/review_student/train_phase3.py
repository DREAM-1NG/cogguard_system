"""Phase 3: Latent Rationale Distillation (LRKD) using HateCOT.

This script demonstrates offline knowledge distillation using the HateCOT dataset.
Instead of relying on online Agent APIs, we use pre-encoded textual explanations
(from HateCOT) as Teacher target vectors to train the Student's `rationale_proj`.
"""

import argparse
import json
import logging
import random
from pathlib import Path
from typing import List, Dict

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer, get_cosine_schedule_with_warmup
from sentence_transformers import SentenceTransformer

from .artifacts import export_student_checkpoint
from system.runtimes.review_student import ReviewStudentInput, XLMRReviewStudent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("train_phase3_distill")


class HateCOTDistillDataset(Dataset):
    def __init__(self, data_list: List[Dict], student_tokenizer, max_length: int = 512):
        self.data = data_list
        self.tokenizer = student_tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        item = self.data[idx]
        post_text = item.get("post", "")
        # Assuming HateCOT labels: offensive -> 1, non-offensive -> 0
        raw_label = item.get("label", "non-offensive")
        binary_label = 1.0 if raw_label.lower() == "offensive" else 0.0

        # Teacher vector is pre-encoded during dataset loading
        teacher_vector = item.get("teacher_vector")

        text_input = ReviewStudentInput(post_text=post_text).serialize()

        encoding = self.tokenizer(
            text_input,
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt"
        )

        return {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
            "label": torch.tensor(binary_label, dtype=torch.float32),
            "teacher_vector": torch.tensor(teacher_vector, dtype=torch.float32)
        }


def load_and_encode_hatecot(filepath: str, sbert_model_name: str, device: torch.device) -> List[Dict]:
    """Loads HateCOT and pre-encodes the `explanation` field into teacher target vectors."""
    logger.info(f"Loading HateCOT from {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    logger.info(f"Loaded {len(data)} records. Pre-encoding Explanations...")
    sbert = SentenceTransformer(sbert_model_name, device=device)

    explanations = [item.get("explanation", "") for item in data]
    # Encode with SBERT (outputs a numpy array)
    embeddings = sbert.encode(explanations, batch_size=64, show_progress_bar=True, normalize_embeddings=True)

    for i, item in enumerate(data):
        item["teacher_vector"] = embeddings[i].tolist()

    return data


def train(args: argparse.Namespace):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Using device: {device}")

    # 1. Load and pre-encode dataset
    raw_data = load_and_encode_hatecot(args.dataset_path, args.sbert_model, device)

    random.seed(args.seed)
    random.shuffle(raw_data)

    split_idx = int(len(raw_data) * 0.8)
    train_data = raw_data[:split_idx]
    val_data = raw_data[split_idx:]

    tokenizer = AutoTokenizer.from_pretrained(args.student_backbone)

    train_dataset = HateCOTDistillDataset(train_data, tokenizer, args.max_length)
    val_dataset = HateCOTDistillDataset(val_data, tokenizer, args.max_length)

    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False)

    model = XLMRReviewStudent(backbone=args.student_backbone).to(device)

    # Optional: Load Phase 1 weights if provided
    if args.phase1_weights:
        logger.info(f"Loading Phase 1 weights from {args.phase1_weights}")
        payload = torch.load(args.phase1_weights, map_location=device, weights_only=True)
        state_dict = payload.get("state_dict") if isinstance(payload, dict) else payload
        model.load_state_dict(state_dict, strict=False)

    criterion_cls = nn.BCEWithLogitsLoss()
    criterion_distill = nn.CosineEmbeddingLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate)

    total_steps = len(train_loader) * args.epochs
    scheduler = get_cosine_schedule_with_warmup(
        optimizer,
        num_warmup_steps=int(total_steps * 0.1),
        num_training_steps=total_steps
    )

    best_val_loss = float("inf")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for epoch in range(args.epochs):
        model.train()
        train_loss = 0.0
        train_cls_loss = 0.0
        train_distill_loss = 0.0

        for batch_idx, batch in enumerate(train_loader):
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["label"].to(device)
            teacher_vectors = batch["teacher_vector"].to(device)

            optimizer.zero_grad()

            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            logits = outputs["attack_hate_offense"]
            rationale_preds = outputs["rationale_proj"]

            # Loss 1: Classification (Hard labels)
            loss_cls = criterion_cls(logits, labels)

            # Loss 2: Latent Distillation
            # CosineEmbeddingLoss expects targets of 1 (make them similar)
            target_cosine = torch.ones(labels.size(0)).to(device)
            loss_distill = criterion_distill(rationale_preds, teacher_vectors, target_cosine)

            # Joint Optimization
            loss = loss_cls + args.alpha * loss_distill
            loss.backward()
            optimizer.step()
            scheduler.step()

            train_loss += loss.item()
            train_cls_loss += loss_cls.item()
            train_distill_loss += loss_distill.item()

            if (batch_idx + 1) % 50 == 0:
                logger.info(f"Epoch {epoch+1}/{args.epochs} | Batch {batch_idx+1}/{len(train_loader)} | Total Loss: {loss.item():.4f} (Cls: {loss_cls.item():.4f}, Distill: {loss_distill.item():.4f})")

        avg_train_loss = train_loss / len(train_loader)

        # Validation
        model.eval()
        val_loss = 0.0
        correct = 0
        total = 0

        with torch.no_grad():
            for batch in val_loader:
                input_ids = batch["input_ids"].to(device)
                attention_mask = batch["attention_mask"].to(device)
                labels = batch["label"].to(device)
                teacher_vectors = batch["teacher_vector"].to(device)

                outputs = model(input_ids=input_ids, attention_mask=attention_mask)
                logits = outputs["attack_hate_offense"]
                rationale_preds = outputs["rationale_proj"]

                loss_cls = criterion_cls(logits, labels)
                target_cosine = torch.ones(labels.size(0)).to(device)
                loss_distill = criterion_distill(rationale_preds, teacher_vectors, target_cosine)

                loss = loss_cls + args.alpha * loss_distill
                val_loss += loss.item()

                preds = (torch.sigmoid(logits) >= 0.5).float()
                correct += (preds == labels).sum().item()
                total += labels.size(0)

        avg_val_loss = val_loss / len(val_loader)
        val_acc = correct / total

        logger.info(f"--- Epoch {epoch+1} Summary ---")
        logger.info(f"Train Loss: {avg_train_loss:.4f} | Val Loss: {avg_val_loss:.4f} | Val Acc: {val_acc:.4f}")

        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            artifact = export_student_checkpoint(
                model=model,
                output_dir=output_dir,
                filename="student_phase3_distilled.pt",
                version="review-student-phase3-distilled",
                backbone=args.student_backbone,
                rationale_dim=768,
                metrics={
                    "training_stage": "phase3_latent_distillation",
                    "validation_loss": avg_val_loss,
                    "validation_accuracy": val_acc,
                },
            )
            logger.info("Saved best distilled model to %s", artifact["checkpoint_path"])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-path", required=True, help="Path to HateCOT dataset JSON")
    parser.add_argument("--student-backbone", default="xlm-roberta-base")
    parser.add_argument("--sbert-model", default="sentence-transformers/all-mpnet-base-v2", help="768d SBERT model")
    parser.add_argument("--phase1-weights", type=str, default="", help="Optional path to phase1 weights to warm-start")
    parser.add_argument("--output-dir", default="./outputs_phase3")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--alpha", type=float, default=1.0, help="Weight for distillation loss")
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    train(args)

if __name__ == "__main__":
    main()
