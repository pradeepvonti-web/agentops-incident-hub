"""Approval binding tests. Implements ADR-0002 section 5.

The property under test: an approval authorises *specific content*, not a run. If
the artifact changes after a human approved it, the approval must not carry over.

This is the test that stops the most dangerous bug this system can have -- a human
reviews a small, safe change, the agent regenerates, and something else deploys
under their name.
"""

from __future__ import annotations

import pytest
from adp_contracts import (
    AgentPrincipal,
    AgentType,
    Environment,
    Run,
    RunPrincipal,
    RunRequest,
)
from agent_runtime.loop import AgentLoop, Artifact


class _RecordingEmitter:
    def __init__(self) -> None:
        self.spans: list = []

    def emit(self, span) -> None:
        self.spans.append(span)


class _StubGateway:
    def __init__(self, response: dict | None = None) -> None:
        self.response = response or {"ok": True, "result": {}}
        self.calls: list[dict] = []

    async def call_tool(self, *, tool_name, arguments, run_has_approval):
        self.calls.append(
            {
                "tool_name": tool_name,
                "arguments": arguments,
                "run_has_approval": run_has_approval,
            }
        )
        return self.response


def _loop(environment: Environment = Environment.PROD) -> tuple[AgentLoop, _RecordingEmitter]:
    run = Run(
        run_id="run-test-001",
        tenant_id="acme",
        principal=RunPrincipal(
            agent=AgentPrincipal(
                agent_type=AgentType.DATA_ENGINEERING,
                tenant_id="acme",
                environment=environment,
            ),
            invoked_by="user-123",
        ),
        request=RunRequest(
            agent_type=AgentType.DATA_ENGINEERING,
            environment=environment,
            requirement="Build a Bronze to Silver pipeline for sales orders",
        ),
    )
    emitter = _RecordingEmitter()
    return AgentLoop(run=run, gateway=_StubGateway(), traces=emitter), emitter


# --------------------------------------------------------- approval binding

async def test_approval_binds_to_content() -> None:
    loop, _ = _loop()
    loop.artifact = Artifact(
        files=[{"path": "pipelines/sales.py", "content": "print('v1')\n"}]
    )

    original = loop.artifact.content_digest
    assert loop.record_approval(approved_digest=original, approved_by="user-123")
    assert loop.approved_digest == original


async def test_approval_is_void_if_artifact_changes() -> None:
    """The core safety property."""
    loop, _ = _loop()
    loop.artifact = Artifact(
        files=[{"path": "pipelines/sales.py", "content": "print('safe')\n"}]
    )
    approved = loop.artifact.content_digest
    assert loop.record_approval(approved_digest=approved, approved_by="user-123")

    # Agent regenerates after approval.
    loop.artifact = Artifact(
        files=[{"path": "pipelines/sales.py", "content": "print('something else')\n"}]
    )

    result = await loop.deploy()
    assert not result.ok
    assert result.error_class == "approval_stale"


async def test_stale_approval_digest_is_rejected_at_record_time() -> None:
    loop, _ = _loop()
    loop.artifact = Artifact(files=[{"path": "a.py", "content": "x = 1\n"}])

    accepted = loop.record_approval(
        approved_digest="sha256:something-else", approved_by="user-123"
    )
    assert not accepted
    assert loop.approved_digest is None


# ------------------------------------------------------------ deploy gating

async def test_prod_deploy_without_approval_is_refused() -> None:
    loop, _ = _loop(Environment.PROD)
    loop.artifact = Artifact(files=[{"path": "a.py", "content": "x = 1\n"}])

    result = await loop.deploy()
    assert not result.ok
    assert result.error_class == "approval_required"


async def test_dev_deploy_does_not_require_approval() -> None:
    """Friction in prod, none in dev -- otherwise nobody uses the thing."""
    loop, _ = _loop(Environment.DEV)
    loop.artifact = Artifact(files=[{"path": "a.py", "content": "x = 1\n"}])

    result = await loop.deploy()
    assert result.ok


async def test_approval_state_reaches_the_gateway() -> None:
    """The gateway's prod approval constraint depends on this flag being honest."""
    loop, _ = _loop(Environment.PROD)
    loop.artifact = Artifact(files=[{"path": "a.py", "content": "x = 1\n"}])

    await loop.call_tool("uc_list_tables", {"catalog": "bronze", "schema": "s"})
    assert loop.gateway.calls[-1]["run_has_approval"] is False

    loop.record_approval(
        approved_digest=loop.artifact.content_digest, approved_by="user-123"
    )
    await loop.call_tool("uc_list_tables", {"catalog": "bronze", "schema": "s"})
    assert loop.gateway.calls[-1]["run_has_approval"] is True


# ----------------------------------------------------------------- tracing

async def test_every_step_emits_a_span() -> None:
    loop, emitter = _loop(Environment.DEV)
    loop.artifact = Artifact(files=[{"path": "a.py", "content": "x = 1\n"}])

    await loop.plan()
    await loop.generate()
    await loop.validate()
    await loop.deploy()
    await loop.monitor()

    kinds = [s.step_kind.value for s in emitter.spans]
    assert kinds == ["plan", "generate", "validate", "deploy", "monitor"]


async def test_failed_deploy_still_emits_a_span() -> None:
    """A loop that only traces success cannot explain a failure."""
    loop, emitter = _loop(Environment.PROD)
    loop.artifact = Artifact(files=[{"path": "a.py", "content": "x = 1\n"}])

    await loop.deploy()

    assert len(emitter.spans) == 1
    assert emitter.spans[0].error_class == "approval_required"


async def test_checkpoint_is_taken_before_deploy() -> None:
    """Checkpoints go in before side effects, not after."""
    loop, _ = _loop(Environment.DEV)
    loop.artifact = Artifact(files=[{"path": "a.py", "content": "x = 1\n"}])

    await loop.deploy()
    assert any("pre-deploy" in c for c in loop._checkpoints)


# ----------------------------------------------------------------- outcome

def test_clean_accept_requires_zero_edits() -> None:
    loop, _ = _loop()
    loop.artifact = Artifact(
        files=[{"path": "a.py", "content": "line1\nline2\nline3\n"}]
    )

    clean = loop.record_outcome(accepted=True, human_edit_lines=0)
    assert clean.clean_accept
    assert clean.edit_ratio == 0.0

    edited = loop.record_outcome(accepted=True, human_edit_lines=2)
    assert edited.accepted
    assert not edited.clean_accept
    assert edited.edit_ratio == pytest.approx(0.5)


def test_edit_ratio_is_capped_at_one() -> None:
    loop, _ = _loop()
    loop.artifact = Artifact(files=[{"path": "a.py", "content": "one line\n"}])

    outcome = loop.record_outcome(accepted=True, human_edit_lines=99)
    assert outcome.edit_ratio == 1.0


def test_registry_usage_is_recorded() -> None:
    """Without this the reuse thesis cannot be measured (ADR-0003 section 5)."""
    loop, _ = _loop()
    loop.artifact = Artifact(files=[{"path": "a.py", "content": "x\n"}])

    outcome = loop.record_outcome(
        accepted=True, registry_assets_used=["template:bronze-to-silver:v3"]
    )
    assert outcome.registry_assets_used == ["template:bronze-to-silver:v3"]
