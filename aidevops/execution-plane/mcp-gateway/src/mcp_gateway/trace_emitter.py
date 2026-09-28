"""Trace emission. Implements ADR-0003 sections 3 and 4.

The privacy boundary is enforced here, in the customer's own process, before
anything is serialised for export. A payload that was never serialised cannot leak.

Two emitters, always both:

  * `LocalTraceSink`  -- full span, payloads included, stays in the tenant.
  * `ControlPlaneTraceExporter` -- `span.for_control_plane()` only, metadata tier.

The exporter **fails closed**. If it cannot determine what is safe to send, it
sends nothing. Losing telemetry is recoverable; leaking a customer's schema names
is not.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

import structlog
from adp_contracts import Environment, Span

log = structlog.get_logger(__name__)


class TraceEmitter(Protocol):
    def emit(self, span: Span) -> None: ...


class LocalTraceSink:
    """Full-fidelity traces, written inside the customer's subscription.

    JSONL on disk in v0. Month 2 points this at the customer's own Azure Monitor
    workspace so they can query agent behaviour with the tooling they already have
    -- which is also the answer to "how do we debug without seeing payloads": they
    can, and they can send us what they choose.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, span: Span) -> None:
        record = span.model_dump(mode="json")
        # Payload and tool arguments are `exclude=True` on the models, so add them
        # back deliberately -- this sink is the one place they belong.
        record["payload"] = span.payload
        if span.tool_call is not None:
            record["tool_call"]["arguments"] = span.tool_call.arguments
            record["tool_call"]["result"] = span.tool_call.result

        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")


class ControlPlaneTraceExporter:
    """Metadata-tier export to our control plane.

    Everything this class sends comes from `Span.for_control_plane()`, which builds
    its output from an explicit allowlist. This class never reads span fields
    directly, and it must not start doing so -- that is what keeps a newly added
    field from leaking by default.
    """

    def __init__(self, *, endpoint: str, tenant_id: str, enabled: bool = True) -> None:
        self._endpoint = endpoint
        self._tenant_id = tenant_id
        self._enabled = enabled

    def emit(self, span: Span) -> None:
        if not self._enabled:
            return

        missing = span.missing_required_attributes()
        if missing:
            # Fail closed: a span we cannot fully attribute is a span we do not
            # export. This is deliberately loud -- it should break CI.
            log.error(
                "span_missing_required_attributes",
                missing=sorted(missing),
                span_id=span.span_id,
                detail="span not exported",
            )
            return

        try:
            projected = span.for_control_plane()
        except Exception:  # noqa: BLE001 - never let projection failure leak a raw span
            log.exception("span_projection_failed", span_id=span.span_id)
            return

        # STUB -- Month 1. Batched OTLP over HTTPS to the control plane collector,
        # outbound-only (ADR-0001). Batching matters: one request per span will not
        # survive a real workload. Until then, log the projection so the boundary is
        # observable in development.
        log.debug("control_plane_span", **projected)


class FanOutEmitter:
    """Emit to several sinks. One sink failing must not stop the others."""

    def __init__(self, *emitters: TraceEmitter) -> None:
        self._emitters = emitters

    def emit(self, span: Span) -> None:
        for emitter in self._emitters:
            try:
                emitter.emit(span)
            except Exception:  # noqa: BLE001
                log.exception(
                    "trace_emitter_failed", emitter=type(emitter).__name__
                )


def build_trace_emitter(
    *,
    tenant_id: str,
    environment: Environment,
    local_path: Path | None = None,
    control_plane_endpoint: str | None = None,
) -> TraceEmitter:
    local = LocalTraceSink(
        local_path or Path(f"/var/log/adp/traces-{tenant_id}-{environment}.jsonl")
    )

    if control_plane_endpoint is None:
        log.warning(
            "control_plane_export_disabled",
            detail="no endpoint configured; traces stay local only",
        )
        return local

    return FanOutEmitter(
        local,
        ControlPlaneTraceExporter(
            endpoint=control_plane_endpoint, tenant_id=tenant_id
        ),
    )
