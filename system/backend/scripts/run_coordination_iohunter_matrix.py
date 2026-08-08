from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from research.coordination_experiments import (
    CANONICAL_IOHUNTER_PROCESSED_ROOT,
    IOHUNTER_COMPACT_CAMPAIGNS,
    IOHUNTER_COMPACT_METHODS,
    IOHUNTER_COMPACT_SEEDS,
    run_compact_iohunter_matrix,
    validate_compact_matrix_output_dir,
)


def _json_scalar(value: str) -> Any:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"override value must be JSON: {value}") from exc
    if isinstance(parsed, (dict, list)):
        raise argparse.ArgumentTypeError("override value must be a JSON scalar")
    return parsed


def _method_overrides(values: Sequence[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for value in values:
        target, separator, raw = value.partition("=")
        method, dot, field = target.partition(".")
        if not separator or not dot or not method or not field:
            raise ValueError("method config overrides must use METHOD.FIELD=JSON_VALUE")
        if method not in IOHUNTER_COMPACT_METHODS:
            raise ValueError(f"unknown compact method in override: {method}")
        method_values = result.setdefault(method, {})
        if field in method_values:
            raise ValueError(f"duplicate method config override: {method}.{field}")
        method_values[field] = _json_scalar(raw)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Execute the research-only compact IOHunter Discovery matrix and external account proxy audit."
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=CANONICAL_IOHUNTER_PROCESSED_ROOT,
        help="IOHunter processed dataset root",
    )
    parser.add_argument(
        "--output",
        type=validate_compact_matrix_output_dir,
        required=True,
        help="required run directory below the canonical G-drive reproduction output root",
    )
    parser.add_argument("--campaign", action="append", choices=IOHUNTER_COMPACT_CAMPAIGNS)
    parser.add_argument("--seed", action="append", type=int, choices=IOHUNTER_COMPACT_SEEDS)
    parser.add_argument("--method", action="append", choices=IOHUNTER_COMPACT_METHODS)
    parser.add_argument("--memory-budget-bytes", type=int, default=16 * 1024**3)
    parser.add_argument("--bootstrap-seed", type=int, default=0)
    parser.add_argument("--bootstrap-resamples", type=int, default=2_000)
    parser.add_argument(
        "--method-config-override",
        action="append",
        default=[],
        metavar="METHOD.FIELD=JSON_VALUE",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    overrides = _method_overrides(args.method_config_override)
    matrix = run_compact_iohunter_matrix(
        args.dataset_root,
        args.output,
        campaigns=args.campaign,
        seeds=args.seed,
        methods=args.method,
        memory_budget_bytes=args.memory_budget_bytes,
        method_config_overrides=overrides,
        bootstrap_seed=args.bootstrap_seed,
        bootstrap_resamples=args.bootstrap_resamples,
    )
    print(json.dumps(matrix.summary(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
