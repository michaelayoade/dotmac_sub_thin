"""N4 runtime wiring: brand module mounted, readiness probes the DB."""

from __future__ import annotations

from dotmac_kernel.planes import ModulePlane

from sub_thin import readiness
from sub_thin.assembly import assembly


def test_brand_module_mounted_tenant_only() -> None:
    codes = {getattr(m, "code", getattr(m, "name", "")) for m in assembly.modules}
    assert "brand_profiles" in codes
    selections = {s.module: s.planes for s in assembly.module_planes}
    assert selections["brand_profiles"] == (ModulePlane.TENANT,)


def test_readiness_probe_shell_mode_without_dsn(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    ok, _ = readiness.readiness_probe()
    assert ok is True


def test_readiness_probe_fails_when_dsn_declared_but_runtime_missing(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:x@127.0.0.1:1/none")

    def _raise():
        from dotmac_kernel.session_runtime import NoDatabaseRuntimeError

        raise NoDatabaseRuntimeError("unbound")

    monkeypatch.setattr(readiness, "resolve_database_runtime", _raise)
    ok, _ = readiness.readiness_probe()
    assert ok is False
