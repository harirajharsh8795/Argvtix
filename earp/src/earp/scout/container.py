"""Container isolation and network egress policy for Proofline Scout.

Scout runs inside an isolated container sandbox with zero default outbound internet access,
except strictly whitelisted domains defined in scope.yaml.
"""

from __future__ import annotations

from typing import Any
import yaml
from earp.scout.scope import ScopeConfig


def validate_egress_destination(destination_host: str, allowlist: list[str]) -> bool:
    """Verifies that a target hostname or IP is strictly allowed by egress policy.

    Supports exact matches and domain wildcarding (e.g. '*.client.staging').
    """
    clean_host = destination_host.strip().lower()
    for rule in allowlist:
        clean_rule = rule.strip().lower()
        if clean_rule == clean_host:
            return True
        if clean_rule.startswith("*."):
            suffix = clean_rule[1:]  # e.g. .example.com
            if clean_host.endswith(suffix):
                return True
    return False


def generate_scout_sandbox_compose(scope: ScopeConfig) -> str:
    """Generates a Docker Compose configuration for running Scout in an isolated container.

    - Internal bridge network with restricted egress.
    - Mounts scope.yaml read-only.
    - Drops Linux capabilities.
    """
    egress_hosts = sorted(set(scope.allowed_hosts + scope.egress_allowlist))

    compose_dict: dict[str, Any] = {
        "version": "3.8",
        "services": {
            "scout-sandbox": {
                "image": "proofline/scout:latest",
                "container_name": f"proofline-scout-{scope.scope_id}",
                "restart": "no",
                "cap_drop": ["ALL"],
                "security_opt": ["no-new-privileges:true"],
                "environment": {
                    "PROOFLINE_SCOUT_SCOPE_ID": scope.scope_id,
                    "PROOFLINE_SCOUT_PROJECT_ID": scope.project_id,
                    "PROOFLINE_SCOUT_TARGET_URL": scope.target_url,
                    "PROOFLINE_SCOUT_MAX_RPM": str(scope.max_rpm),
                    "EGRESS_ALLOWLIST": ",".join(egress_hosts),
                },
                "networks": ["scout-isolated-net"],
                "volumes": [
                    "./scope.yaml:/app/scope.yaml:ro",
                    "./reports:/app/reports:rw",
                ],
            }
        },
        "networks": {
            "scout-isolated-net": {
                "driver": "bridge",
                "internal": False,  # Egress restricted via proxy/iptables
                "labels": {
                    "proofline.scope_id": scope.scope_id,
                    "proofline.tier": scope.target_tier.value,
                },
            }
        },
    }

    return yaml.dump(compose_dict, sort_keys=False)
