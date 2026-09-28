"""Run contracts — the unit of work the orchestrator hands to the execution plane."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from adp_contracts.identity import AgentType, Environment, RunPrincipal


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"

    @property
    def is_terminal(self) -> bool:
        return self in {
            RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.REJECTED,
            RunStatus.CANCELLED, RunStatus.ROLLED_BACK,
        }


class RunRequest(BaseModel):
    """What a human (or the scheduler) asks an agent to do.

    `requirement` is natural language and stays in the tenant. The control plane
    stores only `requirement_digest` so the orchestrator can deduplicate identical
    requests without reading them (ADR-0003 §3).
    """

    agent_type: AgentType
    environment: Environment
    requirement: str = Field(exclude=True)
    requirement_digest: str = ""
    registry_asset_hints: list[str] = Field(
        default_factory=list,
        description="Registry asset ids the caller believes are relevant. The agent "
        "may ignore them; usage is recorded in RunOutcome.registry_assets_used so "
        "we can measure whether reuse actually improves acceptance (ADR-0003 §5).",
    )
    target_catalog: str | None = None
    target_schema: str | None = None


class Run(BaseModel):
    """A single agent invocation, from queue to terminal state."""

    run_id: str
    tenant_id: str
    principal: RunPrincipal
    request: RunRequest
    status: RunStatus = RunStatus.QUEUED
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    ended_at: datetime | None = None

    #: Execution-plane version that claimed this run. The control plane supports the
    #: current and previous two minor versions (ADR-0001 consequences).
    execution_plane_version: str | None = None

    #: Monotonic counter; the runtime resumes from the last checkpoint on retry.
    last_checkpoint_id: str | None = None

    @property
    def agent_type(self) -> AgentType:
        return self.request.agent_type

    @property
    def environment(self) -> Environment:
        return self.request.environment

    @property
    def requires_approval(self) -> bool:
        """Prod writes always need a human (ADR-0002 §6)."""
        return self.environment == Environment.PROD
