# ==============================================================================
# ARGVTIX Multi-Stage Hardened Production Dockerfile
# Stage 1: Build & Dependency Resolution
# Stage 2: Minimal Non-Root Runtime Container with Health Check
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Builder
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefix=/install .

# ------------------------------------------------------------------------------
# Stage 2: Runtime
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PATH="/install/bin:${PATH}"

# Install minimal runtime libraries (curl for healthcheck, libpq5 for Postgres)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root security user & group
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /sbin/nologin -d /app -M appuser

WORKDIR /app

# Copy compiled python packages from builder
COPY --from=builder /install /usr/local

# Copy application code, configuration, and migrations
COPY --chown=appuser:appgroup alembic.ini /app/
COPY --chown=appuser:appgroup alembic/ /app/alembic/
COPY --chown=appuser:appgroup config/ /app/config/
COPY --chown=appuser:appgroup src/ /app/src/

# Switch to unprivileged security context
USER appuser

# Container Healthcheck probe verifying API liveness & DB pool
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/health || exit 1

EXPOSE 8000

# Exec form CMD forwards SIGTERM directly to Uvicorn for graceful connection draining
CMD ["uvicorn", "argvtix.gateway.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--timeout-keep-alive", "65"]
