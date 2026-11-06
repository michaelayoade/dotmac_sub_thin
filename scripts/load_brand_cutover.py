"""Operator load for the brand cutover: dry-run unless --execute.

Dry-run (default) reads only files and prints totals; DATABASE_URL is
not read. With --execute it binds the explicit runtime, verifies the
non-superuser + NOBYPASSRLS posture BEFORE any write, then applies the
load plan inside one tenant-scoped transaction.

Usage:
    python scripts/load_brand_cutover.py EXTRACT.json --tenant-id UUID \
        [--complete-from-resolved RESOLVED.json] [--execute]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sub_thin.cutover.brand_profiles import (  # noqa: E402
    BrandCutoverReport,
    PlatformCompletionPlan,
    apply_load_plan,
    complete_platform_brand,
    transform_brand_rows,
)


def build_report(
    extract: Path, *, tenant_id: str, resolved_path: Path | None
) -> tuple[BrandCutoverReport, PlatformCompletionPlan | None]:
    rows = json.loads(extract.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("extract must be a JSON array of rows")
    report = transform_brand_rows(rows, tenant_id=UUID(tenant_id))
    if resolved_path is None:
        return report, None
    resolved = json.loads(resolved_path.read_text(encoding="utf-8"))
    if not isinstance(resolved, dict):
        raise ValueError("resolved snapshot must be a JSON object")
    plan = complete_platform_brand(report, rows, resolved)
    return plan.completed_report(), plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("extract", type=Path)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--complete-from-resolved", type=Path)
    parser.add_argument(
        "--execute", action="store_true",
        help="actually write (default: dry-run, no database touched)",
    )
    args = parser.parse_args()

    try:
        report, plan = build_report(
            args.extract,
            tenant_id=args.tenant_id,
            resolved_path=args.complete_from_resolved,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"load refused: {exc}", file=sys.stderr)
        return 2

    totals = report.to_dict()["totals"]
    print(json.dumps({"mode": "execute" if args.execute else "dry-run", **totals}, sort_keys=True))
    if plan is not None:
        print(json.dumps({
            "completion_unresolved": [
                [r.field, r.disposition] for r in plan.unresolved
            ]
        }, sort_keys=True))
    if not report.reconciled:
        return 1
    if not args.execute:
        print("dry-run: no database touched")
        return 0

    from sub_thin.database import (
        build_database_runtime,
        verify_runtime_role_posture,
    )

    runtime = build_database_runtime()
    if runtime is None:
        print("load refused: DATABASE_URL is not set", file=sys.stderr)
        return 2
    problems = verify_runtime_role_posture(runtime.engine)
    if problems:
        for problem in problems:
            print(f"load refused: {problem}", file=sys.stderr)
        return 2

    tenant = UUID(args.tenant_id)
    with runtime.tenant_session(tenant) as session:
        loaded = apply_load_plan(session, report)
    print(json.dumps({"loaded": len(loaded), "ids": loaded}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
