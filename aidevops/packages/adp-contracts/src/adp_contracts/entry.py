"""Entry Points. The six front doors from the architecture diagram.

The layer's whole claim is "six doors, one path": a request from Teams and a request
from the CLI must reach the orchestrator as the same object, be authorised the same
way, and be traced the same way. If any door gets its own bespoke path, the
governance story stops being true for that door -- and the door nobody audits is the
one that gets used to bypass approvals.

So the contract is deliberately narrow. A front door may set `source`, and that is
the only thing it gets to vary. Everything else about a run is decided downstream.

The six are fixed by the architecture diagram. Adding a seventh is a product
decision -- it needs an auth story, a trace attribution story and a row in the
security review -- not a new enum member.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from adp_contracts.identity import AgentType, Environment


class EntrySource(StrEnum):
    """Where a request entered the platform.

    Values are stable identifiers: they are written into traces, reported in
    adoption metrics, and appear in the audit log. Renaming one rewrites history,
    so the display label lives in ENTRY_POINTS below, separately from the value.
    """

    PORTAL = "portal"
    DATABRICKS = "databricks"
    VS_CODE = "vs-code"
    POWER_BI = "power-bi"
    TEAMS = "teams"
    API_CLI = "api-cli"


class EntryPoint(BaseModel):
    """Presentation metadata for one front door.

    Held here rather than in the portal so that every surface -- portal, docs,
    onboarding, the adoption dashboard -- names the six doors identically. The
    labels match the architecture diagram exactly and are not editorial.
    """

    model_config = {"frozen": True}

    source: EntrySource
    label: str
    caption: str
    interactive: bool = Field(
        default=True,
        description="Whether a human drives this door directly. False for API/CLI, "
        "which is how automation and scheduled runs arrive -- those have no "
        "invoking human and are capped by the schedule owner instead (ADR-0002).",
    )


#: The six front doors, in diagram order. Order is load-bearing: the portal renders
#: them in this sequence, and the portal comes first because it is the only door we
#: build and control end to end.
ENTRY_POINTS: tuple[EntryPoint, ...] = (
    EntryPoint(
        source=EntrySource.PORTAL,
        label="AI DevOps Portal",
        caption="Single front door",
    ),
    EntryPoint(
        source=EntrySource.DATABRICKS,
        label="Databricks",
        caption="Notebooks & Apps",
    ),
    EntryPoint(
        source=EntrySource.VS_CODE,
        label="VS Code",
        caption="Development",
    ),
    EntryPoint(
        source=EntrySource.POWER_BI,
        label="Power BI",
        caption="Analytics & BI",
    ),
    EntryPoint(
        source=EntrySource.TEAMS,
        label="Microsoft Teams",
        caption="Collaboration",
    ),
    EntryPoint(
        source=EntrySource.API_CLI,
        label="APIs / CLI",
        caption="Automation",
        interactive=False,
    ),
)

ENTRY_POINTS_BY_SOURCE: dict[EntrySource, EntryPoint] = {
    ep.source: ep for ep in ENTRY_POINTS
}


class EntryRequest(BaseModel):
    """What any front door submits. Identical across all six.

    Note what is absent. A door cannot name the tenant (it comes from the token,
    ADR-0001), cannot name the agent principal (derived from agent_type, ADR-0002),
    cannot skip approval, and cannot grant itself permissions. The only thing a
    door contributes beyond the request itself is which door it was.
    """

    source: EntrySource
    agent_type: AgentType
    environment: Environment = Environment.DEV

    requirement: str = Field(
        min_length=1,
        exclude=True,
        description="Natural language, from the human. Stays in the tenant; the "
        "control plane keeps only a digest (ADR-0003 section 3).",
    )

    title: str | None = Field(
        default=None,
        max_length=120,
        description="A short label the human gives the run, shown in run lists. "
        "It is stored by the control plane, so it is typed separately and must "
        "never be derived from the requirement (ADR-0003 section 3).",
    )

    target_catalog: str | None = None
    target_schema: str | None = None
    registry_asset_hints: list[str] = Field(default_factory=list)

    idempotency_key: str | None = Field(
        default=None,
        description="Set by doors that can retry a submission -- a Teams message "
        "delivered twice, a CLI command re-run after a timeout. Without it, a flaky "
        "network turns one request into two pipelines.",
    )

    @property
    def entry_point(self) -> EntryPoint:
        return ENTRY_POINTS_BY_SOURCE[self.source]

    @property
    def requires_invoking_human(self) -> bool:
        """Interactive doors must carry a human identity; API/CLI need not.

        The intersection rule (ADR-0002 section 4) needs someone to intersect
        against. A door that claims to be interactive but presents no human is
        rejected rather than silently treated as unattended -- that would be a way
        to shed the permission cap by lying about the source.
        """
        return self.entry_point.interactive
