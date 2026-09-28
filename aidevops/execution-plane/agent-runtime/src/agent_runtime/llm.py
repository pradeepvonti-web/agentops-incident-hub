"""Model calls, with cost and shape recorded on every one.

Two things this module exists to guarantee:

1. **Every call emits a span.** Tokens, cost, model and cache hits reach the
   control plane; the prompt and completion do not (ADR-0003 §3). Cost per
   accepted run is a number we will be asked for, and it cannot be backfilled.

2. **Structured output, not prose parsing.** Both agent steps return a validated
   Pydantic model via `messages.parse`. An agent that returns markdown and a
   regex that scrapes it is a bug generator; `output_format` makes malformed
   output an API error rather than a silent mis-parse.
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from typing import Protocol, TypeVar

import anthropic
import structlog
from adp_contracts import LlmCall, Run, Span, StepKind, StepStatus
from pydantic import BaseModel

log = structlog.get_logger(__name__)

MODEL = "claude-opus-5"

#: Cached from the pricing table, 2026-06-24. Used only to attribute spend to a
#: run; billing is whatever Anthropic invoices. If these drift the reported cost
#: drifts with them, which is why the portal shows cost *per run* rather than a
#: total anyone would reconcile against an invoice.
INPUT_USD_PER_MTOK = 5.00
OUTPUT_USD_PER_MTOK = 25.00

T = TypeVar("T", bound=BaseModel)


class TraceEmitter(Protocol):
    def emit(self, span: Span) -> None: ...


def estimate_cost(tokens_in: int, tokens_out: int) -> float:
    return (
        tokens_in / 1_000_000 * INPUT_USD_PER_MTOK
        + tokens_out / 1_000_000 * OUTPUT_USD_PER_MTOK
    )


class LlmError(RuntimeError):
    """A model call failed in a way the loop may be able to act on."""

    def __init__(self, message: str, *, error_class: str, retryable: bool) -> None:
        super().__init__(message)
        self.error_class = error_class
        self.retryable = retryable


class ModelClient:
    """Wraps the Anthropic client so no agent code calls it directly.

    Keeping this a single choke point means the span, the cost attribution and
    the error taxonomy cannot be forgotten by a new agent -- the same reason the
    MCP Gateway is the only path to enterprise systems.
    """

    def __init__(
        self,
        *,
        run: Run,
        traces: TraceEmitter,
        client: anthropic.Anthropic | None = None,
    ) -> None:
        # Zero-arg construction resolves ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN,
        # or an `ant auth login` profile. No key is read or stored here.
        self._client = client or anthropic.Anthropic()
        self._run = run
        self._traces = traces
        self.total_cost_usd = 0.0

    def structured(
        self,
        *,
        system: str,
        prompt: str,
        output_format: type[T],
        step_kind: StepKind,
        max_tokens: int = 16000,
        attempt: int = 1,
    ) -> T:
        """One call returning a validated model instance.

        Thinking is left unset: it is on by default for Opus 5, and the default
        effort (`high`) is what this work wants. Setting it explicitly alongside
        `output_format` buys nothing and adds a way to get it wrong.
        """
        run = self._run
        started = datetime.now(UTC)
        t0 = time.monotonic()

        def record(
            status: StepStatus,
            *,
            usage=None,
            error_class: str | None = None,
        ) -> None:
            tokens_in = getattr(usage, "input_tokens", 0) or 0
            tokens_out = getattr(usage, "output_tokens", 0) or 0
            cost = estimate_cost(tokens_in, tokens_out)
            self.total_cost_usd += cost

            self._traces.emit(
                Span(
                    span_id=f"llm-{uuid.uuid4().hex[:12]}",
                    parent_span_id=run.run_id,
                    name=f"llm:{step_kind}",
                    started_at=started,
                    ended_at=datetime.now(UTC),
                    status=status,
                    error_class=error_class,
                    tenant_id=run.tenant_id,
                    run_id=run.run_id,
                    agent_type=str(run.agent_type),
                    agent_principal=run.principal.agent.name,
                    environment=str(run.environment),
                    invoked_by=run.principal.invoked_by,
                    step_kind=step_kind,
                    attempt=attempt,
                    llm_call=LlmCall(
                        model=MODEL,
                        tokens_in=tokens_in,
                        tokens_out=tokens_out,
                        cost_usd=round(cost, 6),
                        duration_ms=int((time.monotonic() - t0) * 1000),
                        cache_hit=bool(
                            getattr(usage, "cache_read_input_tokens", 0) or 0
                        ),
                        # Excluded from the control-plane projection. Kept here so
                        # the tenant-local trace can answer "what did it actually
                        # say" during an incident.
                        prompt=prompt,
                    ),
                )
            )

        try:
            response = self._client.messages.parse(
                model=MODEL,
                max_tokens=max_tokens,
                system=[
                    {
                        "type": "text",
                        "text": system,
                        # The system prompt carries the enterprise conventions and
                        # is stable across every run for a tenant. Caching it is
                        # the single largest cost lever in this loop.
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": prompt}],
                output_format=output_format,
            )
        except anthropic.RateLimitError as exc:
            record(StepStatus.FAILED, error_class="llm_rate_limited")
            raise LlmError(
                "rate limited by the model API", error_class="llm_rate_limited",
                retryable=True,
            ) from exc
        except anthropic.APIConnectionError as exc:
            record(StepStatus.FAILED, error_class="llm_unreachable")
            raise LlmError(
                "could not reach the model API", error_class="llm_unreachable",
                retryable=True,
            ) from exc
        except anthropic.BadRequestError as exc:
            # Usually our fault: a prompt over the context window, or a schema
            # the API rejected. Not retryable without a change.
            record(StepStatus.FAILED, error_class="llm_bad_request")
            raise LlmError(
                f"the model API rejected the request: {exc}",
                error_class="llm_bad_request", retryable=False,
            ) from exc
        except anthropic.APIStatusError as exc:
            record(StepStatus.FAILED, error_class=f"llm_http_{exc.status_code}")
            raise LlmError(
                f"model API error {exc.status_code}",
                error_class=f"llm_http_{exc.status_code}",
                retryable=exc.status_code >= 500,
            ) from exc
        except TypeError as exc:
            # The SDK constructs happily with no credentials and only fails when
            # it builds request headers, raising TypeError rather than one of its
            # own exception types. Catching it here is the difference between a
            # one-line fix and a stack trace through _base_client.
            if "authentication" not in str(exc).lower():
                raise
            record(StepStatus.FAILED, error_class="llm_no_credentials")
            raise LlmError(
                "no Anthropic credentials found. Set ANTHROPIC_API_KEY, "
                "ANTHROPIC_AUTH_TOKEN, or run `ant auth login`.",
                error_class="llm_no_credentials",
                retryable=False,
            ) from exc

        # A refusal is a 200 with no usable content. Check before reading output,
        # or the failure surfaces as a confusing attribute error three frames up.
        if response.stop_reason == "refusal":
            detail = getattr(response.stop_details, "category", None)
            record(
                StepStatus.FAILED,
                usage=response.usage,
                error_class="llm_refusal",
            )
            raise LlmError(
                f"the model declined this request (category: {detail})",
                error_class="llm_refusal", retryable=False,
            )

        if response.stop_reason == "max_tokens":
            # Structured output truncated mid-object. Retryable only with a
            # larger budget, so the loop must not simply try again.
            record(
                StepStatus.FAILED, usage=response.usage, error_class="llm_truncated"
            )
            raise LlmError(
                f"output hit the {max_tokens} token cap before completing",
                error_class="llm_truncated", retryable=False,
            )

        record(StepStatus.SUCCEEDED, usage=response.usage)

        log.info(
            "llm_call",
            run_id=run.run_id,
            step=str(step_kind),
            model=MODEL,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            cost_usd=round(estimate_cost(
                response.usage.input_tokens, response.usage.output_tokens
            ), 4),
        )
        return response.parsed_output
