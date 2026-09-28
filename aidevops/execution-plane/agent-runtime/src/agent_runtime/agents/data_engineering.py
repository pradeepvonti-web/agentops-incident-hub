"""The Data Engineering agent: requirement -> plan -> Databricks Asset Bundle.

Two model calls, deliberately separate rather than one.

The split exists because the plan is the cheap place to be wrong. A human can
read a plan in thirty seconds and say "no, sales orders are keyed on
delivery_id"; reading three hundred lines of generated PySpark to find the same
mistake costs ten minutes. Planning separately also means a rejected plan costs
one small call instead of one large one.

`conventions` is the seam where enterprise knowledge enters. Today it is a
default string describing the bundle layout. Once the registry is seeded from
the customer's own repository, it carries *their* naming, their variable usage,
their file-splitting habits -- and that is the difference between output that
gets merged and output that gets rewritten.
"""

from __future__ import annotations

import re

import structlog
from adp_contracts import StepKind
from pydantic import BaseModel, Field

from agent_runtime.llm import ModelClient

log = structlog.get_logger(__name__)


# --------------------------------------------------------------------- models

class PlanStep(BaseModel):
    order: int = Field(description="1-based position in the sequence")
    action: str = Field(description="Short imperative, e.g. 'Read bronze source'")
    detail: str = Field(description="What this step does and why")


class PipelinePlan(BaseModel):
    """What the agent intends to build, before it builds it."""

    summary: str = Field(description="One or two sentences a reviewer reads first")
    source_tables: list[str] = Field(
        description="Fully qualified source tables, catalog.schema.table"
    )
    target_table: str = Field(description="Fully qualified target, catalog.schema.table")
    grain: str = Field(
        description="What one row of the target represents, and its key columns"
    )
    steps: list[PlanStep]
    data_quality_checks: list[str] = Field(
        description="Checks that must pass before the target is considered good"
    )
    open_questions: list[str] = Field(
        description=(
            "Anything genuinely ambiguous in the requirement. Empty list if "
            "nothing is. Do not invent questions to seem careful, and do not "
            "guess at an answer instead of asking."
        )
    )


class GeneratedFile(BaseModel):
    path: str = Field(description="Repository-relative path, e.g. resources/x.yml")
    content: str = Field(description="Complete file contents")
    purpose: str = Field(description="One line: what this file is for")


class BundleArtifact(BaseModel):
    """Databricks Asset Bundle files, ready for a pull request."""

    branch_name: str = Field(description="Branch name, must start with agent/")
    pull_request_title: str
    rationale: str = Field(
        description="Why these changes, in prose. Becomes the PR description."
    )
    files: list[GeneratedFile]


# -------------------------------------------------------------------- prompts

DEFAULT_CONVENTIONS = """\
Repository layout (Databricks Asset Bundle):
  databricks.yml        root config with variables and per-environment targets
  resources/<job>.yml   one job definition per file
  source/<name>.py      PySpark transformation code
  tests/<name>.py       unit tests

Rules:
- One job per file under resources/. Never put two jobs in one file.
- Nothing environment-specific in resources/*.yml. Catalogs, cluster sizes and
  service principals come from ${var.*}, resolved per target in databricks.yml.
  A hard-coded catalog name is the single most common review rejection.
- Never write databricks.yml, azure-pipelines.yml or anything under .azure/.
  Those belong to the platform team.
- Scheduled jobs deploy with pause_status: PAUSED. A human unpauses after the
  first successful manual run.
- Tag every job with authored_by: ai-devops-agent.
"""

PLAN_SYSTEM = """\
You are a senior data engineer at an enterprise running Databricks on Azure.
You plan pipelines before writing them.

{conventions}

When you plan:
- Work only from what the requirement and the supplied table metadata actually
  say. If the grain, the key, or the source is not determinable from those,
  put it in open_questions rather than picking something plausible.
- Prefer the medallion layering the organisation already uses. Bronze is raw
  and append-only; Silver is typed, deduplicated and keyed; Gold is modelled
  for consumption.
- Data quality checks are part of the pipeline, not an afterthought. A Silver
  table that fails its own checks must not be readable downstream.

An unnecessary open question wastes a reviewer's time. A missing one produces a
pipeline that is quietly wrong. Prefer asking.
"""

GENERATE_SYSTEM = """\
You are a senior data engineer writing Databricks Asset Bundle files.

{conventions}

Write production code, not illustrative code:
- Real transformations. No `# TODO: implement` and no placeholder logic.
- Explicit schemas on reads. Schema inference in a scheduled job is how a
  pipeline silently changes shape when a source adds a column.
- Idempotent writes. A re-run must not double-count.
- Comment the non-obvious decision, not the obvious statement. Explain why a
  join is a left join, not that it is a join.

You are producing a pull request that a human will review and their CI/CD will
deploy. You do not deploy anything yourself.
"""


def _slugify(text: str, limit: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:limit].rstrip("-") or "pipeline"


class DataEngineeringAgent:
    """Plans and generates. Does not deploy -- that is the customer's pipeline."""

    def __init__(self, llm: ModelClient, *, conventions: str | None = None) -> None:
        self._llm = llm
        # Once the registry is seeded, this string is assembled from the
        # customer's own assets rather than the default.
        self._conventions = conventions or DEFAULT_CONVENTIONS

    def plan(
        self,
        requirement: str,
        *,
        table_metadata: str = "",
        attempt: int = 1,
    ) -> PipelinePlan:
        """Turn a requirement into a reviewable plan.

        `table_metadata` is whatever `uc_list_tables` and `uc_get_table_metadata`
        returned -- columns, types, comments. Without it the agent is guessing at
        schemas, and the open_questions list will say so.
        """
        context = table_metadata.strip() or (
            "No table metadata was supplied. Treat every column name and type as "
            "unknown and say so in open_questions."
        )

        prompt = f"""Requirement from the requester:

{requirement}

Unity Catalog metadata available to you:

{context}

Produce a plan for this pipeline."""

        plan = self._llm.structured(
            system=PLAN_SYSTEM.format(conventions=self._conventions),
            prompt=prompt,
            output_format=PipelinePlan,
            step_kind=StepKind.PLAN,
            max_tokens=4000,
            attempt=attempt,
        )

        log.info(
            "plan_produced",
            target=plan.target_table,
            steps=len(plan.steps),
            checks=len(plan.data_quality_checks),
            open_questions=len(plan.open_questions),
        )
        return plan

    def generate(
        self,
        plan: PipelinePlan,
        *,
        attempt: int = 1,
        validation_feedback: str = "",
    ) -> BundleArtifact:
        """Turn an approved plan into bundle files.

        `validation_feedback` carries `bundle validate` diagnostics from a failed
        previous attempt. Feeding the error back is what makes a retry different
        from the attempt that just failed.
        """
        steps = "\n".join(f"{s.order}. {s.action} - {s.detail}" for s in plan.steps)
        checks = "\n".join(f"- {c}" for c in plan.data_quality_checks)

        feedback = ""
        if validation_feedback:
            feedback = f"""

A previous attempt failed `databricks bundle validate` with:

{validation_feedback}

Fix that specifically. Do not rewrite the parts that were correct."""

        prompt = f"""Build the bundle files for this plan.

Summary: {plan.summary}
Sources: {', '.join(plan.source_tables) or 'none specified'}
Target:  {plan.target_table}
Grain:   {plan.grain}

Steps:
{steps}

Data quality checks that must be enforced:
{checks}

Use branch name agent/{_slugify(plan.target_table)}.{feedback}"""

        artifact = self._llm.structured(
            system=GENERATE_SYSTEM.format(conventions=self._conventions),
            prompt=prompt,
            output_format=BundleArtifact,
            step_kind=StepKind.GENERATE,
            max_tokens=16000,
            attempt=attempt,
        )

        # The model is asked for an `agent/` branch and usually complies. Enforce
        # it anyway: the gateway's branch_prefix policy would reject the pull
        # request, and failing here costs nothing while failing there costs a
        # whole generate call.
        if not artifact.branch_name.startswith("agent/"):
            artifact.branch_name = f"agent/{_slugify(artifact.branch_name)}"

        log.info(
            "artifact_generated",
            branch=artifact.branch_name,
            files=len(artifact.files),
            lines=sum(f.content.count("\n") + 1 for f in artifact.files),
        )
        return artifact
