from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_current_product_contract_smoke_reports_explicit_fallbacks():
    backend = Path(__file__).resolve().parents[1]
    script = backend / "scripts" / "verify_product_contract.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=backend,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema"] == "cogguard.product_contract_smoke.v1"
    assert payload["snapshot"]["data_fingerprint"]
    assert payload["coordination_discover"]["claimability"] == "non_claimable"
    assert payload["propagation"]["abstain"] is True
    assert payload["student_review"]["abstain"] is True
    assert payload["teacher_review"]["canonical_allowed"] is False
    assert payload["projection"]["internal_fields_leaked"] == []


def test_current_product_route_inventory_is_documented():
    root = Path(__file__).resolve().parents[3]
    readme = (root / "system" / "README.md").read_text(encoding="utf-8")
    required = (
        "/api/v1/auth", "/api/v1/crawl", "/api/v1/coordination",
        "/api/v1/propagation", "/api/v1/accounts", "/api/v1/dashboard",
        "/api/v1/risk", "/api/v2/review-cases", "/api/v2/governance",
    )
    for route in required:
        assert route in readme
