"""Fetch one legacy resolved-brand snapshot through its read-only seam.

Runs `resolve_brand` inside the legacy app container under
`read_only_snapshot_session` (REPEATABLE READ, READ ONLY). The snapshot is
written only to the requested output path; stdout carries field names and
a digest, never brand values.

Usage:
    python scripts/fetch_resolved_brand.py --out brand_resolved.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REMOTE_CODE = (
    "import json\n"
    "from app.db import read_only_snapshot_session\n"
    "from app.services.brand_profiles import resolve_brand\n"
    "with read_only_snapshot_session() as db:\n"
    "    print(json.dumps(resolve_brand(db).to_dict(), default=str))\n"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--ssh-host", default="sub-prod")
    parser.add_argument("--container", default="dotmac_sub_app")
    parser.add_argument("--python", default="/opt/venv/bin/python")
    args = parser.parse_args()

    result = subprocess.run(
        [
            "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
            args.ssh_host,
            f"docker exec -i {args.container} {args.python} -",
        ],
        input=REMOTE_CODE,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    if result.returncode != 0:
        print("resolved-brand fetch failed (remote output suppressed)", file=sys.stderr)
        return 1
    try:
        payload = json.loads(result.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        print("resolved-brand fetch returned no JSON object", file=sys.stderr)
        return 1
    if not isinstance(payload, dict):
        print("resolved-brand snapshot must be a JSON object", file=sys.stderr)
        return 1

    args.out.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.out.chmod(0o600)
    print("fields=", sorted(payload))
    print("sha256=", hashlib.sha256(args.out.read_bytes()).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
