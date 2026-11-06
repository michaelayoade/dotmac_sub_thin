"""Operator load CLI: dry-run by default, no database touched."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "load_brand_cutover.py"
spec = importlib.util.spec_from_file_location("load_brand_cutover", SCRIPT)
assert spec and spec.loader
loader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loader)

TENANT = "00000000-0000-0000-0000-000000000001"


def test_build_report_without_completion(tmp_path: Path) -> None:
    extract = tmp_path / "extract.json"
    extract.write_text(json.dumps([{
        "id": "row-1", "scope_type": "platform", "scope_id": None,
        "brand_name": "Dotmac", "primary_color": "#112233",
    }]))
    report, plan = loader.build_report(extract, tenant_id=TENANT, resolved_path=None)
    assert plan is None
    assert report.reconciled and len(report.loadable) == 1


def test_build_report_with_completion(tmp_path: Path) -> None:
    extract = tmp_path / "extract.json"
    resolved = tmp_path / "resolved.json"
    extract.write_text(json.dumps([{
        "id": "row-1", "scope_type": "platform", "scope_id": None,
        "product_name": "Profile Product",
    }]))
    resolved.write_text(json.dumps(
        {"name": "Resolved", "primary_color": "#445566"}
    ))
    report, plan = loader.build_report(
        extract, tenant_id=TENANT, resolved_path=resolved
    )
    assert plan is not None
    assert report.loadable[0].fields["primary_hex"] == "#445566"
