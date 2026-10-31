#!/usr/bin/env bash
# ==============================================================================
# Proofline EARP — Staging & Production Deployment Automation Script
# ==============================================================================
# Target: Ubuntu 22.04 LTS / Debian 12 / Docker-enabled Linux Hosts
# Validates environment, checks secrets, launches container cluster,
# executes database migrations, verifies health endpoints, and supports rollback.
# ==============================================================================

set -euo pipefail

# ANSI color formatting
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

COMPOSE_FILE="docker-compose.prod.yml"
MAX_HEALTH_WAIT_SEC=60
HEALTH_POLL_INTERVAL=3
APP_HEALTH_URL="http://localhost/health"
APP_READY_URL="http://localhost/ready"

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

# Ensure script is run from project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

echo -e "${BOLD}======================================================================${NC}"
echo -e "${BOLD}   Proofline EARP — Containerized Staging Deployment Pipeline        ${NC}"
echo -e "${BOLD}======================================================================${NC}"
log_info "Working directory: ${PROJECT_ROOT}"

# ------------------------------------------------------------------------------
# STEP 1: Verify Host Prerequisites
# ------------------------------------------------------------------------------
log_info "Step 1: Checking host system prerequisites..."

if ! command -v docker >/dev/null 2>&1; then
    log_error "Docker Engine is not installed or not available on PATH."
    log_error "Please install Docker: https://docs.docker.com/engine/install/"
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    log_error "Docker Compose v2 plugin is not available."
    log_error "Please install docker-compose-plugin."
    exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
    log_error "curl command-line utility is required for health verification."
    exit 1
fi

DOCKER_VER=$(docker --version)
COMPOSE_VER=$(docker compose version)
log_success "Host prerequisites satisfied: ${DOCKER_VER} | ${COMPOSE_VER}"

# ------------------------------------------------------------------------------
# STEP 2: Environment Configuration & Secret Hardening Validation
# ------------------------------------------------------------------------------
log_info "Step 2: Validating environment configuration and production secrets..."

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        log_warn ".env file missing. Initializing from .env.example..."
        cp .env.example .env
        log_warn "Created default .env template. Please review and populate production secrets."
    else
        log_error "Neither .env nor .env.example found in ${PROJECT_ROOT}."
        exit 1
    fi
fi

# Source .env safely
set -a
# shellcheck disable=SC1091
source .env
set +a

# Mandatory Environment Validations
if [ -z "${DATABASE_URL:-}" ]; then
    log_error "DATABASE_URL is not set in .env. Managed PostgreSQL is required."
    exit 1
fi

if [[ "${DATABASE_URL}" == sqlite* ]]; then
    if [ "${EARP_ENV:-}" = "production" ] || [ "${EARP_ENV:-}" = "staging" ]; then
        log_error "Production/Staging mode rejects SQLite backends. DATABASE_URL must point to PostgreSQL."
        exit 1
    else
        log_warn "Using SQLite (${DATABASE_URL}). Acceptable only for local demo, not staging."
    fi
fi

if [ -z "${REDIS_URL:-}" ]; then
    log_warn "REDIS_URL is not configured. CacheManager will fall back to local in-memory LRU."
fi

if [ -z "${EARP_JWT_SECRET:-}" ] || [ "${#EARP_JWT_SECRET}" -lt 32 ]; then
    log_error "EARP_JWT_SECRET is missing or shorter than 32 characters."
    log_error "Generate a strong secret with: openssl rand -hex 32"
    exit 1
fi

INSECURE_SECRETS=("change-me-in-production" "demo-secret-key-do-not-use-in-prod" "secret" "password" "admin")
for bad in "${INSECURE_SECRETS[@]}"; do
    if [ "${EARP_JWT_SECRET}" = "${bad}" ]; then
        log_error "EARP_JWT_SECRET is set to an insecure default value: '${bad}'."
        exit 1
    fi
done

if [ -z "${CLOUDFLARE_TURNSTILE_SECRET_KEY:-}" ]; then
    log_warn "CLOUDFLARE_TURNSTILE_SECRET_KEY is unconfigured. Public contact forms will fail closed in production."
fi

log_success "Environment secrets and hardening requirements verified."

# ------------------------------------------------------------------------------
# STEP 3: Compose Specification Validation
# ------------------------------------------------------------------------------
log_info "Step 3: Validating Compose specification (${COMPOSE_FILE})..."

if [ ! -f "${COMPOSE_FILE}" ]; then
    log_error "Compose file ${COMPOSE_FILE} not found."
    exit 1
fi

docker compose -f "${COMPOSE_FILE}" config -q
log_success "Compose definition syntax and network bindings are valid."

# ------------------------------------------------------------------------------
# STEP 4: Build and Deploy Containers
# ------------------------------------------------------------------------------
log_info "Step 4: Building and launching containers in detached mode..."

rollback() {
    log_error "Deployment failed! Initiating rollback..."
    docker compose -f "${COMPOSE_FILE}" ps || true
    docker compose -f "${COMPOSE_FILE}" logs --tail 50 api || true
    docker compose -f "${COMPOSE_FILE}" down || true
    log_error "Rollback completed. Containers stopped."
    exit 1
}

trap rollback ERR

docker compose -f "${COMPOSE_FILE}" up -d --build --remove-orphans

log_success "Container stack launched. Current status:"
docker compose -f "${COMPOSE_FILE}" ps

# ------------------------------------------------------------------------------
# STEP 5: Database Schema Migration
# ------------------------------------------------------------------------------
log_info "Step 5: Executing database migrations against active database..."

if docker compose -f "${COMPOSE_FILE}" exec -T api alembic upgrade head; then
    log_success "Alembic migrations executed successfully (schema is at HEAD)."
else
    log_error "Database migration failed."
    rollback
fi

# ------------------------------------------------------------------------------
# STEP 6: Health Check & Readiness Polling
# ------------------------------------------------------------------------------
log_info "Step 6: Polling application health probes (timeout: ${MAX_HEALTH_WAIT_SEC}s)..."

HEALTH_PASSED=false
ELAPSED=0

while [ "${ELAPSED}" -lt "${MAX_HEALTH_WAIT_SEC}" ]; do
    if HTTP_RESP=$(curl -s -f "${APP_HEALTH_URL}" 2>/dev/null); then
        if echo "${HTTP_RESP}" | grep -q '"status":"healthy"'; then
            HEALTH_PASSED=true
            break
        fi
    fi
    sleep "${HEALTH_POLL_INTERVAL}"
    ELAPSED=$((ELAPSED + HEALTH_POLL_INTERVAL))
    echo -n "."
done
echo ""

if [ "${HEALTH_PASSED}" = true ]; then
    log_success "Application passed health check at ${APP_HEALTH_URL} (${ELAPSED}s)."
else
    log_error "Application failed to become healthy within ${MAX_HEALTH_WAIT_SEC}s."
    rollback
fi

# Verify /ready endpoint
if curl -s -f "${APP_READY_URL}" >/dev/null 2>&1; then
    log_success "Application readiness probe passed at ${APP_READY_URL}."
else
    log_warn "Readiness probe warning: ${APP_READY_URL} returned non-200. Check service dependencies."
fi

# Untrap ERR on success
trap - ERR

echo -e "\n${BOLD}======================================================================${NC}"
echo -e "${GREEN}${BOLD}   STAGING DEPLOYMENT COMPLETED SUCCESSFULLY                         ${NC}"
echo -e "${BOLD}======================================================================${NC}"
echo -e "API Gateway & NGINX: ${APP_HEALTH_URL}"
echo -e "Web Console & UI:    http://localhost/"
echo -e "Logs command:        docker compose -f ${COMPOSE_FILE} logs -f"
echo -e "Stop cluster:        docker compose -f ${COMPOSE_FILE} down"
echo -e "======================================================================\n"
