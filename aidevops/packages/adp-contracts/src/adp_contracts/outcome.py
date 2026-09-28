"""Run outcome — the acceptance-rate contract. Implements ADR-0003 §5.

This is the most commercially important model in the codebase. Acceptance rate is
the number we sell on, and `human_edit_lines` is what stops us lying to ourselves
about it.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class RunOutcome(BaseModel):
    """Written exactly once per run that reaches an approve step."""

    run_id: str
    tenant_id: str
    agent_type: str
    environment: str

    accepted: bool = Field(
        description="Did a human merge the agent's output?"
    )
    human_edit_lines: int = Field(
        default=0,
        ge=0,
        description="Lines changed between what the agent produced and what was "
        "merged. A run accepted after heavy editing is not a success; reporting "
        "acceptance without this number would flatter us.",
    )
    generated_lines: int = Field(
        default=0, ge=0, description="Size of the agent's output, for edit ratio."
    )
    rejection_reason: str | None = None
    time_to_decision_seconds: int = 0

    registry_assets_used: list[str] = Field(
        default_factory=list,
        description="Which registry assets the run actually used. The reuse thesis "
        "predicts these runs score higher; if the gap has not appeared by Month 3 "
        "the thesis is wrong and the roadmap changes.",
    )

    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def edit_ratio(self) -> float:
        """Fraction of the agent's output a human had to change. Lower is better."""
        if self.generated_lines == 0:
            return 0.0
        return min(self.human_edit_lines / self.generated_lines, 1.0)

    @property
    def clean_accept(self) -> bool:
        """Accepted with no human edits at all — the honest headline number."""
        return self.accepted and self.human_edit_lines == 0
