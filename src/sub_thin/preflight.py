"""Offline check of production runtime configuration; never authorizes deployment.

Run in the digest-bound image with its final runtime environment:
    python -m sub_thin.preflight
No server, migrations, database connections, or material values are emitted.
"""

from __future__ import annotations

import os
import sys

from sub_thin.materials import runtime_materials_problems


def production_configuration_problems() -> list[str]:
    """Check final process configuration without importing the application."""
    problems = runtime_materials_problems()
    if os.environ.get("ENVIRONMENT", "").lower() not in {"prod", "production"}:
        problems.append("ENVIRONMENT must explicitly select production")
    for name in ("DATABASE_URL", "PLATFORM_DATABASE_URL", "PLATFORM_ROOT_DOMAIN"):
        if not os.environ.get(name, "").strip():
            problems.append(f"{name} must be explicitly supplied")
    # Refuse any letter case: the kernel's settings match names case-insensitively
    # (str.lower(), as in materials.py), so a variant spelling must not slip by.
    present = {key.lower() for key in os.environ}
    for name in ("MIGRATION_DATABASE_URL", "LEGACY_DATABASE_URL"):
        if name.lower() in present:
            problems.append(f"{name} must not be present in a runtime process")

    # config creates a module-level Settings too: keep the import inside this
    # boundary so malformed settings never escape as a value-bearing traceback.
    try:
        from dotmac_kernel.config import Settings, validate_settings

        settings = Settings(_env_file=None)
        for error in validate_settings(settings):
            # The kernel's tenancy diagnostic interpolates the rejected value.
            problems.append(
                "TENANCY must be single or multi"
                if error.startswith("TENANCY ") else error
            )
    except Exception:
        problems.append("kernel settings could not be validated; check material types")
        return list(dict.fromkeys(problems))

    # Engine construction validates URLs and installed drivers but is lazy:
    # it never connects. Application/lifespan checks remain a separate gate.
    try:
        from sub_thin.database import build_database_runtime

        runtime = build_database_runtime()
        if runtime is not None:
            runtime.engine.dispose()
            runtime.platform_engine.dispose()
    except Exception:
        problems.append("runtime database bindings could not be constructed")
    return list(dict.fromkeys(problems))


def main() -> int:
    problems = production_configuration_problems()
    if problems:
        for problem in problems:
            print(f"production configuration refused: {problem}", file=sys.stderr)
        return 2
    print(
        "production configuration passed "
        "(offline only; live readiness and deployment approval still required)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
