from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional, Sequence

from benchmark.adapters.lgb_bot_detection import audit_lgb_reproduction_status


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Audit KT2 LGB strict-reproduction readiness.")
    parser.add_argument("--repo_root", default=".", help="KT2 repository root.")
    parser.add_argument("--dataset_root", default=r"G:\CISCN\dataset", help="Local dataset root.")
    parser.add_argument("--output_dir", default="benchmark", help="Directory for audit JSON/Markdown outputs.")
    args = parser.parse_args(argv)

    audit = audit_lgb_reproduction_status(
        Path(args.repo_root),
        dataset_root=Path(args.dataset_root),
        output_dir=Path(args.output_dir),
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
