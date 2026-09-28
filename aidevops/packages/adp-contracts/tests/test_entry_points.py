"""Entry Points contract tests.

The layer's claim is "six doors, one path". These tests hold the two halves of that
claim: the six are exactly the six from the architecture diagram, and every one of
them submits the same object.

`test_typescript_mirror_matches_python` is the one that earns its keep. The shell
duplicates this list so the entry layer renders on first paint without waiting on
the API, and a duplicated list drifts. Here the drift fails a test instead of
shipping two names for the same door.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from adp_contracts import (
    ENTRY_POINTS,
    ENTRY_POINTS_BY_SOURCE,
    AgentType,
    EntryRequest,
    EntrySource,
)

#: The unified shell's copy (frontend/src/devops/entry.ts at the repository
#: root). The shell renders the entry layer before any session exists, so it
#: cannot wait on /v1/entry/points -- hence a mirror, and hence this test.
TS_MIRROR = (
    Path(__file__).parents[4] / "frontend" / "src" / "devops" / "entry.ts"
)

#: Transcribed from the architecture diagram, in diagram order. This literal is the
#: reference: if the diagram changes, change it here first and let the failures show
#: you every place that needs to follow.
DIAGRAM = [
    ("portal", "AI DevOps Portal", "Single front door"),
    ("databricks", "Databricks", "Notebooks & Apps"),
    ("vs-code", "VS Code", "Development"),
    ("power-bi", "Power BI", "Analytics & BI"),
    ("teams", "Microsoft Teams", "Collaboration"),
    ("api-cli", "APIs / CLI", "Automation"),
]


# ------------------------------------------------------------ the six doors

def test_there_are_exactly_six_entry_points() -> None:
    assert len(ENTRY_POINTS) == 6
    assert len(EntrySource) == 6


def test_entry_points_match_the_diagram_exactly() -> None:
    """Labels and order are not editorial -- they come from the diagram."""
    actual = [(ep.source.value, ep.label, ep.caption) for ep in ENTRY_POINTS]
    assert actual == DIAGRAM


def test_portal_is_first() -> None:
    """Order is load-bearing: the door we build end to end leads."""
    assert ENTRY_POINTS[0].source is EntrySource.PORTAL


def test_only_api_cli_is_non_interactive() -> None:
    non_interactive = [ep.source for ep in ENTRY_POINTS if not ep.interactive]
    assert non_interactive == [EntrySource.API_CLI]


def test_every_source_has_a_spec() -> None:
    for source in EntrySource:
        assert source in ENTRY_POINTS_BY_SOURCE


# ------------------------------------------------------------ one path

def test_all_doors_submit_the_same_object() -> None:
    """A Teams request and a CLI request differ only in `source`."""
    shape: set[frozenset[str]] = set()
    for source in EntrySource:
        request = EntryRequest(
            source=source,
            agent_type=AgentType.DATA_ENGINEERING,
            requirement="Build a Bronze to Silver pipeline",
            idempotency_key="k-1",
        )
        shape.add(frozenset(request.model_dump().keys()))
    assert len(shape) == 1


def test_requirement_is_excluded_from_serialisation() -> None:
    """Natural language stays in the tenant (ADR-0003 section 3)."""
    request = EntryRequest(
        source=EntrySource.PORTAL,
        agent_type=AgentType.DATA_ENGINEERING,
        requirement="SECRET_CUSTOMER_REQUIREMENT",
    )
    assert "SECRET_CUSTOMER_REQUIREMENT" not in json.dumps(request.model_dump())


def test_empty_requirement_is_rejected() -> None:
    with pytest.raises(ValueError):
        EntryRequest(
            source=EntrySource.PORTAL,
            agent_type=AgentType.DATA_ENGINEERING,
            requirement="",
        )


def test_a_seventh_door_cannot_be_invented() -> None:
    """The six are fixed by the architecture. A new source string is not a new
    entry point -- it is a rejected request."""
    with pytest.raises(ValueError):
        EntryRequest(
            source="slack",
            agent_type=AgentType.DATA_ENGINEERING,
            requirement="Build a pipeline",
        )


def test_a_door_cannot_name_its_own_tenant() -> None:
    """Tenant comes from the token, never from the request (ADR-0001)."""
    assert "tenant_id" not in EntryRequest.model_fields


def test_interactive_doors_require_a_human() -> None:
    interactive = EntryRequest(
        source=EntrySource.TEAMS,
        agent_type=AgentType.DATA_ENGINEERING,
        requirement="Refresh the sales pipeline",
    )
    assert interactive.requires_invoking_human

    automated = EntryRequest(
        source=EntrySource.API_CLI,
        agent_type=AgentType.DATA_ENGINEERING,
        requirement="Nightly reconciliation",
        idempotency_key="nightly-2026-09-25",
    )
    assert not automated.requires_invoking_human


# ------------------------------------------------------------ portal parity

def _parse_ts_mirror(text: str) -> list[tuple[str, str, str]]:
    """Pull (source, label, caption) out of the TS literal.

    A regex rather than a parser: the shape is a fixed literal we control, and a
    real parser would be more machinery than the thing it checks.
    """
    block = re.search(
        r"export const ENTRY_POINTS[^=]*=\s*\[(.*?)\]\s*as const;", text, re.S
    )
    assert block, "could not find the ENTRY_POINTS literal in entry.ts"

    return re.findall(
        r'source:\s*"([^"]+)",\s*label:\s*"([^"]+)",\s*caption:\s*"([^"]+)"',
        block.group(1),
    )


def test_typescript_mirror_matches_python() -> None:
    """The portal's copy of the six must not drift from this one."""
    assert TS_MIRROR.exists(), f"expected the portal mirror at {TS_MIRROR}"

    ts_points = _parse_ts_mirror(TS_MIRROR.read_text(encoding="utf-8"))
    py_points = [(ep.source.value, ep.label, ep.caption) for ep in ENTRY_POINTS]

    assert ts_points == py_points, (
        "frontend/src/devops/entry.ts has drifted from adp_contracts.entry.ENTRY_POINTS. "
        "Both render the same six doors to users; update whichever is wrong."
    )


def test_typescript_mirror_agrees_on_interactivity() -> None:
    text = TS_MIRROR.read_text(encoding="utf-8")
    for ep in ENTRY_POINTS:
        pattern = (
            rf'source:\s*"{re.escape(ep.source.value)}".*?'
            rf"interactive:\s*(true|false)"
        )
        match = re.search(pattern, text, re.S)
        assert match, f"no interactive flag for {ep.source.value} in entry.ts"
        assert match.group(1) == ("true" if ep.interactive else "false"), (
            f"{ep.source.value}: interactive disagrees between Python and the portal"
        )
