"""Pull-request wiring tests.

The claim under test: the runtime reaches Azure DevOps *through* the gateway,
so the PR call is authorised, identity-bound and traced like any other tool
call. A convenience path that called `git_open_pull_request` directly would be
faster to write and would quietly invalidate that claim.

The policy tests here construct a real `Gateway` with the real
`policy/agents.yaml`. They never reach Azure: a denial short-circuits before
credentials are acquired, which is itself part of what is being asserted.
"""

from __future__ import annotations

import pytest
from adp_contracts import (
    AgentPrincipal,
    AgentType,
    Environment,
    Run,
    RunPrincipal,
    RunRequest,
)
from agent_runtime.gateway import (
    DEFAULT_POLICY,
    GatewayConfigError,
    build_local_gateway,
    open_pull_request,
)


class RecordingEmitter:
    def __init__(self) -> None:
        self.spans: list = []

    def emit(self, span) -> None:
        self.spans.append(span)


class StubGateway:
    """Records the call the runtime makes, without executing anything."""

    def __init__(self, response: dict) -> None:
        self.response = response
        self.calls: list[dict] = []

    async def call_tool(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def _run(environment: Environment = Environment.DEV) -> Run:
    return Run(
        run_id="run_pr_test",
        tenant_id="acme",
        principal=RunPrincipal(
            agent=AgentPrincipal(
                agent_type=AgentType.DATA_ENGINEERING,
                tenant_id="acme",
                environment=environment,
            ),
            invoked_by="r.mehta",
        ),
        request=RunRequest(
            agent_type=AgentType.DATA_ENGINEERING,
            environment=environment,
            requirement="Build a Silver table",
        ),
    )


FILES = [{"path": "resources/orders.yml", "content": "resources: {}"}]


async def _open(gateway, **overrides):
    defaults = dict(
        repository="data-platform",
        branch="agent/sales-orders",
        base="main",
        title="Add sales orders pipeline",
        rationale="Implements the plan.",
        files=FILES,
    )
    return await open_pull_request(gateway, _run(), **{**defaults, **overrides})


# ------------------------------------------------------- goes via the gateway

async def test_pull_request_goes_through_call_tool() -> None:
    """Not around it. The whole architecture rests on this being true."""
    gateway = StubGateway({"ok": True, "result": {"pull_request_id": 42}})
    await _open(gateway)

    assert len(gateway.calls) == 1
    assert gateway.calls[0]["tool_name"] == "git_open_pull_request"


async def test_call_carries_the_agent_and_the_human() -> None:
    """ADR-0002 section 4: the gateway intersects agent permissions with the
    invoking user's, so it needs both identities."""
    gateway = StubGateway({"ok": True, "result": {}})
    await _open(gateway)

    call = gateway.calls[0]
    assert call["agent_type"] is AgentType.DATA_ENGINEERING
    assert call["invoked_by"] == "r.mehta"
    assert call["run_id"] == "run_pr_test"


async def test_opening_a_pr_does_not_claim_approval() -> None:
    """Opening a pull request needs no approval -- it *is* the request for one.
    Passing run_has_approval=True here would be claiming a human already said
    yes to something nobody has seen."""
    gateway = StubGateway({"ok": True, "result": {}})
    await _open(gateway)

    assert gateway.calls[0].get("run_has_approval") in (None, False)


async def test_bundle_summary_is_forwarded_when_present() -> None:
    gateway = StubGateway({"ok": True, "result": {}})
    await _open(gateway, bundle_summary="2 jobs, 1 pipeline")

    assert gateway.calls[0]["arguments"]["bundle_summary"] == "2 jobs, 1 pipeline"


async def test_bundle_summary_is_omitted_when_absent() -> None:
    """Sending an empty summary would put an empty 'Bundle plan' heading in the
    PR body, which reads as a tool that failed rather than one not used."""
    gateway = StubGateway({"ok": True, "result": {}})
    await _open(gateway)

    assert "bundle_summary" not in gateway.calls[0]["arguments"]


# ------------------------------------------------------------ denials return

async def test_a_denial_is_returned_not_raised() -> None:
    """A policy denial is information the caller reports, not an exception it
    catches. The reason is usually actionable."""
    gateway = StubGateway(
        {
            "ok": False,
            "error": "12 files changed, limit is 25",
            "error_class": "deny_constraint",
        }
    )
    result = await _open(gateway)

    assert not result["ok"]
    assert result["error_class"] == "deny_constraint"


# ------------------------------------------------------------ dev-only guard

def test_local_gateway_refuses_outside_dev() -> None:
    """The static permission resolver approximates the intersection rule rather
    than enforcing it. Fine on a laptop, not fine anywhere else."""
    for environment in (Environment.TEST, Environment.PROD):
        with pytest.raises(GatewayConfigError) as exc:
            build_local_gateway(_run(environment), RecordingEmitter())
        assert "dev-only" in str(exc.value)


def test_local_gateway_reports_a_missing_policy_file(tmp_path) -> None:
    with pytest.raises(GatewayConfigError) as exc:
        build_local_gateway(
            _run(), RecordingEmitter(), policy_path=tmp_path / "nope.yaml"
        )
    assert "policy file not found" in str(exc.value)


def test_default_policy_path_resolves() -> None:
    """The gateway ships its policy with the repository; if this path drifts,
    every local run fails at startup instead of at review time."""
    assert DEFAULT_POLICY.exists(), f"policy not found at {DEFAULT_POLICY}"


# --------------------------------------------- real policy, no Azure required

async def test_real_policy_denies_an_oversized_changeset() -> None:
    """Constructs a real Gateway with the shipped policy.

    Never reaches Azure: the denial short-circuits before credentials are
    acquired, which is the property that makes this test possible at all -- and
    is also the behaviour we want, since a refused call should cost nothing.
    """
    traces = RecordingEmitter()
    gateway = build_local_gateway(_run(), traces)

    result = await open_pull_request(
        gateway,
        _run(),
        repository="data-platform",
        branch="agent/too-big",
        base="main",
        title="Enormous change",
        rationale="Too much at once.",
        # Policy caps data-engineering at 25 files.
        files=[{"path": f"resources/j{i}.yml", "content": "x"} for i in range(40)],
    )

    assert not result["ok"]
    assert result["error_class"] == "deny_constraint"
    assert "limit is 25" in result["error"]


async def test_real_policy_denies_a_protected_branch() -> None:
    traces = RecordingEmitter()
    gateway = build_local_gateway(_run(), traces)

    result = await open_pull_request(
        gateway,
        _run(),
        repository="data-platform",
        branch="main",
        base="main",
        title="Straight to main",
        rationale="No.",
        files=FILES,
    )

    assert not result["ok"]
    assert result["error_class"] == "deny_constraint"


async def test_a_denial_is_traced() -> None:
    """A denied tool call is a security signal and an agent-quality signal.
    A gateway that only traces successes reports neither."""
    traces = RecordingEmitter()
    gateway = build_local_gateway(_run(), traces)

    await open_pull_request(
        gateway,
        _run(),
        repository="data-platform",
        branch="main",
        base="main",
        title="Straight to main",
        rationale="No.",
        files=FILES,
    )

    assert len(traces.spans) == 1
    span = traces.spans[0]
    assert span.tool_call is not None
    assert span.tool_call.tool_name == "git_open_pull_request"
    assert span.tool_call.decision.value.startswith("deny")
    assert span.agent_principal == "agent-data-engineering-acme-dev"
