"""Talking to the MCP Gateway from the runtime.

In production these are separate processes: the runtime speaks MCP over stdio to
a gateway running beside it. For a local CLI run we construct the Gateway
in-process instead.

That is a transport shortcut, not a policy shortcut, and the distinction is the
whole point. The call still goes through `Gateway.call_tool`, so it is still
authorised by the policy engine, still bound to an agent principal, still
subject to the on-behalf-of intersection, and still traced -- including when it
is denied. A convenience path that called `git_open_pull_request` directly would
be faster to write and would quietly invalidate every claim the architecture
makes.

`open_pull_request` below deliberately does not pass `run_has_approval`. Opening
a pull request needs no approval -- it *is* the request for one.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import mcp_gateway
import structlog
from adp_contracts import Environment, Run
from mcp_gateway.auth.on_behalf_of import (
    StaticPermissionResolver,
    developer_permissions,
)
from mcp_gateway.server import Gateway

log = structlog.get_logger(__name__)

#: Ships with the gateway; the same file the security review reads.
#:
#: Located relative to the installed `mcp_gateway` package rather than by
#: walking up from this file. Counting `..` across two sibling packages is a
#: path that silently breaks the moment anyone moves a directory, and it breaks
#: at startup of every local run rather than anywhere obvious.
DEFAULT_POLICY = (
    Path(mcp_gateway.__file__).resolve().parents[2] / "policy" / "agents.yaml"
)


class GatewayConfigError(RuntimeError):
    """Configuration is missing or unsafe for the requested environment."""


def build_local_gateway(run: Run, traces, *, policy_path: Path | None = None) -> Gateway:
    """An in-process Gateway for local runs. Dev only.

    Refuses outside dev on purpose. The permission resolver here is static --
    the invoking user's real Unity Catalog grants are not looked up -- so the
    ADR-0002 intersection rule is approximated rather than enforced. That is
    acceptable on a developer's laptop and is not acceptable anywhere else.
    """
    if run.environment is not Environment.DEV:
        raise GatewayConfigError(
            f"build_local_gateway is dev-only; this run targets "
            f"{run.environment}. Outside dev the runtime must talk to a "
            f"deployed gateway with a real permission resolver (ADR-0002)."
        )

    path = policy_path or DEFAULT_POLICY
    if not path.exists():
        raise GatewayConfigError(f"policy file not found at {path}")

    return Gateway(
        tenant_id=run.tenant_id,
        environment=run.environment,
        databricks_host=os.environ.get("ADP_DATABRICKS_HOST", ""),
        policy_path=path,
        permission_resolver=StaticPermissionResolver(developer_permissions()),
        trace_emitter=traces,
        azure_devops_org=os.environ.get("ADP_AZDO_ORG", ""),
        azure_devops_project=os.environ.get("ADP_AZDO_PROJECT", ""),
    )


async def open_pull_request(
    gateway: Gateway,
    run: Run,
    *,
    repository: str,
    branch: str,
    base: str,
    title: str,
    rationale: str,
    files: list[dict[str, str]],
    bundle_summary: str | None = None,
) -> dict[str, Any]:
    """Open a pull request through the gateway.

    Returns the gateway's verdict envelope rather than raising: a policy denial
    is information the caller should report, not an exception it should catch.
    A denial here means the agent tried something its policy forbids -- an
    oversized changeset, a protected branch -- and the reason is worth showing.
    """
    result = await gateway.call_tool(
        agent_type=run.agent_type,
        invoked_by=run.principal.invoked_by,
        run_id=run.run_id,
        tool_name="git_open_pull_request",
        arguments={
            "repository": repository,
            "branch": branch,
            "base": base,
            "title": title,
            "rationale": rationale,
            "files": files,
            **({"bundle_summary": bundle_summary} if bundle_summary else {}),
        },
    )

    if result.get("ok"):
        log.info(
            "pull_request_opened",
            run_id=run.run_id,
            url=result.get("result", {}).get("url"),
        )
    else:
        log.warning(
            "pull_request_refused",
            run_id=run.run_id,
            error_class=result.get("error_class"),
            error=result.get("error"),
        )
    return result
