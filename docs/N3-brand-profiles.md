# N3 first module: brand profiles (selected 2026-11-06)

## Decision

First transform + reconciliation target is **brand profiles**:
legacy `brand_profiles` (`app/models/branding.py`) ->
Starter `dotmac-brand-profiles==0.1.0a1` (`mod_brand`, TENANT plane).

## Evidence

- Released: 0.1.0a1 published, installed back from Forgejo, tagged from
  exact main `ed69f9d` (module CHANGELOG, release run 32339834679).
- Extracted from Sub itself (ADR-0057 §2; manifest: "extracted from
  Sub's 897-LOC production BrandProfile"). Sub selects TENANT plane via
  explicit `ModulePlaneSelection` (ADR-0028).
- The module ships `translate_legacy_brand_values()`: maps a legacy
  record onto the allowlist and REPORTS every unsupported value with a
  typed `Disposition` — the reject-ledger seed N3 requires, already built.
- Reference-shaped data: small row count, read-mostly, no money writer,
  no network writer. Writers are admin branding settings only.
- Prerequisites force the right first infra step: kernel lineage +
  `bp_0001`, `MODULE_DATABASE_ROLES_V1`, `IDEMPOTENCY_LEDGER_V1`,
  `TENANT_SCOPE_CATALOG_V1` — i.e. the explicit NOBYPASSRLS
  `database_runtime` binding the shell currently lacks.

## Field mapping (legacy -> Starter)

| Legacy | Starter | Note |
|---|---|---|
| brand_name | display_name (+ profile_code) | profile_code derivation = transform rule; null name = reject |
| product_name, legal_name | same | direct |
| primary_color / secondary_color | primary_hex / accent_hex | validated by dotmac-ui parser; invalid hex = reject |
| logo_url / dark_logo_url / favicon_url | logo_file_ref / dark_logo_file_ref / icon_file_ref | URL->file-ref is NOT 1:1; external/data URLs become named rejects until files wave (S9) |
| support_email/phone, from_email/from_name | support_email/phone, sender_email/sender_name | direct |
| app_url / portal_domain | support_url / host binding | portal_domain has no tenant-plane home; disposition required |
| legal_address, metadata | legal_address, (none) | unsupported metadata keys reported, never dropped silently |
| is_active | status | enum mapping |
| scope_type/scope_id | scope_type/scope_id + tenant_id | tenant identity comes from extraction context, never from row data |

## Rejected alternatives for first flip

- Service catalog / plan families: coupled to billing governance and
  subscription reads; money-adjacent pricing. Later wave.
- Numbering: storage already composed, but activation touches invoice
  issuance (money path, frozen). Money wave, with ERP's immutable-series
  precedent.
- Anything network/billing: explicitly later per register sequencing.

## Harness built (2026-11-06)

`sub_thin.cutover.brand_profiles.transform_brand_rows` + CLI
`scripts/brand_cutover.py` (extract JSON in, report JSON out; exit 0 iff
reconciled). Proven on synthetic legacy-shaped fixtures: totals matched,
rejects named (URL file-refs, semantic tones, tagline/portal_domain,
metadata keys, bad hex, accent-without-primary, duplicate codes, bad
scopes). Managed legacy logo paths (`/branding/assets/{uuid}`) become
bare UUID file refs; `/static/...` and external URLs reject. Database
binding landed in `sub_thin.database`.

Disposable composed-Postgres rehearsal completed: `sub_thin.migrate`
upgraded the kernel and brand lineages to `0030_credential_tenant_key`
+ `bp_0001_brand_profiles`; fixture load, parity, idempotent rerun,
tenant isolation and caller rollback passed.

Real production extract completed read-only: 1 platform row extracted,
1 loadable, 0 rejects, reconciled; private packet
`.cutover-private/sub-cutover-n1-20261106/brand_{extract,report}_prod_20261106.json`.
The same row loaded idempotently into the disposable composed DB.
Shadow parity: 7 fields match, `display_name` differs, and 6 fields are
supplied only by legacy static/company/comms fallbacks. Those gaps block
the N4 flip until the separately authorized platform-profile completion;
they do not alter the brand-table totals above.

## N3 closure shape for this module

Extract (read-only legacy snapshot) -> translate with dispositions ->
load into `mod_brand` on the shell -> totals: extracted = loaded +
rejected, every reject named with its typed disposition -> shadow read
parity on resolved brand values -> exceptions queue holds the rejects
for manual disposition. No legacy writes anywhere in the harness.
