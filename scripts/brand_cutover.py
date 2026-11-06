"""Run the N3 brand-profiles transform over a legacy extract file.

The extract is a JSON array of legacy `brand_profiles` rows, produced
read-only from legacy Sub, e.g.:

    SELECT row_to_json(b) FROM brand_profiles b;

(one row's columns, `metadata` as the JSON column value). This tool
never writes anywhere except the report path given.

Usage:
    python scripts/brand_cutover.py EXTRACT.json --tenant-id UUID \
        [--complete-from-resolved RESOLVED.json] [--out REPORT.json]

With `--complete-from-resolved`, the JSON object is one legacy
`resolve_brand(...).to_dict()` snapshot. The output gains a dry-run
`completion` plan; the underlying table totals do not change.

Exit 0 iff totals reconcile (extracted == loadable + row_rejected).
Field rejects are data for the exceptions queue, not failures.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sub_thin.cutover.brand_profiles import (  # noqa: E402
    complete_platform_brand,
    transform_brand_rows,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("extract", type=Path)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--complete-from-resolved", type=Path)
    parser.add_argument(
        "--print-payload", action="store_true",
        help="print the full report JSON to stdout (default: totals only)",
    )
    args = parser.parse_args()

    rows = json.loads(args.extract.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        print("extract must be a JSON array of rows", file=sys.stderr)
        return 2

    report = transform_brand_rows(rows, tenant_id=UUID(args.tenant_id))
    output = report.to_dict()
    if args.complete_from_resolved:
        resolved = json.loads(args.complete_from_resolved.read_text(encoding="utf-8"))
        if not isinstance(resolved, dict):
            print("resolved snapshot must be a JSON object", file=sys.stderr)
            return 2
        plan = complete_platform_brand(report, rows, resolved)
        output = plan.to_dict()
        report = plan.completed_report()
    payload = json.dumps(output, indent=2, sort_keys=True)
    if args.out:
        fd = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload + "\n")
    if args.print_payload:
        print(payload)
    else:
        print(json.dumps(report.to_dict()["totals"], sort_keys=True))
    return 0 if report.reconciled else 1


if __name__ == "__main__":
    raise SystemExit(main())
