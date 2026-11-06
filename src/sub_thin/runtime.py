"""Product-owned process launcher for the composed Sub shell.

The deployment descriptor names this launcher and the container port. The
bind address stays here, in code bound by the image digest, rather than in a
deployment document.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence

import uvicorn

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
    uvicorn.run(app, host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
