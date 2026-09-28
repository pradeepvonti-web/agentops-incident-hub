"""Policy engine tests.

These are security tests, not feature tests. Each one corresponds to a claim we
will make to the design partner's security review, so a failure here means we have
told someone something untrue.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from adp_contracts import AgentType, Environment, ToolDecision
from mcp_gateway.policy import PolicyEngine

POLICY = Path(__file__).parents[1] / "policy" / "agents.yaml"


@pytest.fixture
def engine() -> PolicyEngine:
    return PolicyEngine(POLICY)


def _evaluate(engine: PolicyEngine, **overrides):
    defaults = dict(
        agent_type=AgentType.DATA_ENGINEERING,
        agent_principal="agent-data-engineering-acme-dev",
        environment=Environment.DEV,
        tool_name="uc_list_tables",
        arguments={"catalog": "bronze", "schema": "sales"},
        user_can=True,
        run_has_approval=False,
    )
    return engine.evaluate(**{**defaults, **overrides})


# --------------------------------------------------------------- default deny

def test_unknown_agent_is_denied(engine: PolicyEngine) -> None:
    result = _evaluate(engine, agent_type="nonexistent-agent")
    assert result.decision is ToolDecision.DENY_NOT_ALLOWLISTED


def test_tool_not_in_agent_allowlist_is_denied(engine: PolicyEngine) -> None:
    # The orchestrator has no tools at all, by design.
    result = _evaluate(engine, agent_type=AgentType.ORCHESTRATOR)
    assert result.decision is ToolDecision.DENY_NOT_ALLOWLISTED


def test_orchestrator_has_no_tools(engine: PolicyEngine) -> None:
    assert engine.tools_for(AgentType.ORCHESTRATOR) == []


def test_never_expose_tools_are_denied_for_every_agent(engine: PolicyEngine) -> None:
    for agent in AgentType:
        for tool in engine.never_expose:
            result = _evaluate(engine, agent_type=agent, tool_name=tool)
            assert result.decision is ToolDecision.DENY_NOT_ALLOWLISTED, (
                f"{agent} was not denied {tool}"
            )


def test_never_expose_tools_appear_in_no_allowlist(engine: PolicyEngine) -> None:
    """The stronger claim: they are absent, not merely gated (ADR-0002 section 6)."""
    for agent in AgentType:
        assert not set(engine.tools_for(agent)) & engine.never_expose


# ------------------------------------------------------- intersection rule

def test_agent_cannot_exceed_invoking_user(engine: PolicyEngine) -> None:
    """ADR-0002 section 4. The confused-deputy test."""
    result = _evaluate(engine, user_can=False)
    assert result.decision is ToolDecision.DENY_USER_PERMISSION
    assert "exceed the permissions" in (result.reason or "")


# ------------------------------------------------------------- constraints

def test_catalog_outside_allowlist_is_denied(engine: PolicyEngine) -> None:
    result = _evaluate(
        engine, arguments={"catalog": "gold", "schema": "finance"}
    )
    assert result.decision is ToolDecision.DENY_CONSTRAINT


def test_data_quality_agent_may_read_gold(engine: PolicyEngine) -> None:
    """Different agents genuinely have different reach -- the point of per-agent
    identity. DQ reads gold; data-engineering does not."""
    result = _evaluate(
        engine,
        agent_type=AgentType.DATA_QUALITY,
        agent_principal="agent-data-quality-acme-dev",
        arguments={"catalog": "gold", "schema": "finance"},
    )
    assert result.allowed


def test_job_submission_is_dev_only(engine: PolicyEngine) -> None:
    """ADR-0002 Amendment 1: submit_job is the agent's dev iteration loop, not a
    deployment path. Deployment goes through a bundle and the customer's CI/CD.

    Note this is denied even *with* an approval. Approval does not unlock a
    deployment route we have deliberately chosen not to own."""
    args = {"target": "silver.sales_clean", "num_workers": 2}

    assert _evaluate(
        engine, tool_name="databricks_submit_job", arguments=args
    ).allowed

    for env in (Environment.TEST, Environment.PROD):
        denied = _evaluate(
            engine,
            environment=env,
            tool_name="databricks_submit_job",
            arguments=args,
            run_has_approval=True,
        )
        assert denied.decision is ToolDecision.DENY_CONSTRAINT, (
            f"submit_job should be denied in {env} even with an approval"
        )


def test_deploy_tools_are_absent_not_gated(engine: PolicyEngine) -> None:
    """The customer's pipeline deploys. We do not have a deploy tool to gate."""
    for tool in ("databricks_bundle_deploy", "databricks_bundle_destroy",
                 "databricks_bundle_run"):
        assert tool in engine.never_expose
        for agent in AgentType:
            assert tool not in engine.tools_for(agent)


def test_bundle_validate_is_allowed_in_every_environment(engine: PolicyEngine) -> None:
    """The plan step writes nothing, so it is safe everywhere -- and a reviewer
    needs the prod plan before approving a promotion."""
    for env in (Environment.DEV, Environment.TEST, Environment.PROD):
        result = _evaluate(
            engine,
            environment=env,
            tool_name="databricks_bundle_validate",
            arguments={"bundle_root": "pipelines", "target": str(env)},
        )
        assert result.allowed, f"bundle validate should be allowed in {env}"


def test_cluster_size_is_capped(engine: PolicyEngine) -> None:
    result = _evaluate(
        engine,
        tool_name="databricks_submit_job",
        arguments={"target": "silver.sales", "num_workers": 64},
    )
    assert result.decision is ToolDecision.DENY_CONSTRAINT
    assert "limit is 8" in (result.reason or "")


def test_target_outside_bronze_silver_is_denied(engine: PolicyEngine) -> None:
    result = _evaluate(
        engine,
        tool_name="databricks_submit_job",
        arguments={"target": "gold.revenue", "num_workers": 2},
    )
    assert result.decision is ToolDecision.DENY_CONSTRAINT


def test_agent_cannot_write_to_protected_branch(engine: PolicyEngine) -> None:
    result = _evaluate(
        engine,
        tool_name="git_open_pull_request",
        arguments={"branch": "main", "base": "main", "files": []},
    )
    assert result.decision is ToolDecision.DENY_CONSTRAINT


def test_agent_may_open_pr_targeting_main(engine: PolicyEngine) -> None:
    """Targeting main is the whole point; only writing to it is refused."""
    result = _evaluate(
        engine,
        tool_name="git_open_pull_request",
        arguments={"branch": "agent/add-sales-pipeline", "base": "main", "files": []},
    )
    assert result.allowed


def test_oversized_changeset_is_denied(engine: PolicyEngine) -> None:
    result = _evaluate(
        engine,
        tool_name="git_open_pull_request",
        arguments={
            "branch": "agent/huge",
            "base": "main",
            "files": [{"path": f"f{i}.py", "content": ""} for i in range(40)],
        },
    )
    assert result.decision is ToolDecision.DENY_CONSTRAINT


# ------------------------------------------------------------- rate limiting

def test_rate_limit_eventually_denies(engine: PolicyEngine) -> None:
    principal = "agent-data-engineering-acme-dev"
    limit = 300  # data-engineering override in agents.yaml

    for _ in range(limit):
        assert _evaluate(engine, agent_principal=principal).allowed

    blocked = _evaluate(engine, agent_principal=principal)
    assert blocked.decision is ToolDecision.DENY_RATE_LIMIT


def test_rate_limit_is_per_principal(engine: PolicyEngine) -> None:
    """One noisy agent must not exhaust another's budget."""
    for _ in range(300):
        _evaluate(engine, agent_principal="agent-data-engineering-acme-dev")

    other = _evaluate(
        engine,
        agent_type=AgentType.DATA_QUALITY,
        agent_principal="agent-data-quality-acme-dev",
        arguments={"catalog": "gold", "schema": "finance"},
    )
    assert other.allowed
