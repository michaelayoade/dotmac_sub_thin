"""This assembly's migration prerequisite and plane decisions.

These constants are consumed by the Alembic environment. They intentionally
do not derive decisions from installed package order: N3 composes only the
kernel lineage and the tenant plane of `dotmac-brand-profiles`.
"""

from __future__ import annotations

from typing import Final

from dotmac_kernel.planes import ModulePlane, ModulePlaneSelection
from dotmac_kernel.prerequisites import (
    IDEMPOTENCY_LEDGER_V1,
    MODULE_DATABASE_ROLES_V1,
    TENANT_SCOPE_CATALOG_V1,
    PrerequisiteBinding,
)

ASSEMBLY_PREREQUISITE_BINDINGS: Final[tuple[PrerequisiteBinding, ...]] = (
    PrerequisiteBinding(
        prerequisite=TENANT_SCOPE_CATALOG_V1.name,
        provider_revision="0001_initial_tenant_schema",
        provider_owner="kernel",
    ),
    PrerequisiteBinding(
        prerequisite=MODULE_DATABASE_ROLES_V1.name,
        provider_revision="0001_initial_tenant_schema",
        provider_owner="kernel",
    ),
    # Name the revision that supplies the whole ledger, not the lineage root.
    PrerequisiteBinding(
        prerequisite=IDEMPOTENCY_LEDGER_V1.name,
        provider_revision="0018_idempotency_one_owner",
        provider_owner="kernel",
    ),
)

ASSEMBLY_MODULE_PLANES: Final[tuple[ModulePlaneSelection, ...]] = (
    ModulePlaneSelection(
        module="brand_profiles",
        planes=(ModulePlane.TENANT,),
    ),
)

__all__ = [
    "ASSEMBLY_MODULE_PLANES",
    "ASSEMBLY_PREREQUISITE_BINDINGS",
]
