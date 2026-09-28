"""Tenant isolation. Implements ADR-0001; portal identity per ADR-0005.

Three layers, and the third is the one that matters:

  1. `tenant_id` non-nullable on every row.
  2. A tenant-scoped repository layer.
  3. **PostgreSQL Row-Level Security**, with the tenant set per connection from the
     authenticated principal.

Layers 1 and 2 are discipline; layer 3 is enforcement. Discipline fails at 2am in a
hotfix, which is precisely when a cross-tenant leak is most expensive. With RLS,
a query that forgets its tenant filter returns nothing rather than everything.

The rule this module exists to make true: **application code never supplies a
tenant_id to a query.** It comes from the session, which comes from the token,
which comes from Supabase Auth -- and the token-to-tenant step is one row in
`public.tenant_members`, written by an admin, never by a request.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import structlog
from fastapi import Header, HTTPException, Request

from control_plane.auth.supabase import IdentityUnavailable
from control_plane.settings import Settings

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class TenantContext:
    """Resolved caller identity for one request.

    Frozen: nothing downstream may reassign the tenant mid-request. A mutable
    tenant context is a confused-deputy bug waiting to be written.
    """

    tenant_id: str
    user_object_id: str
    role: str = "member"
    display_name: str = ""
    is_execution_plane: bool = False

    def __post_init__(self) -> None:
        if not self.tenant_id:
            raise ValueError("TenantContext requires a tenant_id")
        if not self.display_name:
            object.__setattr__(self, "display_name", self.user_object_id)

    @property
    def may_approve(self) -> bool:
        """Deciding an approval is a grant, not a default. A member submits runs
        and watches them; an approver or admin can also say yes or no."""
        return self.role in ("approver", "admin")


async def require_tenant(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> TenantContext:
    """Resolve the caller's tenant from their Supabase session.

    Order matters and is deliberate:

      1. No bearer token: 401 before anything else is looked at.
      2. Supabase Auth does not recognise the token: 401.
      3. The user is not in `tenant_members`: 403 -- unless this is a development
         environment with `ADP_DEV_TENANT` set, in which case they are placed in
         that tenant as an approver so a fresh clone has something to look at.

    The tenant never comes from a header, query parameter or body field. A caller
    must not be able to name the tenant they want (ADR-0001).
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()

    state = request.app.state
    identity = getattr(state, "identity", None)
    if identity is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY are not set; the control "
                "plane cannot verify sessions"
            ),
        )

    try:
        user = await identity.user_for(token)
    except IdentityUnavailable as exc:
        raise HTTPException(
            status_code=503, detail=f"identity provider unavailable: {exc}"
        ) from exc
    if user is None:
        raise HTTPException(status_code=401, detail="session is invalid or expired")

    db = getattr(state, "db", None)
    if db is None:
        raise HTTPException(
            status_code=503,
            detail="DATABASE_URL is not set; the control plane cannot resolve tenants",
        )

    membership = await db.resolve_membership(user.id)
    if membership is not None:
        return TenantContext(
            tenant_id=membership.tenant_id,
            user_object_id=user.id,
            role=membership.role,
            display_name=user.display_name,
        )

    settings: Settings = getattr(state, "settings", None) or Settings()
    fallback = settings.dev_tenant_fallback
    if not fallback:
        raise HTTPException(
            status_code=403,
            detail=(
                "this account is not a member of any tenant; membership is an admin "
                "action (public.tenant_members)"
            ),
        )

    log.info("dev_tenant_fallback", user_id=user.id, tenant_id=fallback)
    return TenantContext(
        tenant_id=fallback,
        user_object_id=user.id,
        role="approver",
        display_name=user.display_name,
    )


async def require_execution_plane(
    authorization: Annotated[str | None, Header()] = None,
) -> TenantContext:
    """Resolve an execution-plane caller from its workload identity.

    STUB -- Month 1. Real implementation:
      * Validate the Entra JWT: signature, issuer, audience, expiry.
      * `tenant_id` comes from a claim we issued at onboarding -- never from a
        request header, query parameter or body field.
      * The principal is an agent (ADR-0002). It may claim work and post
        telemetry; it may never approve.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")

    raise HTTPException(
        status_code=501,
        detail="execution-plane token validation is not implemented; see tenant_context.py",
    )


BEGIN_TENANT_SCOPE_SQL = "select public.begin_tenant_scope($1);"
"""Run this FIRST in every transaction that touches tenant data.

It does two things in one call (see migration 0002): drops into the `adp_app`
role, which has no BYPASSRLS, and sets the tenant for the RLS policies. Both are
transaction-local, so a pooled connection cannot carry one request's tenant or
privilege into the next.

Calling only `set_config` is NOT enough. ADR-0001 Amendment 1: a role with
BYPASSRLS -- which `postgres` and `service_role` both have in Supabase -- ignores
row-level security entirely, including FORCE. The catalog reports the policy as
active and every row is still visible. This is why the two actions are one
function rather than two.
"""

TENANT_SCOPED_TABLES = [
    "runs",
    "run_spans",
    "run_outcomes",
    "approvals",
    "registry_assets",
    "registry_asset_versions",
    "evaluation_scores",
]
"""Every table holding tenant data.

CI asserts that each has RLS enabled AND forced, that each has a policy, and that
no table outside this list carries a `tenant_id` column -- a tenant-scoped table
nobody added here would have no policy protecting it.

`tenant_members` is not in this list on purpose. It carries a tenant_id but is
not tenant data: it is how a tenant is chosen, read before any scope exists, and
it is deny-all to every role that does not bypass RLS.
"""


class TenantScopeError(RuntimeError):
    """Raised when tenant data is queried without a scope having been opened.

    ADR-0001 Amendment 1 consequences: admin paths legitimately run as `postgres`
    and bypass RLS, which means a forgotten `begin_tenant_scope` does not fail --
    it silently returns every tenant's rows. The repository layer has to make that
    impossible rather than merely discouraged, so it raises this instead of
    trusting the database to catch it.
    """
