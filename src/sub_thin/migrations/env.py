"""Alembic environment for the composed Sub assembly.

Composes exactly two installed lineages at this stage: the kernel base
lineage and `dotmac-brand-profiles` tenant plane. Bindings and the plane
selection are installed before Alembic resolves the brand lineage's
`depends_on` edges.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from dotmac_brand_profiles import models as brand_models  # noqa: F401
from dotmac_kernel import (
    audit,  # noqa: F401
    entitlements,  # noqa: F401
    idempotency_models,  # noqa: F401
    models_platform,  # noqa: F401
    settings_models,  # noqa: F401
)
from dotmac_kernel.messaging import models as messaging_models  # noqa: F401
from dotmac_kernel.migrations.configuration import set_alembic_database_url
from dotmac_kernel.models import Base
from dotmac_kernel.planes import install_module_plane_selections
from dotmac_kernel.prerequisites import install_prerequisite_bindings
from sqlalchemy import engine_from_config, pool

from alembic import context
from sub_thin.migration_bindings import (
    ASSEMBLY_MODULE_PLANES,
    ASSEMBLY_PREREQUISITE_BINDINGS,
)

config = context.config

held_url = config.get_main_option("sub_thin_migration_url")
if not held_url:
    held_url = os.getenv("MIGRATION_DATABASE_URL")
if held_url:
    set_alembic_database_url(config, database_url=held_url)

install_prerequisite_bindings(ASSEMBLY_PREREQUISITE_BINDINGS)
install_module_plane_selections(
    config.attributes.get("module_plane_selections", ASSEMBLY_MODULE_PLANES)
)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
