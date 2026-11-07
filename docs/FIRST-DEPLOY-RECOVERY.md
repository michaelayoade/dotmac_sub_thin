# First governed deploy — recovery procedure (PROPOSAL)

Status: DRAFT for Michael acceptance (2026-11-07). Grants no authority.
Required by `docs/DEPLOYMENT-READINESS.md` gate "First-deploy recovery":
no governed predecessor image is recorded, and Foundation rollback is
refused until an execute records one. Image retention alone is not
rollback support.

## Why an explicit procedure, not a predecessor baseline

A supported predecessor baseline would mean recording the current
manual candidate as a governed previous image. It was never deployed
through Foundation/Control, carries no execution receipts, and its
provenance chain starts at a `docker run`. Dressing it as a governed
predecessor would fabricate exactly the evidence the rollback refusal
exists to demand. The honest shape for deploy #1 is an explicit,
rehearsed recovery procedure whose endpoint is "candidate stopped,
database restored to the pre-execute backup" — not "previous release
resumed", because there is no previous release.

## Database compatibility facts (verified 2026-11-07)

- Current heads: `0030_credential_tenant_key` (kernel),
  `bp_0001_brand_profiles` (brand). The governed first deploy runs the
  same migration set against the same database; no new migration is
  introduced by the deploy itself.
- Restoring an older image therefore does not need migration reversal
  for deploy #1: schema after execute == schema before execute.
- This equivalence is a deploy-#1 fact only. Any future wave that adds
  a migration must re-derive compatibility before relying on
  image-only rollback; this document must be revised in that wave's PR.

## Procedure (execute window, in order)

1. **Fresh backup, immediately before execute.** Capture with the
   descriptor's primary dataset path (Foundation provider shape).
   Record: checksum, location, retention (14d), schema version,
   both migration heads, brand row count, capture duration. Abort the
   window if capture or checksum verification fails.
2. **Expectations snapshot.** From the live candidate DB, record the
   same five observations the rehearsal checks (heads, public table
   count, brand rows + tenant, `app_user` role flags, tenant-isolation
   counts 0-without/1-with context). Attach to the window packet.
3. **Governed execute.** Only with Track 1 publication + CP readiness
   evidenced (separate gates). Verify heads, `/health`, `/health/ready`
   database mode, and recorded evidence before declaring success.
4. **Recovery trigger.** Any of: readiness not database-mode within
   the window, heads mismatch, posture refusal misfiring on valid
   materials, or operator abort.
5. **Recovery actions.** Stop the governed candidate. Restore the
   step-1 backup into the candidate database (rehearsed path:
   `/root/subthin/ops/rehearsal.sh` mechanics, provider-default
   capture/restore identities). Re-run the step-2 observations; they
   must equal the pre-execute snapshot. Restart the pre-existing
   manual candidate image (`sha256:9d1e26b9…` or its recorded
   successor) with the existing runtime materials. Verify readiness.
6. **Record.** Window outcome, backup checksum actually restored,
   measured recovery time, and register write with
   `expected_version`. A recovered deploy #1 leaves the system exactly
   where it was before the window: manual candidate, no governed
   predecessor recorded. The next attempt is a new window, not a retry.

## Rehearsal status

PROVEN end-to-end 2026-11-07 (swing rehearsal, real candidate never
stopped): fresh capture (sha256 `0478f828…`, 9374 bytes) → scratch
restore (1s, 0 errors, heads `0030_credential_tenant_key` +
`bp_0001_brand_profiles`, brand rows 1) → production preflight in the
exact image against the swing environment (pass) → prior-image
container on the restored database ready in database mode (boot 3s;
total swing 7s) → teardown complete, candidate untouched. Script:
`/root/subthin/ops/swing.sh` on the host. Earlier partial proof also
stands (capture `09b260f4…`, isolation 0-without/1-with context).
Timing is at one-brand-row volume — a floor, not a prediction;
re-measure at each data wave.

## Acceptance

Michael accepts or amends this procedure in the debt register.
Acceptance covers deploy #1 only. The "unencrypted because
rebuildable" backup disposition is revisited when production secrets
or non-rebuildable data first arrive (per descriptor review note).
