"""N3 brand-profiles transform: legacy extract -> load plan + reject ledger.

Pure and DB-free (the Starter translator's own design): run it over a
read-only legacy extract and review the aggregate BEFORE anything is
written. Every legacy field is accounted for exactly once — mapped,
or named in the reject ledger with a disposition. Silent drops are the
failure this harness exists to prevent.

Reconciliation invariant: extracted == loadable + row_rejected. Field
rejects ride along with loadable rows (the row loads, the value does
not) and are counted separately.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any, Final
from uuid import UUID

from dotmac_brand_profiles.brand_values import (
    translate_legacy_brand_values,
    validate_brand_values,
)

# Legacy columns (dotmac_sub app/models/branding.py::BrandProfile).
_DIRECT: Final[Mapping[str, str]] = {
    "brand_name": "display_name",
    "product_name": "product_name",
    "legal_name": "legal_name",
    "support_email": "support_email",
    "support_phone": "support_phone",
    "from_email": "sender_email",
    "from_name": "sender_name",
    "app_url": "support_url",
}
_FILE_REFS: Final[Mapping[str, str]] = {
    "logo_url": "logo_file_ref",
    "dark_logo_url": "dark_logo_file_ref",
    "favicon_url": "icon_file_ref",
}
_NO_HOME: Final = frozenset({"tagline", "portal_domain"})
_KNOWN: Final = frozenset(
    set(_DIRECT)
    | set(_FILE_REFS)
    | _NO_HOME
    | {
        "id", "scope_type", "scope_id", "primary_color", "secondary_color",
        "legal_address", "metadata", "is_active", "created_at", "updated_at",
    }
)
_SLUG_RE: Final = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class Reject:
    """One value (or row) that did not survive transform, and why."""

    source_id: str
    field: str
    disposition: str
    detail: str
    value: str = ""

    def to_dict(self) -> dict[str, str]:
        # Never serialize the rejected value itself: later waves carry
        # real tenant data through this ledger. Length + hash only.
        digest = hashlib.sha256(self.value.encode()).hexdigest() if self.value else ""
        return {
            "source_id": self.source_id, "field": self.field,
            "disposition": self.disposition, "detail": self.detail,
            "value_sha256": digest, "value_length": str(len(self.value)),
        }


@dataclass(frozen=True, slots=True)
class LoadItem:
    """One loadable row, shaped for UpsertTenantProfileCommand."""

    source_id: str
    command_id: str
    scope_type: str
    scope_id: str | None
    profile_code: str
    fields: Mapping[str, Any]
    activate: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id, "command_id": self.command_id,
            "scope_type": self.scope_type, "scope_id": self.scope_id,
            "profile_code": self.profile_code, "fields": dict(self.fields),
            "activate": self.activate,
        }


@dataclass(frozen=True, slots=True)
class BrandCutoverReport:
    tenant_id: str
    loadable: tuple[LoadItem, ...]
    rejects: tuple[Reject, ...]
    extracted: int
    row_rejected: int = field(default=0)

    @property
    def reconciled(self) -> bool:
        return self.extracted == len(self.loadable) + self.row_rejected

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "totals": {
                "extracted": self.extracted,
                "loadable": len(self.loadable),
                "row_rejected": self.row_rejected,
                "field_rejects": len(self.rejects),
                "reconciled": self.reconciled,
            },
            "loadable": [item.to_dict() for item in self.loadable],
            "rejects": [reject.to_dict() for reject in self.rejects],
        }


def _slug(value: str) -> str:
    return _SLUG_RE.sub("-", value.strip().lower()).strip("-")[:120].strip("-")


_MANAGED_BRANDING_PREFIX: Final = "/branding/assets/"


def _file_ref(value: str) -> str | None:
    """Return the opaque StoredFile ID behind a legacy branding value.

    Legacy managed assets are addressed as `/branding/assets/{uuid}` (see
    legacy `branding_storage.file_id_from_branding_url`). Starter stores
    only the opaque file reference, so carry the UUID—not the serving path.
    Already-migrated bare UUIDs pass through. Everything else, including
    `/static/...` and external/data URLs, must be dispositioned by the
    files wave rather than smuggled into a file-ref column.
    """

    candidate = value.strip()
    if candidate.startswith(_MANAGED_BRANDING_PREFIX):
        candidate = candidate[len(_MANAGED_BRANDING_PREFIX) :].split("?", 1)[0].strip("/")
    try:
        return str(UUID(candidate))
    except (ValueError, AttributeError):
        return None


def transform_brand_rows(
    rows: Sequence[Mapping[str, Any]], *, tenant_id: UUID
) -> BrandCutoverReport:
    """Transform legacy brand rows into a load plan with a reject ledger."""

    loadable: list[LoadItem] = []
    rejects: list[Reject] = []
    row_rejected = 0
    seen_codes: dict[str, str] = {}

    for row in rows:
        source_id = str(row.get("id") or "<missing-id>")
        scope_type = str(row.get("scope_type") or "")
        scope_id = row.get("scope_id")

        def reject(field_: str, disposition: str, detail: str, value: Any = "") -> None:
            rejects.append(Reject(source_id, field_, disposition, detail, str(value)))

        # Row-identity gate: mirror the legacy scope check constraint.
        if scope_type == "platform" and scope_id is not None:
            reject("scope_id", "invalid_scope", "platform scope must have no scope_id", scope_id)
            row_rejected += 1
            continue
        if scope_type in {"reseller", "organization"} and scope_id is None:
            reject("scope_id", "invalid_scope", f"{scope_type} scope requires scope_id")
            row_rejected += 1
            continue
        if scope_type not in {"platform", "reseller", "organization"}:
            reject("scope_type", "invalid_scope", f"unknown legacy scope_type {scope_type!r}", scope_type)
            row_rejected += 1
            continue

        fields: dict[str, Any] = {}
        for legacy, target in _DIRECT.items():
            if row.get(legacy) is not None:
                fields[target] = row[legacy]
        if isinstance(row.get("legal_address"), dict):
            fields["legal_address"] = row["legal_address"]

        for legacy, target in _FILE_REFS.items():
            value = row.get(legacy)
            if value is None:
                continue
            file_ref = _file_ref(str(value))
            if file_ref is not None:
                fields[target] = file_ref
            else:
                reject(legacy, "url_not_a_file_ref",
                       "Starter holds opaque dotmac-files refs, never URLs; "
                       "migrate the asset in the files wave (S9)", value)

        for legacy in sorted(_NO_HOME):
            if row.get(legacy) is not None:
                reject(legacy, "no_tenant_plane_home",
                       "no tenant-plane field in dotmac-brand-profiles", row[legacy])

        # Brand values go through the module's own translator: colors plus
        # semantic tones (flat keys and metadata.semantic_colors).
        values: dict[str, str | None] = {
            "primary_color": row.get("primary_color"),
            "secondary_color": row.get("secondary_color"),
        }
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        tones = metadata.get("semantic_colors")
        if isinstance(tones, dict):
            for tone, hex_value in tones.items():
                values[f"semantic_{tone}_color"] = hex_value
        for key, value in row.items():
            if key.startswith(("semantic_", "brand_semantic_")):
                values[key] = value
        translation = translate_legacy_brand_values(values)
        fields.update(translation.accepted)
        for unsupported in translation.unsupported:
            reject(unsupported.source_key, unsupported.disposition.value,
                   unsupported.detail, unsupported.value)

        for key in metadata:
            if key != "semantic_colors":
                reject(f"metadata.{key}", "unsupported_metadata_key",
                       "legacy metadata has no Starter home", metadata[key])
        for key in row:
            if key not in _KNOWN and not key.startswith(("semantic_", "brand_semantic_")):
                reject(key, "unknown_legacy_field",
                       "field not in the legacy BrandProfile contract", row[key])

        try:
            validate_brand_values(fields)
        except ValueError as exc:
            reject("primary_hex/accent_hex", "invalid_brand_values", str(exc))
            row_rejected += 1
            continue

        name_source = str(row.get("brand_name") or row.get("product_name") or "")
        code = _slug(name_source) or (
            f"{scope_type}-profile" if scope_id is None else f"{scope_type}-{str(scope_id)[:8]}"
        )
        if code in seen_codes:
            reject("profile_code", "duplicate_profile_code",
                   f"collides with source row {seen_codes[code]} in this tenant", code)
            row_rejected += 1
            continue
        seen_codes[code] = source_id
        fields.setdefault("display_name", name_source or code)

        loadable.append(LoadItem(
            source_id=source_id,
            command_id=f"n3-brand-{source_id}",
            scope_type=scope_type,
            scope_id=str(scope_id) if scope_id is not None else None,
            profile_code=code,
            fields=fields,
            activate=bool(row.get("is_active", True)),
        ))

    report = BrandCutoverReport(
        tenant_id=str(tenant_id), loadable=tuple(loadable),
        rejects=tuple(rejects), extracted=len(rows), row_rejected=row_rejected,
    )
    assert report.reconciled  # invariant: every row accounted for exactly once
    return report


@dataclass(frozen=True, slots=True)
class FieldProvenance:
    field: str
    source: str
    legacy_field: str

    def to_dict(self) -> dict[str, str]:
        return {
            "field": self.field,
            "source": self.source,
            "legacy_field": self.legacy_field,
        }


@dataclass(frozen=True, slots=True)
class PlatformCompletionPlan:
    """A target-side completion candidate. Planning only; no writes occur."""

    base_report: BrandCutoverReport
    item: LoadItem
    provenance: tuple[FieldProvenance, ...]
    unresolved: tuple[Reject, ...]
    synthetic: bool = False

    def completed_report(self) -> BrandCutoverReport:
        if self.synthetic:
            loadable = (*self.base_report.loadable, self.item)
            extracted = self.base_report.extracted + 1
        else:
            loadable = tuple(
                self.item if old.source_id == self.item.source_id else old
                for old in self.base_report.loadable
            )
            extracted = self.base_report.extracted
        return BrandCutoverReport(
            tenant_id=self.base_report.tenant_id,
            loadable=loadable,
            rejects=(*self.base_report.rejects, *self.unresolved),
            extracted=extracted,
            row_rejected=self.base_report.row_rejected,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "report": self.completed_report().to_dict(),
            "completion": {
                "synthetic": self.synthetic,
                "item": self.item.to_dict(),
                "provenance": [entry.to_dict() for entry in self.provenance],
                "unresolved": [entry.to_dict() for entry in self.unresolved],
            },
        }


def complete_platform_brand(
    report: BrandCutoverReport,
    rows: Sequence[Mapping[str, Any]],
    legacy_resolved: Mapping[str, Any],
) -> PlatformCompletionPlan:
    """Complete one platform profile from a read-only legacy resolved brand.

    Profile-supplied values win. Legacy resolved values fill only missing
    or empty fields, except `display_name`: when the source profile has
    no `brand_name`, the transformer's product-name fallback is replaced
    by the legacy resolved display name. Values with no tenant-plane home
    are returned as unresolved ledger entries, never silently dropped.

    This is a dry-run planner for the target load. It is not authorization
    to mutate the legacy source profile.
    """

    platform_items = [item for item in report.loadable if item.scope_type == "platform"]
    if len(platform_items) > 1:
        raise ValueError("platform completion requires at most one platform profile")
    base_item = platform_items[0] if platform_items else None
    synthetic = base_item is None
    rows_by_id = {str(row.get("id") or "<missing-id>"): row for row in rows}
    raw = rows_by_id.get(base_item.source_id, {}) if base_item else {}
    source_id = base_item.source_id if base_item else "legacy-resolved-platform"
    fields: dict[str, Any] = dict(base_item.fields) if base_item else {}
    provenance: list[FieldProvenance] = []
    unresolved: list[Reject] = []

    def add_reject(field_: str, disposition: str, detail: str, value: Any = "") -> None:
        unresolved.append(Reject(source_id, field_, disposition, detail, str(value)))

    def fill(target: str, legacy_field: str, value: Any) -> None:
        if fields.get(target) not in (None, "", {}, []):
            return
        if value in (None, "", {}, []):
            return
        fields[target] = value
        provenance.append(FieldProvenance(target, "legacy_resolved_fallback", legacy_field))

    if not raw.get("brand_name"):
        legacy_name = legacy_resolved.get("name")
        if legacy_name not in (None, ""):
            fields["display_name"] = legacy_name
            provenance.append(
                FieldProvenance("display_name", "legacy_resolved_fallback", "name")
            )

    fill("product_name", "product_name", legacy_resolved.get("product_name"))
    fill("legal_name", "legal_name", legacy_resolved.get("legal_name"))
    if isinstance(legacy_resolved.get("legal_address"), dict):
        fill("legal_address", "legal_address", legacy_resolved["legal_address"])
    fill("support_email", "support_email", legacy_resolved.get("support_email"))
    fill("support_phone", "support_phone", legacy_resolved.get("support_phone"))
    fill("sender_email", "from_email", legacy_resolved.get("from_email"))
    fill("sender_name", "from_name", legacy_resolved.get("from_name"))
    fill("support_url", "app_url", legacy_resolved.get("app_url"))

    color_translation = translate_legacy_brand_values(
        {
            "primary_color": legacy_resolved.get("primary_color"),
            "secondary_color": legacy_resolved.get("secondary_color"),
        }
    )
    fill("primary_hex", "primary_color", color_translation.accepted.get("primary_hex"))
    fill("accent_hex", "secondary_color", color_translation.accepted.get("accent_hex"))

    tones = legacy_resolved.get("semantic_colors")
    if isinstance(tones, dict):
        semantic = translate_legacy_brand_values(
            {f"semantic_{tone}_color": value for tone, value in tones.items()}
        )
        for unsupported in semantic.unsupported:
            add_reject(
                unsupported.source_key,
                unsupported.disposition.value,
                unsupported.detail,
                unsupported.value,
            )

    for legacy_field, target in _FILE_REFS.items():
        if fields.get(target) not in (None, ""):
            continue
        legacy_value = legacy_resolved.get(legacy_field)
        if legacy_value in (None, ""):
            continue
        ref = _file_ref(str(legacy_value))
        if ref is None:
            add_reject(
                legacy_field,
                "url_not_a_file_ref",
                "legacy resolved asset is not an opaque file reference",
                legacy_value,
            )
        else:
            fill(target, legacy_field, ref)

    for legacy_field in sorted(_NO_HOME):
        if legacy_resolved.get(legacy_field) not in (None, ""):
            add_reject(
                legacy_field,
                "no_tenant_plane_home",
                "no tenant-plane field in dotmac-brand-profiles",
                legacy_resolved[legacy_field],
            )

    known_resolved = {
        "name", "product_name", "legal_name", "legal_address",
        "support_email", "support_phone", "from_email", "from_name",
        "app_url", "primary_color", "secondary_color", "semantic_colors",
        "source_scope", "source_scope_id",
        *_FILE_REFS, *_NO_HOME,
    }
    for key in legacy_resolved:
        if key not in known_resolved:
            add_reject(
                key,
                "unknown_resolved_field",
                "key not in the legacy resolved-brand contract",
                legacy_resolved[key],
            )

    validate_brand_values(fields)

    provenanced = {entry.field for entry in provenance}
    reverse_direct = {target: legacy for legacy, target in _DIRECT.items()}
    reverse_direct.update({target: legacy for legacy, target in _FILE_REFS.items()})
    reverse_direct.update(
        {"primary_hex": "primary_color", "accent_hex": "secondary_color"}
    )
    for field_name in fields:
        if field_name not in provenanced:
            provenance.append(
                FieldProvenance(
                    field_name,
                    "brand_profile",
                    reverse_direct.get(field_name, field_name),
                )
            )

    if base_item is not None:
        command_id = base_item.command_id
        if not command_id.endswith("-completed-v1"):
            command_id = f"{command_id}-completed-v1"
        item = replace(base_item, command_id=command_id, fields=fields)
    else:
        name_source = str(
            fields.get("display_name") or fields.get("product_name") or ""
        )
        item = LoadItem(
            source_id=source_id,
            command_id="n3-brand-legacy-resolved-platform-completed-v1",
            scope_type="platform",
            scope_id=None,
            profile_code=_slug(name_source) or "platform-default",
            fields=fields,
            activate=True,
        )

    return PlatformCompletionPlan(
        base_report=report,
        item=item,
        provenance=tuple(provenance),
        unresolved=tuple(unresolved),
        synthetic=synthetic,
    )


def apply_load_plan(session: Any, report: BrandCutoverReport) -> list[str]:
    """Execute a reconciled load plan against a composed database.

    Operator-run only (cutover step): requires kernel + brand lineages
    migrated and prerequisites verified. Draft-first per the module
    contract; activation is a separate explicit command. Caller owns
    the transaction (module services receive a Session, hard rule 8).
    """

    from dotmac_brand_profiles.ports import ProfileFields
    from dotmac_brand_profiles.service import (
        UpsertTenantProfileCommand,
        activate_tenant_profile,
        upsert_tenant_profile,
    )

    tenant = UUID(report.tenant_id)
    loaded: list[str] = []
    for item in report.loadable:
        profile_id = upsert_tenant_profile(
            session,
            UpsertTenantProfileCommand(
                command_id=item.command_id,
                tenant_id=tenant,
                scope_type=item.scope_type,
                profile_code=item.profile_code,
                fields=ProfileFields(**item.fields),
                scope_id=UUID(item.scope_id) if item.scope_id else None,
            ),
        )
        if item.activate:
            activate_tenant_profile(
                session,
                command_id=f"{item.command_id}-activate",
                tenant_id=tenant,
                profile_id=profile_id,
            )
        loaded.append(str(profile_id))
    return loaded


__all__ = [
    "BrandCutoverReport", "FieldProvenance", "LoadItem",
    "PlatformCompletionPlan", "Reject", "apply_load_plan",
    "complete_platform_brand", "transform_brand_rows",
]
