"""Data Engineering agent tests, with the model call stubbed.

What these cover: the wiring around the model -- span emission, cost
attribution, the error taxonomy, branch-prefix enforcement, and that the
conventions actually reach the system prompt.

What they cannot cover: whether Claude produces a good bundle. That needs a real
API key and an evaluation set (the Month 3 work). These tests prove the loop is
correctly built, not that the agent is any good -- two different claims, and
conflating them is how a team ships an agent nobody measured.
"""

from __future__ import annotations

from types import SimpleNamespace

import anthropic
import pytest
from adp_contracts import (
    AgentPrincipal,
    AgentType,
    Environment,
    Run,
    RunPrincipal,
    RunRequest,
    StepKind,
)
from agent_runtime.agents.data_engineering import (
    BundleArtifact,
    DataEngineeringAgent,
    GeneratedFile,
    PipelinePlan,
    PlanStep,
)
from agent_runtime.llm import LlmError, ModelClient, estimate_cost


class RecordingEmitter:
    def __init__(self) -> None:
        self.spans: list = []

    def emit(self, span) -> None:
        self.spans.append(span)


class StubMessages:
    """Stands in for `client.messages`, returning a canned parsed output."""

    def __init__(self, parsed, *, stop_reason="end_turn", raises=None) -> None:
        self._parsed = parsed
        self._stop_reason = stop_reason
        self._raises = raises
        self.calls: list[dict] = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self._raises is not None:
            raise self._raises
        return SimpleNamespace(
            parsed_output=self._parsed,
            stop_reason=self._stop_reason,
            stop_details=SimpleNamespace(category="cyber"),
            usage=SimpleNamespace(
                input_tokens=1200,
                output_tokens=800,
                cache_read_input_tokens=1000,
            ),
        )


class StubClient:
    def __init__(self, messages: StubMessages) -> None:
        self.messages = messages


PLAN = PipelinePlan(
    summary="Build a Silver table of sales orders keyed on delivery_id.",
    source_tables=["bronze.raw.orders"],
    target_table="silver.curated.sales_orders",
    grain="One row per delivery_id",
    steps=[PlanStep(order=1, action="Read bronze", detail="Explicit schema")],
    data_quality_checks=["delivery_id is never null"],
    open_questions=[],
)

ARTIFACT = BundleArtifact(
    branch_name="agent/silver-curated-sales-orders",
    pull_request_title="Add Silver sales_orders pipeline",
    rationale="Implements the plan.",
    files=[
        GeneratedFile(
            path="resources/sales_orders.yml", content="resources:\n  jobs: {}\n",
            purpose="Job definition",
        )
    ],
)


def _run() -> Run:
    return Run(
        run_id="run_test",
        tenant_id="acme",
        principal=RunPrincipal(
            agent=AgentPrincipal(
                agent_type=AgentType.DATA_ENGINEERING,
                tenant_id="acme",
                environment=Environment.DEV,
            ),
            invoked_by="r.mehta",
        ),
        request=RunRequest(
            agent_type=AgentType.DATA_ENGINEERING,
            environment=Environment.DEV,
            requirement="Build a Silver table for sales orders",
        ),
    )


def _agent(parsed, *, raises=None, stop_reason="end_turn", conventions=None):
    emitter = RecordingEmitter()
    messages = StubMessages(parsed, stop_reason=stop_reason, raises=raises)
    llm = ModelClient(run=_run(), traces=emitter, client=StubClient(messages))
    return DataEngineeringAgent(llm, conventions=conventions), emitter, messages, llm


# ---------------------------------------------------------------------- plan

def test_plan_returns_a_validated_model() -> None:
    agent, _, _, _ = _agent(PLAN)
    plan = agent.plan("Build a Silver table for sales orders")
    assert plan.target_table == "silver.curated.sales_orders"
    assert plan.data_quality_checks


def test_plan_emits_a_span_with_cost() -> None:
    agent, emitter, _, _ = _agent(PLAN)
    agent.plan("Build something")

    assert len(emitter.spans) == 1
    span = emitter.spans[0]
    assert span.step_kind is StepKind.PLAN
    assert span.llm_call is not None
    assert span.llm_call.model == "claude-opus-5"
    assert span.llm_call.cost_usd == pytest.approx(estimate_cost(1200, 800))
    assert span.llm_call.cache_hit is True


def test_missing_metadata_is_stated_not_hidden() -> None:
    """The agent is told to flag unknown schemas rather than invent them."""
    agent, _, messages, _ = _agent(PLAN)
    agent.plan("Build something", table_metadata="")

    prompt = messages.calls[0]["messages"][0]["content"]
    assert "No table metadata was supplied" in prompt
    assert "open_questions" in prompt


def test_supplied_metadata_reaches_the_prompt() -> None:
    agent, _, messages, _ = _agent(PLAN)
    agent.plan("Build something", table_metadata="orders: delivery_id bigint")

    prompt = messages.calls[0]["messages"][0]["content"]
    assert "delivery_id bigint" in prompt


# ------------------------------------------------------------------ generate

def test_generate_enforces_the_agent_branch_prefix() -> None:
    """Policy rejects a branch without the prefix. Failing here costs nothing;
    failing at the gateway costs a whole generate call."""
    stray = ARTIFACT.model_copy(update={"branch_name": "feature/sales-orders"})
    agent, _, _, _ = _agent(stray)

    artifact = agent.generate(PLAN)
    assert artifact.branch_name.startswith("agent/")


def test_generate_keeps_a_valid_branch_name() -> None:
    agent, _, _, _ = _agent(ARTIFACT)
    artifact = agent.generate(PLAN)
    assert artifact.branch_name == "agent/silver-curated-sales-orders"


def test_validation_feedback_reaches_the_retry_prompt() -> None:
    """A retry that does not carry the error is just the same call again."""
    agent, _, messages, _ = _agent(ARTIFACT)
    agent.generate(PLAN, attempt=2, validation_feedback="unknown field 'foo'")

    prompt = messages.calls[0]["messages"][0]["content"]
    assert "unknown field 'foo'" in prompt
    assert "Fix that specifically" in prompt


def test_generate_span_records_the_attempt() -> None:
    agent, emitter, _, _ = _agent(ARTIFACT)
    agent.generate(PLAN, attempt=3)
    assert emitter.spans[0].attempt == 3


# --------------------------------------------------------------- conventions

def test_conventions_reach_the_system_prompt() -> None:
    """The seam enterprise knowledge enters through. If this breaks, the
    registry stops affecting output and nobody notices except acceptance rate."""
    agent, _, messages, _ = _agent(PLAN, conventions="ACME NAMES TABLES LIKE THIS")
    agent.plan("Build something")

    system = messages.calls[0]["system"][0]["text"]
    assert "ACME NAMES TABLES LIKE THIS" in system


def test_system_prompt_is_cached() -> None:
    """The conventions block is identical across every run for a tenant, so it
    is the single largest cost lever in this loop."""
    agent, _, messages, _ = _agent(PLAN)
    agent.plan("Build something")

    assert messages.calls[0]["system"][0]["cache_control"] == {"type": "ephemeral"}


# ------------------------------------------------------------ error taxonomy

def _api_error(cls, status: int):
    """Build a real SDK exception.

    A SimpleNamespace will not do: the SDK's constructor reads
    `response.request`, so a fake response fails inside the exception rather
    than inside the code under test. anthropic 1.x is built on httpx2, not
    httpx -- an object from the httpx package is rejected at request time.
    """
    import httpx2

    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(status, request=request)
    return cls("boom", response=response, body=None)


def test_rate_limit_is_retryable() -> None:
    agent, _, _, _ = _agent(PLAN, raises=_api_error(anthropic.RateLimitError, 429))
    with pytest.raises(LlmError) as exc:
        agent.plan("Build something")
    assert exc.value.error_class == "llm_rate_limited"
    assert exc.value.retryable


def test_bad_request_is_not_retryable() -> None:
    """Usually our fault -- an oversized prompt or a rejected schema. Retrying
    without changing anything burns money to fail identically."""
    agent, _, _, _ = _agent(PLAN, raises=_api_error(anthropic.BadRequestError, 400))
    with pytest.raises(LlmError) as exc:
        agent.plan("Build something")
    assert exc.value.error_class == "llm_bad_request"
    assert not exc.value.retryable


def test_refusal_is_surfaced_not_parsed() -> None:
    """A refusal is HTTP 200 with no usable content. Reading output first turns
    it into a confusing attribute error three frames away from the cause."""
    agent, _, _, _ = _agent(PLAN, stop_reason="refusal")
    with pytest.raises(LlmError) as exc:
        agent.plan("Build something")
    assert exc.value.error_class == "llm_refusal"
    assert not exc.value.retryable


def test_truncated_output_is_not_retryable() -> None:
    """Hitting max_tokens truncates the structured object mid-write. Retrying
    with the same budget produces the same truncation."""
    agent, _, _, _ = _agent(ARTIFACT, stop_reason="max_tokens")
    with pytest.raises(LlmError) as exc:
        agent.generate(PLAN)
    assert exc.value.error_class == "llm_truncated"
    assert not exc.value.retryable


def test_failures_still_emit_a_span() -> None:
    """A loop that only traces success cannot explain a failure, and cost is
    incurred whether or not the call succeeded."""
    agent, emitter, _, _ = _agent(PLAN, stop_reason="refusal")
    with pytest.raises(LlmError):
        agent.plan("Build something")

    assert len(emitter.spans) == 1
    assert emitter.spans[0].error_class == "llm_refusal"


def test_cost_accumulates_across_calls() -> None:
    agent, _, _, llm = _agent(PLAN)
    agent.plan("one")
    agent.plan("two")
    assert llm.total_cost_usd == pytest.approx(estimate_cost(1200, 800) * 2)


# ------------------------------------------------------------------- privacy

def test_prompt_never_reaches_the_control_plane() -> None:
    """ADR-0003: the prompt is kept on the span for tenant-local debugging and
    excluded from the projection that crosses the boundary."""
    agent, emitter, _, _ = _agent(PLAN)
    agent.plan("SECRET_CUSTOMER_REQUIREMENT")

    span = emitter.spans[0]
    assert span.llm_call.prompt is not None
    assert "SECRET_CUSTOMER_REQUIREMENT" not in repr(span.for_control_plane())
