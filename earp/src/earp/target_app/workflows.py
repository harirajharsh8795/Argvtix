"""
ShopOps Workflows Loader & Engine
Loads and validates workflow specs defined in config/workflows.yaml against Pydantic models.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from earp.trace.schemas import Severity, WorkflowConfig, WorkflowType


class WorkflowCatalog(BaseModel):
    """Complete catalog of target application workflows."""

    version: str = "1.0"
    workflows: list[WorkflowConfig] = Field(default_factory=list)

    def get_by_type(self, workflow_type: WorkflowType) -> WorkflowConfig | None:
        """Find workflow specification by enum type."""
        for wf in self.workflows:
            if wf.workflow_type == workflow_type:
                return wf
        return None

    def get_by_id(self, workflow_id: str) -> WorkflowConfig | None:
        """Find workflow specification by ID string."""
        for wf in self.workflows:
            if wf.id == workflow_id:
                return wf
        return None


def get_default_config_path() -> Path:
    """Return default path to workflows.yaml."""
    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    return base_dir / "config" / "workflows.yaml"


def load_workflows_from_yaml(path: Path | str | None = None) -> WorkflowCatalog:
    """Load workflows from YAML file into validated WorkflowCatalog."""
    if path is None:
        config_path = get_default_config_path()
    else:
        config_path = Path(path)

    if not config_path.exists():
        # Fallback to defaults from schemas
        from earp.trace.schemas import SHOPOPS_WORKFLOWS

        return WorkflowCatalog(version="1.0", workflows=list(SHOPOPS_WORKFLOWS))

    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    raw_list = data.get("workflows", [])
    parsed_workflows: list[WorkflowConfig] = []
    for item in raw_list:
        parsed_workflows.append(
            WorkflowConfig(
                id=item["id"],
                name=item["name"],
                workflow_type=WorkflowType(item["type"]),
                description=item["description"],
                risk_level=Severity(item["risk_level"]),
                requires_approval_above=item.get("requires_approval_above"),
                allowed_tools=item.get("allowed_tools", []),
                guard_rules=item.get("guard_rules", []),
            )
        )

    return WorkflowCatalog(version=data.get("version", "1.0"), workflows=parsed_workflows)
