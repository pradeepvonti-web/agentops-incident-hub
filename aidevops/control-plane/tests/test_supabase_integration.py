"""Live database tests. Skipped unless DATABASE_URL is set.

The fakes in `test_tenant_scope.py` prove call ordering -- that a scope is always
opened first. They cannot prove the SQL is valid, that the RLS policies actually
bite, or that idempotency holds under a real unique constraint. This file does
that, against a real Postgres.

Run with:

    DATABASE_URL='postgresql://...' \
        uv run pytest control-plane/tests/test_supabase_integration.py

Not in the default suite on purpose: a test that needs a network and a credential
should not be able to fail someone's local run for reasons unrelated to their
change.

These tests create rows under a `zz-itest-*` tenant and remove them afterwards.
They never touch another tenant's data -- which is itself one of the things under
test.
"""

from __future__ import annotations

import os
import uuid

import pytest
from control_plane.store.database import Database
from control_plane.store.runs import RunRepository

DSN = os.environ.get("DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not DSN, reason="DATABASE_URL not set; live database tests skipped"
)


@pytest.fixture
async def db():
    database = Database(DSN, min_size=1, max_size=2)
    await database.connect()
    try:
        yield database
    finally:
        await database.close()


@pytest.fixture
async def tenants(db):
    """Two throwaway tenants, so cross-tenant reads have something to fail at."""
    a = f"zz-itest-{uuid.uuid4().hex[:8]}"
    b = f"zz-itest-{uuid.uuid4().hex[:8]}"

    async with db.admin_scope(reason="integration test fixture") as conn:
        await conn.execute(
            "insert into public.tenants (tenant_id, display_name) "
            "values ($1, $1), ($2, $2)",
            a, b,
        )
    try:
        yield a, b
    finally:
        async with db.admin_scope(reason="integration test cleanup") as conn:
            await conn.execute(
                "delete from public.tenants where tenant_id = any($1::text[])", [a, b]
            )


async def _seed(repo: RunRepository, tenant: str, title: str) -> str:
    run_id = f"run_{uuid.uuid4().hex[:10]}"
    await repo.create_run(
        tenant,
        run_id=run_id,
        agent="data-engineering",
        environment="dev",
        invoked_by="itest",
        agent_principal=f"agent-data-engineering-{tenant}-dev",
        entry_source="portal",
        requirement="Build a Bronze to Silver pipeline",
        title=title,
    )
    return run_id


# ------------------------------------------------------------------ isolation

async def test_a_tenant_cannot_read_another_tenants_runs(db, tenants) -> None:
    """The claim the whole architecture rests on, against a real database."""
    a, b = tenants
    repo = RunRepository(db)

    await _seed(repo, a, "tenant A pipeline")
    await _seed(repo, b, "TENANT B CONFIDENTIAL")

    a_runs = await repo.list_runs(a)
    b_runs = await repo.list_runs(b)

    assert [r["title"] for r in a_runs] == ["tenant A pipeline"]
    assert [r["title"] for r in b_runs] == ["TENANT B CONFIDENTIAL"]
    assert all(r["tenant_id"] == a for r in a_runs)


async def test_get_run_across_tenants_returns_nothing(db, tenants) -> None:
    """Knowing another tenant's run id must not be enough to read it."""
    a, b = tenants
    repo = RunRepository(db)

    b_run = await _seed(repo, b, "TENANT B CONFIDENTIAL")

    assert await repo.get_run(a, b_run) is None
    assert await repo.get_run(b, b_run) is not None


# --------------------------------------------------------------- idempotency

async def test_same_idempotency_key_returns_the_first_run(db, tenants) -> None:
    """A retried CLI command or a Teams message delivered twice must not become
    two pipelines writing the same target."""
    a, _ = tenants
    repo = RunRepository(db)
    key = f"itest-{uuid.uuid4().hex[:8]}"

    first = await repo.create_run(
        a, run_id="run_first", agent="data-engineering", environment="dev",
        invoked_by="itest", agent_principal=f"agent-data-engineering-{a}-dev",
        entry_source="api-cli", requirement="Nightly reconciliation",
        title="first", idempotency_key=key,
    )
    second = await repo.create_run(
        a, run_id="run_second", agent="data-engineering", environment="dev",
        invoked_by="itest", agent_principal=f"agent-data-engineering-{a}-dev",
        entry_source="api-cli", requirement="Nightly reconciliation",
        title="second", idempotency_key=key,
    )

    assert second["run_id"] == first["run_id"] == "run_first"
    assert len(await repo.list_runs(a)) == 1


async def test_different_tenants_may_reuse_an_idempotency_key(db, tenants) -> None:
    """The key is unique per tenant, not globally. Two customers running the same
    nightly job must not collide."""
    a, b = tenants
    repo = RunRepository(db)
    key = "nightly-reconciliation"

    for tenant in (a, b):
        await repo.create_run(
            tenant, run_id=f"run_{tenant[-6:]}", agent="data-engineering",
            environment="dev", invoked_by="itest",
            agent_principal=f"agent-data-engineering-{tenant}-dev",
            entry_source="api-cli", requirement="Nightly", idempotency_key=key,
        )

    assert len(await repo.list_runs(a)) == 1
    assert len(await repo.list_runs(b)) == 1


# ---------------------------------------------------------------- no payloads

async def test_requirement_is_not_stored(db, tenants) -> None:
    """ADR-0003: the control plane keeps a digest, never the text."""
    a, _ = tenants
    repo = RunRepository(db)

    await repo.create_run(
        a, run_id="run_secret", agent="data-engineering", environment="dev",
        invoked_by="itest", agent_principal=f"agent-data-engineering-{a}-dev",
        entry_source="portal", requirement="SECRET_CUSTOMER_REQUIREMENT",
        title="digest check",
    )

    async with db.tenant_scope(a) as conn:
        row = await conn.fetchrow(
            "select * from public.runs where run_id = 'run_secret'"
        )

    assert "SECRET_CUSTOMER_REQUIREMENT" not in repr(dict(row))
    assert row["requirement_digest"].startswith("sha256:")


# -------------------------------------------------------------- approvals

async def test_approval_moves_the_run_and_is_attributed(db, tenants) -> None:
    a, _ = tenants
    repo = RunRepository(db)
    run_id = await _seed(repo, a, "needs approval")

    async with db.tenant_scope(a) as conn:
        await conn.execute(
            "update public.runs set status = 'awaiting_approval'::run_status "
            "where run_id = $1",
            run_id,
        )

    approval = await repo.record_approval(
        a, run_id=run_id, approved=True,
        artifact_digest="sha256:whatever-the-reviewer-saw",
        approved_by="r.mehta",
    )

    assert approval["approved_by"] == "r.mehta"
    assert approval["artifact_digest"] == "sha256:whatever-the-reviewer-saw"

    run = await repo.get_run(a, run_id)
    assert run is not None
    assert run["status"] == "running"
