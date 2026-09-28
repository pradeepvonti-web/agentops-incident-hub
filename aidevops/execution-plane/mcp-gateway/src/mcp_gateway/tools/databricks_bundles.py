"""Databricks Asset Bundle tools.

Bundles are the native deployment unit for Databricks. A serious shop keeps its
jobs as `resources/*.yml` alongside `source/*.py` under a `databricks.yml`, ships
them through its own CI/CD, and promotes a single `main` through dev -> test ->
prod behind approval gates.

So this is the agent's job: **produce bundle files and open a pull request.** Their
pipeline validates, their tech lead approves, their CD runs `bundle deploy`.

What is absent from this module is the point of it. There is no `bundle deploy`,
no `bundle destroy`, no `bundle run`. Those live on the never-expose list in
policy/agents.yaml. The agent generates; the customer's pipeline ships. That is a
better security posture than gating a deploy tool, and it is a much shorter
conversation than "your agent deploys to our production".

`bundle validate` earns its place because it is the *plan* step -- the native
"show me what this would produce" primitive, and the same command their reviewer
already runs. It writes nothing.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import structlog

from mcp_gateway.tools.base import Tool, ToolContext, ToolError

log = structlog.get_logger(__name__)

#: `bundle validate` on a large bundle resolves every resource. Nationwide run
#: thousands of jobs from one bundle; two minutes is not generous.
_VALIDATE_TIMEOUT_SECONDS = 120

#: Bundle roots the agent may operate on. Anchored to the run's checkout so a
#: crafted path cannot walk into the rest of the container filesystem.
_WORKSPACE_ROOT = Path(os.environ.get("ADP_WORKSPACE_ROOT", "/workspace"))


def _resolve_bundle_root(bundle_root: str) -> Path:
    """Resolve and confine a caller-supplied path to the run workspace.

    A tool that takes a path from a model is a path-traversal bug waiting to be
    written. Resolve first, then check containment on the resolved value --
    checking the raw string lets `..` and symlinks through.
    """
    candidate = (_WORKSPACE_ROOT / bundle_root).resolve()
    workspace = _WORKSPACE_ROOT.resolve()

    if not candidate.is_relative_to(workspace):
        raise ToolError(
            "bundle_root must be inside the run workspace",
            error_class="bundle_path_escape",
            retryable=False,
        )
    if not (candidate / "databricks.yml").exists() and not (
        candidate / "databricks.yaml"
    ).exists():
        raise ToolError(
            f"no databricks.yml found in {bundle_root!r}; a bundle root must "
            f"contain one",
            error_class="bundle_not_found",
            retryable=False,
        )
    return candidate


async def _run_cli(
    ctx: ToolContext, args: list[str], cwd: Path, timeout: int
) -> tuple[int, str, str]:
    """Invoke the Databricks CLI as the agent principal.

    No shell: arguments are passed as a list so nothing in a generated bundle can
    inject a command. Credentials go through the environment rather than argv,
    where they would show up in the process table.
    """
    env = {
        **os.environ,
        "DATABRICKS_HOST": ctx.databricks_host,
        "DATABRICKS_TOKEN": ctx.access_token,
        # Suppress the CLI's own prompts; a blocked prompt looks like a hang.
        "DATABRICKS_CLI_DO_NOT_TRACK": "1",
        "TERM": "dumb",
    }

    try:
        proc = await asyncio.create_subprocess_exec(
            "databricks",
            *args,
            cwd=str(cwd),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise ToolError(
            "the Databricks CLI is not installed in the execution plane image",
            error_class="databricks_cli_missing",
            retryable=False,
        ) from exc

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        raise ToolError(
            f"databricks {args[0]} {args[1] if len(args) > 1 else ''} did not "
            f"finish within {timeout}s",
            error_class="bundle_timeout",
            retryable=True,
        ) from None

    return (
        proc.returncode or 0,
        stdout.decode("utf-8", "replace"),
        stderr.decode("utf-8", "replace"),
    )


async def databricks_bundle_validate(
    ctx: ToolContext, *, bundle_root: str, target: str = "dev"
) -> dict[str, Any]:
    """Validate a bundle and return its resolved resources. Writes nothing.

    This is the agent's `validate` step and the reviewer's plan, in one command.
    A bundle that does not validate must never reach a pull request -- a human's
    attention is the scarcest resource in this loop and spending it on something
    that does not parse wastes it.
    """
    root = _resolve_bundle_root(bundle_root)

    log.info(
        "bundle_validate",
        run_id=ctx.run_id,
        agent_principal=ctx.principal.agent.name,
        bundle_root=bundle_root,
        target=target,
    )

    code, stdout, stderr = await _run_cli(
        ctx, ["bundle", "validate", "-t", target, "-o", "json"], root,
        _VALIDATE_TIMEOUT_SECONDS,
    )

    if code != 0:
        # A validation failure is information the agent can act on, not an
        # infrastructure error. Return it rather than raising so the loop can
        # feed it back into a regenerate attempt.
        return {
            "valid": False,
            "target": target,
            "diagnostics": (stderr or stdout).strip()[:4000],
        }

    try:
        resolved = json.loads(stdout) if stdout.strip() else {}
    except json.JSONDecodeError:
        raise ToolError(
            "bundle validate returned output that was not JSON",
            error_class="bundle_output_unparseable",
            retryable=False,
        ) from None

    resources = resolved.get("resources", {}) or {}
    return {
        "valid": True,
        "target": target,
        "bundle_name": (resolved.get("bundle") or {}).get("name"),
        "workspace_host": (resolved.get("workspace") or {}).get("host"),
        "resource_counts": {kind: len(items or {}) for kind, items in resources.items()},
        "jobs": sorted((resources.get("jobs") or {}).keys()),
        "pipelines": sorted((resources.get("pipelines") or {}).keys()),
        # Warnings matter: they are what a reviewer scans for first.
        "warnings": [
            line for line in (stderr or "").splitlines() if "Warning" in line
        ][:50],
    }


async def databricks_bundle_summary(
    ctx: ToolContext, *, bundle_root: str, target: str = "dev"
) -> dict[str, Any]:
    """What this bundle would produce in the target workspace. Read-only.

    Used to build the pull request body, so a reviewer sees the effect of the
    change rather than only its diff.
    """
    root = _resolve_bundle_root(bundle_root)

    log.info(
        "bundle_summary",
        run_id=ctx.run_id,
        agent_principal=ctx.principal.agent.name,
        target=target,
    )

    code, stdout, stderr = await _run_cli(
        ctx, ["bundle", "summary", "-t", target, "-o", "json"], root, 60
    )

    if code != 0:
        raise ToolError(
            f"bundle summary failed: {(stderr or stdout).strip()[:500]}",
            error_class="bundle_summary_failed",
            retryable=False,
        )

    try:
        return {"target": target, "summary": json.loads(stdout) if stdout.strip() else {}}
    except json.JSONDecodeError:
        raise ToolError(
            "bundle summary returned output that was not JSON",
            error_class="bundle_output_unparseable",
            retryable=False,
        ) from None


DATABRICKS_BUNDLE_VALIDATE = Tool(
    name="databricks_bundle_validate",
    description=(
        "Validate a Databricks Asset Bundle against a target environment and "
        "return its resolved resources. This is the plan step: it writes nothing "
        "and deploys nothing. Run it before opening a pull request -- a bundle "
        "that does not validate should never reach a human reviewer. If "
        "validation fails, the diagnostics come back so you can fix and retry."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "bundle_root": {
                "type": "string",
                "description": "Path to the bundle root (the directory holding "
                "databricks.yml), relative to the run workspace.",
            },
            "target": {
                "type": "string",
                "description": "Bundle target as named in databricks.yml",
                "default": "dev",
            },
        },
        "required": ["bundle_root"],
    },
    handler=databricks_bundle_validate,
    mutating=False,
)

DATABRICKS_BUNDLE_SUMMARY = Tool(
    name="databricks_bundle_summary",
    description=(
        "Show what a bundle would produce in the target workspace: jobs, "
        "pipelines and their resolved settings. Read-only. Use it to write the "
        "pull request body so a reviewer sees the effect of the change, not just "
        "the diff."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "bundle_root": {"type": "string"},
            "target": {"type": "string", "default": "dev"},
        },
        "required": ["bundle_root"],
    },
    handler=databricks_bundle_summary,
    mutating=False,
)
