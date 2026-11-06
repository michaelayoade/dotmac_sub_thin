"""Generate or verify the canonical product manifest for this shell.

Usage:
    python scripts/product_manifest.py write
    python scripts/product_manifest.py check
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dotmac_kernel.product_manifest import ProductManifestSnapshot  # noqa: E402

from sub_thin.assembly import assembly  # noqa: E402

MANIFEST_PATH = ROOT / "deploy" / "product-manifest.json"


def snapshot() -> ProductManifestSnapshot:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return ProductManifestSnapshot.from_assembly(
        assembly,
        product_version=str(project["project"]["version"]),
    )


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"write", "check"}:
        print(__doc__.strip(), file=sys.stderr)
        return 2

    current = snapshot()
    if sys.argv[1] == "write":
        MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST_PATH.write_bytes(current.to_json_bytes())
        print(current.digest)
        return 0

    if not MANIFEST_PATH.exists():
        print(f"missing {MANIFEST_PATH}", file=sys.stderr)
        return 1
    recorded = ProductManifestSnapshot.from_json_bytes(MANIFEST_PATH.read_bytes())
    if recorded != current:
        print(
            f"manifest drift: recorded {recorded.digest}, current {current.digest}",
            file=sys.stderr,
        )
        return 1
    print(current.digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
