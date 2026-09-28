"""Turn scanned facts into conventions the agent can follow.

One model call: a page of counts in, a set of rules out. The repository itself
never enters the prompt.

Every rule carries `evidence` -- the specific count that supports it. That field
is the whole design. A model asked "what are their conventions" will produce a
plausible list whether or not the repository supports it; a model required to
cite a number for each rule produces a list a human can check in thirty seconds,
and a fabricated rule stands out because its evidence does not match the fact
sheet.

`inconsistencies` is separated from the rules deliberately. Where a repository
contradicts itself, that is a finding to hand back to the customer, not a
pattern for the agent to imitate. Teaching an agent to hard-code catalogs
because thirty files do would be learning the wrong lesson precisely.
"""

from __future__ import annotations

import structlog
from adp_contracts import StepKind
from pydantic import BaseModel, Field

from agent_runtime.llm import ModelClient
from agent_runtime.registry.scanner import RepoFacts

log = structlog.get_logger(__name__)


class Convention(BaseModel):
    rule: str = Field(
        description="One imperative sentence an engineer could follow, e.g. "
        "'Name resource files after the target table, in snake_case.'"
    )
    evidence: str = Field(
        description="The specific count from the fact sheet that supports this, "
        "e.g. '18 of 20 resource files are named after their target table'. "
        "If no count supports the rule, do not state the rule."
    )
    confidence: str = Field(
        description="observed (the facts show it directly), likely (the facts "
        "point at it but are not conclusive), or uncertain (a guess worth "
        "confirming with the team)"
    )


class ConventionSet(BaseModel):
    """What this organisation's bundle repository demonstrates."""

    naming: list[Convention] = Field(
        description="How files, resource keys, jobs and tasks are named"
    )
    structure: list[Convention] = Field(
        description="How work is split across files, and what every job carries"
    )
    variables: list[Convention] = Field(
        description="Which values come from ${var.*} and which are inline"
    )
    code_style: list[Convention] = Field(
        description="Patterns in the Python sources"
    )

    inconsistencies: list[str] = Field(
        description="Places the repository contradicts its own conventions, or "
        "carries a known hazard. Findings for the team, NOT rules for the agent."
    )

    prompt_block: str = Field(
        description=(
            "The conventions rewritten as instructions for an engineer who has "
            "never seen this repository. Imperative, specific, no preamble, no "
            "confidence hedging. This text is given to the agent verbatim, so "
            "it must read as rules to follow rather than observations about a "
            "codebase. Do not include anything from the inconsistencies list."
        )
    )


SYSTEM = """\
You infer an organisation's engineering conventions from a fact sheet about
their Databricks Asset Bundle repository.

You are given counts, not code. Work only from those counts.

Rules:
- Every convention you state must cite a specific number from the fact sheet in
  its evidence. If no number supports it, do not state it.
- A pattern holding in most but not all cases is still a convention; say so in
  the evidence ("18 of 20"). A pattern holding in half the cases is not a
  convention and belongs in inconsistencies, or nowhere.
- Where the repository contradicts itself or carries a known hazard -- a
  hard-coded catalog, a schedule deploying unpaused, schema inference in a
  scheduled job -- put it in inconsistencies. Never turn a hazard into a rule
  just because it is common.
- Absence of evidence is not evidence. A small repository supports few
  conventions, and saying so is more useful than inventing ten.

The prompt_block is read by an agent that will write new files for this
repository. Write it as instructions, not as a report.
"""


def extract_conventions(
    llm: ModelClient, facts: RepoFacts, *, organisation: str = "this organisation"
) -> ConventionSet:
    """Synthesise conventions from scanned facts."""
    prompt = f"""Fact sheet for {organisation}'s bundle repository.

{facts.summary()}

Infer their conventions."""

    conventions = llm.structured(
        system=SYSTEM,
        prompt=prompt,
        output_format=ConventionSet,
        # A plan step: this is the agent working out what to do, before doing it.
        step_kind=StepKind.PLAN,
        max_tokens=8000,
    )

    log.info(
        "conventions_extracted",
        naming=len(conventions.naming),
        structure=len(conventions.structure),
        variables=len(conventions.variables),
        code_style=len(conventions.code_style),
        inconsistencies=len(conventions.inconsistencies),
    )
    return conventions


def render_registry_assets(
    conventions: ConventionSet, *, owner_team: str = "unassigned"
) -> list[dict[str, str]]:
    """Shape the conventions as registry asset rows.

    One asset per category rather than one per rule: a rule on its own is not
    independently useful, and a registry of four hundred one-line assets is a
    registry nobody browses.

    `kind` is `prompt` because that is what these are -- text that conditions a
    model. They are not pipeline templates, and filing them as such would make
    the template search return prose.
    """
    categories = {
        "naming": conventions.naming,
        "structure": conventions.structure,
        "variables": conventions.variables,
        "code-style": conventions.code_style,
    }

    assets: list[dict[str, str]] = []
    for name, rules in categories.items():
        if not rules:
            continue
        body = "\n".join(
            f"- {rule.rule}\n  evidence: {rule.evidence} ({rule.confidence})"
            for rule in rules
        )
        assets.append(
            {
                "kind": "prompt",
                "name": f"conventions/{name}",
                "description": f"Observed {name} conventions, extracted from the "
                f"existing bundle repository",
                "owner_team": owner_team,
                "body": body,
            }
        )

    # The assembled block the agent actually consumes. Stored alongside the
    # per-category assets so a human can edit one category and regenerate.
    assets.append(
        {
            "kind": "prompt",
            "name": "conventions/agent-prompt",
            "description": "Conventions as given to the Data Engineering agent",
            "owner_team": owner_team,
            "body": conventions.prompt_block,
        }
    )
    return assets
