"""Production configuration must refuse unsafe inputs without contacting a DB."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
import sqlalchemy as sa

from sub_thin.preflight import main, production_configuration_problems


@pytest.fixture
def production_env(monkeypatch):
    # Include every kernel setting so inherited operator configuration cannot
    # influence these checks. Values here are deliberately fake test material.
    from dotmac_kernel.config import Settings

    for field in Settings.model_fields:
        monkeypatch.delenv(field.upper(), raising=False)
    monkeypatch.delenv("LEGACY_DATABASE_URL", raising=False)
    values = {
        "ENVIRONMENT": "production",
        "DATABASE_URL": "postgresql+psycopg://app_user:test@127.0.0.1:1/subthin",
        "PLATFORM_DATABASE_URL": "postgresql+psycopg://platform_api:test@127.0.0.1:1/subthin",
        "PLATFORM_ROOT_DOMAIN": "sub.example.com",
        "TRUSTED_HOSTS": "127.0.0.1,sub.example.com",
        "JWT_SECRET": "j" * 40,
        "SESSION_HASH_SECRET": "s" * 40,
        "CSRF_SECRET": "c" * 40,
        "SEED_ON_STARTUP": "false",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    # A regression that attempts any connection fails rather than reaching a DB.
    def no_connect(*args, **kwargs):
        pytest.fail("offline preflight attempted a database connection")
    monkeypatch.setattr(sa.engine.Engine, "connect", no_connect)
    return values


def test_production_configuration_is_offline(production_env):
    assert production_configuration_problems() == []


@pytest.mark.parametrize("name", ["ENVIRONMENT", "DATABASE_URL", "PLATFORM_DATABASE_URL", "PLATFORM_ROOT_DOMAIN"])
def test_required_production_facts(production_env, monkeypatch, name):
    monkeypatch.delenv(name)
    assert any(name in problem for problem in production_configuration_problems())


def test_kernel_production_rules_are_applied(production_env, monkeypatch):
    monkeypatch.setenv("CSRF_ENABLED", "false")
    assert any("CSRF_ENABLED" in problem for problem in production_configuration_problems())


@pytest.mark.parametrize("name", ["MIGRATION_DATABASE_URL", "LEGACY_DATABASE_URL"])
def test_owner_materials_are_refused(production_env, monkeypatch, name):
    monkeypatch.setenv(name, "private-owner-material")
    assert any(name in problem for problem in production_configuration_problems())


@pytest.mark.parametrize("name", ["MIGRATION_DATABASE_URL", "LEGACY_DATABASE_URL"])
@pytest.mark.parametrize("spelling", [str.lower, str.title])
def test_owner_materials_are_refused_in_any_case(production_env, monkeypatch, name, spelling):
    secret = "private-owner-material"
    monkeypatch.setenv(spelling(name), secret)
    problems = production_configuration_problems()
    assert f"{name} must not be present in a runtime process" in problems
    assert not any(secret in problem for problem in problems)


def test_malformed_binding_is_sanitized(production_env, monkeypatch, capsys):
    secret = "private-url-that-must-not-be-printed"
    monkeypatch.setenv("DATABASE_URL", secret)
    assert main() == 2
    assert secret not in capsys.readouterr().err


def test_invalid_typed_setting_is_sanitized(production_env, monkeypatch, capsys):
    secret = "private-invalid-value"
    monkeypatch.setenv("CSRF_TOKEN_TTL_SECONDS", secret)
    assert main() == 2
    assert secret not in capsys.readouterr().err


def test_cli_import_failure_has_no_traceback_or_values(production_env, tmp_path):
    env = dict(os.environ, CSRF_ENABLED="private-invalid-boolean", PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run([sys.executable, "-B", "-m", "sub_thin.preflight"], cwd=tmp_path, env=env, text=True, capture_output=True)
    assert result.returncode == 2
    assert "private-invalid-boolean" not in result.stderr
    assert "Traceback" not in result.stderr


def test_dotenv_cannot_supply_final_runtime_materials(production_env, monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("PLATFORM_ROOT_DOMAIN=hidden.example.com\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PLATFORM_ROOT_DOMAIN")
    assert any("PLATFORM_ROOT_DOMAIN" in problem for problem in production_configuration_problems())
