"""Phase 1: Pure Text SFT Training Script (HateXplain).

This script trains the XLMRReviewStudent on the HateXplain dataset using
standard binary cross entropy, mapping HateXplain's 3 classes to binary
risk labels (0: normal, 1: hate/offensive).

Latent rationale distillation is completely disabled in this phase.
"""

import argparse
import json
import logging
import random
from pathlib import Path
from typing import List, Dict, Tuple

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer, get_cosine_schedule_with_warmup

from .artifacts import export_student_checkpoint
from system.runtimes.review_student import ReviewStudentInput, XLMRReviewStudent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("train_phase1")


class HateXplainDataset(Dataset):
    def __init__(self, data_list: List[Dict], tokenizer, max_length: int = 512):
        self.data = data_list
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        item = self.data[idx]
        post_tokens = item.get("post_tokens", [])
        post_text = " ".join(post_tokens)

        # Determine majority label
        counts = {"hatespeech": 0, "offensive": 0, "normal": 0}
        for ann in item.get("annotators", []):
            label = ann.get("label", "normal")
            if label in counts:
                counts[label] += 1

        # Majority vote
        majority_label = max(counts, key=counts.get)
        # Binary mapping: normal -> 0, hatespeech/offensive -> 1
        binary_label = 0.0 if majority_label == "normal" else 1.0

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
            "label": torch.tensor(binary_label, dtype=torch.float32)
        }


def load_hatexplain(filepath: str) -> List[Dict]:
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    # HateXplain is usually a dict {post_id: {data}}
    if isinstance(data, dict):
        return list(data.values())
    return data


def train(args: argparse.Namespace):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Using device: {device}")

    logger.info(f"Loading dataset from {args.dataset_path}")
    raw_data = load_hatexplain(args.dataset_path)
    logger.info(f"Loaded {len(raw_data)} records.")

    random.seed(args.seed)
    random.shuffle(raw_data)

    split_idx = int(len(raw_data) * 0.8)
    train_data = raw_data[:split_idx]
    val_data = raw_data[split_idx:]

    tokenizer = AutoTokenizer.from_pretrained(args.student_backbone)

    train_dataset = HateXplainDataset(train_data, tokenizer, args.max_length)
    val_dataset = HateXplainDataset(val_data, tokenizer, args.max_length)

    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False)

    model = XLMRReviewStudent(backbone=args.student_backbone).to(device)

    criterion = nn.BCEWithLogitsLoss()
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

        for batch_idx, batch in enumerate(train_loader):
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["label"].to(device)

            optimizer.zero_grad()

            # Forward pass: note we only care about attack_hate_offense in Phase 1
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            logits = outputs["attack_hate_offense"]

            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()
            scheduler.step()

            train_loss += loss.item()

            if (batch_idx + 1) % 50 == 0:
                logger.info(f"Epoch {epoch+1}/{args.epochs} | Batch {batch_idx+1}/{len(train_loader)} | Loss: {loss.item():.4f}")

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

                outputs = model(input_ids=input_ids, attention_mask=attention_mask)
                logits = outputs["attack_hate_offense"]
                loss = criterion(logits, labels)
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
                filename="student_phase1_best.pt",
                version="review-student-phase1",
                backbone=args.student_backbone,
                rationale_dim=768,
                metrics={
                    "training_stage": "phase1_sft",
                    "validation_loss": avg_val_loss,
                    "validation_accuracy": val_acc,
                },
            )
            logger.info("Saved best model to %s", artifact["checkpoint_path"])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-path", required=True, help="Path to HateXplain dataset.json")
    parser.add_argument("--student-backbone", default="xlm-roberta-base")
    parser.add_argument("--output-dir", default="./outputs_phase1")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    train(args)

if __name__ == "__main__":
    main()
