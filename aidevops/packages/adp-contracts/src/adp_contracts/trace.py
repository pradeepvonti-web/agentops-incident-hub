"""Trace contracts. Implements ADR-0003.

The span hierarchy is closed: `run` contains `step:*`, and a step contains
`tool_call` and `llm_call`. Adding a step kind requires an ADR, because the
evaluation queries and the portal run-detail view both assume this shape.

The privacy boundary lives here. `Span.for_control_plane()` is the *only* sanctioned
path for a span to leave the customer's subscription, and it is written to fail
closed: it constructs a new object from an allowlist rather than deleting fields from
this one. A field added to Span is invisible to the control plane until someone adds
it to that allowlist deliberately.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, Field, model_validator


def digest(value: Any) -> str:
    """Stable SHA-256 digest of an arbitrary JSON-serialisable value.

    Used so the control plane can tell "same tool, same arguments" across runs
    without seeing the arguments (ADR-0003 §3). Key order is normalised so two
    equivalent dicts always produce the same digest.
    """
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class StepKind(StrEnum):
    """The seven steps of the agent execution plane.

    These map 1:1 to the architecture diagram. The order here is the happy path.
    """

    PLAN = "plan"
    TOOL = "tool"
    GENERATE = "generate"
    VALIDATE = "validate"
    APPROVE = "approve"
    DEPLOY = "deploy"
    MONITOR = "monitor"


class StepStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REJECTED = "rejected"          # human said no at an approve step
    AWAITING_APPROVAL = "awaiting_approval"
    ROLLED_BACK = "rolled_back"


class ToolDecision(StrEnum):
    """Gateway authorisation outcome. Recorded for every tool call, including
    the denials — a denied call is a security signal and an agent-quality signal."""

    ALLOW = "allow"
    DENY_NOT_ALLOWLISTED = "deny_not_allowlisted"
    DENY_CONSTRAINT = "deny_constraint"
    DENY_USER_PERMISSION = "deny_user_permission"   # ADR-0002 §4 intersection rule
    DENY_RATE_LIMIT = "deny_rate_limit"
    DENY_APPROVAL_REQUIRED = "deny_approval_required"


#: Attributes every span must carry. Enforced at the collector and in CI.
REQUIRED_SPAN_ATTRIBUTES: frozenset[str] = frozenset(
    {
        "tenant_id",
        "run_id",
        "agent_type",
        "agent_principal",
        "environment",
        "invoked_by",
        "step_kind",
        "attempt",
    }
)


class ToolCall(BaseModel):
    """One MCP tool invocation.

    `arguments` and `result` never leave the tenant. `arguments_digest` and
    `result_digest` do.
    """

    tool_name: str
    decision: ToolDecision
    policy_reason: str | None = None
    duration_ms: int = 0

    arguments: dict[str, Any] | None = Field(default=None, exclude=True)
    result: Any | None = Field(default=None, exclude=True)

    arguments_digest: str = ""
    result_digest: str = ""

    @model_validator(mode="after")
    def _compute_digests(self) -> Self:
        if self.arguments is not None and not self.arguments_digest:
            object.__setattr__(self, "arguments_digest", digest(self.arguments))
        if self.result is not None and not self.result_digest:
            object.__setattr__(self, "result_digest", digest(self.result))
        return self


class LlmCall(BaseModel):
    """One model call. Cost and shape travel; prompt and completion do not."""

    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    cache_hit: bool = False

    prompt: str | None = Field(default=None, exclude=True)
    completion: str | None = Field(default=None, exclude=True)


class Span(BaseModel):
    """One node in a run's trace tree."""

    span_id: str
    parent_span_id: str | None = None
    name: str
    started_at: datetime
    ended_at: datetime | None = None
    status: StepStatus = StepStatus.RUNNING
    error_class: str | None = Field(
        default=None,
        description="Exception class or error taxonomy code. Travels to the control "
        "plane — it is how we diagnose without payloads (ADR-0003 consequences).",
    )

    # Required attributes (ADR-0003 §2)
    tenant_id: str
    run_id: str
    agent_type: str
    agent_principal: str
    environment: str
    invoked_by: str
    step_kind: StepKind
    attempt: int = 1
    checkpoint_id: str | None = None

    tool_call: ToolCall | None = None
    llm_call: LlmCall | None = None

    #: Free-form payload that stays in the tenant. Never exported.
    payload: dict[str, Any] = Field(default_factory=dict, exclude=True)

    @property
    def duration_ms(self) -> int | None:
        if self.ended_at is None:
            return None
        return int((self.ended_at - self.started_at).total_seconds() * 1000)

    def for_control_plane(self) -> dict[str, Any]:
        """Project this span down to what may cross the tenant boundary.

        Fail-closed by construction: this builds a new dict from an explicit
        allowlist. Any field added to Span is *excluded* from export until someone
        adds it here on purpose. Do not rewrite this as ``self.model_dump(exclude=...)``
        — that inverts the default and the next new field leaks silently.
        """
        out: dict[str, Any] = {
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_ms": self.duration_ms,
            "status": self.status.value,
            "error_class": self.error_class,
            "tenant_id": self.tenant_id,
            "run_id": self.run_id,
            "agent_type": self.agent_type,
            "agent_principal": self.agent_principal,
            "environment": self.environment,
            "invoked_by": self.invoked_by,
            "step_kind": self.step_kind.value,
            "attempt": self.attempt,
            "checkpoint_id": self.checkpoint_id,
        }

        if self.tool_call is not None:
            out["tool_call"] = {
                "tool_name": self.tool_call.tool_name,
                "decision": self.tool_call.decision.value,
                "policy_reason": self.tool_call.policy_reason,
                "duration_ms": self.tool_call.duration_ms,
                "arguments_digest": self.tool_call.arguments_digest,
                "result_digest": self.tool_call.result_digest,
            }

        if self.llm_call is not None:
            out["llm_call"] = {
                "model": self.llm_call.model,
                "tokens_in": self.llm_call.tokens_in,
                "tokens_out": self.llm_call.tokens_out,
                "cost_usd": self.llm_call.cost_usd,
                "duration_ms": self.llm_call.duration_ms,
                "cache_hit": self.llm_call.cache_hit,
            }

        return out

    def missing_required_attributes(self) -> set[str]:
        """Which required attributes are absent or empty. Checked at the collector."""
        present = {
            k for k in REQUIRED_SPAN_ATTRIBUTES if getattr(self, k, None) not in (None, "")
        }
        return set(REQUIRED_SPAN_ATTRIBUTES) - present
