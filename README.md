# dotmac-sub-thin — composed Sub shell (cutover N2)

New thin assembly for Sub: Starter kernel app factory + released modules +
Sub-unique domain code + config. Legacy `dotmac_sub` is never adapted into
this shape (replace-not-adapt); it retires wave by wave as modules flip.

Current state: EMPTY SHELL. No product modules and no product traffic; the
only mounted feature is the assembly-owned `/health/ready` route beside the
kernel's DB-free `/health` liveness route.

## Run (released wheels)

Requires Forgejo index credentials in the operator environment
(`UV_INDEX_FORGEJO_USERNAME` / `UV_INDEX_FORGEJO_PASSWORD`).

```sh
uv sync --extra test
uv run pytest
uv run python -m sub_thin.runtime --port 8011
```

## Proof without registry credentials (source-identical a107)

See `PROOF-2026-11-06.md`. Path sources are proof-only; the committed
`pyproject.toml` keeps released pins.

## Next gates

- Host designated 2026-11-06 (`81.0.221.52`) but currently unreachable
  from every fleet route tried; recovery + re-verification are Gate 2
  in `docs/N2-N4-RUNBOOK.md`. Deploy still waits on security review
  and D1/Gate 0.
- Deploy packet: `Dockerfile` + `deploy/product.toml` (validated; see
  `deploy/README.md` for the blockers that keep it non-deployable).
- First data wave sets explicit `database_runtime` (NOBYPASSRLS) and
  `require_database_runtime=True` in `src/sub_thin/assembly.py`.
- N3: transform + reconciliation harness on one reference/catalog module.
