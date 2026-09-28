"""Databricks job submission -- the agent's dev iteration loop. Dev only.

This is NOT a deployment path. Deployment goes through Databricks Asset Bundles
and the customer's own CI/CD (see `databricks_bundles.py` and ADR-0002
Amendment 1). This tool exists so the agent can try a transformation against dev
data before committing it to a bundle -- the equivalent of an engineer running a
cell before opening a pull request.

Policy pins it to `environments: ["dev"]`. An agent submitting ad-hoc job runs to
test or prod would route around the customer's approval gates and environment
parity, which is the exact problem bundles exist to solve.

Three containment decisions, enforced elsewhere but relied upon here:

  * The policy engine caps cluster size, target schema and environment.
  * The agent's Unity Catalog grants limit what the submitted code can touch, so
    even a prompt-injected job body cannot read a catalog it has no grant on.
  * The job runs as the agent principal, so every run is attributable.

That second point is why the agent identity work had to come before this tool.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from mcp_gateway.tools.base import Tool, ToolContext, ToolError

log = structlog.get_logger(__name__)

_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


async def databricks_submit_job(
    ctx: ToolContext,
    *,
    name: str,
    notebook_path: str,
    target: str,
    environment: str = "dev",
    num_workers: int = 2,
    parameters: dict[str, str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Submit a one-off Databricks job run.

    `dry_run` returns the exact payload that would be submitted without submitting
    it. The agent runtime uses this during the `validate` step so a human reviews
    the real request, not a description of it.
    """
    payload: dict[str, Any] = {
        "run_name": name,
        "tasks": [
            {
                "task_key": "main",
                "notebook_task": {
                    "notebook_path": notebook_path,
                    "base_parameters": {
                        **(parameters or {}),
                        "target": target,
                        "environment": environment,
                    },
                },
                "new_cluster": {
                    "spark_version": "15.4.x-scala2.12",
                    "node_type_id": "Standard_DS3_v2",
                    "num_workers": num_workers,
                    "data_security_mode": "SINGLE_USER",
                    # Runs as the agent principal, so Unity Catalog grants apply to
                    # whatever the notebook does.
                    "single_user_name": ctx.principal.agent.name,
                },
                "timeout_seconds": 3600,
            }
        ],
        # Tags make agent-submitted compute identifiable in the customer's cost
        # reporting. Enterprises ask for this in the first billing conversation.
        "tags": {
            "adp_run_id": ctx.run_id,
            "adp_agent": str(ctx.principal.agent.agent_type),
            "adp_environment": environment,
            "adp_invoked_by": ctx.principal.invoked_by,
        },
    }

    if dry_run:
        log.info("databricks_submit_job_dry_run", run_id=ctx.run_id, job_name=name)
        return {"dry_run": True, "would_submit": payload}

    log.info(
        "databricks_submit_job",
        run_id=ctx.run_id,
        agent_principal=ctx.principal.agent.name,
        job_name=name,
        target=target,
        environment=environment,
        num_workers=num_workers,
    )

    url = f"{ctx.databricks_host.rstrip('/')}/api/2.2/jobs/runs/submit"
    headers = {"Authorization": f"Bearer {ctx.access_token}"}

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.TimeoutException as exc:
        # Ambiguous: the job may or may not have been submitted. Non-retryable on
        # purpose -- a blind retry risks two clusters doing the same write. The
        # runtime surfaces this to a human.
        raise ToolError(
            "job submission timed out; the job may or may not have started. "
            "Check the Databricks jobs UI before retrying.",
            error_class="databricks_submit_timeout",
            retryable=False,
        ) from exc
    except httpx.HTTPError as exc:
        raise ToolError(
            "could not reach the Databricks jobs API",
            error_class="databricks_unreachable",
            retryable=True,
        ) from exc

    if response.status_code == 403:
        raise ToolError(
            "the agent principal may not submit jobs in this workspace",
            error_class="databricks_forbidden",
            retryable=False,
        )
    if response.status_code >= 400:
        raise ToolError(
            f"Databricks rejected the job submission ({response.status_code})",
            error_class="databricks_submit_rejected",
            retryable=response.status_code >= 500,
        )

    body = response.json()
    return {
        "run_id": body.get("run_id"),
        "job_name": name,
        "target": target,
        "environment": environment,
        "submitted_as": ctx.principal.agent.name,
    }


DATABRICKS_SUBMIT_JOB = Tool(
    name="databricks_submit_job",
    description=(
        "Run a notebook against DEV data to check a transformation works. This is "
        "your iteration loop, not a deployment: dev only, and nothing you submit "
        "here reaches test or prod. To ship work, write it into a Databricks Asset "
        "Bundle, validate it with databricks_bundle_validate, and open a pull "
        "request. The job runs as the agent's own identity, so Unity Catalog "
        "grants apply. Pass dry_run=true to see the exact payload without running."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Human-readable run name"},
            "notebook_path": {
                "type": "string",
                "description": "Workspace path of the notebook to execute",
            },
            "target": {
                "type": "string",
                "description": "Target table in catalog.schema.table form",
            },
            "environment": {
                "type": "string",
                "enum": ["dev"],
                "default": "dev",
                "description": "Dev only. Shipping to test or prod goes through a "
                "bundle and the customer's CI/CD.",
            },
            "num_workers": {"type": "integer", "default": 2},
            "parameters": {
                "type": "object",
                "additionalProperties": {"type": "string"},
                "description": "Base parameters passed to the notebook",
            },
            "dry_run": {
                "type": "boolean",
                "default": False,
                "description": "Return the submission payload without submitting",
            },
        },
        "required": ["name", "notebook_path", "target"],
    },
    handler=databricks_submit_job,
    mutating=True,
)
