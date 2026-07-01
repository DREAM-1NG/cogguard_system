from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.coordination.twitter_io_experiment import (
    DEFAULT_METHODS,
    DEFAULT_RELATION_WEIGHTS,
    ExperimentConfig,
    METHOD_CATALOG,
    run_twitter_io_experiment,
)


def parse_args() -> argparse.Namespace:
    available_methods = sorted(METHOD_CATALOG.keys())
    parser = argparse.ArgumentParser(
        description="Run coordination benchmark methods on a Twitter IO archive zip.",
    )
    parser.add_argument("--tweets-zip", required=True, help="Path to *_tweets_csv_hashed.zip")
    parser.add_argument("--output-dir", required=True, help="Directory for summaries and CSV exports")
    parser.add_argument(
        "--methods",
        nargs="+",
        default=list(DEFAULT_METHODS),
        choices=available_methods,
        help="Benchmark methods to run",
    )
    parser.add_argument(
        "--languages",
        nargs="*",
        default=[],
        help="Optional tweet language filter, e.g. en ru",
    )
    parser.add_argument("--time-window-seconds", type=int, default=60)
    parser.add_argument("--min-accounts-per-object", type=int, default=2)
    parser.add_argument("--max-accounts-per-object", type=int, default=50)
    parser.add_argument("--min-events-per-object", type=int, default=2)
    parser.add_argument("--limit-rows", type=int, default=None)
    parser.add_argument("--attention-epochs", type=int, default=200)
    parser.add_argument("--attention-learning-rate", type=float, default=0.1)
    parser.add_argument("--attention-l2", type=float, default=1e-3)
    parser.add_argument("--attention-max-samples", type=int, default=20000)
    parser.add_argument("--attention-backend", choices=["auto", "numpy", "torch"], default="auto")
    parser.add_argument("--attention-hidden-dim", type=int, default=16)
    parser.add_argument("--attention-negative-ratio", type=float, default=1.0)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument(
        "--relation-weight",
        action="append",
        default=[],
        metavar="REL=WEIGHT",
        help="Override multi-relation weights, e.g. url_share=1.2",
    )
    return parser.parse_args()


def parse_relation_weights(raw_items: list[str]) -> dict[str, float]:
    weights = dict(DEFAULT_RELATION_WEIGHTS)
    for raw_item in raw_items:
        key, _, raw_value = raw_item.partition("=")
        key = key.strip()
        if not key or not raw_value:
            raise ValueError(f"Invalid relation weight: {raw_item!r}")
        weights[key] = float(raw_value)
    return weights


def main() -> None:
    args = parse_args()
    config = ExperimentConfig(
        tweets_zip_path=Path(args.tweets_zip).resolve(),
        output_dir=Path(args.output_dir).resolve(),
        methods=tuple(args.methods),
        languages=tuple(args.languages),
        time_window_seconds=args.time_window_seconds,
        min_accounts_per_object=args.min_accounts_per_object,
        max_accounts_per_object=args.max_accounts_per_object,
        min_events_per_object=args.min_events_per_object,
        limit_rows=args.limit_rows,
        relation_weights=parse_relation_weights(args.relation_weight),
        attention_epochs=args.attention_epochs,
        attention_learning_rate=args.attention_learning_rate,
        attention_l2=args.attention_l2,
        attention_max_samples=args.attention_max_samples,
        attention_backend=args.attention_backend,
        attention_hidden_dim=args.attention_hidden_dim,
        attention_negative_ratio=args.attention_negative_ratio,
        random_seed=args.random_seed,
    )
    summary = run_twitter_io_experiment(config)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
