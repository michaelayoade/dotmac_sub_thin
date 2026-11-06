"""Read-only legacy brand_profiles extractor (operator-run).

Reads LEGACY_DATABASE_URL from the environment, opens ONE read-only
transaction, and writes the extract JSON the cutover CLI consumes.
It refuses non-Postgres DSNs and never writes to the source database.

Usage (where the legacy DB is reachable):
    LEGACY_DATABASE_URL=postgresql+psycopg://reader@host/db \
        python scripts/extract_brand_profiles.py --out brand_extract.json
    python scripts/brand_cutover.py brand_extract.json --tenant-id UUID

Use a read-only database user. The SET TRANSACTION READ ONLY below is
defense in depth, not a substitute for one.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import sqlalchemy as sa

COLUMNS = (
    "id", "scope_type", "scope_id", "brand_name", "product_name",
    "legal_name", "tagline", "primary_color", "secondary_color",
    "logo_url", "dark_logo_url", "favicon_url", "support_email",
    "support_phone", "from_email", "from_name", "app_url",
    "portal_domain", "legal_address", "metadata", "is_active",
    "created_at", "updated_at",
)


def extract(engine: sa.Engine) -> list[dict]:
    cols = ", ".join(COLUMNS)
    with engine.connect() as conn:
        with conn.begin():
            conn.execute(sa.text("SET TRANSACTION READ ONLY"))
            rows = conn.execute(
                sa.text(f"SELECT row_to_json(t) FROM (SELECT {cols} FROM brand_profiles) t")
            ).scalars().all()
    return [json.loads(r) if isinstance(r, str) else r for r in rows]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    raw = os.environ.get("LEGACY_DATABASE_URL", "")
    if not raw.strip():
        print("LEGACY_DATABASE_URL is not set", file=sys.stderr)
        return 2
    url = sa.make_url(raw)
    if url.get_dialect().name != "postgresql":
        print("LEGACY_DATABASE_URL must be PostgreSQL", file=sys.stderr)
        return 2

    engine = sa.create_engine(url, hide_parameters=True)
    rows = extract(engine)
    fd = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(rows, indent=2, sort_keys=True) + "\n")
    print(f"extracted {len(rows)} brand_profiles rows -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
