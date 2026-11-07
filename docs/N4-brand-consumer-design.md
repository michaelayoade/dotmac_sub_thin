# N4 brand flip — field dispositions and first-consumer design

Status: DRAFT for Michael/architect decisions (2026-11-06). Companion to
`docs/N3-brand-profiles.md`. Completion authority is already endorsed:
target-side planner (`complete_platform_brand`), rehearsed at 14/14
mapped-field parity. No legacy production write.

## Remaining unresolved fields — proposed dispositions

| Field(s) | Module position | Proposed disposition |
|---|---|---|
| 5 semantic colors (`semantic_*_color`) | `translate_legacy_brand_values` returns them unsupported: `owned_by_published_token` — semantic tones belong to the published UI token set, not per-tenant brand rows | ACCEPT token ownership. Per-tenant semantic overrides are dropped by design, not lost by accident. If a future surface proves a tenant needs its own tones, that is an upstream module feature request with its own release, not a cutover patch. Ledger keeps naming them so the acceptance stays visible. |
| `tagline` (present in production resolved brand, 30 chars) | No field in `dotmac-brand-profiles` on either plane (`DISPLAY_FIELDS` has no tagline) | DO NOT drop silently: it is customer-visible copy. Recommended: upstream feature request to add `tagline` to the module display fields + migration, released as a new module version, then map it like any other field. Interim: legacy remains the source for this one string; the completion report keeps it named `no_tenant_plane_home`. Rejected: a product-owned side table in this repo — it splits brand ownership across two stores for one string. |
| `portal_domain` | No tenant-plane home, but the module has `PlatformBrandHostBinding` + `resolve_by_host` on the platform plane | Map at flip time to a platform host binding for the tenant profile. Requires mounting the platform plane (or a platform-plane load step), which the current assembly deliberately does not do yet. Decide with the first-consumer choice below. |

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
   first consumes brand from this app from its first day. Recommended
   first: portal theming (read-only, visual, trivially rolled back by
   repointing one read). Email sender identity is last (send-path,
   deliverability risk).
3. **Legacy read retirement.** Only when every named consumer reads
   here does legacy `brand_profiles` become read-retired; the write
   side retires with the legacy branding admin surface in its own
   wave. Until then legacy stays the writer and this app re-loads on
   change (extract → transform → load is idempotent and rehearsed).

## Decisions owed

1. Tagline: approve upstream field addition (Starter module change +
   release), or accept legacy-carried interim indefinitely.
2. Portal domain: mount platform plane for host binding at flip, yes/no.
3. First consuming wave: confirm portal theming, or name another.

None of these block Track 1 (Foundation publication) or the governed
deploy; they block only calling brand "flipped".
