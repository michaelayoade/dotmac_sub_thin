"""Image binding refuses false provenance and changes only [image]."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "bind_image.py"
spec = importlib.util.spec_from_file_location("bind_image", SCRIPT)
assert spec and spec.loader
bind_image = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bind_image)

DESCRIPTOR = '''[image]
# UNBOUND SENTINEL, deliberately. No CI build of this shell exists yet, and
# inventing a digest would be false provenance. The first test-server/CI
# build binds the real repo@sha256 digest together with source_revision.
reference = "ghcr.io/example/app@sha256:0000000000000000000000000000000000000000000000000000000000000000"
source_revision = "0000000000000000000000000000000000000000"
'''
DIGEST = "a" * 64
REVISION = "b" * 40


def test_bind_replaces_only_image_provenance() -> None:
    bound = bind_image.bind_descriptor(
        DESCRIPTOR,
        reference=f"ghcr.io/example/app@sha256:{DIGEST}",
        source_revision=REVISION,
    )
    assert f"@sha256:{DIGEST}" in bound
    assert f'source_revision = "{REVISION}"' in bound
    assert "UNBOUND SENTINEL" not in bound


@pytest.mark.parametrize(
    ("reference", "revision"),
    [
        (f"ghcr.io/example/app@sha256:{'0' * 64}", REVISION),
        ("ghcr.io/example/other@sha256:" + DIGEST, REVISION),
        ("ghcr.io/example/app@sha256:not-a-digest", REVISION),
        (f"ghcr.io/example/app@sha256:{DIGEST}", "0" * 40),
        (f"ghcr.io/example/app@sha256:{DIGEST}", "not-a-revision"),
    ],
)
def test_bind_refuses_sentinel_wrong_repo_and_bad_shapes(
    reference: str, revision: str
) -> None:
    with pytest.raises(bind_image.ImageBindingError):
        bind_image.bind_descriptor(
            DESCRIPTOR, reference=reference, source_revision=revision
        )
