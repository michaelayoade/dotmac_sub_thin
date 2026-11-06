"""Sub thin assembly spec — N2 empty shell.

Unlike legacy `dotmac_sub/app/composition.py` (metadata-only; the S1 guard
forbids `mount_features` there), this spec is RUNTIME input to
`dotmac_kernel.create_app`. Replace-not-adapt: the composed app is born
here, legacy Sub is never mounted into it.

N2 posture:
- One data module mounted, still no product traffic: `brand_profiles`
  (TENANT plane, no routers) beside the assembly-owned readiness route.
  Further modules arrive one wave at a time with transform + parity
  evidence. Mounting is not a flip: no consumer reads brand through
  this app yet.
- `tenancy="single"`: Sub is a dedicated single-operator ISP deployment
  (legacy ADR-0009), declared rather than inherited from the kernel's
  multi-tenant default.
- `web_enabled=False`: API/health surface only until a wave mounts a
  browser surface deliberately.
- Explicit database binding (`sub_thin.database`): if `DATABASE_URL` is
  declared, the assembly binds its own `DatabaseRuntime` and a startup
  check proves the DSN role is non-superuser + NOBYPASSRLS (register S11).
  Absent DSN = empty-shell mode (health only, `/health` is DB-free by
  kernel design); blank/non-Postgres DSN refuses at import. When a DSN
  is declared, `require_database_runtime` is True (no reference-runtime
  fallback) and `/health/ready` probes the bound engine.
"""

from __future__ import annotations

from typing import Final

from dotmac_kernel.api_documentation import environment_api_documentation_policy
from dotmac_kernel.assembly import ProductAssemblySpec, ProductSecurityPolicy

from dotmac_brand_profiles.manifest import module as brand_profiles_module

from sub_thin.database import build_database_runtime, database_startup_checks
from sub_thin.migration_bindings import ASSEMBLY_MODULE_PLANES
from sub_thin.readiness import readiness_feature

PRODUCT_NAME: Final = "dotmac-sub"

# Built at import like the reference assembly's settings reads. Engine
# construction opens no connection; posture is proven by the startup check.
_database_runtime = build_database_runtime()

assembly: Final = ProductAssemblySpec(
    name=PRODUCT_NAME,
    modules=(readiness_feature, brand_profiles_module),
    module_planes=ASSEMBLY_MODULE_PLANES,
    tenancy="single",
    platform_surface_enabled=False,
    web_enabled=False,
    database_runtime=_database_runtime,
    require_database_runtime=_database_runtime is not None,
    startup_checks=database_startup_checks(_database_runtime),
    startup_hooks=(),
    security_policy=ProductSecurityPolicy(),
    # Kernel fails closed without an explicit docs policy; resolve from
    # ENVIRONMENT (production = docs off), as the reference assembly does.
    api_documentation=environment_api_documentation_policy(),
)

__all__ = ["PRODUCT_NAME", "assembly"]
