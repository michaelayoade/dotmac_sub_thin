# N2 deploy + N4 brand flip runbook (draft, gate-controlled)

Status: planning/rehearsal only. This runbook authorizes nothing.
Production writes, host mutation, and deployment each keep their own
approval gate below.

## Current evidence

- N1 done; N3 brand table totals done (register v1059 baseline).
- Shell boots; database posture proven on disposable live Postgres.
- `sub_thin.migrate` rehearsed to kernel `0030_credential_tenant_key`
  and brand `bp_0001_brand_profiles`.
- Real production brand extract: 1 row -> 1 loadable, reconciled.
- Target-side completion rehearsed to full mapped-field parity in a
  disposable composed DB (caller rollback + idempotent rerun passed).
- Designated host `81.0.221.52` is currently **unreachable** from this
  workstation and from four fleet jump hosts; its node exporter also
  refuses from `dotmac-observe` (checked 2026-11-06). Treat power or
  network recovery as Gate 2.0.

## Gate 0 — decisions before any mutation

1. Architect security review of: thin assembly, database role family,
   descriptor exposure (loopback only), migration owner separation,
   completion authority (see Gate 4), and host recovery findings.
2. Michael approval for each of: provider/host recovery actions, the
   platform-profile completion route, any legacy write, image push from
   protected source, and any `dotmac-deploy ... --execute` step.
3. Freeze record: name the change window and the legacy brand/settings
   writers paused during Gate 4. Billing freeze rules remain in force.

## Gate 1 — bind the image (no deploy)

1. Put this source under version control on a protected main. The shell
   source is not yet a repository; do not invent a source revision.
2. Configure `UV_INDEX_FORGEJO_USERNAME` / `UV_INDEX_FORGEJO_PASSWORD`
   as CI secrets. Run the manual `image` workflow
   (`.github/workflows/image.yml`): tests -> buildx push to GHCR ->
   `binding/` artifact containing a bound descriptor copy.
3. Review the artifact diff: only `[image] reference`,
   `source_revision`, and the provenance comment may change. The binder
   (`scripts/bind_image.py`) refuses sentinel digest/revision and any
   repository change.
4. Supply real Sub alert thresholds, then render and audit:
   `dotmac-deploy validate`, `dotmac-deploy render --check`,
   `dotmac-deploy image-audit` against the pushed digest.
5. Record workflow run, digest, revision, and audit output in the
   register detail record. Still no host contact.

## Gate 2 — recover and verify the host (read-only first)

1. Restore power/network through the provider if required (separate
   approval). Confirm `hostname` is `vmi3698737` before trusting it.
2. Read-only sweep: OS/kernel, CPU/RAM/disk, failed units, `ss -lnt`,
   ufw rules, docker state (expected inactive), `/opt`, and the inert
   nginx/PHP-FPM/MariaDB WHMCS stack inventory.
3. Decide WHMCS-stack disposition (remove vs inert) in the security
   review. The shell needs Docker; activating it is a host mutation
   under Gate 3 approval, not part of verification.
4. Close onboarding debts that deploy depends on: fleet registry
   declaration, root password into OpenBao, backup target + restore
   proof, Prometheus scrape. RAM stays 11 GB for the empty shell.

## Gate 3 — N2 candidate deploy (no product traffic)

1. Operator database bootstrap (cluster operator, before migrations):
   migration owner owns `public`; roles `app_admin` (BYPASSRLS,
   non-super), `app_user`, `platform_api`, `outbox_dispatcher`,
   `platform_outbox_dispatcher` (all NOBYPASSRLS, non-super) exist, or
   the migration owner holds CREATEROLE. Kernel migrations 0011/0012
   cannot create dispatcher roles as plain `app_admin`.
2. Deliver secrets out-of-band: runtime `DATABASE_URL` (app_user) and
   owner `MIGRATION_DATABASE_URL` (app_admin) stay distinct materials.
   No DSN value enters Git, the register, or this runbook.
3. Dry-run in order and record each output:
   `dotmac-deploy validate` -> `render --check` -> `preflight` ->
   `plan` -> `deploy` (dry run). Review the plan against the bound
   digest and both expected heads.

   **Facility-version fork (found 2026-11-06, decision required).**
   The descriptor targets unreleased Foundation 0.4.0a1. The latest
   released facility (0.2.0a2) refuses it; the full delta is:
   ports `exposure`/`address_family` (0.2 uses `bind`), backup
   `lineage` + `expected_backup_interval_seconds`, and the four
   privilege verifications. A scratch downgrade validates + dry-runs
   clean under 0.2.0a2 but deletes exactly those controls. Options:
   (A) wait for the 0.4 release, (B) downgrade the descriptor with
   recorded acceptances, (C) run unreleased 0.4 from source. No execute
   until Michael/architect picks one. The repo descriptor stays 0.4.
4. Only with Gate 0 approval: execute deploy. Verify loopback health
   (`/health`, `/health/ready` on 127.0.0.1:18011), migration heads via
   the migrate role, and runtime posture (startup check clean as
   app_user). No ingress is declared; public reachability is a defect.
5. Rollback: Foundation retains 2 rollback images; with no traffic and
   no durable brand state loaded yet, rollback = previous image or
   stop the candidate. Record the rehearsal result before N2 closes.

## Gate 4 — N4 brand flip rehearsal, then flip

Authority choice comes first (writer-boundary record): either
**(A)** complete the platform profile in legacy through the existing
reviewed sync surface, or **(B)** approve the target-side completion
planner rehearsed here (`complete_platform_brand`) as the completion
authority. Do not run both. Option A is a legacy write; option B writes
only the composed target. Neither has run against production state.

1. Freeze legacy brand/settings writers for the window.
2. Fresh read-only evidence, same snapshot discipline as N3:
   - `scripts/extract_brand_profiles.py` (read-only transaction),
   - `scripts/fetch_resolved_brand.py` (read-only snapshot session),
   - record SHA-256 of both files; rerun
     `scripts/brand_cutover.py ... --complete-from-resolved ...`.
3. Review provenance field-by-field. Expected unresolved today:
   five semantic colors (`owned_by_published_token`) and `tagline`
   (`no_tenant_plane_home`). Each needs a named accepted disposition
   before flip; semantic colors belong to published UI tokens.
4. Runtime wiring status: brand module is mounted (TENANT plane),
   `require_database_runtime` engages whenever a DSN is declared, and
   `/health/ready` probes the bound engine (503 when unreachable,
   rehearsed both ways). Still owed before a user-visible flip:
   consumer/read integration — the module has no routers, and no
   surface reads brand through this app yet.
5. Load with `scripts/load_brand_cutover.py` (dry-run default;
   `--execute` verifies role posture before any write, then applies
   inside one tenant-scoped transaction). Verify: row count,
   command-id idempotent rerun, tenant isolation.
6. Shadow parity: Starter `resolve_for_tenant` vs legacy
   `resolve_brand` on every mapped field. Zero mismatch and zero
   starter-missing is the flip bar; rehearsal reached it only with
   completion applied.
7. Rollback rehearsal before flip: caller-transaction rollback leaves
   the prior resolved brand unchanged (proven). Post-commit rollback =
   serve legacy resolution again; restore composed fields from the
   recorded pre-completion snapshot under a fresh command ID.
8. Flip only inside the approved window. Exit evidence: extract and
   snapshot digests, totals, load IDs, parity table (field names),
   rollback rehearsal result, and register write with expected_version.

## Stop conditions

Stop and record, do not improvise, if: host identity differs, any role
posture check fails, heads differ from the descriptor, parity shows an
unexplained field, the freeze is broken mid-window, or a credential
would need to be copied between projects to proceed.
