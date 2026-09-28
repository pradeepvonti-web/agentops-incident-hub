"""Identity contracts. Implements ADR-0002.

The invariant this module exists to enforce: an agent principal is always scoped to
(agent_type, tenant, environment). There is no such thing as "the platform agent".
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class AgentType(StrEnum):
    """Agent types. Deliberately short.

    ADR-0002 and the 6-month plan cap v1 at three agents. Adding a fourth is a
    product decision with an identity, policy and evaluation cost attached to it,
    not a convenience.
    """

    DATA_ENGINEERING = "data-engineering"
    DATA_QUALITY = "data-quality"
    ORCHESTRATOR = "orchestrator"


class Environment(StrEnum):
    DEV = "dev"
    TEST = "test"
    PROD = "prod"


_TENANT_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$")


class AgentPrincipal(BaseModel):
    """A non-human principal. One per (agent_type, tenant, environment)."""

    model_config = {"frozen": True}

    agent_type: AgentType
    tenant_id: str
    environment: Environment
    object_id: str | None = Field(
        default=None, description="Entra ID object id, populated by Terraform"
    )

    @field_validator("tenant_id")
    @classmethod
    def _tenant_is_slug(cls, v: str) -> str:
        if not _TENANT_RE.match(v):
            raise ValueError(
                f"tenant_id must be a lowercase slug, 3-40 chars: got {v!r}"
            )
        return v

    @property
    def name(self) -> str:
        """Entra display name. Must match the Terraform module exactly."""
        return f"agent-{self.agent_type}-{self.tenant_id}-{self.environment}"

    def __str__(self) -> str:
        return self.name


class RunPrincipal(BaseModel):
    """Who a run acts as: the agent, on behalf of a human.

    ADR-0002 §4: effective permissions are the intersection of the two. This model
    carries both so the gateway can enforce that; it never carries only the agent.
    """

    model_config = {"frozen": True}

    agent: AgentPrincipal
    invoked_by: str = Field(
        description="Entra object id of the invoking human, or 'system:scheduler' "
        "for unattended runs"
    )

    @property
    def is_unattended(self) -> bool:
        return self.invoked_by.startswith("system:")
