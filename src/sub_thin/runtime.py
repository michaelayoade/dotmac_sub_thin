"""Product-owned process launcher for the composed Sub shell.

The deployment descriptor names this launcher and the container port. The
bind address stays here, in code bound by the image digest, rather than in a
deployment document.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence

import uvicorn

from sub_thin.assembly import database_runtime
from sub_thin.database import DatabaseBindingError, enforce_runtime_posture
from sub_thin.main import app


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m sub_thin.runtime")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("APP_PORT", "8000")),
        help="Container port to bind (default: APP_PORT or 8000)",
    )
    args = parser.parse_args(argv)
    # Fail closed in every environment: kernel startup checks only warn
    # outside production, which once let a superuser DSN serve traffic.
    try:
        enforce_runtime_posture(database_runtime)
    except DatabaseBindingError as exc:
        print(f"refusing to serve: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    uvicorn.run(app, host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
