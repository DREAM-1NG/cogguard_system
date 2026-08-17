from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Mapping


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge official SocGFM and CogGuard IOHunter Detection metrics.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--official-summary-dirs",
        nargs="*",
        default=[],
        help="Directories or CSV files containing official iohunter_metric_summary.csv outputs.",
    )
    parser.add_argument(
        "--internal-dirs",
        nargs="*",
        default=[],
        help="Directories or CSV files containing CogGuard detect_metrics_mean_std.csv outputs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    _require_g_drive(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    long_rows = []
    for row in _official_rows(args.official_summary_dirs):
        long_rows.append(row)
    for row in _internal_rows(args.internal_dirs):
        long_rows.append(row)

    long_csv = output_dir / "iohunter_detection_comparison_long.csv"
    wide_csv = output_dir / "iohunter_detection_comparison_wide.csv"
    json_path = output_dir / "iohunter_detection_comparison.json"
    markdown_path = output_dir / "iohunter_detection_comparison.md"

    _write_csv(long_csv, long_rows)
    wide_rows = _wide_rows(long_rows)
    _write_csv(wide_csv, wide_rows)
    json_path.write_text(
        json.dumps({"long_rows": long_rows, "wide_rows": wide_rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown_path.write_text(_markdown_report(wide_rows), encoding="utf-8")
    print(
        json.dumps(
            {
                "row_count": len(long_rows),
                "wide_row_count": len(wide_rows),
                "long_csv": str(long_csv),
                "wide_csv": str(wide_csv),
                "markdown": str(markdown_path),
                "json": str(json_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _require_g_drive(path: Path) -> None:
    if path.drive.upper() != "G:":
        raise ValueError(f"Experiment outputs must stay on G: drive, got: {path}")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file_handle:
        return [dict(row) for row in csv.DictReader(file_handle)]


def _resolve_metric_files(paths: Iterable[str], default_name: str) -> list[Path]:
    output = []
    for value in paths:
        path = Path(value).resolve()
        candidate = path / default_name if path.is_dir() else path
        if candidate.exists():
            output.append(candidate)
    return output


def _official_rows(paths: Iterable[str]) -> list[dict[str, object]]:
    rows = []
    for path in _resolve_metric_files(paths, "iohunter_metric_summary.csv"):
        for row in _read_csv(path):
            rows.append(
                {
                    "source": "official_socgfm",
                    "dataset": row.get("dataset"),
                    "method": row.get("method"),
                    "setting": row.get("setting"),
                    "gnn": row.get("gnn"),
                    "lm_backend": "",
                    "split": row.get("split"),
                    "metric": row.get("metric"),
                    "run_count": _to_int(row.get("run_count")),
                    "mean": _to_float(row.get("mean")),
                    "std": _to_float(row.get("std")),
                    "input_path": str(path),
                }
            )
    return rows


def _internal_rows(paths: Iterable[str]) -> list[dict[str, object]]:
    rows = []
    metric_map = {
        "macro_f1_at_selected_threshold": ("TEST", "f1_macro"),
        "macro_f1_at_0_5": ("TEST", "diagnostic_macro_f1_at_0_5"),
        "diagnostic_f1_at_0_5": ("TEST", "positive_f1_at_0_5"),
        "selected_threshold": ("MODEL", "selected_threshold"),
        "validation_macro_f1": ("VAL", "f1_macro"),
        "validation_ece": ("VAL", "ece"),
        "validation_brier": ("VAL", "brier"),
        "max_f1": ("TEST", "max_f1"),
        "accuracy": ("TEST", "accuracy"),
        "auc": ("TEST", "roc_auc"),
        "auprc": ("TEST", "auprc"),
        "runtime_seconds": ("RUN", "runtime_seconds"),
    }
    for path in _resolve_metric_files(paths, "detect_metrics_mean_std.csv"):
        for row in _read_csv(path):
            for field, (split, metric) in metric_map.items():
                mean = _to_float(row.get(f"{field}_mean"))
                if mean is None:
                    continue
                rows.append(
                    {
                        "source": "cogguard_internal",
                        "dataset": row.get("dataset"),
                        "method": f"CogGuard:{row.get('gnn_backend')}",
                        "setting": row.get("split_mode"),
                        "gnn": row.get("gnn_backend"),
                        "lm_backend": row.get("lm_backend"),
                        "split": split,
                        "metric": metric,
                        "run_count": _to_int(row.get("run_count")),
                        "mean": mean,
                        "std": _to_float(row.get(f"{field}_std")),
                        "input_path": str(path),
                    }
                )
    return rows


def _wide_rows(rows: list[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], dict[str, object]] = {}
    for row in rows:
        key = (
            row.get("source"),
            row.get("dataset"),
            row.get("method"),
            row.get("setting"),
            row.get("gnn"),
            row.get("lm_backend"),
        )
        item = grouped.setdefault(
            key,
            {
                "source": key[0],
                "dataset": key[1],
                "method": key[2],
                "setting": key[3],
                "gnn": key[4],
                "lm_backend": key[5],
                "run_count": row.get("run_count"),
            },
        )
        metric = str(row.get("metric") or "")
        split = str(row.get("split") or "")
        if not metric:
            continue
        column = metric if split in {"", "TEST"} else f"{split.lower()}_{metric}"
        item[column] = row.get("mean")
        item[f"{column}_std"] = row.get("std")
    return sorted(grouped.values(), key=lambda item: tuple(str(item.get(key, "")) for key in ("dataset", "source", "method", "setting")))


def _write_csv(path: Path, rows: list[Mapping[str, object]]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row.keys()))
    with path.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def _markdown_report(rows: list[Mapping[str, object]]) -> str:
    lines = [
        "# IOHunter Detection Fair Comparison",
        "",
        "This report merges official SocGFM metrics with CogGuard internal Detection metrics.",
        "Official `f1_macro` is compared against CogGuard held-out TEST `macro_f1_at_selected_threshold`; fixed-threshold 0.5 and `max_f1` are diagnostics.",
        "",
        "| Dataset | Source | Method | Setting | GNN | LM | Runs | TEST F1 Macro | VAL F1 Macro | Threshold | Accuracy | ROC-AUC | AUPRC | Runtime(s) |",
        "| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {dataset} | {source} | {method} | {setting} | {gnn} | {lm} | {runs} | {f1} | {val_f1} | {threshold} | {acc} | {auc} | {auprc} | {runtime} |".format(
                dataset=row.get("dataset", ""),
                source=row.get("source", ""),
                method=row.get("method", ""),
                setting=row.get("setting", ""),
                gnn=row.get("gnn", ""),
                lm=row.get("lm_backend", ""),
                runs=row.get("run_count", ""),
                f1=_fmt(row.get("f1_macro")),
                val_f1=_fmt(row.get("val_f1_macro")),
                threshold=_fmt(row.get("model_selected_threshold")),
                acc=_fmt(row.get("accuracy")),
                auc=_fmt(row.get("roc_auc")),
                auprc=_fmt(row.get("auprc")),
                runtime=_fmt(row.get("run_runtime_seconds")),
            )
        )
    lines.extend(
        [
            "",
            "Caveats:",
            "",
            "- This table is fair only for rows whose dataset, split protocol, and metric definitions match.",
            "- CogGuard threshold selection and calibration use validation data only; TEST labels remain held out for the table metric.",
            "- `max_f1` and fixed-threshold 0.5 metrics are retained in CSV outputs as diagnostics and should not be used as headline metrics against official SocGFM `f1_macro`.",
            "- Cross-country and scarce-supervision rows require separate claim gates.",
        ]
    )
    return "\n".join(lines) + "\n"


def _fmt(value: object) -> str:
    number = _to_float(value)
    return "" if number is None else f"{number:.4f}"


def _to_float(value: object) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: object) -> int | None:
    number = _to_float(value)
    return None if number is None else int(number)


if __name__ == "__main__":
    main()
