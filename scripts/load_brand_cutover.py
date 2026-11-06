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
import hashlib
import json
import sys
from dataclasses import replace
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
    parser.add_argument("--expected-extract-sha256")
    parser.add_argument("--expected-resolved-sha256")
    parser.add_argument(
        "--accept-unresolved", action="append", default=[],
        metavar="FIELD:DISPOSITION",
        help="accept one completion unresolved entry on --execute (repeatable)",
    )
    parser.add_argument(
        "--activate", action="store_true",
        help="activate loaded profiles (default: load as draft)",
    )
    args = parser.parse_args()

    def _digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    digests = {"extract_sha256": _digest(args.extract)}
    if args.complete_from_resolved:
        digests["resolved_sha256"] = _digest(args.complete_from_resolved)
    if args.execute:
        if args.expected_extract_sha256 != digests["extract_sha256"]:
            print("load refused: extract digest mismatch or not supplied", file=sys.stderr)
            return 2
        if args.complete_from_resolved and (
            args.expected_resolved_sha256 != digests.get("resolved_sha256")
        ):
            print("load refused: resolved digest mismatch or not supplied", file=sys.stderr)
            return 2

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
    print(json.dumps({"mode": "execute" if args.execute else "dry-run", **digests, **totals}, sort_keys=True))
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

    if plan is not None and plan.unresolved:
        accepted = set(args.accept_unresolved)
        missing = [
            f"{r.field}:{r.disposition}"
            for r in plan.unresolved
            if f"{r.field}:{r.disposition}" not in accepted
        ]
        if missing:
            print(f"load refused: unaccepted unresolved {missing}", file=sys.stderr)
            return 2
    if not args.activate:
        report = replace(
            report,
            loadable=tuple(replace(item, activate=False) for item in report.loadable),
        )

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

    import sqlalchemy as sa

    from sub_thin.migrate import EXPECTED_HEADS

    try:
        with runtime.engine.connect() as connection:
            heads = tuple(sorted(connection.execute(
                sa.text("SELECT version_num FROM alembic_version")
            ).scalars().all()))
    except sa.exc.SQLAlchemyError as exc:
        print(f"load refused: migration heads unverifiable ({type(exc).__name__})", file=sys.stderr)
        return 2
    if heads != tuple(sorted(EXPECTED_HEADS)):
        print(f"load refused: migration heads {heads} != expected {sorted(EXPECTED_HEADS)}", file=sys.stderr)
        return 2

    tenant = UUID(args.tenant_id)
    with runtime.tenant_session(tenant) as session:
        loaded = apply_load_plan(session, report)
    print(json.dumps({"loaded": len(loaded), "ids": loaded}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
