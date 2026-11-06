# Thin-shell deployment packet — draft, not deployable yet

`deploy/product.toml` is the composed Sub shell's `ProductDeploymentSpec.v1`
candidate for the designated N2 host `81.0.221.52` (`vmi3698737`). Nothing
consumes it today. `deploy/product-manifest.json` is generated from the
runtime assembly by `scripts/product_manifest.py` (kernel canonical bytes);
regenerate it, never hand-edit it.

## Verified locally (2026-11-06)

- `dotmac-deploy validate`: PASS (Foundation 0.4.0a1 source install).
- Product manifest: `scripts/product_manifest.py check` PASS,
  digest `sha256:d4c28478…a87693a`.
- Render: succeeds only with borrowed Starter alert thresholds
  (`/tmp/thin-render-proof`, proof-only). The renderer requires product
  threshold values even with telemetry off; Sub thresholds are a real
  product decision, so no rendered assets are committed yet.

## Blockers that stop this descriptor being deployable

1. **Image bound as a deployment artifact.** The repo descriptor
   keeps the zero sentinel by convention; CI binds digest+revision
   into an artifact copy (latest: `sha256:851a49f5…` at `de0f7e0`,
   run 42245657543). The GHCR package is currently PUBLIC by owner
   decision — that publishes the bundled Starter sources; revisit
   before any non-candidate use (security review H1).
2. **Migration bootstrap not product-owned.** `sub_thin.migrate` now
   composes the kernel + brand lineages and rehearsed to both heads on a
   disposable Postgres. Before first deploy, the operator must make the
   migration owner own the public schema and pre-create the kernel role
   family—including `outbox_dispatcher` and
   `platform_outbox_dispatcher`—or grant the owner CREATEROLE.
3. **No backup dataset.** The empty shell holds no durable state, so none
   is declared — true only until the first data wave, which must declare a
   dataset with encryption + restore proof before it may hold state.
4. **Alert thresholds provisional.** `deploy/alerts/thresholds.json`
   carries the Starter reference values so the renderer can run while
   telemetry stays off. They are NOT Sub product decisions; review them
   before telemetry is ever enabled. Rendered assets are generated from
   the bound descriptor, never committed from the sentinel.
5. **Host and path gates open.** Live host re-verification, WHMCS-stack
   disposition, OpenBao/fleet-registry gaps, architect security review, and
   the D1/Gate 0 Control deploy path (debt register N2/D1/D7).

## Health paths

Live is `/health`, ready is `/health/ready` — deliberately not
`/health/live`: kernel tenant middleware bypasses only `/health` and
`/health/ready`, so `/health/live` would attempt tenant resolution and
fail without a database. Readiness is dependency-free only while no
data-bearing module is mounted.
