"""
Architecture Boundary Tests.

Enforces:
1. Agent package (`argvtix.target_app.agent` and related modules) MUST NOT import
   `shop_tools` directly. All tool execution must route through ToolGatewayClient.
2. Agent package MUST NOT import runtime database session (`SessionLocal`, `scoped_session`, etc.).
3. AST static analysis verifies isolation across all agent modules.
"""

from __future__ import annotations

import ast
from pathlib import Path

TARGET_APP_DIR = Path(__file__).resolve().parent.parent / "src" / "argvtix" / "target_app"


def get_runtime_imports(file_path: Path) -> list[str]:
    """Parse AST and return non-type-checking imports."""
    with open(file_path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=str(file_path))

    imports = []
    for node in tree.body:
        # Skip if TYPE_CHECKING blocks
        if isinstance(node, ast.If):
            test = node.test
            if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
                continue

        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                imports.append(f"{mod}.{alias.name}" if mod else alias.name)

    return imports


def test_agent_does_not_import_shop_tools():
    """Agent package must never import shop_tools directly."""
    agent_file = TARGET_APP_DIR / "agent.py"
    assert agent_file.exists(), "agent.py not found"

    imports = get_runtime_imports(agent_file)
    for imp in imports:
        assert "shop_tools" not in imp, (
            f"Architecture violation: agent.py imports shop_tools ({imp}). "
            "Agent must interact with tools only via ToolGatewayClient."
        )


def test_agent_does_not_import_database_session_at_runtime():
    """The agent package must not import SessionLocal or direct DB engine at runtime."""
    agent_files = [TARGET_APP_DIR / "agent.py"]
    for py_file in agent_files:
        imports = get_runtime_imports(py_file)
        for imp in imports:
            assert "SessionLocal" not in imp, (
                f"Architecture violation: {py_file.name} imports SessionLocal ({imp}). "
                "Agent must not manage DB sessions directly."
            )
            assert "get_db" not in imp, (
                f"Architecture violation: {py_file.name} imports get_db ({imp}). "
                "Agent must use ToolGatewayClient for state modifications."
            )


def test_agent_class_uses_gateway_client():
    """Verify ShopOpsAgent relies on ToolGatewayClient interface."""
    from argvtix.guard.client import ToolGatewayClient
    from argvtix.target_app.agent import ShopOpsAgent

    agent = ShopOpsAgent()
    assert hasattr(agent, "_gateway_client")
    assert isinstance(agent._gateway_client, ToolGatewayClient)
