"""Tenant-scoped persistence.

Nothing here hands out a bare connection for tenant data. The only way to
reach it is `Database.tenant_scope`, which opens the RLS context as the first
statement of the transaction (ADR-0001 Amendment 1).
"""

from control_plane.store.database import (
    Database,
    Membership,
    Repository,
    TenantScopeError,
    database_from_env,
)
from control_plane.store.runs import RunRepository
from control_plane.store.tenant_context import (
    TenantContext,
    require_execution_plane,
    require_tenant,
)

__all__ = [
    "Database",
    "Membership",
    "Repository",
    "TenantScopeError",
    "database_from_env",
    "RunRepository",
    "TenantContext",
    "require_execution_plane",
    "require_tenant",
]
