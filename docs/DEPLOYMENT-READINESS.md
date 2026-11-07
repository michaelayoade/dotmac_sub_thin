# Governed deployment readiness

Status: HOLD (2026-11-07). This checklist records evidence; it grants no
release, deployment, brand-flip, or telemetry authority.

## Verified candidate evidence

Track 2 evidence reported by the executing session: M2 gate at f74e33c,
image `sha256:160b1214…`, CI run 42341969377, database readiness green,
and a host negative test refusing missing runtime materials. Recovery
rehearsal: 9382-byte capture, checksum prefix `09b260f4`, capture/restore
1s each, both heads, one brand row, runtime flags false, isolation 0/1.
These abbreviated digests are references, never executable bindings.
Full receipts and full digests must be attached to the approved packet.

Corrections: backup_reader was created during that rehearsal, not earlier.
Foundation captures as the database-service postgres identity; the
NOBYPASSRLS reader verifies the restored database. Privileged capture
material must never enter the app process. Rehearsal success does not
constitute a governed execute or a fresh pre-deployment backup.

## Release and execution are separate gates

| Gate | Required evidence | Current disposition |
|---|---|---|
| Publication ruling | Captain/architect ruling and guarantee map; repo amendment | Pending; allocation held |
| Foundation certifications | Rule 49 per-gap answer, Q1, CP Q2 | Pending |
| CP execution readiness | Installed admission provider, approval subject, adopted D/E replacements, executor behavior proofs | Pending; execute held |
| Production configuration | Offline preflight in exact image with final runtime materials, then live posture/heads/readiness | Offline command implemented; final packet proof pending |
| First-deploy recovery | Supported predecessor baseline OR explicitly accepted first-deploy recovery procedure, database compatibility, rehearsal | Pending; no previous governed image recorded |
| Telemetry | Product threshold approval bound to threshold-file SHA-256 | Pending; all telemetry switches remain off |
| Brand flip | N4 dispositions, consumer integration/parity, named window | Pending; target-side completion authority already endorsed |

## Certification accountability

Authoritative request: Knowledge `dotmac-foundation-gate2-040a2-20261106`
v3 plus the sole-owner clarification recorded on 2026-11-07. A peer-session
pointer alone does not acknowledge custody or constitute certification.

| Request | Accountable role | Named person | Ownership / certification | Due |
|---|---|---|---|---|
| Gate ruling | Starter release captain + architect | Michael | Assigned by Michael; certification pending | 2026-11-13 |
| Rule 49 + Q1 | Starter release captain | Michael | Assigned by Michael; certification pending | 2026-11-18 |
| Q2 + CP execution readiness | Platform CP owner | Michael | Assigned by Michael; certification pending | 2026-11-18 |
| Gate-0 D retirement/replacement | Michael | Michael | Ruling pending | With gate ruling |

Michael is the sole developer and approver, by explicit instruction on
2026-11-07. He holds the release-captain, architect and Platform CP roles;
no additional human approver is required. Agent review supplies evidence,
not a ruling or approval. Assignment is acknowledged by that instruction;
each technical certification and operational approval remains pending.
Escalation/reminder date to Michael is 2026-11-20. These are recorded dates, not scheduled
notifications. No messages are sent by this checklist.

## Final production preflight

The candidate's independent secret gate is not full production-mode proof.
Run `python -m sub_thin.preflight` inside the exact digest-bound image,
with only final runtime materials delivered by the governed path. Require
explicit ENVIRONMENT=production (prod also accepted by the kernel),
DATABASE_URL, PLATFORM_DATABASE_URL, PLATFORM_ROOT_DOMAIN, all three
secrets, TRUSTED_HOSTS and SEED_ON_STARTUP=false. Include loopback probe
hosts in TRUSTED_HOSTS as well as the final domain. The platform DSN is
an explicit runtime binding, never the migration owner DSN.

The command reuses kernel settings validation, ignores dotenv for its
settings instance, validates lazy database bindings, and emits no values.
It opens no database connection and starts no application. It does not
prove domain routing, host binding, role posture, migration heads, tenant
count, health, or admission. Follow with Foundation validate/render/
preflight/plan, live startup checks and `/health/ready` mode=database.
Do not copy secrets into command arguments or evidence output.

## Recovery acceptance before first execute

The current manual candidate is not a recorded governed predecessor;
retaining two images does not establish rollback support. The owner must
choose and evidence a supported predecessor baseline or accept a distinct
first-deploy recovery procedure. Record full previous image digest,
command/config bindings through secret pointers, port/volume ownership,
stop/start ordering, migration compatibility, expected health, operator
and elapsed recovery time. Rehearse the approved procedure before execute.
An image rollback is insufficient if database changes are incompatible.

Immediately before execution, take a fresh backup and bind its receipt to
lineage, source identity, checksum, capture time, both migration heads,
schema/brand expectations and runtime privilege expectations captured at
the same point in time. Record storage location, retention, recovery
proof and measured times. Repeat restore verification against those
expectations; never compare to a later schema snapshot. Review the current
unencrypted/rebuildable-data disposition whenever data sensitivity or
rebuildability changes. Keep privileged capture separate from read-only
verification. Retain the newest proved recovery point.

## Telemetry decision

`deploy/alerts/thresholds.json` remains provisional Starter reference
values. Product approval must name the approving person, decision date,
file SHA-256, applicable signals and accepted values. Record unavailable
signals explicitly. Until then all telemetry switches stay false; offline
render success is not monitoring coverage. Re-review approval if the file
or enabled signals change.

## Local implementation validation (2026-11-07)

- Full suite: 57 passed (one existing Starlette/httpx deprecation warning).
- Product manifest check: unchanged
  `sha256:d4c28478a765783faf1cf11dfad44fcd94046b5c7b696f14ebff10a5aa87693a`.
- Descriptor validates with local Foundation source; this is not a
  released-wheel or final bound-packet proof.
- Independent agent review found no actionable defects and verified fake
  production bindings do not connect or import the application/assembly.
- The existing virtualenv imports the kernel from editable sibling source;
  the released-image proof remains pending. Changes are local and unbuilt.
