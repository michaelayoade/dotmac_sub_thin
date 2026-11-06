"""Bind a pushed image digest + source revision into deploy/product.toml.

Accepts only the descriptor's existing repository, a non-zero sha256
digest, and a 40-hex source revision. Changes the two provenance lines
(and their sentinel comment) and nothing else.

Usage:
    python scripts/bind_image.py \
        --image ghcr.io/michaelayoade/dotmac_sub_thin@sha256:<64-hex> \
        --source-revision <40-hex>
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

_REFERENCE_RE = re.compile(r"(?P<repo>[^\s@]+)@sha256:(?P<digest>[0-9a-f]{64})")
_REVISION_RE = re.compile(r"[0-9a-f]{40}")
_SENTINEL_COMMENT = (
    "# UNBOUND SENTINEL, deliberately. No CI build of this shell exists yet, and\n"
    "# inventing a digest would be false provenance. The first test-server/CI\n"
    "# build binds the real repo@sha256 digest together with source_revision.\n"
)
_BOUND_COMMENT = (
    "# Bound from a CI/test-server build of the source_revision below.\n"
    "# Rebind only through scripts/bind_image.py with the pushed digest.\n"
)


class ImageBindingError(ValueError):
    """A refusal to write provenance the caller has not proven."""


def bind_descriptor(text: str, *, reference: str, source_revision: str) -> str:
    match = _REFERENCE_RE.fullmatch(reference)
    if match is None:
        raise ImageBindingError("image must be repo@sha256:<64 lowercase hex>")
    if set(match.group("digest")) == {"0"}:
        raise ImageBindingError("refusing the all-zero sentinel digest")
    if _REVISION_RE.fullmatch(source_revision) is None or set(source_revision) == {"0"}:
        raise ImageBindingError("source revision must be a non-zero 40-hex revision")

    current = tomllib.loads(text)["image"]["reference"]
    current_match = _REFERENCE_RE.fullmatch(str(current))
    if current_match is None or current_match.group("repo") != match.group("repo"):
        raise ImageBindingError("image repository differs from the descriptor repository")

    bound, n_ref = re.subn(
        r'(?m)^reference = "[^"]*"$',
        f'reference = "{reference}"',
        text,
    )
    bound, n_rev = re.subn(
        r'(?m)^source_revision = "[^"]*"$',
        f'source_revision = "{source_revision}"',
        bound,
    )
    if n_ref != 1 or n_rev != 1:
        raise ImageBindingError("descriptor must contain exactly one image binding pair")
    return bound.replace(_SENTINEL_COMMENT, _BOUND_COMMENT)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument(
        "--descriptor",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "deploy" / "product.toml",
    )
    args = parser.parse_args()

    try:
        text = args.descriptor.read_text(encoding="utf-8")
        bound = bind_descriptor(
            text, reference=args.image, source_revision=args.source_revision
        )
    except (OSError, ValueError) as exc:
        print(f"image binding refused: {exc}", file=sys.stderr)
        return 2

    temporary = args.descriptor.with_suffix(".toml.tmp")
    temporary.write_text(bound, encoding="utf-8")
    temporary.replace(args.descriptor)
    print(f"bound {args.image} at {args.source_revision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
