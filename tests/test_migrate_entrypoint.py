"""Migration entrypoint contract without a live database."""

from __future__ import annotations

import pytest

from alembic.script import ScriptDirectory

from sub_thin.migrate import (
    EXPECTED_HEADS,
    MigrationConfigurationError,
    build_config,
    migration_paths,
    select_url,
)

DSN = "postgresql+psycopg://app_admin:x@127.0.0.1:1/subthin"


def test_migration_url_has_no_runtime_fallback() -> None:
    with pytest.raises(MigrationConfigurationError):
        select_url(environ={"DATABASE_URL": DSN})
    with pytest.raises(MigrationConfigurationError):
        select_url(environ={"MIGRATION_DATABASE_URL": "sqlite:///tmp/x.db"})


def test_build_config_composes_kernel_and_brand_lineages() -> None:
    config = build_config(DSN)
    locations = config.get_main_option("version_locations") or ""
    assert "dotmac_kernel" in locations
    assert "dotmac_brand_profiles" in locations
    assert config.attributes["module_plane_selections"][0].module == "brand_profiles"
    script_location, versions = migration_paths()
    assert (script_location / "env.py").is_file()
    assert len(versions) == 3
    assert all(path.is_dir() for path in versions)
    heads = ScriptDirectory.from_config(config).get_heads()
    assert sorted(heads) == sorted(EXPECTED_HEADS)
