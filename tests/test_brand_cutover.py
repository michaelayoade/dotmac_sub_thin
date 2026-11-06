"""N3 brand transform: totals reconcile, every reject is named.

Synthetic legacy-shaped rows (no production data). The invariant under
test is the N3 closure shape: extracted == loadable + row_rejected,
and no legacy value disappears without a ledger entry.
"""

from __future__ import annotations

from uuid import UUID

from sub_thin.cutover.brand_profiles import transform_brand_rows

TENANT = UUID("00000000-0000-0000-0000-000000000001")
RESELLER = "11111111-1111-1111-1111-111111111111"


def _report(rows: list[dict]):
    return transform_brand_rows(rows, tenant_id=TENANT)


def test_clean_platform_row_loads() -> None:
    report = _report([{
        "id": "row-1", "scope_type": "platform", "scope_id": None,
        "brand_name": "Dotmac", "primary_color": "#112233",
        "secondary_color": "#445566", "support_email": "help@example.io",
        "is_active": True,
    }])
    assert report.reconciled
    assert len(report.loadable) == 1 and report.rejects == ()
    item = report.loadable[0]
    assert item.profile_code == "dotmac" and item.activate is True
    assert item.fields["primary_hex"] == "#112233"
    assert item.fields["accent_hex"] == "#445566"


def test_semantic_tones_and_urls_are_named_field_rejects() -> None:
    report = _report([{
        "id": "row-2", "scope_type": "reseller", "scope_id": RESELLER,
        "brand_name": "Reseller One", "primary_color": "#aabbcc",
        "logo_url": "https://cdn.example/logo.png", "tagline": "Fast!",
        "metadata": {"semantic_colors": {"positive": "#00aa00"}, "misc": 1},
    }])
    assert len(report.loadable) == 1  # row loads; values do not
    by_field = {r.field: r.disposition for r in report.rejects}
    assert by_field["logo_url"] == "url_not_a_file_ref"
    assert by_field["tagline"] == "no_tenant_plane_home"
    assert by_field["semantic_positive_color"] == "owned_by_published_token"
    assert by_field["metadata.misc"] == "unsupported_metadata_key"


def test_managed_branding_asset_paths_become_file_ids() -> None:
    file_id = "d513eafd-4b93-4be9-a749-15b93ecfe1b3"
    report = _report([
        {
            "id": "managed", "scope_type": "platform", "scope_id": None,
            "brand_name": "Managed", "logo_url": f"/branding/assets/{file_id}",
            "dark_logo_url": file_id,
            "favicon_url": "/branding/assets/not-a-uuid",
        },
        {
            "id": "static", "scope_type": "platform", "scope_id": None,
            "brand_name": "Static", "logo_url": "/static/logo.png",
        },
    ])
    managed = report.loadable[0]
    assert managed.fields["logo_file_ref"] == file_id
    assert managed.fields["dark_logo_file_ref"] == file_id
    by_source_field = {
        (r.source_id, r.field): r.disposition for r in report.rejects
    }
    assert by_source_field[("managed", "favicon_url")] == "url_not_a_file_ref"
    assert by_source_field[("static", "logo_url")] == "url_not_a_file_ref"


def test_invalid_hex_and_accent_only_rows_reject() -> None:
    report = _report([
        {"id": "bad-hex", "scope_type": "platform", "scope_id": None,
         "brand_name": "Bad", "primary_color": "not-a-color"},
        {"id": "accent-only", "scope_type": "platform", "scope_id": None,
         "brand_name": "Accent", "secondary_color": "#445566"},
    ])
    assert report.loadable == () and report.row_rejected == 2
    assert {r.disposition for r in report.rejects} == {"invalid_brand_values"}


def test_scope_and_duplicate_and_unknown_are_named() -> None:
    report = _report([
        {"id": "ok", "scope_type": "platform", "scope_id": None,
         "brand_name": "Same Name", "surprise_field": "x"},
        {"id": "dup", "scope_type": "reseller", "scope_id": RESELLER,
         "brand_name": "Same Name"},
        {"id": "bad-scope", "scope_type": "organization", "scope_id": None,
         "brand_name": "No Scope"},
    ])
    assert report.reconciled and report.extracted == 3
    assert len(report.loadable) == 1 and report.row_rejected == 2
    dispositions = {(r.source_id, r.disposition) for r in report.rejects}
    assert ("ok", "unknown_legacy_field") in dispositions
    assert ("dup", "duplicate_profile_code") in dispositions
    assert ("bad-scope", "invalid_scope") in dispositions
    totals = report.to_dict()["totals"]
    assert totals == {
        "extracted": 3, "loadable": 1, "row_rejected": 2,
        "field_rejects": 3, "reconciled": True,
    }
