"""Entrypoint: hand the assembly spec to the kernel factory.

Run: `uvicorn sub_thin.main:app --host 127.0.0.1 --port 8011`
"""

from __future__ import annotations

from dotmac_kernel import create_app

from sub_thin.assembly import assembly

app = create_app(assembly)
