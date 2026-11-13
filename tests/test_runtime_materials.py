"""M2 dev-secret gate: a DB-bound runtime refuses kernel dev defaults.

The kernel only enforces its secret rules when ENVIRONMENT is production;
a candidate/staging process would otherwise serve with published sentinel
secrets and seed-on-startup enabled. The product entrypoint must fail
closed in every environment once a database is bound.
"""

from __future__ import annotations

import pytest

from sub_thin.materials import (
    RuntimeMaterialsError,
    enforce_runtime_materials,
    runtime_materials_problems,
)

_DSN = "postgresql+psycopg://app_user:x@127.0.0.1:5432/subthin"
_SECRET = "x" * 40


def _valid_env() -> dict[str, str]:
    return {
        "DATABASE_URL": _DSN,
        "JWT_SECRET": "j" * 40,
        "SESSION_HASH_SECRET": "s" * 40,
        "CSRF_SECRET": "c" * 40,
        "TRUSTED_HOSTS": "127.0.0.1,localhost",
        "SEED_ON_STARTUP": "false",
    }


def test_shell_mode_without_database_needs_no_materials() -> None:
    assert runtime_materials_problems({}) == []


def test_valid_materials_pass() -> None:
    assert runtime_materials_problems(_valid_env()) == []
    enforce_runtime_materials(_valid_env())  # must not raise


def test_db_bound_without_materials_refuses_each_missing_one() -> None:
    problems = runtime_materials_problems({"DATABASE_URL": _DSN})
    joined = "; ".join(problems)
    for name in (
        "JWT_SECRET",
        "SESSION_HASH_SECRET",
        "CSRF_SECRET",
        "TRUSTED_HOSTS",
        "SEED_ON_STARTUP",
    ):
        assert name in joined
    with pytest.raises(RuntimeMaterialsError):
        enforce_runtime_materials({"DATABASE_URL": _DSN})


def test_published_dev_sentinel_is_refused() -> None:
    env = _valid_env()
    env["JWT_SECRET"] = "dev-insecure-change-me"  # noqa: S105 — kernel sentinel
    assert any("JWT_SECRET" in p for p in runtime_materials_problems(env))


def test_short_secret_is_refused() -> None:
    env = _valid_env()
    env["SESSION_HASH_SECRET"] = "short"
    assert any("SESSION_HASH_SECRET" in p for p in runtime_materials_problems(env))


def test_csrf_must_differ_from_other_secrets() -> None:
    env = _valid_env()
    env["CSRF_SECRET"] = env["JWT_SECRET"]
    assert any("CSRF_SECRET" in p for p in runtime_materials_problems(env))


@pytest.mark.parametrize("value", ["true", "1", "yes", "on"])
def test_seed_on_startup_truthy_is_refused(value: str) -> None:
    env = _valid_env()
    env["SEED_ON_STARTUP"] = value
    assert any("SEED_ON_STARTUP" in p for p in runtime_materials_problems(env))


def test_seed_on_startup_must_be_explicit() -> None:
    env = _valid_env()
    del env["SEED_ON_STARTUP"]
    assert any("SEED_ON_STARTUP" in p for p in runtime_materials_problems(env))


def test_blank_trusted_hosts_is_refused() -> None:
    env = _valid_env()
    env["TRUSTED_HOSTS"] = "   "
    assert any("TRUSTED_HOSTS" in p for p in runtime_materials_problems(env))


def test_problems_never_echo_secret_values() -> None:
    env = _valid_env()
    env["JWT_SECRET"] = _SECRET
    env["CSRF_SECRET"] = _SECRET  # forces a distinctness problem
    joined = "; ".join(runtime_materials_problems(env))
    assert _SECRET not in joined


def _anon_env(**extra: str) -> dict[str, str]:
    env = _valid_env()
    env.update(
        {
            "ANONYMOUS_RATE_LIMIT_ROUTES": "/login",
            "ANONYMOUS_RATE_LIMIT_STORE": "postgres",
            "ANONYMOUS_RATE_LIMIT_KEY_SECRET": "a" * 40,
        }
    )
    env.update(extra)
    return env


def test_anonymous_key_not_checked_when_routes_undeclared() -> None:
    env = _valid_env()
    env["ANONYMOUS_RATE_LIMIT_STORE"] = "postgres"
    env["ANONYMOUS_RATE_LIMIT_KEY_SECRET"] = "dev-insecure-change-me"
    assert runtime_materials_problems(env) == []


def test_anonymous_key_not_checked_on_memory_store() -> None:
    env = _anon_env(ANONYMOUS_RATE_LIMIT_STORE="memory")
    del env["ANONYMOUS_RATE_LIMIT_KEY_SECRET"]
    assert runtime_materials_problems(env) == []


def test_valid_anonymous_key_passes() -> None:
    assert runtime_materials_problems(_anon_env()) == []


@pytest.mark.parametrize(
    "value", [None, "dev-insecure-change-me", "short", "j" * 40, "c" * 40]
)
def test_unsafe_anonymous_key_is_refused_without_disclosure(value: str | None) -> None:
    env = _anon_env()
    if value is None:
        del env["ANONYMOUS_RATE_LIMIT_KEY_SECRET"]
    else:
        env["ANONYMOUS_RATE_LIMIT_KEY_SECRET"] = value
    problems = runtime_materials_problems(env)
    assert any("ANONYMOUS_RATE_LIMIT_KEY_SECRET" in p for p in problems)
    if value:
        assert all(value not in p for p in problems)
    with pytest.raises(RuntimeMaterialsError, match="ANONYMOUS_RATE_LIMIT_KEY_SECRET"):
        enforce_runtime_materials(env)
