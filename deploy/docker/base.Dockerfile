# lens - shared base image.
# Per-role Dockerfiles (api, scheduler, crawler, notifier, ai, cli) extend this
# and add role-specific entrypoints.
#
# Build:
#   docker build -f deploy/docker/base.Dockerfile -t lens-base:latest .

ARG PYTHON_VERSION=3.12
ARG UV_VERSION=0.5.7

FROM python:${PYTHON_VERSION}-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/usr/local

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        ca-certificates \
        git \
        libpq5 \
        libxml2 \
        libxslt1.1 \
 && rm -rf /var/lib/apt/lists/*

# ---- uv ---------------------------------------------------------------------
COPY --from=ghcr.io/astral-sh/uv:${UV_VERSION} /uv /usr/local/bin/uv

WORKDIR /app

# ---- dependency layer (cached when only sources change) --------------------
COPY pyproject.toml uv.lock ./
COPY libs libs
COPY apps apps

# Sync the full workspace; the role-specific Dockerfile will invoke the role's
# CLI script. This keeps the base image reusable for all roles.
RUN uv sync --all-packages --all-groups --no-dev --frozen \
 || uv sync --all-packages --no-dev --frozen

# ---- runtime defaults ------------------------------------------------------
ENV APP_ROLE=api \
    LOG_FORMAT=json \
    LOG_LEVEL=INFO

EXPOSE 8000

# Each role's Dockerfile sets its own CMD.
CMD ["echo", "lens-base: set a role-specific CMD in the derived image"]
