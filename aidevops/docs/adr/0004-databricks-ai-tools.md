# ADR-0004: Databricks AI Tools — adopt the skills, not the tool surface

**Status:** Accepted
**Date:** 2026-09-26
**Deciders:** Founding team
**Depends on:** [ADR-0002](0002-agent-identity.md)

## Context

Databricks ships [`databricks-solutions/ai-dev-kit`](https://github.com/databricks-solutions/ai-dev-kit),
which contains three things we could build on:

1. **Official agent skills** — now delivered as *Databricks AI Tools* through
   `databricks aitools install`, engineering-owned, agent-agnostic. Includes
   `databricks-dabs` (Asset Bundles), `databricks-pipelines`, `databricks-genie-agents`.
2. **A FastMCP server** — `databricks-mcp-server`, exposing Databricks operations
   as MCP tools.
3. **`databricks-tools-core`** — the SDK plumbing underneath both.

We have already built our own MCP Gateway with six narrow tools. The question is
whether to keep it, replace it with theirs, or wrap theirs.

Databricks' own guidance in the repo: *"We recommend skills instead, but maintain
this as a good foundation if a custom MCP server is required."*

## Decision

**Adopt the skills. Keep our own tool surface. Do not depend on their MCP server
or vendor `databricks-tools-core` into anything we sell.**

### 1. Adopt the official skills

`databricks-dabs` and friends encode how to write a good bundle — the conventions,
the pitfalls, the idioms — maintained by Databricks field engineering and updated
with the product. That is domain knowledge we would otherwise hand-roll into
prompts and then own forever.

This is the Enterprise Knowledge layer from the architecture, supplied free and
kept current by the vendor. Installed into the agent runtime image via
`databricks aitools install`.

It does not replace the Reusable Asset Registry. Their skills are how to write
*any* good bundle; the registry is how to write one that matches *this customer's*
conventions. Generic knowledge plus accumulated specifics — the second is the part
that compounds, and the part they cannot supply.

### 2. Do not adopt their MCP server as our tool surface

**Granularity is our security model, and theirs is shaped for a different threat.**

Their tools are coarse and action-parameterised:

```python
manage_jobs(action: str, ...)   # create | get | list | find_by_name | update | delete
manage_uc_grants(...)           # grant management
manage_uc_objects(...)          # including _delete_catalog_resource
```

That is the right shape for a human-supervised assistant in an editor, where the
engineer sees every call and a wrong one is an annoyance.

It is the wrong shape for a policy-governed agent that can run unattended. Our
policy engine allowlists by **tool name** and constrains by **argument shape**
(`target_schema_pattern`, `max_cluster_workers`, `environments`). Allowlisting
`manage_jobs` allows delete. To prevent that we would have to police an `action`
string, which inverts the model: instead of narrow tools that cannot do the
dangerous thing, we get one broad tool where policy is the only thing standing
between the agent and destruction.

Compare directly. We deliberately **do not implement** `databricks_delete_job` or
`uc_grant_privilege` — they are on the never-expose list, absent rather than
gated (ADR-0002 §6). Their server implements both, as `manage_jobs(action="delete")`
and `manage_uc_grants`. An agent that can grant privileges can escape every other
constraint we have built.

This is not a criticism of their design. It is a different product for a different
user, and the difference is exactly the one that matters to us.

### 3. Do not vendor `databricks-tools-core` into a sellable product

Tempting — it is tested SDK plumbing we would otherwise write. Rejected on the
licence.

`ai-dev-kit` is under the **Databricks proprietary "DB license"**, not an OSI
licence. Two clauses matter:

> *"You may not use the Licensed Materials except in connection with your use of
> the Databricks Services pursuant to the Agreement."*

> *"Databricks may terminate this license at any time on notice. Upon termination,
> you must permanently delete the Licensed Materials and all copies thereof."*

For **consulting delivery** into a client's own Databricks environment this is
fine: they hold a Databricks Agreement, and redistribution is permitted with the
NOTICE retained.

For the **ISV path** it puts a termination-on-notice clause under our product's
core. That is not a dependency to discover during diligence. We use the official
CLI and the public REST API — both covered by the customer's own Agreement — and
keep our own thin implementations.

## Consequences

**Good**
- We stop owning "how to write a bundle" and inherit it from the vendor.
- Our tool surface stays six narrow tools, and the never-expose list keeps meaning
  what it says.
- No proprietary licence under the part of the product we might sell.
- The skills work with any agent, so this survives a model or framework change.

**Bad — accepted**
- We maintain our own Databricks REST implementations rather than reusing theirs.
  That is real duplicated effort, and we are choosing it for the licence and the
  granularity, not because ours are better.
- The skills change as Databricks updates them. An `aitools install` that shifts
  guidance could move acceptance rate without any change on our side, so the
  installed version is pinned in the runtime image and upgraded deliberately.
- If Databricks later ships a *narrow*, policy-friendly tool surface under an OSI
  licence, this decision should be revisited. It is a reasonable thing for them
  to do.

**Follow-up required**
- Pin the AI Tools version in the agent runtime image; treat an upgrade as a change
  that needs an evaluation run before it ships.
- Record in the customization ledger that skills come from the vendor and registry
  assets come from the client — they are different property with different owners.

## Alternatives considered

**Wrap their MCP server behind our gateway.** Elegant on paper: they supply tools,
we supply policy, identity and tracing. Rejected because wrapping a coarse tool
does not make it narrow — we would be policing `action` strings, and a new action
added upstream would be allowed by default. The gateway's guarantee is that a tool
cannot do a thing, not that we noticed it trying.

**Use their server for reads, ours for writes.** Reduces our surface but splits the
audit trail across two systems with different identity handling, and ADR-0003
requires every tool call to trace identically. Rejected.

**Skip the skills and write bundle guidance ourselves.** Rejected: it is work the
vendor does better, updates more often, and gives away.
