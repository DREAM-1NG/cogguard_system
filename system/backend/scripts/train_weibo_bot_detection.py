"""Train the local Weibo bot detection baseline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.bot_training import DEFAULT_DATASET_ROOT
from app.core.bot_training import DEFAULT_OUTPUT_DIR
from app.core.bot_training import train_weibo_bot_model


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the local Weibo bot detection baseline.")
    parser.add_argument("--dataset-root", default=str(DEFAULT_DATASET_ROOT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--max-features", type=int, default=5000)
    args = parser.parse_args()

    report = train_weibo_bot_model(
        args.dataset_root,
        output_dir=args.output_dir,
        test_size=args.test_size,
        random_state=args.random_state,
        max_features=args.max_features,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

