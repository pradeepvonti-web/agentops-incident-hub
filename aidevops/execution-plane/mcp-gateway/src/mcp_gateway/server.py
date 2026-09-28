"""MCP Gateway server -- the single mediated path from agents to enterprise systems.

Every tool call an agent makes passes through `call_tool` below, and that function
does four things in a fixed order:

    1. authorise  (policy engine + on-behalf-of intersection)
    2. acquire    (short-lived token for the agent principal)
    3. execute    (the tool itself)
    4. record     (a span, whatever happened -- including denials)

Step 4 happens on every path, including the denial paths. A denied tool call is a
security signal and an agent-quality signal, and a gateway that only traces
successes cannot tell you either. There is no early return that skips it.
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from adp_contracts import (
    AgentPrincipal,
    AgentType,
    Environment,
    RunPrincipal,
    Span,
    StepKind,
    StepStatus,
    ToolCall,
    ToolDecision,
)

from mcp_gateway.auth.credentials import build_credential_provider
from mcp_gateway.auth.on_behalf_of import (
    PermissionResolver,
    StaticPermissionResolver,
    UnityCatalogPermissionResolver,
    developer_permissions,
)
from mcp_gateway.policy import PolicyEngine
from mcp_gateway.tools.base import ToolContext, ToolError, build_default_registry
from mcp_gateway.trace_emitter import TraceEmitter, build_trace_emitter

log = structlog.get_logger(__name__)




class Gateway:
    """Holds the policy, credentials, tools and trace emitter for one process."""

    def __init__(
        self,
        *,
        tenant_id: str,
        environment: Environment,
        databricks_host: str,
        policy_path: Path,
        permission_resolver: PermissionResolver,
        trace_emitter: TraceEmitter,
        azure_devops_org: str = "",
        azure_devops_project: str = "",
    ) -> None:
        self.tenant_id = tenant_id
        self.environment = environment
        self.databricks_host = databricks_host
        self.azure_devops_org = azure_devops_org
        self.azure_devops_project = azure_devops_project
        self.policy = PolicyEngine(policy_path)
        self.registry = build_default_registry()
        self.credentials = build_credential_provider(environment)
        self.permissions = permission_resolver
        self.traces = trace_emitter

        self._assert_safe_configuration()

    def _assert_safe_configuration(self) -> None:
        """Fail at startup rather than at the first prod tool call.

        Both of these have bitten real platforms: a dev shortcut that survived into
        production, and a tool that exists in code but was never reviewed into
        policy.
        """
        if self.environment is not Environment.DEV and isinstance(
            self.permissions, StaticPermissionResolver
        ):
            raise RuntimeError(
                "StaticPermissionResolver is dev-only. Outside dev the invoking "
                "user's permissions must be resolved for real (ADR-0002 section 4)."
            )

        registered = set(self.registry.names())
        policied = {
            name
            for agent in AgentType
            for name in self.policy.tools_for(agent)
        }
        orphans = registered - policied - self.policy.never_expose
        if orphans:
            raise RuntimeError(
                f"tools are implemented but appear in no agent policy: "
                f"{sorted(orphans)}. Add them to policy/agents.yaml or to "
                f"never_expose, so the security review sees a complete picture."
            )

    # ------------------------------------------------------------------ listing

    def list_tools(self, agent_type: AgentType) -> list[dict[str, Any]]:
        """Tools this agent may call. Policy-filtered, so an agent never sees a
        tool it cannot use."""
        allowed = self.policy.tools_for(agent_type)
        return [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.input_schema,
            }
            for t in self.registry.subset(allowed)
        ]

    # ------------------------------------------------------------------ calling

    async def call_tool(
        self,
        *,
        agent_type: AgentType,
        invoked_by: str,
        run_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        run_has_approval: bool = False,
    ) -> dict[str, Any]:
        """Authorise, execute and record one tool call."""
        step_id = f"step-{uuid.uuid4().hex[:12]}"
        started = datetime.now(UTC)
        t0 = time.monotonic()

        agent = AgentPrincipal(
            agent_type=agent_type,
            tenant_id=self.tenant_id,
            environment=self.environment,
        )
        principal = RunPrincipal(agent=agent, invoked_by=invoked_by)

        def record(
            decision: ToolDecision,
            *,
            reason: str | None = None,
            status: StepStatus,
            result: Any = None,
            error_class: str | None = None,
        ) -> None:
            span = Span(
                span_id=step_id,
                name=f"tool:{tool_name}",
                started_at=started,
                ended_at=datetime.now(UTC),
                status=status,
                error_class=error_class,
                tenant_id=self.tenant_id,
                run_id=run_id,
                agent_type=str(agent_type),
                agent_principal=agent.name,
                environment=str(self.environment),
                invoked_by=invoked_by,
                step_kind=StepKind.TOOL,
                tool_call=ToolCall(
                    tool_name=tool_name,
                    decision=decision,
                    policy_reason=reason,
                    duration_ms=int((time.monotonic() - t0) * 1000),
                    arguments=arguments,
                    result=result,
                ),
            )
            self.traces.emit(span)

        # 1 -- authorise -----------------------------------------------------
        try:
            user_permissions = self.permissions.resolve(principal)
            user_can = user_permissions.permits(tool_name=tool_name, arguments=arguments)
        except NotImplementedError as exc:
            record(
                ToolDecision.DENY_USER_PERMISSION,
                reason=str(exc),
                status=StepStatus.FAILED,
                error_class="obo_unresolved",
            )
            return {"ok": False, "error": str(exc), "error_class": "obo_unresolved"}

        verdict = self.policy.evaluate(
            agent_type=agent_type,
            agent_principal=agent.name,
            environment=self.environment,
            tool_name=tool_name,
            arguments=arguments,
            user_can=user_can,
            run_has_approval=run_has_approval,
        )

        if not verdict.allowed:
            log.warning(
                "tool_call_denied",
                run_id=run_id,
                agent_principal=agent.name,
                tool_name=tool_name,
                decision=verdict.decision.value,
                reason=verdict.reason,
            )
            record(
                verdict.decision,
                reason=verdict.reason,
                status=StepStatus.FAILED,
                error_class=verdict.decision.value,
            )
            return {
                "ok": False,
                "error": verdict.reason,
                "error_class": verdict.decision.value,
                "retryable": False,
            }

        tool = self.registry.get(tool_name)
        if tool is None:
            # Policy allows it but nothing implements it -- a configuration bug,
            # not an agent mistake. _assert_safe_configuration catches the reverse.
            record(
                ToolDecision.DENY_NOT_ALLOWLISTED,
                reason="tool is in policy but not implemented",
                status=StepStatus.FAILED,
                error_class="tool_not_implemented",
            )
            return {
                "ok": False,
                "error": f"{tool_name} is not implemented",
                "error_class": "tool_not_implemented",
            }

        # 2 -- acquire -------------------------------------------------------
        # Lazily, and per scope: a tool that never touches Azure DevOps never
        # causes an Azure DevOps token to be minted. The provider caches per
        # (principal, scope) for the token's own lifetime.
        def get_token(scope: str) -> str:
            return self.credentials.token_for(agent, scope).token

        ctx = ToolContext(
            principal=principal,
            run_id=run_id,
            step_id=step_id,
            tenant_id=self.tenant_id,
            databricks_host=self.databricks_host,
            get_token=get_token,
            azure_devops_org=self.azure_devops_org,
            azure_devops_project=self.azure_devops_project,
        )

        # 3 -- execute -------------------------------------------------------
        try:
            result = await tool.handler(ctx, **arguments)
        except ToolError as exc:
            record(
                ToolDecision.ALLOW,
                status=StepStatus.FAILED,
                error_class=exc.error_class,
            )
            return {
                "ok": False,
                "error": str(exc),
                "error_class": exc.error_class,
                "retryable": exc.retryable,
            }
        except Exception as exc:  # noqa: BLE001 - unexpected failures must still trace
            log.exception("tool_call_crashed", tool_name=tool_name, run_id=run_id)
            record(
                ToolDecision.ALLOW,
                status=StepStatus.FAILED,
                error_class=type(exc).__name__,
            )
            return {
                "ok": False,
                "error": "the tool failed unexpectedly",
                "error_class": type(exc).__name__,
                "retryable": False,
            }

        # 4 -- record --------------------------------------------------------
        record(ToolDecision.ALLOW, status=StepStatus.SUCCEEDED, result=result)
        return {"ok": True, "result": result}


def build_gateway_from_env() -> Gateway:
    """Construct a Gateway from environment configuration.

    Terraform sets these in the container app; see
    infra/terraform/execution-plane/main.tf.
    """
    tenant_id = os.environ["ADP_TENANT_ID"]
    environment = Environment(os.environ.get("ADP_ENVIRONMENT", "dev"))
    databricks_host = os.environ["ADP_DATABRICKS_HOST"]
    policy_path = Path(
        os.environ.get("ADP_POLICY_PATH", Path(__file__).parents[3] / "policy" / "agents.yaml")
    )

    if environment is Environment.DEV:
        resolver: PermissionResolver = StaticPermissionResolver(developer_permissions())
    else:
        resolver = UnityCatalogPermissionResolver(
            databricks_host=databricks_host, tenant_id=tenant_id
        )

    return Gateway(
        tenant_id=tenant_id,
        environment=environment,
        databricks_host=databricks_host,
        policy_path=policy_path,
        permission_resolver=resolver,
        trace_emitter=build_trace_emitter(tenant_id=tenant_id, environment=environment),
        azure_devops_org=os.environ.get("ADP_AZDO_ORG", ""),
        azure_devops_project=os.environ.get("ADP_AZDO_PROJECT", ""),
    )


def main() -> int:
    """Entry point. Serves MCP over stdio.

    STUB -- Month 1. The Gateway class above is complete and unit-tested; what
    remains is binding it to the `mcp` package's stdio server, which needs the
    agent's identity to arrive per-session. The plan: the runtime passes
    agent_type and invoked_by in the MCP initialize params, and the session
    holds them -- an agent cannot choose its own identity per call.
    """
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )
    gateway = build_gateway_from_env()
    log.info(
        "gateway_ready",
        tenant_id=gateway.tenant_id,
        environment=str(gateway.environment),
        tools=gateway.registry.names(),
    )
    log.error("stdio_server_not_implemented", detail="see main() docstring")
    return 1


if __name__ == "__main__":
    sys.exit(main())
