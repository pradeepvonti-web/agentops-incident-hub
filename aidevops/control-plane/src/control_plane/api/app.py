"""Control plane API.

Two distinct audiences, deliberately separated:

  * `/v1/runs`, `/v1/entry`   -- the **unified shell**, called by humans in a browser
                                 with a Supabase Auth session (ADR-0005).
  * `/v1/agent`               -- the **execution plane**, called by agent runtimes
                                 in customer subscriptions with a workload identity.

The `/v1/agent` routes are the only ones a customer's network reaches, and they are
all *outbound from the customer* (ADR-0001): the runtime polls us for work and posts
telemetry. We never call into their network, so there is no inbound path to secure
on their side -- which is the whole reason their network team signs off quickly.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated, Any

import structlog
from adp_contracts import AgentType, EntrySource, Environment, RunStatus
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from control_plane.api.deps import runs_repo
from control_plane.api.entry import router as entry_router
from control_plane.auth.supabase import SupabaseIdentity
from control_plane.evaluation.acceptance import MIN_MEANINGFUL_SAMPLE
from control_plane.settings import Settings
from control_plane.store.database import Database
from control_plane.store.runs import RunRepository
from control_plane.store.tenant_context import (
    TenantContext,
    require_execution_plane,
    require_tenant,
)

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Wire identity and the database from the environment.

    Both are optional at startup so `uv run pytest` and a fresh clone work with
    nothing configured; the routes that need them answer 503 and say which
    variable is missing.
    """
    settings = Settings.from_env()
    app.state.settings = settings
    app.state.identity = None
    app.state.db = None
    app.state.runs = None

    if settings.supabase_url and settings.supabase_publishable_key:
        app.state.identity = SupabaseIdentity(
            settings.supabase_url, settings.supabase_publishable_key
        )
    else:
        log.warning(
            "identity_not_configured", hint="set SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY"
        )

    if settings.database_url:
        db = Database(settings.database_url)
        await db.connect()
        app.state.db = db
        app.state.runs = RunRepository(db)
    else:
        log.warning("database_not_configured", hint="set DATABASE_URL")

    yield

    if app.state.identity is not None:
        await app.state.identity.aclose()
    if app.state.db is not None:
        await app.state.db.close()


app = FastAPI(
    title="AI DevOps Platform - Control Plane",
    version="0.1.0",
    description="Multi-tenant control plane. Holds no customer data (ADR-0001).",
    lifespan=lifespan,
)

# The unified shell is a browser on another origin. Credentials travel in the
# Authorization header, not cookies, so no allow_credentials.
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(Settings.from_env().allowed_origins),
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Entry Points: all six front doors submit through this one router.
app.include_router(entry_router)

#: Execution-plane versions we still accept. ADR-0001 commits us to the current
#: version plus the previous two minors, because the runtime upgrades on the
#: customer's schedule, not ours.
SUPPORTED_EXECUTION_PLANE_VERSIONS = {"0.1.0"}

Tenant = Annotated[TenantContext, Depends(require_tenant)]
Runs = Annotated[RunRepository, Depends(runs_repo)]


# ------------------------------------------------------------------ portal API

class RunSummary(BaseModel):
    """A row in the shell's runs list."""

    run_id: str
    agent_type: AgentType
    environment: Environment
    status: RunStatus
    entry_source: EntrySource
    title: str = Field(description="Short human label, given at submission")
    invoked_by: str
    created_at: datetime
    duration_seconds: int | None = None
    awaiting_approval: bool = False


class RunDetail(BaseModel):
    run: RunSummary
    #: Metadata tier only: digests, timing, decisions. The columns are spelled out
    #: in the repository, so a payload column cannot arrive here by being added to
    #: the table (ADR-0003).
    spans: list[dict[str, Any]]
    #: What an approver is deciding on: the result digest of the latest successful
    #: generate step. None until the agent has produced something.
    artifact_digest: str | None
    approvals: list[dict[str, Any]]


class ApprovalDecision(BaseModel):
    """A human's answer at an approve step.

    `artifact_digest` is required and is what binds the decision to specific
    content (ADR-0002 section 5). A decision without it would be an approval of a
    run, which is exactly the thing we refuse to build.
    """

    approved: bool
    artifact_digest: str = Field(min_length=1)
    comment: str | None = None


class AcceptanceStats(BaseModel):
    n: int
    accepted: int
    clean_accepted: int
    median_edit_ratio: float
    acceptance_rate: float
    clean_accept_rate: float
    #: Below MIN_MEANINGFUL_SAMPLE the rates are noise. The shell shows them
    #: greyed with the n, never as a headline.
    meaningful: bool


class RunStats(BaseModel):
    by_status: dict[str, int]
    acceptance: AcceptanceStats


def _summary(row: dict[str, Any]) -> RunSummary:
    started, ended = row.get("started_at"), row.get("ended_at")
    duration = int((ended - started).total_seconds()) if started and ended else None
    return RunSummary(
        run_id=row["run_id"],
        agent_type=row["agent"],
        environment=row["environment"],
        status=row["status"],
        entry_source=row["entry_source"],
        title=row.get("title") or row["run_id"],
        invoked_by=row["invoked_by"],
        created_at=row["created_at"],
        duration_seconds=duration,
        awaiting_approval=row["status"] == RunStatus.AWAITING_APPROVAL,
    )


def _artifact_digest(spans: list[dict[str, Any]]) -> str | None:
    """The digest a reviewer is shown: the newest successful generate step."""
    for span in reversed(spans):
        if span.get("step") == "generate" and span.get("status") == "succeeded":
            return span.get("result_digest") or None
    return None


@app.get("/v1/runs", response_model=list[RunSummary])
async def list_runs(
    tenant: Tenant,
    runs: Runs,
    status: RunStatus | None = None,
    agent_type: AgentType | None = None,
    environment: Environment | None = None,
    limit: int = Query(default=50, le=200),
) -> list[RunSummary]:
    """Runs for the caller's tenant, newest first.

    Tenant scoping is enforced in the store by PostgreSQL RLS, not by a `WHERE`
    clause here -- application code cannot forget what it cannot write (ADR-0001).
    """
    rows = await runs.list_runs(
        tenant.tenant_id,
        status=status.value if status else None,
        agent=agent_type.value if agent_type else None,
        environment=environment.value if environment else None,
        limit=limit,
    )
    return [_summary(r) for r in rows]


@app.get("/v1/runs/stats", response_model=RunStats)
async def run_stats(tenant: Tenant, runs: Runs) -> RunStats:
    """The home strip. Acceptance is never reported alone (ADR-0003 section 5)."""
    by_status = await runs.count_by_status(tenant.tenant_id)
    a = await runs.acceptance_stats(tenant.tenant_id)
    n = int(a.get("n") or 0)
    accepted = int(a.get("accepted") or 0)
    clean = int(a.get("clean_accepted") or 0)
    return RunStats(
        by_status=by_status,
        acceptance=AcceptanceStats(
            n=n,
            accepted=accepted,
            clean_accepted=clean,
            median_edit_ratio=float(a.get("median_edit_ratio") or 0.0),
            acceptance_rate=accepted / n if n else 0.0,
            clean_accept_rate=clean / n if n else 0.0,
            meaningful=n >= MIN_MEANINGFUL_SAMPLE,
        ),
    )


@app.get("/v1/runs/{run_id}", response_model=RunDetail)
async def get_run(run_id: str, tenant: Tenant, runs: Runs) -> RunDetail:
    """One run with its span tree, for the run detail view.

    The span tree is the metadata tier only. Payloads -- prompts, generated code,
    diffs -- live in the customer's subscription and the shell links out to them
    rather than proxying them (ADR-0003 section 3).
    """
    row = await runs.get_run(tenant.tenant_id, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="run not found")
    spans = await runs.get_spans(tenant.tenant_id, run_id)
    approvals = await runs.get_approvals(tenant.tenant_id, run_id)
    return RunDetail(
        run=_summary(row),
        spans=spans,
        artifact_digest=_artifact_digest(spans),
        approvals=approvals,
    )


@app.post("/v1/runs/{run_id}/approval")
async def submit_approval(
    run_id: str,
    decision: ApprovalDecision,
    tenant: Tenant,
    runs: Runs,
) -> dict[str, Any]:
    """Record a human decision and release the run.

    Authenticated as the human, never the agent. The approving identity, the exact
    digest and the timestamp are all recorded (ADR-0002 section 5). The digest the
    reviewer saw must still be the digest on record: if the agent regenerated in
    between, the decision is refused rather than silently re-bound.
    """
    if not tenant.may_approve:
        raise HTTPException(
            status_code=403,
            detail=(
                f"role {tenant.role!r} may not decide approvals; approver or admin required"
            ),
        )

    row = await runs.get_run(tenant.tenant_id, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="run not found")
    if row["status"] != RunStatus.AWAITING_APPROVAL:
        raise HTTPException(
            status_code=409, detail=f"run is {row['status']}, not awaiting approval"
        )

    current = _artifact_digest(await runs.get_spans(tenant.tenant_id, run_id))
    if current is None:
        raise HTTPException(status_code=409, detail="run has no artifact to decide on")
    if decision.artifact_digest != current:
        raise HTTPException(
            status_code=409,
            detail="artifact changed after it was reviewed; reload and decide again",
        )

    recorded = await runs.record_approval(
        tenant.tenant_id,
        run_id=run_id,
        approved=decision.approved,
        artifact_digest=decision.artifact_digest,
        approved_by=tenant.user_object_id,
        comment=decision.comment,
    )
    log.info(
        "approval_submitted",
        tenant_id=tenant.tenant_id,
        run_id=run_id,
        approved=decision.approved,
        artifact_digest=decision.artifact_digest,
        approved_by=tenant.user_object_id,
    )
    return {
        **recorded,
        "status": RunStatus.RUNNING if decision.approved else RunStatus.REJECTED,
    }


# ----------------------------------------------------------- execution plane API

Agent = Annotated[TenantContext, Depends(require_execution_plane)]


class WorkClaim(BaseModel):
    execution_plane_version: str
    environment: Environment
    capacity: int = Field(default=1, ge=1, le=10)


@app.post("/v1/agent/claim")
async def claim_work(claim: WorkClaim, tenant: Agent) -> dict[str, Any]:
    """Execution plane polls for queued runs.

    This is the outbound-only connection from ADR-0001. Long-poll, not webhook:
    a webhook would require inbound access into the customer's network, which is
    the thing we are avoiding.

    STUB -- Month 1.
    """
    if claim.execution_plane_version not in SUPPORTED_EXECUTION_PLANE_VERSIONS:
        raise HTTPException(
            status_code=426,
            detail=(
                f"execution plane {claim.execution_plane_version} is no longer "
                f"supported; supported: {sorted(SUPPORTED_EXECUTION_PLANE_VERSIONS)}"
            ),
        )

    log.info(
        "work_claimed",
        tenant_id=tenant.tenant_id,
        version=claim.execution_plane_version,
        environment=claim.environment,
    )
    return {"runs": []}


@app.post("/v1/agent/spans")
async def ingest_spans(spans: list[dict[str, Any]], tenant: Agent) -> dict[str, Any]:
    """Metadata-tier span ingest.

    Rejects any span carrying a field from the payload tier. The exporter should
    never send one -- `Span.for_control_plane()` cannot construct one -- so a
    rejection here means a client is not using the sanctioned path, and that is
    worth failing loudly over rather than quietly accepting.
    """
    forbidden = {"arguments", "result", "prompt", "completion", "payload"}
    for span in spans:
        leaked = forbidden & set(span.get("tool_call", {}))
        leaked |= forbidden & set(span.get("llm_call", {}))
        leaked |= forbidden & set(span)
        if leaked:
            log.error(
                "payload_tier_field_rejected",
                tenant_id=tenant.tenant_id,
                fields=sorted(leaked),
                span_id=span.get("span_id"),
            )
            raise HTTPException(
                status_code=422,
                detail=(
                    f"span contains payload-tier fields {sorted(leaked)}; the "
                    f"control plane does not accept them (ADR-0003)"
                ),
            )

    log.info("spans_ingested", tenant_id=tenant.tenant_id, count=len(spans))
    return {"accepted": len(spans)}


@app.post("/v1/agent/outcomes")
async def record_outcome(outcome: dict[str, Any], tenant: Agent) -> dict[str, Any]:
    """Acceptance-rate record. One per run (ADR-0003 section 5). STUB -- Month 1."""
    log.info(
        "outcome_recorded",
        tenant_id=tenant.tenant_id,
        run_id=outcome.get("run_id"),
        accepted=outcome.get("accepted"),
    )
    return {"recorded": True}


# ------------------------------------------------------------------ operational

@app.get("/health")
async def health() -> dict[str, Any]:
    state = app.state
    return {
        "status": "ok",
        "time": datetime.now(UTC).isoformat(),
        "supported_execution_plane_versions": sorted(SUPPORTED_EXECUTION_PLANE_VERSIONS),
        "identity_configured": getattr(state, "identity", None) is not None,
        "database_configured": getattr(state, "db", None) is not None,
    }
