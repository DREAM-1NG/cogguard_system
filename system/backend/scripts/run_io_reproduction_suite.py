from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.coordination_baseline.io_reproduction import (
    DEFAULT_RELATIONS,
    DISCOVER_STRUCTURE_FILTERS,
    DISCOVER_STRUCTURE_FILTER_METRICS,
    STABLE_DISCOVER_ENCODER,
    build_iohunter_commands,
    build_iohunter_run_plan,
    build_coordination_discover_comparison_report,
    ensure_iohunter_official_data_layout,
    inspect_iohunter_data,
    iohunter_workspace_status,
    load_iohunter_run_plan,
    patch_iohunter_official_scripts,
    prepare_iohunter_workspace,
    read_event_table,
    IOHUNTER_CANONICAL_RELATIONS,
    run_dyna_colm_ablation_suite,
    run_dyna_colm_characterize,
    run_dyna_colm_detect,
    run_dyna_colm_discover,
    run_iohunter_lightweight_batch,
    run_iohunter_plan,
    run_reproduction_suite,
    summarize_iohunter_runs,
    write_iohunter_event_table,
    write_iohunter_run_exports,
    write_sample_events,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run CoordinationDiscover IO reproduction baselines and DynaCoLM-GNN smoke experiments.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sample_parser = subparsers.add_parser("make-sample", help="Write a tiny labeled event table")
    sample_parser.add_argument("--output", required=True, help="CSV path for the sample event table")

    run_parser = subparsers.add_parser("run", help="Run Unmasking/LLM/Ours on an event table")
    run_parser.add_argument("--events", required=True, help="CSV/JSONL event table")
    run_parser.add_argument("--output-dir", required=True, help="Directory for JSON outputs")
    run_parser.add_argument("--relations", nargs="*", default=list(DEFAULT_RELATIONS))
    run_parser.add_argument("--no-text-similarity", action="store_true", help="Disable text-similarity graph construction")
    run_parser.add_argument("--max-edges-per-node", type=int, default=0, help="Optional per-node cap for similarity graph edges")
    run_parser.add_argument("--embedding-dim", type=int, default=128)
    run_parser.add_argument("--seed", type=int, default=42)

    discover_parser = subparsers.add_parser("discover", help="Run DynaCoLM-Discover for unsupervised coordination discovery")
    discover_parser.add_argument("--events", required=True, help="CSV/JSONL event table")
    discover_parser.add_argument("--output-dir", required=True, help="Directory for discovery_summary.json")
    discover_parser.add_argument("--relations", nargs="*", default=list(DEFAULT_RELATIONS))
    discover_parser.add_argument("--seed", type=int, default=42)
    discover_parser.add_argument(
        "--encoder",
        choices=("lightweight", "han_relation", "han", "magnn_legacy", "magnn", "amdn_hage"),
        default=STABLE_DISCOVER_ENCODER,
        help="Label-free Discover encoder; defaults to the stable legacy MAGNN baseline. Use magnn only for deprecated historical replay.",
    )
    discover_parser.add_argument("--epochs", type=int, default=80)
    discover_parser.add_argument("--embedding-dim", type=int, default=64)
    discover_parser.add_argument("--hidden-dim", type=int, default=64)
    discover_parser.add_argument("--lr", type=float, default=1e-3)
    discover_parser.add_argument("--negative-ratio", type=float, default=1.0)
    discover_parser.add_argument("--device", default="auto")
    discover_parser.add_argument("--community-algorithm", choices=("leiden", "louvain", "greedy"), default="leiden")
    discover_parser.add_argument(
        "--structure-filter",
        choices=DISCOVER_STRUCTURE_FILTERS,
        default="none",
        help="Deprecated compatibility flag. CoordinationDiscover Discover always runs the stable full-graph encoder and ignores structural filtering requests.",
    )
    discover_parser.add_argument(
        "--structure-filter-metric",
        choices=DISCOVER_STRUCTURE_FILTER_METRICS,
        default="eigenvector",
        help="Deprecated compatibility flag retained for old manifests; ignored by CoordinationDiscover Discover.",
    )
    discover_parser.add_argument(
        "--structure-filter-percentile",
        type=float,
        default=90.0,
        help="Deprecated compatibility flag retained for old manifests; ignored by CoordinationDiscover Discover.",
    )
    discover_parser.add_argument(
        "--structure-filter-use-weights",
        action="store_true",
        help="Deprecated compatibility flag retained for old manifests; ignored by CoordinationDiscover Discover.",
    )

    detect_parser = subparsers.add_parser("detect", help="Run DynaCoLM-Detect for labeled coordination discrimination")
    detect_parser.add_argument("--events", required=True, help="CSV/JSONL event table with labels")
    detect_parser.add_argument("--output-dir", required=True, help="Directory for detection_summary.json and predictions.csv")
    detect_parser.add_argument("--relations", nargs="*", default=list(DEFAULT_RELATIONS))
    detect_parser.add_argument("--seed", type=int, default=42)
    detect_parser.add_argument(
        "--discover-encoder",
        choices=("lightweight", "han_relation", "han", "magnn_legacy", "magnn", "amdn_hage"),
        default=STABLE_DISCOVER_ENCODER,
        help="Label-free Discover encoder whose outputs become Detect features",
    )
    detect_parser.add_argument("--discover-epochs", type=int, default=20)
    detect_parser.add_argument("--detect-epochs", type=int, default=0, help="Optional supervised Detect training epochs; 0 keeps the default derived from discover epochs")
    detect_parser.add_argument("--embedding-dim", type=int, default=32)
    detect_parser.add_argument("--hidden-dim", type=int, default=32)
    detect_parser.add_argument("--device", default="auto")
    detect_parser.add_argument("--lm-backend", choices=("sbert", "tfidf"), default="sbert")
    detect_parser.add_argument(
        "--gnn-backend",
        choices=("gfm_lm_gnn", "gfm_lm_gnn_cpu_light", "fusion_gnn", "relation_gnn", "classifier"),
        default="gfm_lm_gnn",
    )
    detect_parser.add_argument(
        "--split-mode",
        choices=("supervised", "scarce_supervised", "cross_io"),
        default="supervised",
    )

    characterize_parser = subparsers.add_parser("characterize", help="Run Detect-Characterize two-stage community characterization")
    characterize_parser.add_argument("--events", required=True, help="CSV/JSONL event table with labels")
    characterize_parser.add_argument("--output-dir", required=True, help="Directory for characterization_summary.json")
    characterize_parser.add_argument("--relations", nargs="*", default=list(DEFAULT_RELATIONS))
    characterize_parser.add_argument("--seed", type=int, default=42)

    ablation_parser = subparsers.add_parser("ablation", help="Run DynaCoLM-Detect ablation suite")
    ablation_parser.add_argument("--events", required=True, help="CSV/JSONL event table with labels")
    ablation_parser.add_argument("--output-dir", required=True, help="Directory for ablation_summary.json")
    ablation_parser.add_argument("--relations", nargs="*", default=list(DEFAULT_RELATIONS))
    ablation_parser.add_argument("--seed", type=int, default=42)

    convert_parser = subparsers.add_parser("iohunter-convert", help="Convert official IOHunter processed pickle to event CSV/JSONL")
    convert_parser.add_argument("--dataset-dir", required=True, help="Directory containing 0.7_datasets.pkl")
    convert_parser.add_argument("--output", required=True, help="Output CSV/JSONL event table")
    convert_parser.add_argument("--dataset-name", default="", help="Optional dataset name override")
    convert_parser.add_argument("--threshold", default="0.7")
    convert_parser.add_argument("--train-percentage", default="")
    convert_parser.add_argument("--undersampling", default="")
    convert_parser.add_argument("--max-edges-per-relation", type=int, default=0)

    iohunter_light_parser = subparsers.add_parser("iohunter-lightweight", help="Run Unmasking/LLM/Ours on IOHunter processed data")
    iohunter_light_parser.add_argument("--dataset-dir", required=True, help="Directory containing 0.7_datasets.pkl")
    iohunter_light_parser.add_argument("--output-dir", required=True, help="Directory for converted events and metrics")
    iohunter_light_parser.add_argument("--dataset-name", default="", help="Optional dataset name override")
    iohunter_light_parser.add_argument("--threshold", default="0.7")
    iohunter_light_parser.add_argument("--train-percentage", default="")
    iohunter_light_parser.add_argument("--undersampling", default="")
    iohunter_light_parser.add_argument("--max-edges-per-relation", type=int, default=0)
    iohunter_light_parser.add_argument("--no-text-similarity", action="store_true", help="Disable text-similarity graph construction")
    iohunter_light_parser.add_argument("--max-edges-per-node", type=int, default=0, help="Optional per-node cap for similarity graph edges")
    iohunter_light_parser.add_argument("--embedding-dim", type=int, default=128)
    iohunter_light_parser.add_argument("--seed", type=int, default=42)
    iohunter_light_parser.add_argument("--relations", nargs="*", default=list(IOHUNTER_CANONICAL_RELATIONS))

    iohunter_batch_parser = subparsers.add_parser("iohunter-lightweight-batch", help="Run Unmasking/LLM/Ours on multiple IOHunter processed datasets")
    iohunter_batch_parser.add_argument("--processed-root", required=True, help="Root containing dataset subdirectories with 0.7_datasets.pkl")
    iohunter_batch_parser.add_argument("--output-dir", required=True, help="Directory for per-dataset outputs and aggregate report")
    iohunter_batch_parser.add_argument("--datasets", nargs="*", default=["UAE", "cuba", "russia", "venezuela", "iran", "china"])
    iohunter_batch_parser.add_argument("--threshold", default="0.7")
    iohunter_batch_parser.add_argument("--train-percentage", default="")
    iohunter_batch_parser.add_argument("--undersampling", default="")
    iohunter_batch_parser.add_argument("--max-edges-per-relation", type=int, default=0)
    iohunter_batch_parser.add_argument("--include-text-similarity", action="store_true", help="Enable text-similarity graph construction; off by default for processed IOHunter data")
    iohunter_batch_parser.add_argument("--max-edges-per-node", type=int, default=50, help="Per-node cap for similarity graph edges")
    iohunter_batch_parser.add_argument("--embedding-dim", type=int, default=32)
    iohunter_batch_parser.add_argument("--include-temporal-edge-candidate", action="store_true", help="Also run the temporal-edge research candidate as a sidecar evaluation")
    iohunter_batch_parser.add_argument(
        "--research-candidate-only",
        action="store_true",
        help="Skip historical lightweight baselines and run only the non-claimable research candidate",
    )
    iohunter_batch_parser.add_argument("--candidate-epochs", type=int, default=8)
    iohunter_batch_parser.add_argument("--candidate-embedding-dim", type=int, default=16)
    iohunter_batch_parser.add_argument("--candidate-hidden-dim", type=int, default=32)
    iohunter_batch_parser.add_argument("--candidate-lr", type=float, default=0.01)
    iohunter_batch_parser.add_argument("--candidate-negative-ratio", type=int, default=2)
    iohunter_batch_parser.add_argument("--candidate-device", default="cpu")
    iohunter_batch_parser.add_argument("--candidate-early-stop-patience", type=int, default=3)
    iohunter_batch_parser.add_argument("--candidate-seeds", nargs="*", type=int, default=[])
    iohunter_batch_parser.add_argument(
        "--include-temporal-edge-ablations",
        action="store_true",
        help="Run research-only temporal edge ablations alongside the multi-seed candidate",
    )
    iohunter_batch_parser.add_argument("--candidate-ablation-seeds", nargs="*", type=int, default=[])
    iohunter_batch_parser.add_argument("--seed", type=int, default=42)
    iohunter_batch_parser.add_argument("--relations", nargs="*", default=list(IOHUNTER_CANONICAL_RELATIONS))
    iohunter_batch_parser.add_argument("--continue-on-error", action="store_true")

    iohunter_parser = subparsers.add_parser("iohunter", help="Prepare or inspect IOHunter reproduction")
    iohunter_parser.add_argument("--workspace", required=True, help="Workspace that contains SocGFM and data/")
    iohunter_parser.add_argument("--clone-code", action="store_true", help="Clone official SocGFM repository")
    iohunter_parser.add_argument("--download-data", action="store_true", help="Download and extract Zenodo data.zip")
    iohunter_parser.add_argument("--ensure-official-layout", action="store_true", help="Link data/processed into SocGFM/data/processed")
    iohunter_parser.add_argument("--patch-official-scripts", action="store_true", help="Patch local SocGFM scripts for Windows/repro cleanup issues")
    iohunter_parser.add_argument("--experiment-python", default="", help="Optional Python executable for official dependency checks")
    iohunter_parser.add_argument("--datasets", nargs="*", default=[])
    iohunter_parser.add_argument("--seeds", nargs="*", type=int, default=[42, 43, 44, 45, 46])
    iohunter_parser.add_argument("--gnns", nargs="*", default=["sage"])
    iohunter_parser.add_argument("--lr", nargs="*", type=float, default=[1e-2])
    iohunter_parser.add_argument("--early", type=int, default=30)
    iohunter_parser.add_argument("--splits", type=int, default=5)
    iohunter_parser.add_argument("--device", default="0")
    iohunter_parser.add_argument("--epochs", type=int, default=0, help="Optional official training epochs override")
    iohunter_parser.add_argument("--check", type=int, default=0, help="Optional validation check frequency override")
    iohunter_parser.add_argument("--latent", type=int, default=0, help="Optional latent dimension override")
    iohunter_parser.add_argument("--embed-type", default="", help="Optional structural embedding type override")
    iohunter_parser.add_argument("--under", nargs="*", default=[])
    iohunter_parser.add_argument("--skip-primary", action="store_true")
    iohunter_parser.add_argument("--include-official-baselines", action="store_true")
    iohunter_parser.add_argument("--include-cross-country", action="store_true")
    iohunter_parser.add_argument("--export-dir", default="", help="Optional directory for run plan and scripts")

    iohunter_run_parser = subparsers.add_parser("iohunter-run", help="Execute an exported IOHunter run plan")
    iohunter_run_parser.add_argument("--run-plan", required=True, help="Path to iohunter_run_plan.json")
    iohunter_run_parser.add_argument("--output-dir", required=True, help="Directory for run manifest and logs")
    iohunter_run_parser.add_argument("--python", default="python", help="Python executable in the experiment env")
    iohunter_run_parser.add_argument("--limit", type=int, default=0, help="Optional max number of runs")
    iohunter_run_parser.add_argument("--dry-run", action="store_true")
    iohunter_run_parser.add_argument("--stop-on-error", action="store_true")
    iohunter_run_parser.add_argument("--no-resume", action="store_true", help="Do not skip existing successful runs")

    iohunter_summary_parser = subparsers.add_parser("iohunter-summarize", help="Summarize IOHunter run logs")
    iohunter_summary_parser.add_argument("--run-output-dir", required=True, help="Directory containing iohunter_run_manifest.json")
    iohunter_summary_parser.add_argument("--output-dir", default="", help="Optional output directory for metric tables")

    report_parser = subparsers.add_parser("coordination_discover-report", help="Merge lightweight and IOHunter official metrics into one CoordinationDiscover table")
    report_parser.add_argument("--output-dir", required=True, help="Directory for unified CSV/JSON/Markdown report")
    report_parser.add_argument("--lightweight-dirs", nargs="*", default=[], help="Directories containing lightweight metrics.csv")
    report_parser.add_argument("--iohunter-summary-dirs", nargs="*", default=[], help="Directories containing iohunter_metric_summary.csv")
    report_parser.add_argument(
        "--research-candidate-dirs",
        nargs="*",
        default=[],
        help="Directories containing research candidate metrics, kept separate from user-level Detect metrics",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "make-sample":
        output = Path(args.output).resolve()
        write_sample_events(output)
        print(json.dumps({"sample_path": str(output)}, ensure_ascii=False, indent=2))
        return

    if args.command == "run":
        events = read_event_table(Path(args.events).resolve())
        summary = run_reproduction_suite(
            events,
            output_dir=Path(args.output_dir).resolve(),
            relations=tuple(args.relations),
            include_text_similarity=not args.no_text_similarity,
            max_edges_per_node=args.max_edges_per_node or None,
            embedding_dim=args.embedding_dim,
            seed=args.seed,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    if args.command == "discover":
        events = read_event_table(Path(args.events).resolve())
        try:
            summary = run_dyna_colm_discover(
                events,
                output_dir=Path(args.output_dir).resolve(),
                relations=tuple(args.relations),
                seed=args.seed,
                encoder=args.encoder,
                epochs=args.epochs,
                embedding_dim=args.embedding_dim,
                hidden_dim=args.hidden_dim,
                lr=args.lr,
                negative_ratio=args.negative_ratio,
                device=args.device,
                community_algorithm=args.community_algorithm,
                structure_filter=args.structure_filter,
                structure_filter_metric=args.structure_filter_metric,
                structure_filter_percentile=args.structure_filter_percentile,
                structure_filter_use_weights=args.structure_filter_use_weights,
            )
        except ModuleNotFoundError as exc:
            print(json.dumps({"error": str(exc), "encoder": args.encoder}, ensure_ascii=False, indent=2), file=sys.stderr)
            raise SystemExit(1) from exc
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    if args.command == "detect":
        events = read_event_table(Path(args.events).resolve())
        summary = run_dyna_colm_detect(
            events,
            output_dir=Path(args.output_dir).resolve(),
            relations=tuple(args.relations),
            seed=args.seed,
            discover_encoder=args.discover_encoder,
            discover_epochs=args.discover_epochs,
            detect_epochs=args.detect_epochs or None,
            embedding_dim=args.embedding_dim,
            hidden_dim=args.hidden_dim,
            device=args.device,
            lm_backend=args.lm_backend,
            gnn_backend=args.gnn_backend,
            split_mode=args.split_mode,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    if args.command == "characterize":
        events = read_event_table(Path(args.events).resolve())
        summary = run_dyna_colm_characterize(
            events,
            output_dir=Path(args.output_dir).resolve(),
            relations=tuple(args.relations),
            seed=args.seed,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    if args.command == "ablation":
        events = read_event_table(Path(args.events).resolve())
        output_dir = Path(args.output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        summary = run_dyna_colm_ablation_suite(
            events,
            relations=tuple(args.relations),
            seed=args.seed,
        )
        (output_dir / "ablation_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    if args.command == "iohunter-convert":
        result = write_iohunter_event_table(
            Path(args.dataset_dir).resolve(),
            Path(args.output).resolve(),
            dataset_name=args.dataset_name or None,
            threshold=args.threshold,
            train_percentage=args.train_percentage or None,
            undersampling=args.undersampling or None,
            max_edges_per_relation=args.max_edges_per_relation or None,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "iohunter-lightweight":
        output_dir = Path(args.output_dir).resolve()
        events_path = output_dir / "iohunter_events.csv"
        conversion = write_iohunter_event_table(
            Path(args.dataset_dir).resolve(),
            events_path,
            dataset_name=args.dataset_name or None,
            threshold=args.threshold,
            train_percentage=args.train_percentage or None,
            undersampling=args.undersampling or None,
            max_edges_per_relation=args.max_edges_per_relation or None,
        )
        events = read_event_table(events_path)
        summary = run_reproduction_suite(
            events,
            output_dir=output_dir,
            relations=tuple(args.relations),
            include_text_similarity=not args.no_text_similarity,
            max_edges_per_node=args.max_edges_per_node or None,
            embedding_dim=args.embedding_dim,
            seed=args.seed,
        )
        summary["iohunter_conversion"] = conversion
        (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    if args.command == "iohunter-lightweight-batch":
        result = run_iohunter_lightweight_batch(
            Path(args.processed_root).resolve(),
            output_dir=Path(args.output_dir).resolve(),
            datasets=tuple(args.datasets),
            threshold=args.threshold,
            train_percentage=args.train_percentage or None,
            undersampling=args.undersampling or None,
            max_edges_per_relation=args.max_edges_per_relation or None,
            seed=args.seed,
            relations=tuple(args.relations),
            include_text_similarity=args.include_text_similarity,
            max_edges_per_node=args.max_edges_per_node or None,
            embedding_dim=args.embedding_dim,
            include_temporal_edge_candidate=args.include_temporal_edge_candidate,
            research_candidate_only=args.research_candidate_only,
            candidate_epochs=args.candidate_epochs,
            candidate_embedding_dim=args.candidate_embedding_dim,
            candidate_hidden_dim=args.candidate_hidden_dim,
            candidate_lr=args.candidate_lr,
            candidate_negative_ratio=args.candidate_negative_ratio,
            candidate_device=args.candidate_device,
            candidate_early_stop_patience=args.candidate_early_stop_patience,
            candidate_seeds=tuple(args.candidate_seeds) or None,
            include_temporal_edge_ablations=args.include_temporal_edge_ablations,
            candidate_ablation_seeds=tuple(args.candidate_ablation_seeds) or None,
            continue_on_error=args.continue_on_error,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "iohunter":
        workspace = Path(args.workspace).resolve()
        datasets = tuple(args.datasets) if args.datasets else ("UAE", "cuba", "russia", "venezuela", "iran", "china")
        undersampling = tuple(args.under) if args.under else (None,)
        layout = ensure_iohunter_official_data_layout(workspace) if args.ensure_official_layout else None
        official_patch = patch_iohunter_official_scripts(workspace) if args.patch_official_scripts else None
        epochs = args.epochs or None
        check = args.check or None
        latent = args.latent or None
        embed_type = args.embed_type or None
        experiment_python = args.experiment_python or None
        if args.clone_code or args.download_data:
            summary = prepare_iohunter_workspace(
                workspace,
                clone_code=args.clone_code,
                download_data=args.download_data,
                python_executable=experiment_python,
            )
            if layout is not None:
                summary["official_data_layout"] = layout
            if official_patch is not None:
                summary["official_script_patch"] = official_patch
            if experiment_python is not None:
                summary["status"] = iohunter_workspace_status(workspace, python_executable=experiment_python)
        else:
            run_plan = build_iohunter_run_plan(
                workspace,
                datasets=datasets,
                seeds=tuple(args.seeds),
                gnns=tuple(args.gnns),
                learning_rates=tuple(args.lr),
                early=args.early,
                splits=args.splits,
                device=args.device,
                epochs=epochs,
                check=check,
                latent=latent,
                embed_type=embed_type,
                undersampling=undersampling,
                include_primary=not args.skip_primary,
                include_official_baselines=args.include_official_baselines,
                include_cross_country=args.include_cross_country,
            )
            summary = {
                "workspace": str(workspace),
                "status": iohunter_workspace_status(workspace, python_executable=experiment_python),
                "data": inspect_iohunter_data(workspace),
                "official_data_layout": layout,
                "official_script_patch": official_patch,
                "run_plan": run_plan,
                "commands": build_iohunter_commands(
                    workspace,
                    datasets=datasets,
                    seeds=tuple(args.seeds),
                    gnns=tuple(args.gnns),
                    learning_rates=tuple(args.lr),
                    early=args.early,
                    splits=args.splits,
                    device=args.device,
                    epochs=epochs,
                    check=check,
                    latent=latent,
                    embed_type=embed_type,
                    undersampling=undersampling,
                    include_primary=not args.skip_primary,
                    include_official_baselines=args.include_official_baselines,
                    include_cross_country=args.include_cross_country,
                ),
            }
        if args.export_dir:
            run_plan = build_iohunter_run_plan(
                workspace,
                datasets=datasets,
                seeds=tuple(args.seeds),
                gnns=tuple(args.gnns),
                learning_rates=tuple(args.lr),
                early=args.early,
                splits=args.splits,
                device=args.device,
                epochs=epochs,
                check=check,
                latent=latent,
                embed_type=embed_type,
                undersampling=undersampling,
                include_primary=not args.skip_primary,
                include_official_baselines=args.include_official_baselines,
                include_cross_country=args.include_cross_country,
            )
            summary["exports"] = write_iohunter_run_exports(
                workspace,
                Path(args.export_dir).resolve(),
                run_plan=run_plan,
            )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    if args.command == "iohunter-run":
        run_plan = load_iohunter_run_plan(Path(args.run_plan).resolve())
        manifest = run_iohunter_plan(
            run_plan,
            output_dir=Path(args.output_dir).resolve(),
            python_executable=args.python,
            limit=args.limit or None,
            dry_run=args.dry_run,
            stop_on_error=args.stop_on_error,
            resume=not args.no_resume,
        )
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return

    if args.command == "iohunter-summarize":
        summary = summarize_iohunter_runs(
            Path(args.run_output_dir).resolve(),
            output_dir=Path(args.output_dir).resolve() if args.output_dir else None,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    if args.command == "coordination_discover-report":
        report = build_coordination_discover_comparison_report(
            output_dir=Path(args.output_dir).resolve(),
            lightweight_dirs=tuple(Path(item).resolve() for item in args.lightweight_dirs),
            iohunter_summary_dirs=tuple(Path(item).resolve() for item in args.iohunter_summary_dirs),
            research_candidate_dirs=tuple(Path(item).resolve() for item in args.research_candidate_dirs),
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return


if __name__ == "__main__":
    main()
