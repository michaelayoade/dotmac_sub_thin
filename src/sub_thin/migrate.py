"""Migration owner entrypoint for the composed Sub assembly.

Descriptor contract:

    python -m sub_thin.migrate upgrade heads
    python -m sub_thin.migrate current

`MIGRATION_DATABASE_URL` is required. There is deliberately no fallback to
the runtime `DATABASE_URL`: Foundation's credential-separation rule gives
DDL to the migration owner identity alone. Error messages never include the
supplied DSN.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping, Sequence
from importlib import import_module
from pathlib import Path

import sqlalchemy as sa
from dotmac_kernel.migrations.configuration import (
    select_migration_database_url,
    set_alembic_database_url,
)
from dotmac_kernel.planes import install_module_plane_selections
from dotmac_kernel.prerequisites import install_prerequisite_bindings

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sub_thin.migration_bindings import (
    ASSEMBLY_MODULE_PLANES,
    ASSEMBLY_PREREQUISITE_BINDINGS,
)


class MigrationConfigurationError(RuntimeError):
    """A sanitized migration configuration refusal."""


# Mirrors deploy/product.toml [migration] expected_heads. The durable
# migrate-entrypoint test asserts ScriptDirectory heads equal this set.
EXPECTED_HEADS: tuple[str, ...] = (
    "0030_credential_tenant_key",
    "bp_0001_brand_profiles",
)


def _module_dir(package: str) -> Path:
    module_file = import_module(package).__file__
    if module_file is None:  # pragma: no cover - installed packages are files
        raise MigrationConfigurationError(f"installed package {package!r} has no file path")
    return Path(module_file).resolve().parent


def migration_paths() -> tuple[Path, tuple[Path, ...]]:
    """Return `(script_location, version_locations)` for installed lineages."""

    script_location = _module_dir("sub_thin.migrations")
    version_locations = (
        script_location / "versions",
        _module_dir("dotmac_kernel.migrations") / "versions",
        _module_dir("dotmac_brand_profiles.migrations") / "versions",
    )
    return script_location, version_locations


def select_url(
    database_url: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> str:
    env = os.environ if environ is None else environ
    supplied = database_url if database_url is not None else env.get("MIGRATION_DATABASE_URL")
    try:
        selected = select_migration_database_url(
            migration_database_url=supplied,
            fallback_database_url=None,
        )
        url = sa.make_url(selected)
    except (sa.exc.ArgumentError, ValueError) as exc:
        raise MigrationConfigurationError(
            "MIGRATION_DATABASE_URL is required and must be a valid PostgreSQL DSN"
        ) from exc
    if url.get_dialect().name != "postgresql":
        raise MigrationConfigurationError(
            "MIGRATION_DATABASE_URL is required and must be a valid PostgreSQL DSN"
        )
    return selected


def build_config(database_url: str | None = None) -> Config:
    """Build the Alembic config after installing assembly decisions."""

    selected = select_url(database_url)
    install_prerequisite_bindings(ASSEMBLY_PREREQUISITE_BINDINGS)
    install_module_plane_selections(ASSEMBLY_MODULE_PLANES)

    script_location, version_locations = migration_paths()
    config = Config()
    config.set_main_option("script_location", str(script_location))
    config.set_main_option(
        "version_locations", os.pathsep.join(str(path) for path in version_locations)
    )
    config.set_main_option("version_path_separator", "os")
    config.set_main_option("sub_thin_migration_url", selected.replace("%", "%%"))
    set_alembic_database_url(config, database_url=selected)
    config.attributes["module_plane_selections"] = ASSEMBLY_MODULE_PLANES
    return config


def _preflight_owner(selected: str) -> None:
    """Refuse a superuser migration identity; name the target database."""

    engine = sa.create_engine(selected, pool_pre_ping=True, hide_parameters=True)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                sa.text(
                    "SELECT current_database(), current_user, "
                    "(SELECT rolsuper FROM pg_catalog.pg_roles "
                    " WHERE rolname = current_user)"
                )
            ).one()
    finally:
        engine.dispose()
    print(f"migration target: database={row[0]} user={row[1]}")
    if row[2]:
        raise MigrationConfigurationError(
            "migration identity is a superuser; use the non-super owner role"
        )


def upgrade_heads(database_url: str | None = None) -> None:
    config = build_config(database_url)
    _preflight_owner(select_url(database_url))
    command.upgrade(config, "heads")


def current_heads(database_url: str | None = None) -> tuple[str, ...]:
    """Return sorted current heads without creating a version table."""

    selected = select_url(database_url)
    engine = sa.create_engine(
        selected,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={"application_name": "dotmac-sub-thin-migrate"},
    )
    try:
        with engine.connect() as connection:
            if not sa.inspect(connection).has_table("alembic_version"):
                return ()
            context = MigrationContext.configure(connection)
            return tuple(sorted(context.get_current_heads()))
    finally:
        engine.dispose()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m sub_thin.migrate")
    subparsers = parser.add_subparsers(dest="command", required=True)
    upgrade = subparsers.add_parser("upgrade")
    upgrade.add_argument("target", choices=("heads",))
    subparsers.add_parser("current")
    args = parser.parse_args(argv)

    try:
        if args.command == "upgrade":
            upgrade_heads()
        else:
            for head in current_heads():
                print(head)
    except MigrationConfigurationError as exc:
        print(f"migration configuration error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - fixed sanitized boundary
        print(f"migration failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
