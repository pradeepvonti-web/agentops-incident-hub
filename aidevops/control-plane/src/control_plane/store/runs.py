"""Run and approval persistence.

Every method opens its own tenant scope. There is no variant that takes a
connection from the caller -- that would let a caller pass one opened for a
different tenant, or for none at all, which is the whole class of bug
`Database.tenant_scope` exists to remove.
"""

from __future__ import annotations

from typing import Any

import structlog
from adp_contracts import digest

from control_plane.store.database import Repository

log = structlog.get_logger(__name__)

#: Columns the portal's run list needs. Spelled out rather than `select *` so a
#: new column -- particularly a payload-bearing one -- cannot reach the API by
#: being added to the table (ADR-0003).
_RUN_COLUMNS = """
    run_id, tenant_id, agent, environment, status, invoked_by, agent_principal,
    entry_source, title, created_at, started_at, ended_at, execution_plane_version
"""


class RunRepository(Repository):
    async def list_runs(
        self,
        tenant_id: str,
        *,
        status: str | None = None,
        agent: str | None = None,
        environment: str | None = None,
        entry_source: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Runs for one tenant, newest first.

        Note the absence of a `tenant_id` filter in the SQL. It is not an
        oversight: RLS applies it from the scope. Adding `where tenant_id = $n`
        here would work, and would also train the next person to believe the
        filter is what protects them.
        """
        clauses: list[str] = []
        args: list[Any] = []

        # Column -> Postgres enum type. Explicit because the two only coincide by
        # accident: `agent` is of type `agent_type`, and inferring the cast from
        # the column name produces `::agent`, which does not exist.
        filters: tuple[tuple[str, str, str | None], ...] = (
            ("status", "run_status", status),
            ("agent", "agent_type", agent),
            ("environment", "environment", environment),
            ("entry_source", "entry_source", entry_source),
        )

        for column, pg_type, value in filters:
            if value is not None:
                args.append(value)
                clauses.append(f"{column} = ${len(args)}::{pg_type}")

        where = f"where {' and '.join(clauses)}" if clauses else ""
        args.append(min(limit, 200))

        sql = f"""
            select {_RUN_COLUMNS}
            from public.runs
            {where}
            order by created_at desc
            limit ${len(args)}
        """

        async with self._db.tenant_scope(tenant_id) as conn:
            rows = await conn.fetch(sql, *args)
        return [dict(r) for r in rows]

    async def get_run(self, tenant_id: str, run_id: str) -> dict[str, Any] | None:
        async with self._db.tenant_scope(tenant_id) as conn:
            row = await conn.fetchrow(
                f"select {_RUN_COLUMNS} from public.runs where run_id = $1", run_id
            )
        return dict(row) if row else None

    async def get_spans(self, tenant_id: str, run_id: str) -> list[dict[str, Any]]:
        """The span tree for the run detail view. Metadata tier only.

        `arguments_digest` and `result_digest` are selected; `arguments` and
        `result` do not exist as columns, so there is nothing here to leak.
        """
        async with self._db.tenant_scope(tenant_id) as conn:
            rows = await conn.fetch(
                """
                select span_id, parent_span_id, name, step, status, attempt,
                       checkpoint_id, started_at, ended_at, duration_ms, error_class,
                       tool_name, tool_decision, policy_reason,
                       arguments_digest, result_digest,
                       model, tokens_in, tokens_out, cost_usd, cache_hit
                from public.run_spans
                where run_id = $1
                order by started_at, span_id
                """,
                run_id,
            )
        return [dict(r) for r in rows]

    async def create_run(
        self,
        tenant_id: str,
        *,
        run_id: str,
        agent: str,
        environment: str,
        invoked_by: str,
        agent_principal: str,
        entry_source: str,
        requirement: str,
        title: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Queue a run.

        `requirement` is hashed here and the plaintext is dropped. The control
        plane never stores it (ADR-0003 §3), so it is taken as a value and
        converted rather than accepted pre-digested -- a caller that had to
        remember to hash it would eventually forget.

        On an idempotency-key collision the existing run is returned rather than a
        second one created. A retried Teams message must not become two pipelines
        writing the same target.
        """
        async with self._db.tenant_scope(tenant_id) as conn:
            row = await conn.fetchrow(
                """
                insert into public.runs (
                    run_id, tenant_id, agent, environment, invoked_by,
                    agent_principal, entry_source, requirement_digest, title,
                    idempotency_key
                )
                values ($1, $2, $3::agent_type, $4::environment, $5, $6,
                        $7::entry_source, $8, $9, $10)
                on conflict (tenant_id, idempotency_key) do nothing
                returning """ + _RUN_COLUMNS,
                run_id, tenant_id, agent, environment, invoked_by,
                agent_principal, entry_source, digest(requirement), title,
                idempotency_key,
            )

            if row is None:
                # Conflict: someone already submitted this. Return theirs.
                row = await conn.fetchrow(
                    f"select {_RUN_COLUMNS} from public.runs "
                    f"where idempotency_key = $1",
                    idempotency_key,
                )
                log.info(
                    "run_idempotent_hit",
                    tenant_id=tenant_id,
                    idempotency_key=idempotency_key,
                    existing_run_id=row["run_id"] if row else None,
                )

        return dict(row) if row else {}

    async def count_by_status(self, tenant_id: str) -> dict[str, int]:
        """How many runs sit in each status. The sidebar and the home strip."""
        async with self._db.tenant_scope(tenant_id) as conn:
            rows = await conn.fetch(
                "select status::text as status, count(*)::int as n "
                "from public.runs group by 1"
            )
        return {r["status"]: r["n"] for r in rows}

    async def runs_by_source(self, tenant_id: str) -> dict[str, int]:
        """Runs per entry point, for adoption. Which of the six doors is load-bearing."""
        async with self._db.tenant_scope(tenant_id) as conn:
            rows = await conn.fetch(
                "select entry_source::text as source, count(*)::int as n "
                "from public.runs group by 1"
            )
        return {r["source"]: r["n"] for r in rows}

    # ---------------------------------------------------------------- approvals

    async def get_approvals(self, tenant_id: str, run_id: str) -> list[dict[str, Any]]:
        """Every decision recorded against a run, newest first. The audit trail
        the run detail shows next to the span tree."""
        async with self._db.tenant_scope(tenant_id) as conn:
            rows = await conn.fetch(
                """
                select approval_id, approved, artifact_digest, approved_by, comment,
                       decided_at
                from public.approvals
                where run_id = $1
                order by decided_at desc
                """,
                run_id,
            )
        return [dict(r) for r in rows]

    async def record_approval(
        self,
        tenant_id: str,
        *,
        run_id: str,
        approved: bool,
        artifact_digest: str,
        approved_by: str,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """Record a human decision against a specific artifact.

        `artifact_digest` is what the reviewer actually saw. It is stored, not
        recomputed: recomputing it here would re-bind the approval to whatever the
        artifact is *now*, which is precisely the bug ADR-0002 §5 forbids.

        Approval and the run's status move in one transaction. A recorded approval
        with the run still sitting in `awaiting_approval` is a run that blocks
        forever while the audit log says someone unblocked it.
        """
        async with self._db.tenant_scope(tenant_id) as conn:
            row = await conn.fetchrow(
                """
                insert into public.approvals (
                    tenant_id, run_id, approved, artifact_digest, approved_by, comment
                )
                values ($1, $2, $3, $4, $5, $6)
                returning approval_id, run_id, approved, artifact_digest,
                          approved_by, decided_at
                """,
                tenant_id, run_id, approved, artifact_digest, approved_by, comment,
            )

            await conn.execute(
                """
                update public.runs
                   set status = $2::run_status
                 where run_id = $1 and status = 'awaiting_approval'
                """,
                run_id,
                "running" if approved else "rejected",
            )

        log.info(
            "approval_recorded",
            tenant_id=tenant_id,
            run_id=run_id,
            approved=approved,
            approved_by=approved_by,
            artifact_digest=artifact_digest,
        )
        return dict(row)

    async def acceptance_stats(self, tenant_id: str, days: int = 7) -> dict[str, Any]:
        """Acceptance rate, never reported alone.

        Returns clean-accept and median edit ratio alongside it, and `n`, because
        an 80% rate over five runs is noise and that is exactly the number that
        reaches a slide (see `evaluation/acceptance.py`).
        """
        async with self._db.tenant_scope(tenant_id) as conn:
            row = await conn.fetchrow(
                """
                select
                  count(*)                                        as n,
                  count(*) filter (where accepted)                as accepted,
                  count(*) filter (where accepted
                                     and human_edit_lines = 0)    as clean_accepted,
                  coalesce(
                    percentile_cont(0.5) within group (
                      order by case when generated_lines > 0
                               then least(human_edit_lines::numeric
                                          / generated_lines, 1)
                               else 0 end
                    ), 0)                                         as median_edit_ratio
                from public.run_outcomes
                where recorded_at > now() - ($1 || ' days')::interval
                """,
                str(days),
            )
        return dict(row)
