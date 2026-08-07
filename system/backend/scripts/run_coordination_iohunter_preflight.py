from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from research.coordination_experiments import (
    CANONICAL_IOHUNTER_PROCESSED_ROOT,
    CANONICAL_REPRODUCTION_OUTPUT_ROOT,
    IOHUNTER_PREFLIGHT_STATUS,
    preflight_iohunter_matrix,
    validate_iohunter_preflight_output_dir,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Write deterministic IOHunter compact preflight manifests without model execution."
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=CANONICAL_IOHUNTER_PROCESSED_ROOT,
        help="IOHunter processed dataset root containing campaign/0.7_datasets.pkl",
    )
    parser.add_argument(
        "--output",
        type=validate_iohunter_preflight_output_dir,
        default=CANONICAL_REPRODUCTION_OUTPUT_ROOT / "preflight",
        help="G-drive descendant of the canonical coordination reproduction output root",
    )
    parser.add_argument(
        "--memory-budget-bytes",
        type=int,
        default=16 * 1024**3,
        help="pre-model compact loading memory budget",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    matrix = preflight_iohunter_matrix(
        args.dataset_root,
        args.output,
        memory_budget_bytes=args.memory_budget_bytes,
    )
    print(
        json.dumps(
            {
                "status": IOHUNTER_PREFLIGHT_STATUS,
                "output": matrix.output_dir,
                "matrix_fingerprint": matrix.matrix_fingerprint,
                "row_count": len(matrix.rows),
                "model_execution_started": matrix.model_execution_started,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
