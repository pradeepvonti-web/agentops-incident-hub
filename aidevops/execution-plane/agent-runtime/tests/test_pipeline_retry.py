"""Generate/validate retry loop tests.

The validator is injected, so these run without the Databricks CLI and without
an API key. What is under test is the retry *policy* -- how many times, with
what feedback, and against what output directory -- not whether Claude writes
good YAML.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from agent_runtime.agents.data_engineering import (
    BundleArtifact,
    GeneratedFile,
    PipelinePlan,
    PlanStep,
)
from agent_runtime.llm import LlmError
from agent_runtime.pipeline import MAX_ATTEMPTS, build_bundle

PLAN = PipelinePlan(
    summary="Silver sales orders",
    source_tables=["bronze.raw.orders"],
    target_table="silver.curated.sales_orders",
    grain="One row per delivery_id",
    steps=[PlanStep(order=1, action="Read bronze", detail="Explicit schema")],
    data_quality_checks=["delivery_id is never null"],
    open_questions=[],
)


def _artifact(filename: str = "orders.yml", body: str = "resources: {}") -> BundleArtifact:
    return BundleArtifact(
        branch_name="agent/sales-orders",
        pull_request_title="Add sales orders pipeline",
        rationale="Implements the plan.",
        files=[
            GeneratedFile(
                path=f"resources/{filename}", content=body, purpose="Job definition"
            )
        ],
    )


class StubAgent:
    """Returns a queued artifact per call and records the feedback it was given."""

    def __init__(self, artifacts: list, raises: Exception | None = None) -> None:
        self._artifacts = list(artifacts)
        self._raises = raises
        self.feedback_seen: list[str] = []
        self.attempts_seen: list[int] = []

    def generate(self, plan, *, attempt=1, validation_feedback=""):
        self.attempts_seen.append(attempt)
        self.feedback_seen.append(validation_feedback)
        if self._raises is not None:
            raise self._raises
        return self._artifacts.pop(0) if self._artifacts else _artifact()


def _validator(results: list[tuple[bool, str]]):
    """A validator that returns each queued result in turn."""
    queue = list(results)

    async def validate(bundle_root: Path, target: str):
        return queue.pop(0) if queue else (True, "")

    return validate


# ------------------------------------------------------------------- success

async def test_valid_first_time_does_not_retry(tmp_path: Path) -> None:
    agent = StubAgent([_artifact()])
    result = await build_bundle(
        agent, PLAN, out_dir=tmp_path / "out", target="dev",
        validator=_validator([(True, "")]),
    )

    assert result.valid
    assert result.attempt_count == 1
    assert not result.self_corrected
    assert agent.feedback_seen == [""]


async def test_invalid_then_valid_self_corrects(tmp_path: Path) -> None:
    agent = StubAgent([_artifact(body="broken"), _artifact(body="fixed")])
    result = await build_bundle(
        agent, PLAN, out_dir=tmp_path / "out", target="dev",
        validator=_validator([(False, "unknown field 'schedul'"), (True, "")]),
    )

    assert result.valid
    assert result.attempt_count == 2
    assert result.self_corrected
    assert result.diagnostics == ""


async def test_diagnostics_are_fed_into_the_retry(tmp_path: Path) -> None:
    """The whole point. A retry without the error is the same call again."""
    agent = StubAgent([_artifact(), _artifact()])
    await build_bundle(
        agent, PLAN, out_dir=tmp_path / "out", target="dev",
        validator=_validator([(False, "unknown field 'schedul' at line 12"), (True, "")]),
    )

    assert agent.feedback_seen[0] == ""
    assert "unknown field 'schedul' at line 12" in agent.feedback_seen[1]


async def test_attempt_number_is_passed_through(tmp_path: Path) -> None:
    """Spans record the attempt; retries must be distinguishable from noise."""
    agent = StubAgent([_artifact(), _artifact(), _artifact()])
    await build_bundle(
        agent, PLAN, out_dir=tmp_path / "out", target="dev",
        validator=_validator([(False, "a"), (False, "b"), (True, "")]),
    )
    assert agent.attempts_seen == [1, 2, 3]


# ------------------------------------------------------------------ giving up

async def test_gives_up_after_max_attempts(tmp_path: Path) -> None:
    agent = StubAgent([_artifact() for _ in range(10)])
    result = await build_bundle(
        agent, PLAN, out_dir=tmp_path / "out", target="dev",
        validator=_validator([(False, "still broken")] * 10),
    )

    assert not result.valid
    assert result.attempt_count == MAX_ATTEMPTS
    assert "still broken" in result.diagnostics


async def test_max_attempts_is_configurable(tmp_path: Path) -> None:
    agent = StubAgent([_artifact() for _ in range(10)])
    result = await build_bundle(
        agent, PLAN, out_dir=tmp_path / "out", target="dev",
        validator=_validator([(False, "nope")] * 10), max_attempts=1,
    )
    assert result.attempt_count == 1


# --------------------------------------------------------- stale-file gotcha

async def test_output_directory_is_cleared_between_attempts(tmp_path: Path) -> None:
    """The bug this guards against is subtle and expensive.

    Attempt one writes resources/orders.yml. Attempt two renames it to
    resources/sales.yml. Without clearing, `bundle validate` sees BOTH and fails
    on a file the agent no longer knows it wrote -- producing diagnostics that
    make no sense against the code it just generated.
    """
    out = tmp_path / "out"
    agent = StubAgent([_artifact("orders.yml"), _artifact("sales.yml")])

    seen: list[set[str]] = []

    async def validate(bundle_root: Path, target: str):
        seen.append({p.name for p in bundle_root.rglob("*.yml")})
        return (len(seen) == 2, "renamed the resource file")

    result = await build_bundle(
        agent, PLAN, out_dir=out, target="dev", validator=validate
    )

    assert result.valid
    assert seen[0] == {"orders.yml"}
    # The critical assertion: orders.yml is gone, not lingering alongside.
    assert seen[1] == {"sales.yml"}


async def test_pre_existing_files_are_removed(tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    (out / "leftover.yml").write_text("from a previous run", encoding="utf-8")

    agent = StubAgent([_artifact()])
    await build_bundle(
        agent, PLAN, out_dir=out, target="dev", validator=_validator([(True, "")])
    )

    assert not (out / "leftover.yml").exists()


# ------------------------------------------------------- model errors escape

async def test_model_error_is_not_retried(tmp_path: Path) -> None:
    """A refusal or truncation is not a validation problem. Re-running it burns
    money to fail identically, so it propagates instead."""
    agent = StubAgent(
        [], raises=LlmError("declined", error_class="llm_refusal", retryable=False)
    )

    with pytest.raises(LlmError) as exc:
        await build_bundle(
            agent, PLAN, out_dir=tmp_path / "out", target="dev",
            validator=_validator([(True, "")]),
        )

    assert exc.value.error_class == "llm_refusal"
    assert len(agent.attempts_seen) == 1


# ----------------------------------------------------------- no validator

async def test_without_a_validator_the_result_is_not_claimed_valid(
    tmp_path: Path,
) -> None:
    """Claiming validity we never checked is worse than admitting we did not."""
    agent = StubAgent([_artifact()])
    result = await build_bundle(
        agent, PLAN, out_dir=tmp_path / "out", target="dev", validator=None
    )

    assert not result.valid
    assert result.diagnostics == "not validated"
    assert result.attempt_count == 1


# ------------------------------------------------------------------ feedback

async def test_feedback_is_truncated(tmp_path: Path) -> None:
    """A wall of diagnostics crowds the plan out of the next prompt, and the
    useful part of a validate failure is at the top."""
    agent = StubAgent([_artifact(), _artifact()])
    await build_bundle(
        agent, PLAN, out_dir=tmp_path / "out", target="dev",
        validator=_validator([(False, "x" * 10_000), (True, "")]),
    )

    assert len(agent.feedback_seen[1]) <= 3000


async def test_files_are_actually_written(tmp_path: Path) -> None:
    out = tmp_path / "out"
    agent = StubAgent([_artifact(body="resources:\n  jobs: {}")])
    await build_bundle(
        agent, PLAN, out_dir=out, target="dev", validator=_validator([(True, "")])
    )

    written = out / "resources" / "orders.yml"
    assert written.exists()
    assert "jobs" in written.read_text(encoding="utf-8")
