# ADR-0001: Tenancy — pooled control plane, isolated execution plane

**Status:** Accepted
**Date:** 2026-09-25
**Deciders:** Founding team
**Supersedes:** —

## Context

We are building a multi-tenant SaaS product whose agents generate and deploy data
pipelines against customer systems: Databricks, Unity Catalog, SAP, production
databases, Azure DevOps.

Three constraints shape this decision:

1. **Enterprise buyers will not let a startup hold their credentials.** Our design
   partner's security team has to sign off before production. A design where customer
   secrets or customer data transit our cloud fails that review and there is no
   argument that wins it.
2. **Data residency and sovereignty.** EU and regulated customers require that data
   never leaves their subscription or region.
3. **We are 2–5 people.** We cannot operate a per-customer control plane, and
   retrofitting multi-tenancy onto a single-tenant product is a rewrite, not a refactor.

## Decision

Split the product into two planes, following the model Databricks itself uses.

### Control plane — ours, multi-tenant, pooled

Runs in our Azure subscription. Holds:

- Portal and API
- Orchestrator: run scheduling, agent selection, work queue
- Reusable Asset Registry (templates, DQ rules, transformation and prompt patterns)
- Evaluation store: metrics, scores, acceptance rate
- Identity, billing, tenant configuration

**Never holds:** customer data, customer credentials, or by default the payload
contents of prompts, generated code, or tool results.

Tenant isolation is enforced at three levels:
- `tenant_id` on every row, non-nullable
- PostgreSQL Row-Level Security, with the tenant set per connection from the
  authenticated principal — application code cannot forget the `WHERE` clause
- A tenant-scoped repository layer; raw SQL against tenant tables is rejected in CI

### Execution plane — customer's Azure subscription, isolated

Deployed by Terraform into the customer's tenant. Contains:

- Agent runtime (plan → tool → generate → validate → deploy)
- MCP Gateway and all tool implementations
- All credentials, in the customer's Key Vault
- Full traces including payloads

### Connection: outbound-only

The execution plane **polls** the control plane for work over an authenticated
outbound HTTPS connection. The control plane never initiates a connection into the
customer network.

This is deliberate and is the detail that makes enterprise network review
straightforward: no inbound firewall rules, no public ingress into the customer's
VNet, no site-to-site VPN, no IP allowlisting on their side.

```
Customer Azure Subscription          |   Our Azure Subscription
                                     |
  ┌─────────────────────────┐        |   ┌──────────────────────┐
  │ Agent Runtime           │        |   │ Orchestrator         │
  │ MCP Gateway             │──poll──┼──▶│ Work queue           │
  │ Key Vault (secrets)     │        |   │ Registry             │
  │ Traces (full payloads)  │──otel──┼──▶│ Metrics only         │
  └───────────┬─────────────┘        |   └──────────────────────┘
              │ private endpoints    |
      Databricks / SAP / ADLS        |
```

## Consequences

**Good**
- Customer data and credentials never leave their subscription; residency is theirs
- Security review becomes a short conversation instead of a negotiation
- Blast radius of a compromise of our control plane excludes customer data
- Second tenant costs a Terraform apply, not an engineering quarter

**Bad — accepted**
- We cannot debug customer runs by reading payloads. Diagnosis depends on the metrics
  and redacted metadata in ADR-0003, plus a customer-initiated support bundle. This
  will hurt and we are accepting it deliberately.
- Upgrades are distributed. The execution plane is versioned software in someone
  else's cloud, so we need version skew tolerance and a documented support window
  from day one. The control plane API must stay backward compatible for at least
  two execution-plane minor versions.
- Higher per-tenant onboarding cost than a pure-SaaS design.
- We carry Terraform as a shipped product surface, and it needs the same review and
  release discipline as application code.

**Follow-up required**
- Version negotiation on the poll endpoint (execution plane reports its version)
- Support bundle: customer-triggered, redacted, explicitly consented
- Onboarding runbook, target under one day (Month 5 milestone)

## Alternatives considered

**Pure SaaS — everything in our cloud.** Simplest to build and operate, fastest to
second customer. Rejected: fails enterprise security review for a startup vendor
handling production credentials, and forecloses regulated and EU customers entirely.

**Fully single-tenant — a dedicated control plane per customer.** Strongest isolation.
Rejected: operationally impossible at our headcount, and it turns every customer into
a bespoke deployment — the consultancy failure mode.

**Agent runtime in our cloud, connecting into customer networks via VPN or
PrivateLink.** Rejected: inbound access into the customer network is the hardest
thing to get approved, we would still hold credentials, and it multiplies networking
support burden per customer.

---

## Amendment 1 — 2026-09-25: FORCE is not sufficient; BYPASSRLS defeats it

**Status:** Accepted. Amends the "Tenant isolation is enforced at three levels"
section above.

### What we got wrong

The original decision said RLS with `FORCE ROW LEVEL SECURITY` was the enforcement
layer, and called FORCE "not optional" because the table owner would otherwise
bypass the policy. That was right as far as it went, and still not enough.

**A role with the `BYPASSRLS` attribute ignores row-level security entirely,
including `FORCE`.** In Supabase, both `postgres` and `service_role` carry it. A
control plane connecting as either has *no tenant isolation whatsoever*, while
every table reports `rowsecurity = true`, `forcerowsecurity = true` and one policy
attached. The catalog looks correct. The isolation does not exist.

This was caught by an isolation test that inserted two tenants and asserted a
cross-tenant read returned nothing. It returned both rows. No amount of reading
the schema would have found it.

### Decision

A fourth level, and the one that actually bites:

**The application connects as a role with no `BYPASSRLS`.** Concretely, a `NOLOGIN`
role `adp_app` that the application *drops into* per transaction:

```sql
select public.begin_tenant_scope('acme');  -- SET LOCAL ROLE adp_app + set tenant
```

`begin_tenant_scope` does both things in one call on purpose. Two separate
functions would allow setting a tenant while still holding a role that ignores it,
which is precisely the failure above. Both settings are `LOCAL`, so they revert on
commit or rollback and a pooled connection cannot carry one request's tenant or
privilege into the next.

`NOLOGIN` is deliberate: there is no new credential to rotate or leak. The
application keeps its existing connection and gives up privilege rather than
acquiring it.

### Consequences

- Admin paths (tenant onboarding, migrations) still run as `postgres` and still
  bypass RLS. That is correct — but it means **any code path that forgets
  `begin_tenant_scope` silently has full cross-tenant access**. The repository
  layer must make that impossible to forget, not merely discouraged.
- The isolation test is now a permanent fixture, not a one-off. It asserts three
  things: each tenant sees only its own rows, and a query with *no* tenant context
  returns zero rows rather than everything.
- Anything that grants a new role access to tenant tables must be checked for
  `BYPASSRLS`. Add it to the access review in ADR-0002.

### Generalisation beyond Supabase

This is not a Supabase quirk. Any managed Postgres where the application's default
role is an admin has the same hole — AWS RDS `rdsadmin`-adjacent superusers, Azure
Database for PostgreSQL's `azure_pg_admin`. The rule is provider-independent:
**verify `rolbypassrls = false` on the role the application actually queries with,
and test it rather than assuming it.**
