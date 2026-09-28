"""Tenant scope discipline tests.

ADR-0001 Amendment 1 left one gap the database cannot close: admin paths connect
as `postgres`, which has BYPASSRLS, so a query that forgets `begin_tenant_scope`
returns every tenant's rows instead of failing. These tests hold the Python side
of that guarantee.

They use a recording fake rather than a live database on purpose. The property
under test is *"every read opens a scope first"*, which is about call ordering,
not about SQL. A live-database test would also pass if the ordering were wrong
and RLS happened to save us — and RLS is exactly what does not save us here.

The live integration test is `test_supabase_integration.py`, skipped without
DATABASE_URL.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from control_plane.store.database import Database, TenantScopeError
from control_plane.store.runs import RunRepository


class FakeConnection:
    """Records every statement in order."""

    def __init__(self) -> None:
        self.statements: list[tuple[str, tuple]] = []
        self.rows: list[dict] = []

    async def execute(self, sql: str, *args):
        self.statements.append((sql.strip(), args))

    async def fetch(self, sql: str, *args):
        self.statements.append((sql.strip(), args))
        return self.rows

    async def fetchrow(self, sql: str, *args):
        self.statements.append((sql.strip(), args))
        return self.rows[0] if self.rows else None

    @property
    def first_statement(self) -> str:
        return self.statements[0][0] if self.statements else ""

    def opened_scope_for(self) -> str | None:
        """The tenant passed to begin_tenant_scope, if it was called first."""
        if not self.statements:
            return None
        sql, args = self.statements[0]
        if "begin_tenant_scope" in sql and args:
            return args[0]
        return None


class FakeDatabase(Database):
    """A Database whose scopes hand back a recording connection."""

    def __init__(self) -> None:
        super().__init__("postgresql://fake/fake")
        self.conn = FakeConnection()
        self.admin_reasons: list[str] = []

    @asynccontextmanager
    async def tenant_scope(self, tenant_id: str):
        if not tenant_id:
            raise TenantScopeError("tenant_scope requires a tenant id")
        # Mirrors the real implementation: the scope statement is the first thing
        # to run inside the transaction.
        await self.conn.execute("select public.begin_tenant_scope($1)", tenant_id)
        yield self.conn

    @asynccontextmanager
    async def admin_scope(self, *, reason: str):
        self.admin_reasons.append(reason)
        yield self.conn


@pytest.fixture
def db() -> FakeDatabase:
    return FakeDatabase()


@pytest.fixture
def runs(db: FakeDatabase) -> RunRepository:
    return RunRepository(db)


# ------------------------------------------------------- scope is always opened

async def test_list_runs_opens_scope_before_querying(runs, db) -> None:
    await runs.list_runs("acme")
    assert db.conn.opened_scope_for() == "acme"


async def test_get_run_opens_scope_before_querying(runs, db) -> None:
    await runs.get_run("acme", "run_1")
    assert db.conn.opened_scope_for() == "acme"


async def test_get_spans_opens_scope_before_querying(runs, db) -> None:
    await runs.get_spans("acme", "run_1")
    assert db.conn.opened_scope_for() == "acme"


async def test_acceptance_stats_opens_scope_before_querying(runs, db) -> None:
    db.conn.rows = [{"n": 0, "accepted": 0, "clean_accepted": 0, "median_edit_ratio": 0}]
    await runs.acceptance_stats("acme")
    assert db.conn.opened_scope_for() == "acme"


async def test_record_approval_opens_scope_before_writing(runs, db) -> None:
    db.conn.rows = [{"approval_id": 1, "run_id": "run_1", "approved": True,
                     "artifact_digest": "sha256:x", "approved_by": "u1",
                     "decided_at": None}]
    await runs.record_approval(
        "acme", run_id="run_1", approved=True,
        artifact_digest="sha256:x", approved_by="u1",
    )
    assert db.conn.opened_scope_for() == "acme"


async def test_every_repository_read_opens_a_scope(runs, db) -> None:
    """The general property, so a newly added method is caught too."""
    db.conn.rows = [{"n": 0, "accepted": 0, "clean_accepted": 0, "median_edit_ratio": 0}]

    for call in (
        runs.list_runs("acme"),
        runs.get_run("acme", "r"),
        runs.get_spans("acme", "r"),
        runs.acceptance_stats("acme"),
    ):
        db.conn.statements.clear()
        await call
        assert "begin_tenant_scope" in db.conn.first_statement


# ------------------------------------------------------------- empty tenant id

async def test_empty_tenant_is_refused(runs) -> None:
    """An empty tenant would set an empty RLS context, which matches no rows --
    but it would do so silently. Refusing is louder and easier to debug."""
    with pytest.raises(TenantScopeError):
        await runs.list_runs("")


async def test_real_database_refuses_empty_tenant() -> None:
    real = Database("postgresql://unused/unused")
    with pytest.raises(TenantScopeError):
        async with real.tenant_scope(""):
            pass


# ------------------------------------------------------------------ no leakage

async def test_repository_never_filters_by_tenant_in_sql(runs, db) -> None:
    """RLS applies the tenant filter. A hand-written `where tenant_id = ...`
    would work and would teach the next reader that the filter is what protects
    them -- so the queries deliberately do not carry one."""
    await runs.list_runs("acme", status="running")

    query = db.conn.statements[-1][0]
    assert "tenant_id" not in query.split("from")[1], (
        "run queries must not filter on tenant_id; RLS does that from the scope"
    )


async def test_run_queries_select_no_payload_columns(runs, db) -> None:
    """ADR-0003: nothing payload-bearing may reach the API. The columns are
    spelled out so a new column cannot arrive by being added to the table."""
    await runs.list_runs("acme")
    await runs.get_spans("acme", "r")

    forbidden = ("requirement", "arguments", "result", "prompt", "completion", "payload")
    for sql, _ in db.conn.statements:
        select_clause = sql.split("from")[0]
        for word in forbidden:
            # `requirement_digest` and `arguments_digest` are fine; the bare
            # column names are not.
            assert f" {word}," not in select_clause and not select_clause.rstrip().endswith(
                f" {word}"
            ), f"{word!r} must not be selected: {select_clause[:120]}"


# -------------------------------------------------------------- admin is loud

async def test_admin_scope_requires_a_written_reason(db) -> None:
    async with db.admin_scope(reason="onboarding tenant acme"):
        pass
    assert db.admin_reasons == ["onboarding tenant acme"]


def test_admin_scope_is_keyword_only() -> None:
    """`reason` cannot be passed positionally, so it cannot be supplied by
    accident or omitted by habit."""
    import inspect

    sig = inspect.signature(Database.admin_scope)
    assert sig.parameters["reason"].kind is inspect.Parameter.KEYWORD_ONLY
