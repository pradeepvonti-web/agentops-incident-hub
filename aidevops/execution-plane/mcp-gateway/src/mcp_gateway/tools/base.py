"""Tool base types and registry.

Every tool the agents can reach goes through here. The registry is the list a
security reviewer reads to answer "what can these things actually do", so tools are
registered explicitly -- there is no auto-discovery by module scan, because a tool
that appears by being imported is a tool nobody reviewed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

import structlog
from adp_contracts import RunPrincipal

from mcp_gateway import scopes

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ToolContext:
    """Everything a tool needs about who is calling and why.

    Carried explicitly rather than read from ambient state, so a tool cannot
    accidentally act as the wrong principal.

    Tokens are fetched lazily and per scope. A tool asks for the one system it
    talks to and gets a token for that system only, so a compromised Databricks
    token is not also a source-control token. Laziness matters too: most calls
    never touch Azure DevOps, and acquiring a token it will not use would put a
    second identity round trip on every tool call.
    """

    principal: RunPrincipal
    run_id: str
    step_id: str
    tenant_id: str
    databricks_host: str
    get_token: Callable[[str], str]

    #: Azure DevOps coordinates come from tenant configuration, never from the
    #: model. An agent that could name its own organisation could open a pull
    #: request into a repository nobody is watching.
    azure_devops_org: str = ""
    azure_devops_project: str = ""

    @property
    def environment(self) -> str:
        return str(self.principal.agent.environment)

    @property
    def access_token(self) -> str:
        """Databricks token. Most tools want this one."""
        return self.get_token(scopes.DATABRICKS)


class ToolError(Exception):
    """A tool failed in a way the agent may be able to reason about and retry.

    The message reaches the agent, so it must be actionable and must not contain
    credentials, tokens or connection strings.
    """

    def __init__(self, message: str, *, error_class: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.error_class = error_class
        self.retryable = retryable


class ToolHandler(Protocol):
    async def __call__(self, ctx: ToolContext, **kwargs: Any) -> Any: ...


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler
    #: Mutating tools are the ones that need approval gates and appear in audit
    #: summaries. Read-only tools do not.
    mutating: bool = False


@dataclass
class ToolRegistry:
    _tools: dict[str, Tool] = field(default_factory=dict)

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool {tool.name!r} is already registered")
        self._tools[tool.name] = tool
        log.debug("tool_registered", tool_name=tool.name, mutating=tool.mutating)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def subset(self, names: list[str]) -> list[Tool]:
        """Tools with the given names, in registry order.

        Used to build the per-agent tool list so an agent only ever sees what its
        policy allows (see `PolicyEngine.tools_for`).
        """
        wanted = set(names)
        return [t for n, t in sorted(self._tools.items()) if n in wanted]


def build_default_registry() -> ToolRegistry:
    """The v0 tool surface, deliberately small.

    Read metadata, iterate in dev, validate a bundle, open a pull request. That is
    the whole loop. Anything an agent wants beyond this needs a policy entry, a
    test, and a line in the security review.

    Note what is not here: no deploy. The agent produces Databricks Asset Bundle
    files and opens a pull request; the customer's own CI/CD validates, a human
    approves, and their CD runs `bundle deploy` (ADR-0002 Amendment 1).
    """
    from mcp_gateway.tools.databricks_bundles import (
        DATABRICKS_BUNDLE_SUMMARY,
        DATABRICKS_BUNDLE_VALIDATE,
    )
    from mcp_gateway.tools.databricks_jobs import DATABRICKS_SUBMIT_JOB
    from mcp_gateway.tools.git_pr import GIT_OPEN_PULL_REQUEST
    from mcp_gateway.tools.unity_catalog import UC_GET_TABLE_METADATA, UC_LIST_TABLES

    registry = ToolRegistry()
    registry.register(UC_LIST_TABLES)
    registry.register(UC_GET_TABLE_METADATA)
    registry.register(DATABRICKS_SUBMIT_JOB)
    registry.register(DATABRICKS_BUNDLE_VALIDATE)
    registry.register(DATABRICKS_BUNDLE_SUMMARY)
    registry.register(GIT_OPEN_PULL_REQUEST)
    return registry
