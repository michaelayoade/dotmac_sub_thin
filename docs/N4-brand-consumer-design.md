# N4 brand flip — field dispositions and first-consumer design

Status: DESIGN APPROVED by Michael (2026-11-08); implementation pending. Companion to
`docs/N3-brand-profiles.md`. Completion authority is already endorsed:
target-side planner (`complete_platform_brand`), rehearsed at 14/14
mapped-field parity. No legacy production write.

## Approved field dispositions

| Field(s) | Module position | Approved disposition |
|---|---|---|
| 5 semantic colors (`semantic_*_color`) | `translate_legacy_brand_values` returns them unsupported: `owned_by_published_token` — semantic tones belong to the published UI token set, not per-tenant brand rows | Approved: token ownership. Per-tenant semantic overrides are dropped by design, not lost by accident. If a future surface proves a tenant needs its own tones, that is an upstream module feature request with its own release, not a cutover patch. Ledger keeps naming them so the acceptance stays visible. |
| `tagline` (present in production resolved brand, 30 chars) | No field in `dotmac-brand-profiles` on either plane (`DISPLAY_FIELDS` has no tagline) | DO NOT drop silently: it is customer-visible copy. Approved: upstream feature request to add `tagline` to the module display fields + migration, released as a new module version, then map it like any other field. Interim: legacy remains the source for this one string; the completion report keeps it named `no_tenant_plane_home`. Rejected: a product-owned side table in this repo — it splits brand ownership across two stores for one string. |
| `portal_domain` | No tenant-plane home, but the module has `PlatformBrandHostBinding` + `resolve_by_host` on the platform plane | Map at flip time to a platform host binding for the tenant profile. Requires mounting the platform plane (or a platform-plane load step), which the current assembly deliberately does not do yet. Mount the platform plane for this binding at flip; implementation and the flip remain gated. |

## First consumer — what "flip" means

Loading and parity-proving the module is not a flip. No surface reads
brand through this app today, and the module ships service functions
(`resolve_for_tenant`, `resolve_by_host`), no routers.

Proposed sequence:

1. **Internal resolve surface (this repo, next build).** A product-owned,
   read-only feature exposing the resolved brand for the single tenant,
   loopback/internal only, calling `resolve_for_tenant`. Purpose is
   evidence, not traffic: a live parity probe comparing thin-resolved
   vs legacy `resolve_brand` over the same production extract, on a
   schedule, until they agree field-for-field (modulo accepted
   dispositions above).
2. **First flipped surface = the first surface that itself moves.**
   Brand has no standalone user surface; it is read by statements,
   email identity, and portal theming, all still legacy-owned. The
   honest flip order is therefore: whichever of those waves moves
   first consumes brand from this app from its first day. Approved
   first: portal theming (read-only, visual, trivially rolled back by
   repointing one read). Email sender identity is last (send-path,
   deliverability risk).
3. **Legacy read retirement.** Only when every named consumer reads
   here does legacy `brand_profiles` become read-retired; the write
   side retires with the legacy branding admin surface in its own
   wave. Until then legacy stays the writer and this app re-loads on
   change (extract → transform → load is idempotent and rehearsed).

## Decision record — 2026-11-08

Michael approved the proposed design:

1. The published UI token set owns all five semantic colors. The completion
   ledger must keep naming excluded tenant overrides so the accepted
   disposition stays visible.
2. Add `tagline` upstream to the module before the brand flip. Legacy carries
   the string only until the upstream field and consuming wave are ready;
   accepting a permanent legacy dependency was not the selected disposition.
3. Mount the platform plane for the `portal_domain` host binding at flip.
4. Portal theming is the first consuming wave.

This is design approval only. The upstream field, module release and consumer
integration remain to be implemented. Foundation/module release, governed
deployment and the brand flip retain their separate gates. No legacy write
or traffic flip is authorized by this decision.

These remaining brand implementation steps do not block Track 1
(Foundation publication) or the governed deploy.
