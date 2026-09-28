"""Contracts shared by the control plane and the execution plane.

This package is the only code both planes import. It is deliberately small and has
no dependencies beyond pydantic, because a breaking change here forces a coordinated
deployment across a boundary we do not control (ADR-0001: the execution plane runs
in the customer's subscription and upgrades on their schedule).

Compatibility rule: the control plane must accept payloads from the previous two
execution-plane minor versions. Add optional fields; never repurpose or remove one.
"""

from adp_contracts.entry import (
    ENTRY_POINTS,
    ENTRY_POINTS_BY_SOURCE,
    EntryPoint,
    EntryRequest,
    EntrySource,
)
from adp_contracts.identity import AgentPrincipal, AgentType, Environment, RunPrincipal
from adp_contracts.outcome import RunOutcome
from adp_contracts.run import Run, RunRequest, RunStatus
from adp_contracts.trace import (
    REQUIRED_SPAN_ATTRIBUTES,
    LlmCall,
    Span,
    StepKind,
    StepStatus,
    ToolCall,
    ToolDecision,
    digest,
)

__all__ = [
    "AgentPrincipal", "AgentType", "Environment", "RunPrincipal",
    "ENTRY_POINTS", "ENTRY_POINTS_BY_SOURCE", "EntryPoint", "EntryRequest",
    "EntrySource",
    "Run", "RunRequest", "RunStatus", "RunOutcome",
    "REQUIRED_SPAN_ATTRIBUTES", "LlmCall", "Span", "StepKind", "StepStatus",
    "ToolCall", "ToolDecision", "digest",
]

__version__ = "0.1.0"
