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
    "value", [None, "dev-insecure-change-me", "short", "j" * 40, "s" * 40, "c" * 40]
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


def test_anonymous_key_rule_applies_when_store_unset() -> None:
    env = _anon_env()
    del env["ANONYMOUS_RATE_LIMIT_STORE"]
    del env["ANONYMOUS_RATE_LIMIT_KEY_SECRET"]
    assert any(
        "ANONYMOUS_RATE_LIMIT_KEY_SECRET" in p for p in runtime_materials_problems(env)
    )


def test_anonymous_key_rule_applies_to_padded_uppercase_store() -> None:
    env = _anon_env(ANONYMOUS_RATE_LIMIT_STORE=" POSTGRES ")
    del env["ANONYMOUS_RATE_LIMIT_KEY_SECRET"]
    assert any(
        "ANONYMOUS_RATE_LIMIT_KEY_SECRET" in p for p in runtime_materials_problems(env)
    )


def test_whitespace_only_routes_leave_behaviour_unchanged() -> None:
    env = _anon_env(ANONYMOUS_RATE_LIMIT_ROUTES="   ")
    del env["ANONYMOUS_RATE_LIMIT_KEY_SECRET"]
    assert runtime_materials_problems(env) == []


def test_anonymous_key_rule_applies_without_database_url() -> None:
    env = {
        "ANONYMOUS_RATE_LIMIT_ROUTES": "/login",
        "ANONYMOUS_RATE_LIMIT_STORE": "postgres",
    }
    assert any(
        "ANONYMOUS_RATE_LIMIT_KEY_SECRET" in p for p in runtime_materials_problems(env)
    )
    env["ANONYMOUS_RATE_LIMIT_KEY_SECRET"] = "a" * 40
    assert runtime_materials_problems(env) == []


def test_lowercase_anonymous_routes_with_missing_key_is_refused() -> None:
    env = _valid_env()
    env["anonymous_rate_limit_routes"] = "/login"
    assert any(
        "ANONYMOUS_RATE_LIMIT_KEY_SECRET" in p for p in runtime_materials_problems(env)
    )


@pytest.mark.parametrize("value", ["short", "dev-insecure-change-me"])
def test_lowercase_signing_secret_is_refused_like_uppercase(value: str) -> None:
    env = _valid_env()
    del env["JWT_SECRET"]
    env["jwt_secret"] = value
    problems = runtime_materials_problems(env)
    assert any("JWT_SECRET" in p for p in problems)
    assert all(value not in p for p in problems)


def test_case_collision_is_refused_without_disclosure() -> None:
    env = _valid_env()
    other = "q" * 40
    env["jwt_secret"] = other
    problems = runtime_materials_problems(env)
    assert any("JWT_SECRET" in p for p in problems)
    joined = "; ".join(problems)
    assert other not in joined
    assert env["JWT_SECRET"] not in joined


def test_lowercase_weak_signing_secret_reports_exact_weak_message() -> None:
    env = _valid_env()
    del env["JWT_SECRET"]
    env["jwt_secret"] = "short"
    assert runtime_materials_problems(env) == [
        "JWT_SECRET must contain at least 32 bytes"
    ]


def test_case_collision_message_is_exact() -> None:
    env = _valid_env()
    env["jwt_secret"] = "q" * 40
    assert runtime_materials_problems(env) == [
        "JWT_SECRET is set under more than one letter case; supply exactly one spelling"
    ]


def test_only_lowercase_spellings_with_strong_distinct_values_pass() -> None:
    env = {key.lower(): value for key, value in _anon_env().items()}
    assert runtime_materials_problems(env) == []


def test_non_ascii_fold_lookalike_does_not_satisfy_gate_key() -> None:
    env = _valid_env()
    del env["JWT_SECRET"]
    env["JWT_\u017fECRET"] = "j" * 40
    assert runtime_materials_problems(env) == [
        "JWT_SECRET must be supplied when a database is bound"
    ]


def test_kelvin_sign_name_is_treated_as_the_gate_key_like_the_kernel() -> None:
    env = _anon_env()
    del env["ANONYMOUS_RATE_LIMIT_KEY_SECRET"]
    good = {**env, "ANONYMOUS_RATE_LIMIT_\u212aEY_SECRET": "a" * 40}
    assert runtime_materials_problems(good) == []
    weak = {**env, "ANONYMOUS_RATE_LIMIT_\u212aEY_SECRET": "short"}
    assert runtime_materials_problems(weak) == [
        "ANONYMOUS_RATE_LIMIT_KEY_SECRET must contain at least 32 bytes"
    ]
