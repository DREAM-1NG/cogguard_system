from __future__ import annotations

import argparse
import json

from .analysis import analyze_events
from .diagnostics import inspect_dataset
from .full_run import run_weibo_rumor_full
from .loaders import load_dataset, make_synthetic_events
from .prediction import run_prediction
from .reporting import build_final_report
from .visualization import build_dashboard


DATASET_CHOICES = ["weibo", "weibo_rumor", "ma-weibo", "rumor_rvnn_twitter", "rumor_rvnn", "pheme", "pheme-rnr"]


def main() -> None:
    parser = argparse.ArgumentParser(description="传播分析、路径/规模预测 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo", help="Run synthetic demo")
    demo.add_argument("--output", default="outputs/demo")

    inspect = sub.add_parser("inspect", help="Audit dataset coverage before analysis")
    inspect.add_argument("--dataset", required=True, choices=DATASET_CHOICES)
    inspect.add_argument("--data-dir", required=True)
    inspect.add_argument("--output", default=None)

    analyze = sub.add_parser("analyze", help="Analyze a local propagation dataset")
    analyze.add_argument("--dataset", required=True, choices=DATASET_CHOICES)
    analyze.add_argument("--data-dir", required=True)
    analyze.add_argument("--output", required=True)
    analyze.add_argument("--dashboard", action="store_true", help="Generate polished HTML dashboard")
    analyze.add_argument("--event-id", default=None, help="Focus the generated event_report.md and dashboard on one event/thread")
    analyze.add_argument("--max-events", type=int, default=None, help="Analyze only the largest N parsed events")

    pred = sub.add_parser("predict", help="Run propagation path and size prediction")
    pred.add_argument("--dataset", required=True, choices=DATASET_CHOICES)
    pred.add_argument("--data-dir", required=True)
    pred.add_argument("--output", required=True)
    pred.add_argument("--observation-ratio", type=float, default=0.3)
    pred.add_argument("--dashboard", action="store_true", help="Generate polished HTML dashboard")
    pred.add_argument("--event-id", default=None, help="Run prediction on one event/thread when applicable")
    pred.add_argument("--max-events", type=int, default=None, help="Use only the largest N parsed events")

    dash = sub.add_parser("dashboard", help="Analyze, predict, and generate a presentation dashboard")
    dash.add_argument("--dataset", required=True, choices=DATASET_CHOICES)
    dash.add_argument("--data-dir", required=True)
    dash.add_argument("--output", required=True)
    dash.add_argument("--observation-ratio", type=float, default=0.3)
    dash.add_argument("--event-id", default=None, help="Focus the dashboard and event report on one event/thread")
    dash.add_argument("--max-events", type=int, default=None, help="Use only the largest N parsed events")

    weibo_full = sub.add_parser("weibo-full", help="Run full streaming ScienceDB/Ma-Weibo analysis")
    weibo_full.add_argument("--data-dir", required=True)
    weibo_full.add_argument("--output", required=True)
    weibo_full.add_argument("--observation-ratio", type=float, default=0.3)
    weibo_full.add_argument("--path-sample-limit", type=int, default=750_000)
    weibo_full.add_argument("--path-future-per-event", type=int, default=200)
    weibo_full.add_argument("--progress-every", type=int, default=100)
    weibo_full.add_argument("--max-events", type=int, default=None, help="Optional dry-run cap; omit for full 4664-event run")

    report = sub.add_parser("report", help="Build final acceptance report from generated artifacts")
    report.add_argument("--output", default="outputs/FINAL_REPORT.md")

    args = parser.parse_args()
    if args.command == "demo":
        events = make_synthetic_events()
        summary = analyze_events(events, args.output)
        report = run_prediction(events, args.output, 0.3)
        dashboard = build_dashboard(events, args.output, report)
        print(json.dumps({"summary": summary["narrative"], "prediction": report, "dashboard": str(dashboard)}, ensure_ascii=False, indent=2))
    elif args.command == "inspect":
        report = inspect_dataset(args.dataset, args.data_dir, args.output)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    elif args.command == "analyze":
        events = _select_events(load_dataset(args.dataset, args.data_dir, args.max_events, args.event_id), args.event_id, args.max_events)
        summary = analyze_events(events, args.output, args.event_id)
        if args.dashboard:
            dashboard = build_dashboard(events, args.output)
            summary["dashboard"] = str(dashboard)
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    elif args.command == "predict":
        events = _select_events(load_dataset(args.dataset, args.data_dir, args.max_events, args.event_id), args.event_id, args.max_events)
        report = run_prediction(events, args.output, args.observation_ratio)
        if args.dashboard:
            analyze_events(events, args.output, args.event_id)
            dashboard = build_dashboard(events, args.output, report)
            report["dashboard"] = str(dashboard)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    elif args.command == "dashboard":
        events = _select_events(load_dataset(args.dataset, args.data_dir, args.max_events, args.event_id), args.event_id, args.max_events)
        summary = analyze_events(events, args.output, args.event_id)
        report = run_prediction(events, args.output, args.observation_ratio)
        dashboard = build_dashboard(events, args.output, report)
        print(json.dumps({"summary": summary["narrative"], "prediction": report, "dashboard": str(dashboard)}, ensure_ascii=False, indent=2, default=str))
    elif args.command == "weibo-full":
        summary = run_weibo_rumor_full(
            args.data_dir,
            args.output,
            observation_ratio=args.observation_ratio,
            path_sample_limit=args.path_sample_limit,
            path_future_per_event=args.path_future_per_event,
            progress_every=args.progress_every,
            max_events=args.max_events,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    elif args.command == "report":
        report = build_final_report(args.output)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


def _select_events(events, event_id=None, max_events=None):
    if event_id:
        events = [event for event in events if event.event_id == event_id]
        if not events:
            raise ValueError(f"event_id not found: {event_id}")
    if max_events is not None:
        if max_events <= 0:
            raise ValueError("--max-events must be positive")
        events = sorted(events, key=lambda event: len(event.nodes), reverse=True)[:max_events]
    return events


if __name__ == "__main__":
    main()
