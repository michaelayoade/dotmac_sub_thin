# Thin-shell deployment packet — governed execution held

`deploy/product.toml` describes the composed Sub candidate for
`81.0.221.52` (`vmi3698737`). CI binds its image and source revision into
an artifact copy. The repository retains zero sentinels intentionally;
never deploy that copy or invent bindings.

The [readiness checklist](../docs/DEPLOYMENT-READINESS.md) records current
holds, accountable ownership, production preflight, backup requirements
and first-deploy recovery acceptance. The [runbook](../docs/N2-N4-RUNBOOK.md)
contains the deployment and brand-flip sequence.

## Candidate evidence and remaining gates

- The executing session reports the manual candidate healthy in database
  mode, the M2 secret gate verified, and candidate restore rehearsal passed.
  This is not a Foundation/Control execute. Refer to the checklist for the
  source/image and recovery evidence; use full digests in executable packets.
- Migration bootstrap and both expected heads were rehearsed. Reverify the
  role family and migration owner separation before governed execution.
- Primary backup dataset is declared with lineage, checksum, retention and
  verification requirements. Privileged capture and reader verification
  are distinct. A fresh pre-execute backup and accepted first-deploy recovery
  procedure remain required; no governed predecessor image is recorded.
- `python -m sub_thin.preflight` checks final production configuration
  offline. It needs PLATFORM_DATABASE_URL and PLATFORM_ROOT_DOMAIN in
  addition to the existing runtime materials. It does not prove live health.
- `deploy/alerts/thresholds.json` contains provisional Starter reference
  values. Rendering may use them with telemetry off; enabling telemetry
  requires Michael's product approval bound to the threshold-file digest.
- Foundation publication, CP readiness and execution approval remain held.
  Package visibility H1 was accepted by Michael; source remains private,
  the GHCR image public. Target-side completion authority is endorsed;
  brand consumer integration and the flip window remain separate gates.

## Local validation (2026-11-07)

57 tests passed. Product manifest unchanged at
`sha256:d4c28478a765783faf1cf11dfad44fcd94046b5c7b696f14ebff10a5aa87693a`.
Descriptor validates with local Foundation source. The existing virtualenv
uses editable kernel source, so these are not released-wheel/image proofs.
No image was built and no host was changed by this implementation.

## Health paths

Live is `/health`, ready is `/health/ready`. Kernel tenant middleware
bypasses these paths; `/health/live` is not an equivalent probe. Final
readiness must report database mode and runtime posture must pass.
