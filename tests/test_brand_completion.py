"""Platform completion: legacy fallbacks fill gaps, never overwrite."""

from __future__ import annotations

from uuid import UUID

from sub_thin.cutover.brand_profiles import (
    complete_platform_brand,
    transform_brand_rows,
)

TENANT = UUID("00000000-0000-0000-0000-000000000001")
LOGO = "d513eafd-4b93-4be9-a749-15b93ecfe1b3"


def test_completion_fills_only_missing_fields() -> None:
    rows = [{
        "id": "platform-row", "scope_type": "platform", "scope_id": None,
        "product_name": "Profile Product",
        "logo_url": f"/branding/assets/{LOGO}",
        "support_phone": "",
        "is_active": True,
    }]
    base = transform_brand_rows(rows, tenant_id=TENANT)
    plan = complete_platform_brand(
        base,
        rows,
        {
            "name": "Resolved Name",
            "product_name": "Fallback Product",
            "primary_color": "#112233",
            "secondary_color": "#445566",
            "support_email": "help@example.io",
            "support_phone": "+2340000000000",
            "from_email": "no-reply@example.io",
            "from_name": "Example",
            "app_url": "https://selfcare.example.io",
            "tagline": "Hello",
            "portal_domain": "selfcare.example.io",
            "semantic_colors": {"positive": "#00aa00"},
        },
    )

    item = plan.item
    assert item.command_id.endswith("-completed-v1")
    assert item.fields["display_name"] == "Resolved Name"
    assert item.fields["product_name"] == "Profile Product"
    assert item.fields["primary_hex"] == "#112233"
    assert item.fields["accent_hex"] == "#445566"
    assert item.fields["logo_file_ref"] == LOGO
    assert item.fields["support_phone"] == "+2340000000000"
    assert item.fields["sender_email"] == "no-reply@example.io"
    assert {p.field: p.source for p in plan.provenance}["primary_hex"] == (
        "legacy_resolved_fallback"
    )
    unresolved = {(r.field, r.disposition) for r in plan.unresolved}
    assert ("tagline", "no_tenant_plane_home") in unresolved
    assert ("portal_domain", "no_tenant_plane_home") in unresolved
    assert ("semantic_positive_color", "owned_by_published_token") in unresolved
    completed = plan.completed_report()
    assert completed.reconciled and completed.loadable == (item,)


def test_completion_creates_platform_item_when_extract_has_none() -> None:
    base = transform_brand_rows([], tenant_id=TENANT)
    plan = complete_platform_brand(
        base,
        [],
        {"name": "Only Resolved", "primary_color": "#123456"},
    )
    assert plan.item.source_id == "legacy-resolved-platform"
    assert plan.item.profile_code == "only-resolved"
    assert plan.item.fields["display_name"] == "Only Resolved"
    completed = plan.completed_report()
    assert completed.extracted == 1  # the resolved snapshot is the source record
    assert completed.reconciled
