"""Entry Points API. One endpoint, six doors.

Every front door in the architecture -- Portal, Databricks, VS Code, Power BI,
Teams, API/CLI -- submits through `POST /v1/entry/runs`. There is no per-door
endpoint and there will not be one.

The reason is governance, not tidiness. Approval gating, the permission
intersection and trace attribution are all applied here. A door with its own path
is a door where one of those three quietly does not happen, and it will be the door
someone reaches for when the approval gate is inconvenient.

What a door gets to vary is `source`, and `source` is recorded rather than trusted:
it attributes the run and drives adoption metrics, but it never affects
authorisation. Claiming to be the CLI does not shed the permission cap.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

import structlog
from adp_contracts import (
    ENTRY_POINTS,
    AgentPrincipal,
    EntryRequest,
    EntrySource,
    digest,
)
from fastapi import APIRouter, Depends, HTTPException

from control_plane.api.deps import runs_repo
from control_plane.store.runs import RunRepository
from control_plane.store.tenant_context import TenantContext, require_tenant

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/entry", tags=["entry"])


@router.get("/points")
async def list_entry_points() -> dict[str, Any]:
    """The six front doors.

    Unauthenticated on purpose: this is presentation metadata with nothing
    tenant-specific in it, and the shell needs it before a session exists so the
    entry screen renders on first paint rather than after a round trip.
    """
    return {
        "entry_points": [
            {
                "source": ep.source.value,
                "label": ep.label,
                "caption": ep.caption,
                "interactive": ep.interactive,
            }
            for ep in ENTRY_POINTS
        ]
    }


@router.post("/runs", status_code=202)
async def submit_run(
    request: EntryRequest,
    tenant: Annotated[TenantContext, Depends(require_tenant)],
    runs: Annotated[RunRepository, Depends(runs_repo)],
) -> dict[str, Any]:
    """Accept a run request from any front door and queue it.

    202, not 201: the run is queued, not done. A door that gets 201 back will tell
    its user the pipeline was built, and the first thing they will do is look for
    something that does not exist yet.

    What is queued is a row in `runs` with the requirement reduced to its digest.
    Picking it up is the orchestrator's job (Month 2); until then the execution
    plane's `claim` route returns nothing and the run waits, visibly, in the list.
    """
    entry_point = request.entry_point

    # An interactive door must present a human. Rejected rather than downgraded to
    # unattended -- silently treating it as a scheduled run would drop the
    # permission intersection (ADR-0002 section 4), which is the cap that stops an
    # agent exceeding its invoker.
    if request.requires_invoking_human and tenant.is_execution_plane:
        raise HTTPException(
            status_code=403,
            detail=(
                f"{entry_point.label} is an interactive entry point and requires a "
                f"user identity; this token is a service principal"
            ),
        )

    # Unattended submissions must be idempotent. A Teams retry or a re-run CLI
    # command otherwise becomes two pipelines writing the same target.
    if not entry_point.interactive and request.idempotency_key is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "automation entry points must supply an idempotency_key; without "
                "one a retried submission creates a duplicate run"
            ),
        )

    # The principal a run acts as is derived, never supplied (ADR-0002).
    principal = AgentPrincipal(
        agent_type=request.agent_type,
        tenant_id=tenant.tenant_id,
        environment=request.environment,
    )
    run_id = f"run_{uuid.uuid4().hex[:12]}"

    row = await runs.create_run(
        tenant.tenant_id,
        run_id=run_id,
        agent=request.agent_type.value,
        environment=request.environment.value,
        invoked_by=tenant.display_name,
        agent_principal=principal.name,
        entry_source=request.source.value,
        requirement=request.requirement,
        title=request.title,
        idempotency_key=request.idempotency_key,
    )

    log.info(
        "entry_run_submitted",
        tenant_id=tenant.tenant_id,
        run_id=row.get("run_id", run_id),
        source=request.source.value,
        agent_type=request.agent_type.value,
        environment=request.environment.value,
        invoked_by=tenant.user_object_id,
        # The requirement itself stays in the tenant; the digest is enough to
        # deduplicate identical asks without reading them (ADR-0003 section 3).
        requirement_digest=digest(request.requirement),
        idempotency_key=request.idempotency_key,
    )

    return {
        "run_id": row.get("run_id", run_id),
        "status": row.get("status", "queued"),
        "entry_point": entry_point.label,
        "requires_approval": request.environment.value == "prod",
    }


@router.get("/adoption")
async def entry_adoption(
    tenant: Annotated[TenantContext, Depends(require_tenant)],
    runs: Annotated[RunRepository, Depends(runs_repo)],
) -> dict[str, Any]:
    """Runs per entry point, for this tenant.

    Worth measuring from day one. Six front doors is a large surface for a small
    team, and this is the data that says which of them are load-bearing and which
    are a maintenance cost nobody uses. Expect at least one of the six to be dead
    weight by Month 5 -- better to find out from this endpoint than from a support
    ticket about a door we forgot we shipped.
    """
    counts = await runs.runs_by_source(tenant.tenant_id)
    return {
        "tenant_id": tenant.tenant_id,
        "by_source": {source.value: counts.get(source.value, 0) for source in EntrySource},
    }
