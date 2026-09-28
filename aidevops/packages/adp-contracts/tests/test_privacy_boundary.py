"""The privacy boundary test. Implements the ADR-0003 follow-up requirement.

If one test in this repository must never be deleted or weakened, it is
`test_no_payload_field_reaches_control_plane`. It is the executable form of the
promise we make in the security review: payloads stay in the customer's tenant.

It is written to fail when someone *adds* a field to Span and forgets to think
about export, which is the realistic way this promise gets broken -- not by someone
deciding to leak data, but by a field being added six months from now in a hurry.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from adp_contracts import (
    LlmCall,
    Span,
    StepKind,
    StepStatus,
    ToolCall,
    ToolDecision,
    digest,
)

#: Values planted in payload positions. If any string appears in the exported
#: projection, the boundary has been breached.
SECRET_MARKERS = {
    "arguments": "SECRET_CUSTOMER_TABLE_NAME",
    "result": "SECRET_ROW_VALUE",
    "prompt": "SECRET_PROMPT_TEXT",
    "completion": "SECRET_GENERATED_CODE",
    "payload": "SECRET_FREEFORM_PAYLOAD",
}


@pytest.fixture
def loaded_span() -> Span:
    return Span(
        span_id="step-abc123",
        parent_span_id="run-xyz789",
        name="tool:uc_get_table_metadata",
        started_at=datetime(2026, 9, 25, 10, 0, tzinfo=UTC),
        ended_at=datetime(2026, 9, 25, 10, 0, 3, tzinfo=UTC),
        status=StepStatus.SUCCEEDED,
        tenant_id="acme",
        run_id="run-xyz789",
        agent_type="data-engineering",
        agent_principal="agent-data-engineering-acme-dev",
        environment="dev",
        invoked_by="user-object-id-123",
        step_kind=StepKind.TOOL,
        attempt=1,
        tool_call=ToolCall(
            tool_name="uc_get_table_metadata",
            decision=ToolDecision.ALLOW,
            arguments={"table": SECRET_MARKERS["arguments"]},
            result={"columns": [SECRET_MARKERS["result"]]},
        ),
        llm_call=LlmCall(
            model="claude-opus-5",
            tokens_in=1200,
            tokens_out=400,
            cost_usd=0.03,
            prompt=SECRET_MARKERS["prompt"],
            completion=SECRET_MARKERS["completion"],
        ),
        payload={"note": SECRET_MARKERS["payload"]},
    )


def test_no_payload_field_reaches_control_plane(loaded_span: Span) -> None:
    """No payload marker may appear anywhere in the exported projection."""
    exported = repr(loaded_span.for_control_plane())

    for field, marker in SECRET_MARKERS.items():
        assert marker not in exported, (
            f"{field} leaked into the control-plane projection. "
            f"Span.for_control_plane() must build from an allowlist; if you added "
            f"a field, decide deliberately whether it may cross the tenant boundary "
            f"(ADR-0003 section 3)."
        )


def test_digests_are_exported_instead_of_arguments(loaded_span: Span) -> None:
    """We get deduplication and caching analysis without seeing the values."""
    exported = loaded_span.for_control_plane()

    assert exported["tool_call"]["arguments_digest"].startswith("sha256:")
    assert exported["tool_call"]["result_digest"].startswith("sha256:")
    assert "arguments" not in exported["tool_call"]
    assert "result" not in exported["tool_call"]


def test_digest_is_stable_across_key_order() -> None:
    """Same arguments, different dict ordering, same digest -- otherwise
    deduplication across runs is meaningless."""
    assert digest({"a": 1, "b": 2}) == digest({"b": 2, "a": 1})


def test_digest_differs_for_different_values() -> None:
    assert digest({"catalog": "bronze"}) != digest({"catalog": "silver"})


def test_cost_and_shape_do_cross_the_boundary(loaded_span: Span) -> None:
    """The metadata tier has to be useful, or we cannot compute acceptance rate
    or cost per run (ADR-0003 alternatives considered)."""
    exported = loaded_span.for_control_plane()

    assert exported["llm_call"]["cost_usd"] == 0.03
    assert exported["llm_call"]["tokens_in"] == 1200
    assert exported["duration_ms"] == 3000
    assert exported["status"] == "succeeded"
    assert exported["agent_principal"] == "agent-data-engineering-acme-dev"


def test_export_is_allowlist_based_not_exclusion_based() -> None:
    """Guards the mechanism itself.

    A span carrying an unexpected extra attribute must not export it. This is what
    makes the boundary hold for fields that do not exist yet.
    """
    span = Span(
        span_id="s1",
        name="tool:test",
        started_at=datetime.now(UTC),
        tenant_id="acme",
        run_id="r1",
        agent_type="data-engineering",
        agent_principal="agent-data-engineering-acme-dev",
        environment="dev",
        invoked_by="u1",
        step_kind=StepKind.TOOL,
    )
    object.__setattr__(span, "future_field_nobody_reviewed", "SECRET_FUTURE_VALUE")

    assert "SECRET_FUTURE_VALUE" not in repr(span.for_control_plane())


def test_missing_required_attributes_are_detected() -> None:
    """The collector rejects spans it cannot attribute (ADR-0003 section 2)."""
    span = Span(
        span_id="s1",
        name="tool:test",
        started_at=datetime.now(UTC),
        tenant_id="",           # empty
        run_id="r1",
        agent_type="data-engineering",
        agent_principal="",     # empty
        environment="dev",
        invoked_by="u1",
        step_kind=StepKind.TOOL,
    )

    assert span.missing_required_attributes() == {"tenant_id", "agent_principal"}


def test_complete_span_has_no_missing_attributes(loaded_span: Span) -> None:
    assert loaded_span.missing_required_attributes() == set()
