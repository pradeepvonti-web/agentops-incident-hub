"""The agent execution loop. Implements the seven-step execution plane.

    plan -> tool -> generate -> validate -> approve -> deploy -> monitor

Three properties this loop must have, and the reasons they are structural rather
than best-effort:

  * **Every step emits a span.** Including failures, including denials. Acceptance
    rate and failure diagnosis both come from the trace (ADR-0003), and a loop that
    only traces its happy path cannot produce either.
  * **Checkpoints before side effects.** A retry after a partially-applied deploy is
    the worst failure mode available to us, so the checkpoint goes in before the
    step that can change the world, not after.
  * **Approval binds to content.** The human approves a specific artifact digest.
    If the artifact changes after approval, the approval is void -- otherwise
    "approved" degrades into "was approved once, for something".
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

import structlog
from adp_contracts import (
    Run,
    RunOutcome,
    RunStatus,
    Span,
    StepKind,
    StepStatus,
    digest,
)

log = structlog.get_logger(__name__)


class TraceEmitter(Protocol):
    def emit(self, span: Span) -> None: ...


class GatewayClient(Protocol):
    async def call_tool(
        self, *, tool_name: str, arguments: dict[str, Any], run_has_approval: bool
    ) -> dict[str, Any]: ...


@dataclass
class Artifact:
    """What the agent produced, and what a human approves.

    `content_digest` is the binding identity. Approval is recorded against it, and
    `ApprovalGate` refuses a deploy whose artifact no longer matches.
    """

    files: list[dict[str, str]] = field(default_factory=list)
    rationale: str = ""
    #: Output of `bundle validate`, carried into the pull request body so a
    #: reviewer sees the effect of the change and not only its diff.
    bundle_summary: str | None = None

    @property
    def content_digest(self) -> str:
        return digest(sorted((f["path"], f["content"]) for f in self.files))

    @property
    def line_count(self) -> int:
        return sum(f["content"].count("\n") + 1 for f in self.files)


@dataclass
class StepResult:
    status: StepStatus
    error_class: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status is StepStatus.SUCCEEDED


class AgentLoop:
    """Runs one `Run` through the execution plane."""

    def __init__(
        self,
        *,
        run: Run,
        gateway: GatewayClient,
        traces: TraceEmitter,
        max_attempts: int = 3,
    ) -> None:
        self.run = run
        self.gateway = gateway
        self.traces = traces
        self.max_attempts = max_attempts

        self.artifact = Artifact()
        self.approved_digest: str | None = None
        self._checkpoints: list[str] = []

    # ------------------------------------------------------------------ tracing

    def _span(
        self,
        kind: StepKind,
        *,
        status: StepStatus,
        started: datetime,
        attempt: int = 1,
        error_class: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.traces.emit(
            Span(
                span_id=f"step-{uuid.uuid4().hex[:12]}",
                parent_span_id=self.run.run_id,
                name=f"step:{kind}",
                started_at=started,
                ended_at=datetime.now(UTC),
                status=status,
                error_class=error_class,
                tenant_id=self.run.tenant_id,
                run_id=self.run.run_id,
                agent_type=str(self.run.agent_type),
                agent_principal=self.run.principal.agent.name,
                environment=str(self.run.environment),
                invoked_by=self.run.principal.invoked_by,
                step_kind=kind,
                attempt=attempt,
                checkpoint_id=self._checkpoints[-1] if self._checkpoints else None,
                payload=payload or {},
            )
        )

    def _checkpoint(self, label: str) -> str:
        """Record a resumable point. Taken *before* anything irreversible."""
        cid = f"ckpt-{len(self._checkpoints):02d}-{label}"
        self._checkpoints.append(cid)
        log.info("checkpoint", run_id=self.run.run_id, checkpoint_id=cid)
        return cid

    # -------------------------------------------------------------------- steps

    async def plan(self) -> StepResult:
        """Decide what to do. STUB -- Month 1.

        Wiring note: this is where the model call goes, and where registry assets
        are pulled in as context. `RunRequest.registry_asset_hints` carries the
        caller's suggestions; whatever is actually used must be recorded so
        `RunOutcome.registry_assets_used` can prove or disprove the reuse thesis
        (ADR-0003 section 5).
        """
        started = datetime.now(UTC)
        self._span(
            StepKind.PLAN,
            status=StepStatus.SUCCEEDED,
            started=started,
            payload={"requirement": self.run.request.requirement},
        )
        return StepResult(StepStatus.SUCCEEDED, data={"steps": []})

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> StepResult:
        """One gateway-mediated action.

        The gateway emits its own span for the tool call itself, so this method
        does not duplicate it -- it only translates the gateway's verdict into a
        loop-level result.
        """
        response = await self.gateway.call_tool(
            tool_name=tool_name,
            arguments=arguments,
            run_has_approval=self.approved_digest is not None,
        )

        if response.get("ok"):
            return StepResult(StepStatus.SUCCEEDED, data=response.get("result", {}))

        return StepResult(
            StepStatus.FAILED,
            error_class=response.get("error_class"),
            data={
                "error": response.get("error"),
                "retryable": response.get("retryable", False),
            },
        )

    async def generate(self) -> StepResult:
        """Produce the artifact. STUB -- Month 1."""
        started = datetime.now(UTC)
        self._span(StepKind.GENERATE, status=StepStatus.SUCCEEDED, started=started)
        return StepResult(StepStatus.SUCCEEDED)

    async def validate(self) -> StepResult:
        """Tests and checks before a human is asked to look.

        Validation runs before approval on purpose: a human's attention is the
        scarcest resource in this loop, and asking them to review output that does
        not compile spends it badly.

        `databricks_bundle_validate` is the right primitive here rather than
        anything we would build: it is the native plan operation, it resolves
        every target-specific variable, and it is the same command the
        customer's reviewer already runs. A failure comes back as diagnostics
        rather than an exception, so the loop can feed it into a regenerate
        attempt instead of dying.

        STUB -- Month 1. Remaining: call the tool, and gate the approve step
        on `valid == True`.
        """
        started = datetime.now(UTC)
        self._span(StepKind.VALIDATE, status=StepStatus.SUCCEEDED, started=started)
        return StepResult(StepStatus.SUCCEEDED)

    async def request_approval(self) -> StepResult:
        """Pause for a human. The run stops here until the portal answers.

        Returns AWAITING_APPROVAL rather than blocking: the runtime is not a
        long-lived process holding state across a human's lunch break. The control
        plane resumes the run from the checkpoint when the decision arrives.
        """
        started = datetime.now(UTC)
        self._checkpoint("pre-approval")

        self._span(
            StepKind.APPROVE,
            status=StepStatus.AWAITING_APPROVAL,
            started=started,
            payload={"artifact_digest": self.artifact.content_digest},
        )
        self.run.status = RunStatus.AWAITING_APPROVAL
        return StepResult(
            StepStatus.AWAITING_APPROVAL,
            data={"artifact_digest": self.artifact.content_digest},
        )

    def record_approval(self, *, approved_digest: str, approved_by: str) -> bool:
        """Accept a human decision, binding it to exact content (ADR-0002 section 5).

        Returns False if the artifact changed after the human looked at it. That is
        not an edge case to smooth over -- it means the thing approved is not the
        thing about to deploy.
        """
        if approved_digest != self.artifact.content_digest:
            log.error(
                "approval_digest_mismatch",
                run_id=self.run.run_id,
                approved=approved_digest,
                current=self.artifact.content_digest,
                detail="artifact changed after approval; approval is void",
            )
            return False

        self.approved_digest = approved_digest
        log.info(
            "approval_recorded",
            run_id=self.run.run_id,
            approved_by=approved_by,
            artifact_digest=approved_digest,
        )
        return True

    async def deploy(self) -> StepResult:
        """Hand off to the customer's CI/CD. Refuses without a current approval.

        Note what this does NOT do: it does not run `bundle deploy`. That is
        the customer's pipeline (ADR-0002 Amendment 1). This step records that
        the artifact was approved and the pull request is ready to merge --
        the handoff point, not the deployment itself.
        """
        started = datetime.now(UTC)

        if self.run.requires_approval and self.approved_digest is None:
            self._span(
                StepKind.DEPLOY,
                status=StepStatus.FAILED,
                started=started,
                error_class="approval_required",
            )
            return StepResult(StepStatus.FAILED, error_class="approval_required")

        if (
            self.approved_digest is not None
            and self.approved_digest != self.artifact.content_digest
        ):
            # Belt and braces: record_approval already checks this, but the artifact
            # could change between approval and deploy.
            self._span(
                StepKind.DEPLOY,
                status=StepStatus.FAILED,
                started=started,
                error_class="approval_stale",
            )
            return StepResult(StepStatus.FAILED, error_class="approval_stale")

        self._checkpoint("pre-deploy")
        self._span(StepKind.DEPLOY, status=StepStatus.SUCCEEDED, started=started)
        return StepResult(StepStatus.SUCCEEDED)

    async def monitor(self) -> StepResult:
        """Watch the deployed artifact. STUB -- Month 1."""
        started = datetime.now(UTC)
        self._span(StepKind.MONITOR, status=StepStatus.SUCCEEDED, started=started)
        return StepResult(StepStatus.SUCCEEDED)

    # ------------------------------------------------------------------ outcome

    def record_outcome(
        self,
        *,
        accepted: bool,
        human_edit_lines: int = 0,
        rejection_reason: str | None = None,
        registry_assets_used: list[str] | None = None,
    ) -> RunOutcome:
        """Write the acceptance record. Exactly once per run (ADR-0003 section 5)."""
        outcome = RunOutcome(
            run_id=self.run.run_id,
            tenant_id=self.run.tenant_id,
            agent_type=str(self.run.agent_type),
            environment=str(self.run.environment),
            accepted=accepted,
            human_edit_lines=human_edit_lines,
            generated_lines=self.artifact.line_count,
            rejection_reason=rejection_reason,
            registry_assets_used=registry_assets_used or [],
        )
        log.info(
            "run_outcome",
            run_id=self.run.run_id,
            accepted=accepted,
            clean_accept=outcome.clean_accept,
            edit_ratio=round(outcome.edit_ratio, 3),
        )
        return outcome
