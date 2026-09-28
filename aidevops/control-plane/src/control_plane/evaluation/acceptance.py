"""Acceptance rate. The number the company is run on.

Two reporting rules, both defensive against self-deception:

  1. **Never report acceptance alone.** A run "accepted" after a human rewrote half
     of it is not a success. Acceptance always ships next to clean-accept rate and
     median edit ratio.
  2. **Always report n.** An 80% acceptance rate over five runs is noise, and it is
     exactly the number a founder quotes on a slide in month 3. `AcceptanceReport`
     carries `n` and refuses to describe itself as meaningful below a threshold.

The reuse comparison at the bottom is the falsifiable form of the moat thesis: runs
that used a registry asset should beat runs that did not. If that gap is absent by
Month 3, the thesis is wrong and the roadmap should change.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass

from adp_contracts import RunOutcome

#: Below this, a rate is not reportable. Chosen to be uncomfortable rather than
#: statistically rigorous -- its job is to stop a five-run number reaching a slide.
MIN_MEANINGFUL_SAMPLE = 20


@dataclass(frozen=True)
class AcceptanceReport:
    n: int
    accepted: int
    clean_accepted: int
    median_edit_ratio: float

    @property
    def acceptance_rate(self) -> float:
        return self.accepted / self.n if self.n else 0.0

    @property
    def clean_acceptance_rate(self) -> float:
        """Accepted with zero human edits. The honest headline."""
        return self.clean_accepted / self.n if self.n else 0.0

    @property
    def is_meaningful(self) -> bool:
        return self.n >= MIN_MEANINGFUL_SAMPLE

    def summary(self) -> str:
        """One line, formatted so the caveat cannot be dropped by accident."""
        if self.n == 0:
            return "no runs"
        caveat = "" if self.is_meaningful else f"  [n={self.n}, NOT MEANINGFUL]"
        return (
            f"acceptance {self.acceptance_rate:.0%} "
            f"(clean {self.clean_acceptance_rate:.0%}, "
            f"median edit ratio {self.median_edit_ratio:.2f}, n={self.n})"
            f"{caveat}"
        )


def compute_acceptance(outcomes: Sequence[RunOutcome]) -> AcceptanceReport:
    if not outcomes:
        return AcceptanceReport(n=0, accepted=0, clean_accepted=0, median_edit_ratio=0.0)

    return AcceptanceReport(
        n=len(outcomes),
        accepted=sum(1 for o in outcomes if o.accepted),
        clean_accepted=sum(1 for o in outcomes if o.clean_accept),
        median_edit_ratio=statistics.median(o.edit_ratio for o in outcomes),
    )


@dataclass(frozen=True)
class ReuseComparison:
    """Does registry reuse actually improve output quality?"""

    with_reuse: AcceptanceReport
    without_reuse: AcceptanceReport

    @property
    def acceptance_lift(self) -> float:
        """Percentage points. Positive means reuse helps."""
        return self.with_reuse.acceptance_rate - self.without_reuse.acceptance_rate

    @property
    def is_conclusive(self) -> bool:
        return self.with_reuse.is_meaningful and self.without_reuse.is_meaningful

    def verdict(self) -> str:
        if not self.is_conclusive:
            return (
                f"inconclusive (n={self.with_reuse.n} with reuse, "
                f"{self.without_reuse.n} without)"
            )
        if self.acceptance_lift > 0.05:
            return f"reuse helps: +{self.acceptance_lift:.0%} acceptance"
        if self.acceptance_lift < -0.05:
            return (
                f"reuse HURTS: {self.acceptance_lift:.0%} acceptance -- "
                f"investigate before promoting the registry further"
            )
        return (
            f"no measurable effect ({self.acceptance_lift:+.0%}); the reuse thesis "
            f"is not yet supported by the data"
        )


def compare_reuse(outcomes: Sequence[RunOutcome]) -> ReuseComparison:
    """Split runs by whether they used a registry asset, and compare."""
    with_reuse = [o for o in outcomes if o.registry_assets_used]
    without_reuse = [o for o in outcomes if not o.registry_assets_used]
    return ReuseComparison(
        with_reuse=compute_acceptance(with_reuse),
        without_reuse=compute_acceptance(without_reuse),
    )
