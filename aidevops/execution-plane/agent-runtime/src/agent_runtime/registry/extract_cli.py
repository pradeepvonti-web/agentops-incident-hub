"""Extract conventions from an existing bundle repository.

    uv run adp-extract /path/to/their-bundle-repo --out conventions.md

Then feed the result back in:

    uv run adp-run "Build a Silver table for returns" --conventions-file conventions.md

That round trip is the point. Generic bundle knowledge comes free from the
Databricks skills; what makes the agent's first output acceptable is that it
looks like *their* repository. This is where that comes from.

`--facts-only` runs the scan with no model call and no API key. The fact sheet
is worth reading on its own -- the inconsistencies it surfaces (hard-coded
catalogs, schedules deploying unpaused) are findings a consultant can hand back
in week one, before any agent has written a line.
"""

from __future__ import annotations

import argparse
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

from agent_runtime.cli import ConsoleTraceEmitter, _rule, _warn
from agent_runtime.llm import LlmError, ModelClient
from agent_runtime.registry.conventions import (
    ConventionSet,
    extract_conventions,
    render_registry_assets,
)
from agent_runtime.registry.scanner import scan_bundle_repo

log = structlog.get_logger(__name__)

NEWLINE = chr(10)


def _build_run(repo: Path, tenant: str) -> Run:
    """A run, so the extraction is traced and costed like any other agent work.

    Conventions extraction is agent work: it spends tokens and it shapes every
    run that follows. Leaving it outside the trace would put the one call that
    determines output quality outside the accounting.
    """
    agent = AgentPrincipal(
        agent_type=AgentType.DATA_ENGINEERING,
        tenant_id=tenant,
        environment=Environment.DEV,
    )
    return Run(
        run_id=f"extract_{uuid.uuid4().hex[:10]}",
        tenant_id=tenant,
        principal=RunPrincipal(agent=agent, invoked_by="cli"),
        request=RunRequest(
            agent_type=AgentType.DATA_ENGINEERING,
            environment=Environment.DEV,
            requirement=f"Extract conventions from {repo}",
        ),
        started_at=datetime.now(UTC),
    )


def _print_conventions(conventions: ConventionSet) -> None:
    sections = (
        ("NAMING", conventions.naming),
        ("STRUCTURE", conventions.structure),
        ("VARIABLES", conventions.variables),
        ("CODE STYLE", conventions.code_style),
    )

    for title, rules in sections:
        if not rules:
            continue
        _rule(title)
        for item in rules:
            print(f"  {item.rule}")
            print(f"    {item.evidence}  [{item.confidence}]")

    if conventions.inconsistencies:
        # Findings, not rules. Kept visually separate so nobody reads them as
        # something the agent should imitate.
        _rule("INCONSISTENCIES")
        print("  Where the repository contradicts itself. Findings for the team;")
        print("  deliberately excluded from what the agent is told.")
        print()
        for finding in conventions.inconsistencies:
            print("  " + _warn("!") + f" {finding}")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="adp-extract",
        description="Extract engineering conventions from a bundle repository.",
    )
    parser.add_argument("repo", type=Path, help="Path to the bundle repository")
    parser.add_argument(
        "--out",
        type=Path,
        help="Write the agent-facing conventions block here. Feed it to adp-run "
        "with --conventions-file.",
    )
    parser.add_argument(
        "--assets-out",
        type=Path,
        help="Write the registry assets as JSON, ready to load into "
        "registry_assets",
    )
    parser.add_argument(
        "--facts-only",
        action="store_true",
        help="Scan and print the fact sheet without calling a model. No API key "
        "required.",
    )
    parser.add_argument("--tenant", default="acme")
    parser.add_argument(
        "--organisation", default="", help="Name used in the prompt, for context"
    )
    args = parser.parse_args()

    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(30))

    _rule("SCAN")
    facts = scan_bundle_repo(args.repo)

    for error in facts.errors:
        print("  " + _warn("!") + f" {error}")

    if facts.is_empty:
        print(f"  no bundle resources found under {args.repo}", file=sys.stderr)
        print("  is this the repository root, next to databricks.yml?", file=sys.stderr)
        return 1

    print()
    print("  " + facts.summary().replace(NEWLINE, NEWLINE + "  "))

    if args.facts_only:
        return 0

    # ----------------------------------------------------------- synthesise
    run = _build_run(args.repo, args.tenant)
    traces = ConsoleTraceEmitter()
    llm = ModelClient(run=run, traces=traces)

    try:
        conventions = extract_conventions(
            llm, facts, organisation=args.organisation or "this organisation"
        )
    except LlmError as exc:
        print(f"  extraction failed: {exc}  [{exc.error_class}]", file=sys.stderr)
        return 1

    _print_conventions(conventions)

    if args.out:
        args.out.write_text(conventions.prompt_block, encoding="utf-8")
        print()
        print(f"  conventions written to {args.out.resolve()}")
        print(f"  use: adp-run ... --conventions-file {args.out}")

    if args.assets_out:
        import json

        assets = render_registry_assets(conventions)
        args.assets_out.write_text(
            json.dumps(assets, indent=2), encoding="utf-8"
        )
        print(f"  {len(assets)} registry asset(s) written to {args.assets_out.resolve()}")

    _rule("COST")
    tokens_in, tokens_out = traces.total_tokens
    print(f"  {tokens_in:,} in  |  {tokens_out:,} out  |  ${traces.total_cost:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
