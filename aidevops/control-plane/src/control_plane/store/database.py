"""Database access, with tenant scope enforced rather than encouraged.

ADR-0001 Amendment 1 left a gap: admin paths legitimately connect as `postgres`,
which has BYPASSRLS, so a query that forgets `begin_tenant_scope` does not fail --
it silently returns every tenant's rows. The database cannot catch that. This
module is where it gets caught.

The shape: you cannot get a connection without naming a tenant.

    async with db.tenant_scope("acme") as conn:
        rows = await conn.fetch("select * from runs")

`tenant_scope` opens a transaction, calls `begin_tenant_scope`, and hands back the
connection. There is no public method that returns a bare connection for tenant
data, so "forgot to set the tenant" is not a mistake that can be made -- it is
code that does not compile into existence.

Admin work (onboarding, migrations) goes through `admin_scope`, which is
deliberately named to be uncomfortable and is the only path that bypasses RLS.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:  # pragma: no cover - import cost only matters at runtime
    import asyncpg

log = structlog.get_logger(__name__)


class TenantScopeError(RuntimeError):
    """Raised when tenant data is reached without a scope having been opened."""


@dataclass(frozen=True)
class Membership:
    """One row of `public.tenant_members`: the tenant a signed-in user belongs to."""

    tenant_id: str
    role: str


class Database:
    """Owns the connection pool and the tenant-scope discipline."""

    def __init__(self, dsn: str, *, min_size: int = 2, max_size: int = 10) -> None:
        if not dsn:
            raise ValueError("Database requires a DSN")
        self._dsn = dsn
        self._min_size = min_size
        self._max_size = max_size
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        import asyncpg

        self._pool = await asyncpg.create_pool(
            self._dsn,
            min_size=self._min_size,
            max_size=self._max_size,
            # Statement caching and transaction-scoped SET ROLE do not mix well
            # with a server-side pooler. Disabling it costs a little planning time
            # and avoids a class of bug that only appears under load.
            statement_cache_size=0,
            command_timeout=30,
        )
        log.info("database_pool_ready", min_size=self._min_size, max_size=self._max_size)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("Database.connect() has not been awaited")
        return self._pool

    # ------------------------------------------------------------------ scopes

    @asynccontextmanager
    async def tenant_scope(self, tenant_id: str) -> AsyncIterator[asyncpg.Connection]:
        """A transaction scoped to one tenant. The only way to read tenant data.

        `begin_tenant_scope` drops into the `adp_app` role (no BYPASSRLS) and sets
        the tenant for RLS. Both are transaction-local, so they revert on commit or
        rollback and a pooled connection cannot carry one request's tenant or
        privilege into the next.

        The scope is opened *inside* the transaction on purpose. Opening it outside
        would leave the first statement of the transaction unprotected, which is
        exactly the window a bug would slip through.
        """
        if not tenant_id:
            raise TenantScopeError(
                "tenant_scope requires a tenant id. It comes from the authenticated "
                "principal, never from a request parameter (ADR-0001)."
            )

        async with self.pool.acquire() as conn, conn.transaction():
            await conn.execute("select public.begin_tenant_scope($1)", tenant_id)
            yield conn

    async def resolve_membership(self, auth_user_id: str) -> Membership | None:
        """The one query that runs before a tenant scope exists.

        It has to: this is how the scope is chosen (ADR-0005). It runs as the
        pool's own role, reads one row of one table by primary key, and returns
        nothing that is tenant data. Do not add a second method like it. If a
        query needs a tenant, it goes through `tenant_scope`.
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "select tenant_id, role from public.tenant_members "
                "where auth_user_id = $1::uuid",
                auth_user_id,
            )
        return Membership(tenant_id=row["tenant_id"], role=row["role"]) if row else None

    @asynccontextmanager
    async def admin_scope(self, *, reason: str) -> AsyncIterator[asyncpg.Connection]:
        """A transaction that bypasses RLS. Onboarding and migrations only.

        Named to be uncomfortable, and requires a written reason that lands in the
        log, because every call is a place where cross-tenant data is reachable.
        If you are reaching for this to read a run, you want `tenant_scope`.
        """
        log.warning("admin_scope_opened", reason=reason)
        async with self.pool.acquire() as conn, conn.transaction():
            yield conn


def database_from_env() -> Database:
    """Build a Database from DATABASE_URL.

    The DSN is a credential. It comes from the environment or Key Vault, never
    from a config file in the repository -- see `.env.example`.
    """
    dsn = os.environ.get("DATABASE_URL", "")
    if not dsn:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env and fill it in "
            "from the Supabase dashboard."
        )
    return Database(dsn)


class Repository:
    """Base for repositories. Carries the database and nothing else.

    Every method takes an explicit `tenant_id` and opens its own scope. Repositories
    deliberately do not hold a connection between calls: a long-lived connection is
    a long-lived tenant context, and that is the thing we are preventing.
    """

    def __init__(self, db: Database) -> None:
        self._db = db

    @staticmethod
    def _row_to_dict(row: Any) -> dict[str, Any]:
        return dict(row) if row is not None else {}
