# ADR-0003: Trace model — OpenTelemetry spans, payloads stay in the tenant

**Status:** Accepted
**Date:** 2026-09-25
**Deciders:** Founding team
**Depends on:** [ADR-0001](0001-tenancy-model.md), [ADR-0002](0002-agent-identity.md)

## Context

The product claim is "agents that generate production data pipelines." No enterprise
buys that on assertion. They buy it on a number, and the number is:

> **Acceptance rate — the percentage of agent outputs merged without human edit.**

That number, and every diagnostic that explains it, comes from traces. Traces cannot
be backfilled: whatever we fail to capture on run #1 is gone permanently. So the
trace model is a day-one decision, not a month-three feature.

ADR-0001 puts run execution in the customer's subscription and forbids customer data
in our control plane. That creates the tension this ADR resolves: we need telemetry
to improve the product, and we are not allowed to see the payloads.

## Decision

### 1. OpenTelemetry, with a fixed span hierarchy

Traces are OTel spans. Every run is one trace:

```
run                       (root span — one per agent invocation)
├── step:plan             agent decides what to do
├── step:tool             a gateway-mediated action
│   ├── tool_call         one MCP tool invocation
│   └── llm_call          one model call
├── step:generate         produce code / pipeline / model
├── step:validate         tests and checks
├── step:approve          human decision (ADR-0002 §5)
├── step:deploy           dev → test → prod
└── step:monitor          post-deploy observation
```

The seven step kinds are exactly the execution plane from the architecture. The
hierarchy is closed — new step kinds require an ADR — because the evaluation queries
and the portal UI both depend on it being stable.

### 2. Every span carries the same required attributes

```
tenant_id, run_id, agent_type, agent_principal, environment,
invoked_by, step_kind, attempt, checkpoint_id
```

`attempt` and `checkpoint_id` make retries and resumes analyzable rather than noise.
Spans missing a required attribute are rejected at the collector, loudly, in CI.

### 3. Two-tier storage — the privacy boundary

This is the core of the decision.

| | Customer tenant (full) | Our control plane (metadata) |
|---|---|---|
| Span structure and timing | Yes | Yes |
| Required attributes | Yes | Yes |
| Outcome, scores, error class | Yes | Yes |
| Token counts and cost | Yes | Yes |
| Prompts and completions | Yes | **No** |
| Generated code and diffs | Yes | **No** |
| Tool arguments and results | Yes | **Digests only** |
| Table, column, schema names | Yes | **Hashed** |

Payloads stay in the customer's subscription. What reaches us is shape, timing,
outcome and cost — enough to compute acceptance rate, find which step fails, and see
which registry assets help. Not enough to reconstruct their data model.

Tool arguments travel as **SHA-256 digests**. Two runs that called the same tool with
the same arguments produce the same digest, so we get deduplication and caching
analysis without seeing the values.

**Payload export is opt-in, per tenant, default off**, and when enabled it is scoped,
time-boxed, and surfaced in the portal as an active setting. Design partners
frequently enable it; we never assume it.

### 4. Redaction happens before the span leaves the process

Not at the collector, not at our ingest — in the SDK, in the customer's process.
A payload that was never serialized cannot leak. The exporter fails closed: if
redaction config cannot be loaded, it exports nothing rather than everything.

### 5. Outcome recording — the acceptance rate contract

Every run that reaches `step:approve` writes exactly one outcome:

```python
RunOutcome(
    run_id, accepted: bool,
    human_edit_lines: int,       # lines changed between agent output and merge
    rejection_reason: str | None,
    time_to_decision_seconds: int,
    registry_assets_used: list[str],
)
```

`human_edit_lines` is the honest metric. A run that is "accepted" after a human
rewrites half of it is not a success, and a binary flag would let us lie to ourselves.
Acceptance rate is reported alongside median edit distance, always.

`registry_assets_used` is how we prove the moat: runs that used a registry asset
should show a higher acceptance rate than runs that did not. If that gap does not
appear by Month 3, the reuse thesis is wrong and we need to know.

### 6. Sampling

Never sample runs. Volume is low (thousands/day at scale, not millions) and every run
is a product signal. Sample verbose sub-spans inside a run if cost demands it.

## Consequences

**Good**
- Acceptance rate is computable from day one, per tenant, per agent, per asset
- Privacy boundary is structural, not procedural — enforced by the exporter
- Standard OTel means customers can fan traces into their own Azure Monitor or
  Datadog with no work from us
- Retry and checkpoint analysis falls out of `attempt` / `checkpoint_id`
- Evaluation (Month 3) reads traces; no separate instrumentation needed

**Bad — accepted**
- We debug customer failures without payloads. Error *classes* and span shapes have
  to be rich enough to diagnose blind. Expect this to drive a support-bundle flow.
- Digest-only arguments mean we cannot answer "what were they actually querying"
  in aggregate. Accepted; it is the point.
- Hashing schema names loses cross-tenant pattern analysis ("everyone struggles with
  SAP BSEG"). We may add opt-in, consented schema-shape sharing later — it needs its
  own ADR.
- Strict required attributes will break builds when someone adds a span carelessly.
  Intentional.

**Follow-up required**
- Redacting exporter with fail-closed behavior, and a test that asserts no payload
  field ever reaches the control-plane exporter
- Evaluation golden set of ~50 tasks (Month 3)
- Portal run detail renders directly from the span tree

## Alternatives considered

**Custom logging, not OpenTelemetry.** Less initial ceremony. Rejected: we would
rebuild context propagation and sampling badly, and lose the customer-facing benefit
of exporting into their existing observability stack.

**Full payloads to the control plane, encrypted at rest.** Far better debugging and
far better training data. Rejected: it contradicts ADR-0001, and "we hold your
pipeline source and prompts, but encrypted" is a materially harder security
conversation than "we never receive them."

**Payloads in the tenant, nothing at all to the control plane.** Purest privacy.
Rejected: we could not compute acceptance rate across customers, which means we
could not prove the product works or steer the roadmap. The metadata tier is the
minimum viable telemetry and the two-tier split is the compromise.

**LangSmith / Langfuse as the trace backend.** Good tooling, fast start. Rejected as
the *system of record*: it puts a third party inside the customer's data boundary and
re-opens the ADR-0001 conversation. We emit OTel, so either can be attached by a
customer who already runs one.
