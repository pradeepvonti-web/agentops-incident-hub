"""Generate and validate, with the failure fed back in.

    generate -> validate -> (fail) -> generate with diagnostics -> validate -> ...

This is the piece that makes the agent self-correcting rather than one-shot.
`bundle validate` is a precise, machine-checkable oracle: it tells you the field
name that is wrong and the line it is on. Handing that straight back is far more
effective than asking the model to try again.

Three rules the loop enforces, each earned:

1. **A cap, and a low one.** Three attempts. An agent that cannot fix its own
   bundle in three tries is not going to on the fourth -- it is stuck on
   something the diagnostics do not explain, and the cost is linear while the
   chance of success is not.

2. **Clear the output between attempts.** Attempt one writes
   `resources/orders.yml`; attempt two renames it to `resources/sales.yml`.
   Without a clean directory, `bundle validate` sees both and the second attempt
   fails on debris from the first -- with diagnostics that make no sense against
   the code the agent just wrote.

3. **Never retry a non-retryable model error.** A refusal or a truncated response
   is not a validation problem, and re-running it burns money to fail the same
   way. Those propagate immediately.
"""

from __future__ import annotations

import shutil
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

import structlog

from agent_runtime.agents.data_engineering import (
    BundleArtifact,
    DataEngineeringAgent,
    PipelinePlan,
)
from agent_runtime.llm import LlmError

log = structlog.get_logger(__name__)

#: Matches AgentLoop.max_attempts. Two places, one number, deliberately equal:
#: a retry budget that differs by layer is a budget nobody can reason about.
MAX_ATTEMPTS = 3

#: (bundle_root, target) -> (ok, diagnostics). Injected so the retry policy can
#: be tested without the Databricks CLI on PATH.
Validator = Callable[[Path, str], Awaitable[tuple[bool, str]]]


@dataclass
class Attempt:
    number: int
    valid: bool
    diagnostics: str = ""
    files: int = 0


@dataclass
class BuildResult:
    artifact: BundleArtifact
    valid: bool
    attempts: list[Attempt] = field(default_factory=list)

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)

    @property
    def diagnostics(self) -> str:
        """Why the last attempt failed. Empty when it succeeded."""
        return self.attempts[-1].diagnostics if self.attempts else ""

    @property
    def self_corrected(self) -> bool:
        """Failed at least once, then fixed itself.

        Worth measuring separately from plain success: it is the difference
        between an agent that gets it right and one that gets it right
        eventually, and only the second justifies the retry machinery.
        """
        return self.valid and self.attempt_count > 1


def _write_files(artifact: BundleArtifact, out_dir: Path) -> None:
    """Write the artifact to a clean directory.

    Clearing first is not tidiness. A file from a previous attempt that this
    attempt did not write is still there when `bundle validate` runs, and the
    resulting diagnostics describe code the agent cannot see.
    """
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    for file in artifact.files:
        path = out_dir / file.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(file.content, encoding="utf-8")


async def build_bundle(
    agent: DataEngineeringAgent,
    plan: PipelinePlan,
    *,
    out_dir: Path,
    target: str,
    validator: Validator | None = None,
    max_attempts: int = MAX_ATTEMPTS,
    on_attempt: Callable[[Attempt], None] | None = None,
) -> BuildResult:
    """Generate a bundle, validating and retrying on failure.

    With no `validator`, generation runs once and the result is reported as
    unvalidated rather than as valid -- claiming validity we never checked is
    worse than admitting we did not check.
    """
    attempts: list[Attempt] = []
    feedback = ""
    artifact: BundleArtifact | None = None

    for number in range(1, max_attempts + 1):
        try:
            artifact = agent.generate(
                plan, attempt=number, validation_feedback=feedback
            )
        except LlmError as exc:
            # Model-level failures carry their own retryability. A refusal or a
            # truncation is not something more diagnostics will fix.
            log.error(
                "generate_failed",
                attempt=number,
                error_class=exc.error_class,
                retryable=exc.retryable,
            )
            raise

        _write_files(artifact, out_dir)

        if validator is None:
            attempt = Attempt(number=number, valid=False, files=len(artifact.files),
                              diagnostics="not validated")
            attempts.append(attempt)
            if on_attempt:
                on_attempt(attempt)
            return BuildResult(artifact=artifact, valid=False, attempts=attempts)

        ok, diagnostics = await validator(out_dir, target)
        attempt = Attempt(
            number=number,
            valid=ok,
            diagnostics="" if ok else diagnostics,
            files=len(artifact.files),
        )
        attempts.append(attempt)
        if on_attempt:
            on_attempt(attempt)

        if ok:
            log.info("bundle_valid", attempt=number, files=len(artifact.files))
            return BuildResult(artifact=artifact, valid=True, attempts=attempts)

        log.warning(
            "bundle_invalid",
            attempt=number,
            remaining=max_attempts - number,
            diagnostics=diagnostics[:200],
        )
        # Truncated: a wall of diagnostics crowds out the plan in the next
        # prompt, and the useful part of a validate failure is at the top.
        feedback = diagnostics[:3000]

    log.error("bundle_never_validated", attempts=max_attempts)
    assert artifact is not None  # loop runs at least once
    return BuildResult(artifact=artifact, valid=False, attempts=attempts)
