"""Command-line entrypoint for the internal Weibo BotRHG experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .contracts import ModelConfig, TrainingConfig
from .strict_training import train_strict_botrhg
from .training import train_botrhg

__all__ = ["main"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train and evaluate internal BotRHG on a supported social-bot corpus.")
    parser.add_argument("--dataset-name", default="botection", choices=["botection", "cresci_2015", "cresci_2017", "midterm_2018"])
    parser.add_argument("--dataset-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--text-model-path", required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--base-epochs", type=int, default=3)
    parser.add_argument("--correction-epochs", type=int, default=3)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-chunks-per-account", type=int, default=8)
    parser.add_argument("--max-posts-per-account", type=int, default=64)
    parser.add_argument("--encoder-trainable", action="store_true", help="fine-tune the local RoBERTa encoder")
    parser.add_argument("--support-k", type=int, default=8)
    parser.add_argument("--routing-budget", type=float, default=0.10)
    parser.add_argument("--strict-method", action="store_true", help="train the strict NLPCC-aligned BotRHG stack")
    args = parser.parse_args(argv)
    config = TrainingConfig(
        seed=args.seed,
        base_epochs=args.base_epochs,
        correction_epochs=args.correction_epochs,
        device=args.device,
        dataset_name=args.dataset_name,
        model=ModelConfig(
            text_model_path=args.text_model_path,
            max_length=args.max_length,
            batch_size=args.batch_size,
            max_chunks_per_account=args.max_chunks_per_account,
            max_posts_per_account=args.max_posts_per_account,
            encoder_trainable=args.encoder_trainable,
            support_k=args.support_k,
            routing_budget=args.routing_budget,
        ),
    )
    if args.strict_method:
        if args.dataset_name == "botection":
            parser.error("--strict-method requires one of: cresci_2015, cresci_2017, midterm_2018")
        report = train_strict_botrhg(args.dataset_root, args.output_dir, dataset_name=args.dataset_name, config=config)
    else:
        report = train_botrhg(args.dataset_root, args.output_dir, config=config)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
