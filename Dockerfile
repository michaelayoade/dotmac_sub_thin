# syntax=docker/dockerfile:1
#
# Released wheels only. The private Forgejo index credentials arrive as
# BuildKit secrets and never enter an image layer or build argument:
#
#   docker buildx build \
#     --secret id=forgejo_username,env=UV_INDEX_FORGEJO_USERNAME \
#     --secret id=forgejo_password,env=UV_INDEX_FORGEJO_PASSWORD .
#
# Per fleet policy, build this on the dedicated test/CI host, not a
# workstation Docker daemon.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY scripts ./scripts

RUN --mount=type=secret,id=forgejo_username \
    --mount=type=secret,id=forgejo_password \
    UV_INDEX_FORGEJO_USERNAME="$(cat /run/secrets/forgejo_username)" \
    UV_INDEX_FORGEJO_PASSWORD="$(cat /run/secrets/forgejo_password)" \
    uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/app/.venv/bin:$PATH

WORKDIR /app

RUN groupadd --gid 10001 app && useradd --uid 10001 --gid 10001 --no-create-home app

COPY --from=builder --chown=10001:10001 /app/.venv ./.venv
COPY --from=builder --chown=10001:10001 /app/src ./src
# Operator CLIs ship in the image so ops runs are digest-bound, never
# whatever happens to sit in a host mount.
COPY --from=builder --chown=10001:10001 /app/scripts ./scripts

USER 10001:10001
EXPOSE 8000

# The descriptor names this launcher and port; the bind address is owned by
# sub_thin.runtime and therefore by the image digest.
CMD ["python", "-m", "sub_thin.runtime", "--port", "8000"]
