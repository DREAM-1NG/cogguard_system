"""CLI for deploying and querying the fixed-graph TwiBot-20 research runtime."""

from __future__ import annotations

import argparse
import json

from .twibot20_runtime import TwiBot20ResearchRuntime, build_twibot20_research_bundle

__all__ = ["main"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deploy or query the NLPCC TwiBot-20 research checkpoint.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="build a hash-verified fixed-graph research bundle")
    build.add_argument("--output-dir", required=True)
    build.add_argument("--checkpoint", required=True)
    build.add_argument("--outputs", required=True)
    build.add_argument("--node-ids", required=True)
    build.add_argument("--source-manifest", required=True)
    build.add_argument("--selection-metrics", required=True)

    info = subparsers.add_parser("info", help="verify a bundle and print its deployment contract")
    info.add_argument("--bundle", required=True)

    predict = subparsers.add_parser("predict", help="query nodes already present in the fixed TwiBot-20 graph")
    predict.add_argument("--bundle", required=True)
    predict.add_argument("--node-id", action="append", required=True)

    args = parser.parse_args(argv)
    if args.command == "build":
        result = build_twibot20_research_bundle(
            args.output_dir,
            checkpoint_path=args.checkpoint,
            outputs_path=args.outputs,
            node_ids_path=args.node_ids,
            source_manifest_path=args.source_manifest,
            selection_metrics_path=args.selection_metrics,
        )
    else:
        runtime = TwiBot20ResearchRuntime(args.bundle)
        result = runtime.model_info() if args.command == "info" else runtime.predict_nodes(args.node_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
