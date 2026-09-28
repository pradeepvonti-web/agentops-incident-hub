# Architecture Decision Records

Decisions that are expensive to reverse. Each ADR is immutable once `Accepted` —
supersede it with a new one rather than editing it.

| ADR | Title | Status | Reversibility |
|-----|-------|--------|---------------|
| [0001](0001-tenancy-model.md) | Tenancy: pooled control plane, isolated execution plane | Accepted (+1 amendment) | Very low — rewrite |
| [0002](0002-agent-identity.md) | Agent identity: one workload identity per agent per tenant | Accepted (+1 amendment) | Low — re-onboard every tenant |
| [0003](0003-trace-model.md) | Trace model: OTel spans, payloads stay in tenant | Accepted | Low — historical data not backfillable |
| [0004](0004-databricks-ai-tools.md) | Databricks AI Tools: adopt the skills, not the tool surface | Accepted | Medium — swapping tool surfaces |
| [0005](0005-one-platform-with-restora.md) | One platform: the control plane inside the Restora shell, Supabase Auth for humans | Accepted | Medium — a second shell and identity path |

## Why the first three came first

They are the decisions that cannot be deferred:

- **Tenancy** determines whether a second customer costs a week or a quarter.
- **Agent identity** is the first question the design partner's security review asks,
  and the answer has to be in the code before the review, not after.
- **Trace model** cannot be backfilled. Data not captured on run #1 is gone, and it
  is the data that proves the agents work.

0004 came later, on reading what Databricks already ships. It is here because
"build on the vendor's tools" is the kind of decision that looks free at the time
and is expensive to unwind once a product depends on it.

## Template

```
# ADR-NNNN: Title
Status / Date / Deciders / Context / Decision / Consequences / Alternatives considered
```
