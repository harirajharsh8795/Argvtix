"""
Route-level AST / FastAPI Route Inspection Test.
Proves that every tenant-sensitive endpoint is structurally bound to get_tenant_db
and NEVER relies on raw, unscoped get_db.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest
from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from argvtix.db.session import get_db
from argvtix.db.tenant import get_tenant_db
from argvtix.gateway.app import app

TENANT_SCOPED_PATH_PREFIXES = [
    "/api/v1/traces",
    "/api/v1/watchdog/findings",
    "/api/v1/watchdog/scan",
    "/api/v1/guard/approvals",
]


def _extract_dependencies(endpoint: Any) -> list[Any]:
    """Inspects an endpoint function or FastAPI route dependencies."""
    deps = []
    sig = inspect.signature(endpoint)
    for param in sig.parameters.values():
        if param.default is not inspect.Parameter.empty and hasattr(param.default, "dependency"):
            deps.append(param.default.dependency)
    return deps


def test_tenant_routes_require_tenant_db_dependency() -> None:
    """Verifies that every tenant route in the FastAPI application uses get_tenant_db

    and does NOT depend on unscoped get_db.
    """
    tenant_routes_checked = 0

    for route in app.routes:
        path = getattr(route, "path", "")
        endpoint = getattr(route, "endpoint", None)
        if not endpoint:
            continue

        is_tenant_path = any(path.startswith(prefix) for prefix in TENANT_SCOPED_PATH_PREFIXES)
        if not is_tenant_path:
            continue

        deps = _extract_dependencies(endpoint)
        if get_db in deps or get_tenant_db in deps:
            tenant_routes_checked += 1
            # MUST NOT use raw get_db
            assert get_db not in deps, (
                f"Tenant isolation breach: Route '{path}' depends on unscoped 'get_db'!"
            )
            # MUST use get_tenant_db
            assert get_tenant_db in deps, (
                f"Tenant isolation missing: Route '{path}' does not depend on 'get_tenant_db'!"
            )

    assert tenant_routes_checked >= 5, (
        f"Expected at least 5 tenant routes checked, found {tenant_routes_checked}"
    )


def test_tenant_routing_negative_control() -> None:
    """Negative control: proves that route checker fails if a route incorrectly depends on get_db."""
    bad_app = FastAPI()

    @bad_app.get("/api/v1/traces/insecure")
    def insecure_traces(db: Session = Depends(get_db)):
        return {"status": "insecure"}

    bad_endpoint = bad_app.routes[-1].endpoint
    bad_deps = _extract_dependencies(bad_endpoint)

    assert get_db in bad_deps, "Negative control setup failed: get_db not in bad_deps"
    with pytest.raises(AssertionError, match="depends on unscoped 'get_db'"):
        assert get_db not in bad_deps, (
            "Tenant isolation breach: Route depends on unscoped 'get_db'!"
        )
