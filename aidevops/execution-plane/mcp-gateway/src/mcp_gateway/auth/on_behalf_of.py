"""On-behalf-of permission resolution. Implements ADR-0002 section 4.

    effective = agent_permissions AND invoking_user_permissions

The policy engine enforces the agent half. This module answers the other half:
*could the human who asked for this have done it themselves?*

Without this, an analyst who can invoke the Data Engineering agent inherits
everything that agent can do -- the classic confused-deputy escalation. With it,
the agent is capped at the invoker's own reach.

Unattended runs (`system:scheduler`) have no invoking human. They are capped
instead by the schedule's own registered owner, which is resolved at schedule
creation time and stored with the schedule, never inferred here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import structlog
from adp_contracts import RunPrincipal

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class UserPermissionSet:
    """What the invoking human can do, resolved once per run and cached for its life.

    Resolution costs a Unity Catalog and a Graph call, so it is not done per tool
    call. The cache lifetime is the run, not longer -- a permission revoked mid-run
    should stop the *next* run, and runs are short.
    """

    principal_object_id: str
    can_write_catalogs: frozenset[str]
    can_read_catalogs: frozenset[str]
    can_deploy_environments: frozenset[str]
    can_open_pull_requests: bool

    def permits(self, *, tool_name: str, arguments: dict) -> bool:
        """Whether this human could perform the action themselves."""
        catalog = arguments.get("catalog")

        if tool_name in {"uc_list_tables", "uc_get_table_metadata"}:
            return catalog is None or catalog in self.can_read_catalogs

        if tool_name == "databricks_submit_job":
            target = str(arguments.get("target") or "")
            target_catalog = target.split(".")[0] if "." in target else target
            env = str(arguments.get("environment") or "dev")
            return (
                target_catalog in self.can_write_catalogs
                and env in self.can_deploy_environments
            )

        if tool_name == "git_open_pull_request":
            return self.can_open_pull_requests

        # Unknown tool: deny. A new tool must be taught to this resolver explicitly,
        # otherwise it silently bypasses the intersection rule.
        log.warning("obo_unknown_tool_denied", tool_name=tool_name)
        return False


class PermissionResolver(Protocol):
    def resolve(self, principal: RunPrincipal) -> UserPermissionSet: ...


class UnityCatalogPermissionResolver:
    """Resolves a human's effective grants from Unity Catalog and Entra.

    STUB -- Month 1. The shape is real and the call sites are correct; the two
    lookups are not implemented yet.

    Implementation notes for whoever picks this up:
      * Unity Catalog: `GET /api/2.1/unity-catalog/effective-permissions` for the
        user, per catalog. Batch it; do not loop per table.
      * Entra group membership: Graph `/me/transitiveMemberOf`, mapped to
        deploy-environment entitlements by the tenant config.
      * Both calls use the *gateway's* identity reading *about* the user, not the
        user's own token -- the gateway never holds user tokens.
    """

    def __init__(self, *, databricks_host: str, tenant_id: str) -> None:
        self._host = databricks_host
        self._tenant_id = tenant_id

    def resolve(self, principal: RunPrincipal) -> UserPermissionSet:
        if principal.is_unattended:
            raise NotImplementedError(
                "Unattended runs must be capped by the schedule owner's permissions, "
                "resolved at schedule creation. Scheduling lands Month 2."
            )

        log.info(
            "resolving_user_permissions",
            invoked_by=principal.invoked_by,
            agent_principal=principal.agent.name,
        )
        raise NotImplementedError(
            "Unity Catalog effective-permissions lookup is not implemented. "
            "Use StaticPermissionResolver in dev, and see this class's docstring "
            "for the two API calls required."
        )


class StaticPermissionResolver:
    """Fixed permissions from tenant config. Dev and tests only.

    Deliberately not wired into the prod server path -- see `server.py`, which
    refuses to start with this resolver outside dev.
    """

    def __init__(self, permissions: UserPermissionSet) -> None:
        self._permissions = permissions

    def resolve(self, principal: RunPrincipal) -> UserPermissionSet:
        return self._permissions


def developer_permissions(object_id: str = "dev-user") -> UserPermissionSet:
    """Permissive-but-not-unlimited defaults for local development."""
    return UserPermissionSet(
        principal_object_id=object_id,
        can_write_catalogs=frozenset({"bronze", "silver"}),
        can_read_catalogs=frozenset({"bronze", "silver", "gold", "raw"}),
        can_deploy_environments=frozenset({"dev"}),
        can_open_pull_requests=True,
    )
