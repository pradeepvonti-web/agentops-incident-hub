"""Headless runner: requirement -> plan -> generate -> validate -> pull request.

    uv run adp-run "Build a Silver table for sales orders from bronze.raw.orders" \\
        --target silver.curated.sales_orders \\
        --validate --open-pr --repo data-platform

The point of a CLI before a UI: this is the loop that has to work. A portal
around a loop that works is a week of styling; a portal around a loop that does
not is a demo that lies.

Stages are opt-in cheapest-first, so you can stop at the one you trust today:

    --plan-only    stop after planning, before anything is generated
    (default)      plan + generate + write files locally
    --validate     also run `databricks bundle validate`, and let the agent
                   fix its own diagnostics for up to three attempts
    --open-pr      also open a pull request (requires --validate)

`--open-pr` requires `--validate` deliberately. A bundle that does not validate
must never reach a human reviewer: their attention is the scarcest resource in
this loop and spending it on something that does not resolve wastes it.

Nothing here deploys. The pull request is the handoff -- their CI validates,
a reviewer approves, their CD runs `bundle deploy` (ADR-0002 Amendment 1).

Output is deliberately plain ASCII. The first real run of this CLI died with
UnicodeEncodeError: the default Windows console is cp1252 and a box-drawing
character cannot be encoded to it, so the process crashed mid-print -- after the
work was done, before anything useful was shown.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import structlog
from adp_contracts import (
    AgentPrincipal,
    AgentType,
    Environment,
    Run,
    RunPrincipal,
    RunRequest,
)

from agent_runtime.agents.data_engineering import DataEngineeringAgent
from agent_runtime.gateway import (
    GatewayConfigError,
    build_local_gateway,
    open_pull_request,
)
from agent_runtime.llm import LlmError, ModelClient
from agent_runtime.pipeline import Attempt, build_bundle

log = structlog.get_logger(__name__)

NEWLINE = chr(10)


def _supports_colour() -> bool:
    """Whether to emit ANSI escapes.

    The default Windows console does not interpret them unless virtual terminal
    processing is enabled, so they print as literal garbage. Ask rather than
    assume: a pipe, NO_COLOR, or TERM=dumb all mean plain text.
    """
    # Not every stdout is reconfigurable (a pipe under some runners, an already
    # wrapped stream). Failing to widen the encoding is not worth failing over.
    with contextlib.suppress(AttributeError, OSError):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    return bool(
        sys.stdout.isatty()
        and not os.environ.get("NO_COLOR")
        and os.environ.get("TERM") != "dumb"
    )


COLOUR = _supports_colour()


def _bold(text: str) -> str:
    return f"\033[1m{text}\033[0m" if COLOUR else text


def _warn(text: str) -> str:
    return f"\033[33m{text}\033[0m" if COLOUR else text


def _error(text: str) -> str:
    return f"\033[31m{text}\033[0m" if COLOUR else text


class ConsoleTraceEmitter:
    """Collects spans and prints a cost summary.

    Stands in for the real emitter until the runtime is deployed. The span shape
    is identical, so what shows up here is what the control plane will receive --
    including the spans the gateway emits for tool calls and denials.
    """

    def __init__(self) -> None:
        self.spans: list = []

    def emit(self, span) -> None:
        self.spans.append(span)

    @property
    def llm_spans(self) -> list:
        return [s for s in self.spans if s.llm_call is not None]

    @property
    def total_cost(self) -> float:
        return sum(s.llm_call.cost_usd for s in self.llm_spans)

    @property
    def total_tokens(self) -> tuple[int, int]:
        return (
            sum(s.llm_call.tokens_in for s in self.llm_spans),
            sum(s.llm_call.tokens_out for s in self.llm_spans),
        )


def _build_run(requirement: str, environment: Environment, tenant: str) -> Run:
    agent = AgentPrincipal(
        agent_type=AgentType.DATA_ENGINEERING,
        tenant_id=tenant,
        environment=environment,
    )
    return Run(
        run_id=f"run_{uuid.uuid4().hex[:10]}",
        tenant_id=tenant,
        principal=RunPrincipal(agent=agent, invoked_by=os.environ.get("USER") or "cli"),
        request=RunRequest(
            agent_type=AgentType.DATA_ENGINEERING,
            environment=environment,
            requirement=requirement,
        ),
        started_at=datetime.now(UTC),
    )


def _rule(title: str) -> None:
    print(NEWLINE + _bold(title))
    print("-" * min(len(title) + 8, 72))


async def _databricks_validate(bundle_root: Path, target: str) -> tuple[bool, str]:
    """Run `databricks bundle validate` on what the agent just wrote."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "databricks",
            "bundle",
            "validate",
            "-t",
            target,
            cwd=str(bundle_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return False, "the Databricks CLI is not on PATH"

    stdout, stderr = await proc.communicate()
    return proc.returncode == 0, (stdout + stderr).decode("utf-8", "replace").strip()


def _print_attempt(attempt: Attempt) -> None:
    """Report each attempt as it happens, so a retry is visible rather than a
    mysterious pause."""
    if attempt.diagnostics == "not validated":
        return
    if attempt.valid:
        print(f"  attempt {attempt.number}: valid ({attempt.files} files)")
        return

    first_line = attempt.diagnostics.splitlines()[0] if attempt.diagnostics else ""
    print("  " + _warn(f"attempt {attempt.number}: invalid") + f"  {first_line[:80]}")


def _summary(traces: ConsoleTraceEmitter) -> None:
    tokens_in, tokens_out = traces.total_tokens
    _rule("COST")
    print(f"  {len(traces.llm_spans)} model call(s), {len(traces.spans)} span(s)")
    print(f"  {tokens_in:,} in  |  {tokens_out:,} out")
    print(f"  ${traces.total_cost:.4f}")


def _print_plan(plan) -> None:
    print(f"  {plan.summary}")
    print()
    print(f"  target  {plan.target_table}")
    print(f"  grain   {plan.grain}")
    if plan.source_tables:
        print(f"  sources {', '.join(plan.source_tables)}")
    print()

    for step in plan.steps:
        print(f"  {step.order}. {step.action}")
        print(f"     {step.detail}")

    if plan.data_quality_checks:
        print()
        print("  quality checks")
        for check in plan.data_quality_checks:
            print(f"   - {check}")

    if plan.open_questions:
        # Surfaced loudly. An agent that guesses at an ambiguous grain produces
        # a pipeline that is quietly wrong, which is worse than one that stops.
        print()
        print("  " + _warn("open questions - answer these before generating"))
        for question in plan.open_questions:
            print(f"   ? {question}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="adp-run",
        description="Run the Data Engineering agent end to end, headless.",
    )
    parser.add_argument("requirement", help="What to build, in plain language")
    parser.add_argument(
        "--target", default="", help="Target table, catalog.schema.table"
    )
    parser.add_argument(
        "--metadata-file",
        type=Path,
        help="File of Unity Catalog metadata to give the agent. Without it the "
        "agent will flag unknown schemas in open_questions, which is correct.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("./.agent-output"),
        help="Where to write the generated bundle files",
    )
    parser.add_argument(
        "--environment", default="dev", choices=[e.value for e in Environment]
    )
    parser.add_argument("--tenant", default="acme")
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run `databricks bundle validate` and let the agent fix its own "
        "diagnostics, up to three attempts",
    )
    parser.add_argument("--plan-only", action="store_true", help="Stop after planning")
    parser.add_argument(
        "--open-pr",
        action="store_true",
        help="Open a pull request through the MCP Gateway. Requires --validate.",
    )
    parser.add_argument("--repo", default="", help="Azure DevOps repository name")
    parser.add_argument("--base", default="main", help="Branch to merge into")
    parser.add_argument(
        "--conventions-file",
        type=Path,
        help="Conventions extracted from the customer's own repository "
        "(see adp-extract). Without it the agent follows generic defaults, "
        "and its output will look generic.",
    )
    args = parser.parse_args()

    if args.open_pr and not args.repo:
        parser.error("--open-pr requires --repo")
    if args.open_pr and not args.validate:
        # A bundle that does not validate must never reach a human reviewer.
        # Their attention is the scarcest resource in this loop.
        parser.error(
            "--open-pr requires --validate: do not send an unvalidated bundle "
            "to a reviewer"
        )
    if args.open_pr and args.plan_only:
        parser.error("--plan-only and --open-pr are mutually exclusive")

    return args


def main() -> int:
    args = _parse_args()

    # Warnings and above; the agent's own structured logs would drown the report.
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(30))

    requirement = args.requirement
    if args.target:
        requirement = f"{requirement}{NEWLINE}{NEWLINE}Target table: {args.target}"

    run = _build_run(requirement, Environment(args.environment), args.tenant)
    traces = ConsoleTraceEmitter()
    llm = ModelClient(run=run, traces=traces)
    conventions = None
    if args.conventions_file:
        conventions = args.conventions_file.read_text(encoding="utf-8")
        print(f"conventions from {args.conventions_file}")
    agent = DataEngineeringAgent(llm, conventions=conventions)

    metadata = ""
    if args.metadata_file:
        metadata = args.metadata_file.read_text(encoding="utf-8")

    print(f"run {run.run_id}  |  {run.agent_type}  |  {run.environment}")

    # ------------------------------------------------------------------ plan
    _rule("PLAN")
    try:
        plan = agent.plan(requirement, table_metadata=metadata)
    except LlmError as exc:
        print(f"  planning failed: {exc}  [{exc.error_class}]", file=sys.stderr)
        return 1

    _print_plan(plan)

    if args.plan_only:
        _summary(traces)
        return 0

    # ------------------------------------------------- generate and validate
    _rule("GENERATE")
    validator = _databricks_validate if args.validate else None

    try:
        build = asyncio.run(
            build_bundle(
                agent,
                plan,
                out_dir=args.out,
                target=args.environment,
                validator=validator,
                on_attempt=_print_attempt,
            )
        )
    except LlmError as exc:
        print(f"  generation failed: {exc}  [{exc.error_class}]", file=sys.stderr)
        return 1

    artifact = build.artifact
    print()
    for file in artifact.files:
        print(f"  {file.path}  ({file.content.count(NEWLINE) + 1} lines)")
        print(f"    {file.purpose}")

    print()
    print(f"  branch  {artifact.branch_name}")
    print(f"  title   {artifact.pull_request_title}")
    print(f"  written to {args.out.resolve()}")

    if validator is not None and not build.valid:
        print()
        print(
            "  "
            + _error(f"bundle never validated after {build.attempt_count} attempts")
        )
        print()
        print("  " + build.diagnostics.replace(NEWLINE, NEWLINE + "  ")[:2000])
        _summary(traces)
        # Non-zero: a bundle that does not validate must never reach a human
        # reviewer, so this is a failed run rather than a warning.
        return 1

    if build.self_corrected:
        print()
        print(f"  self-corrected after {build.attempt_count} attempts")

    # ----------------------------------------------------------- pull request
    if args.open_pr:
        _rule("PULL REQUEST")
        try:
            gateway = build_local_gateway(run, traces)
        except GatewayConfigError as exc:
            print("  " + _error(str(exc)), file=sys.stderr)
            _summary(traces)
            return 1

        result = asyncio.run(
            open_pull_request(
                gateway,
                run,
                repository=args.repo,
                branch=artifact.branch_name,
                base=args.base,
                title=artifact.pull_request_title,
                rationale=artifact.rationale,
                files=[{"path": f.path, "content": f.content} for f in artifact.files],
            )
        )

        if not result.get("ok"):
            # A denial is the policy engine working, not a crash. Show the
            # reason: it is usually actionable (oversized changeset, protected
            # branch) and it is exactly what a security reviewer wants logged.
            print("  " + _error("pull request refused"))
            print(f"  [{result.get('error_class')}] {result.get('error')}")
            _summary(traces)
            return 1

        pr = result.get("result", {})
        print(f"  opened  #{pr.get('pull_request_id')}")
        print(f"  {pr.get('url')}")
        print(f"  {pr.get('next_step')}")
        _summary(traces)
        return 0

    _rule("NEXT")
    print("  Review the files, then open a pull request into the bundle repo")
    print("  (or re-run with --open-pr --repo <name>).")
    print("  Their pipeline validates, a reviewer approves, their CD deploys.")
    _summary(traces)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
