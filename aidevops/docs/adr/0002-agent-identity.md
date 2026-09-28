# ADR-0002: Agent identity — one workload identity per agent, per tenant, per environment

**Status:** Accepted
**Date:** 2026-09-25
**Deciders:** Founding team
**Depends on:** [ADR-0001](0001-tenancy-model.md)

## Context

Our agents take real actions against production systems: they read Unity Catalog,
submit Databricks jobs, and open pull requests. An agent is a non-human principal
acting autonomously, and the first question every enterprise security review asks is:

> *"What can this thing do, who authorized it, and how do I revoke it at 3am?"*

"The agent runs as the platform service account" is not an answer that survives that
question. It gives every agent the union of all permissions any agent needs, and it
makes the audit log useless — every action attributes to one identity.

There is a second, subtler requirement. Agents act **on behalf of** a human who made
a request, and the permissions that apply must be the intersection of what the agent
is allowed to do and what that human is allowed to do. An agent must never become a
privilege-escalation path for the user who invoked it.

## Decision

### 1. Identity granularity

One Microsoft Entra ID workload identity per **(agent_type, tenant, environment)**.

```
agent-data-engineering-acme-dev
agent-data-engineering-acme-prod
agent-data-quality-acme-dev
agent-data-quality-acme-prod
```

The Data Engineering agent in prod is a different principal from the same agent in
dev, and from the Data Quality agent anywhere. Revocation is per-agent, per-environment,
and takes effect immediately. Audit logs attribute to a specific agent.

### 2. No secrets — federated credentials only

Agents authenticate via **workload identity federation**. The runtime's Kubernetes
service account (or Container App managed identity) exchanges a platform-issued token
for an Entra token. There is no client secret and no certificate to rotate, leak,
or check into a repository.

Databricks access uses the same identity through a service principal federated to
Entra — no Databricks personal access tokens, anywhere, ever.

### 3. Least privilege, declared in code

Each agent's permissions are declared in `execution-plane/mcp-gateway/policy/agents.yaml`,
provisioned by Terraform, and enforced at two layers:

- **Coarse, at the platform:** Azure RBAC role assignments and Unity Catalog grants.
  The Data Engineering agent has `USE CATALOG` + `SELECT` on bronze/silver and
  `MODIFY` on its own target schema — and nothing on gold.
- **Fine, at the gateway:** a per-agent tool allowlist with argument-level constraints
  (see [ADR-0003](0003-trace-model.md) for how each decision is recorded).

Both layers are required. Platform grants are the real boundary; the gateway policy
catches mistakes earlier, with a better error message, and gives us an auditable
record of intent.

### 4. On-behalf-of, and the intersection rule

Every run carries the invoking human's identity. The effective permission set is:

```
effective = agent_permissions ∩ invoking_user_permissions
```

An agent invoked by an analyst cannot write to a schema that analyst cannot write to,
even where the agent's own service principal could. This closes the confused-deputy
hole where an agent becomes an escalation path.

### 5. Human approval is a separate identity act

Approvals (ADR-0003 step kind `approve`) are authenticated as the **human**, never
the agent, and are recorded with that human's identity, the exact artifact digest
approved, and a timestamp. An agent cannot approve its own work, and the approval
binds to content — if the diff changes after approval, the approval is void.

### 6. Blast-radius limits

- Agent tokens are scoped to a single run and expire in 15 minutes, renewed per step
- Write operations to prod require an approved `approve` step in the same run
- Destructive tools (`DROP`, `TRUNCATE`, force-push) are not exposed as tools at all
  in v0 — not policy-gated, absent
- Per-agent, per-hour rate limits on tool calls, enforced at the gateway

## Consequences

**Good**
- Security review has a concrete, demonstrable answer
- Revocation is granular and immediate — disable one principal, one environment
- Audit trail attributes every action to a specific agent and a specific human
- No secrets to rotate or leak
- Adding an agent is a policy entry plus a Terraform apply, not a security exception

**Bad — accepted**
- Identity count grows as `agents × tenants × environments`. At 3 agents, 10 tenants,
  3 environments that is 90 principals. Provisioning must be fully automated from
  day one — manual creation does not scale past the design partner.
- Local development needs a credential path that is neither production nor a shared
  secret. Developers use their own Entra identity with a dev-only policy; the gateway
  refuses to start in `prod` mode without federation.
- The intersection rule requires resolving the invoking user's permissions per run,
  which costs a Unity Catalog and Graph lookup. Cached for the run's lifetime.

**Follow-up required**
- Automated provisioning module: `infra/terraform/modules/agent-identity`
- Quarterly access review export of every agent principal and its grants
- Alert on any agent principal receiving a grant outside Terraform

## Alternatives considered

**One service principal for the whole platform.** Trivial to build. Rejected: union
of all permissions, useless audit trail, no granular revocation. This is the design
that fails the security review.

**One service principal per tenant, shared across agents.** Better isolation between
customers. Rejected: within a tenant, a compromised or misbehaving BI agent can do
anything the Data Engineering agent can, and the audit log cannot distinguish them.

**Per-run ephemeral identities.** Strongest isolation. Rejected for v0: Entra
principal creation is slow and rate-limited, and it would put identity provisioning
on the critical path of every run. Revisit if per-run scoping is ever demanded.

**Pure on-behalf-of — agents act only as the invoking user.** Attractively simple.
Rejected: agents legitimately need permissions no single user has (writing platform
telemetry, reading the registry), and unattended and scheduled runs have no invoking
user at all.

---

## Amendment 1 — 2026-09-26: deployment is the customer's pipeline, not ours

**Status:** Accepted. Narrows section 6 above.

### What changed

Section 6 said prod writes require an approved `approve` step in the same run, and
gated `databricks_submit_job` accordingly. That treated *us* as the deployment
mechanism, with an approval gate bolted on.

A Databricks shop of any size already has a deployment mechanism: **Databricks
Asset Bundles**. Jobs live as `resources/*.yml` beside `source/*.py` under a
`databricks.yml`; a single `main` is promoted dev → test → prod; their CI runs the
tests, `bundle validate` produces the plan, a tech lead approves, and their CD runs
`bundle deploy`. An agent submitting ad-hoc job runs routes around all of it — the
approval gates, the environment parity, the audit trail — which is precisely the
"engineers writing custom deployment scripts" problem bundles exist to solve.

### Decision

**Our agents generate bundle files and open a pull request. They do not deploy.**

- `databricks_bundle_deploy`, `databricks_bundle_destroy` and
  `databricks_bundle_run` are on the never-expose list. Not gated — absent.
- `databricks_bundle_validate` is exposed, because it is the *plan* step: it
  writes nothing, and it is the same command the customer's reviewer already runs.
- `databricks_submit_job` is demoted to `environments: ["dev"]`. It is the agent's
  own iteration loop — trying a transformation against dev data before committing
  it to a bundle — not a deployment path.
- The `deploy` step in the agent loop is now a **handoff**: it records that the
  artifact was approved and the pull request is ready to merge.

### Consequences

**Good**
- Removes a whole category of security objection. "Your agent deploys to our
  production" is a hard conversation; "your agent opens a pull request our existing
  pipeline handles like any other" is not a conversation at all.
- Less of our code sits on the critical path to their prod, so less of it has to
  clear their change-management process.
- `human_edit_lines` (ADR-0003 §5) gets cleaner: the diff between proposed and
  merged is already a PR diff in their repository.
- We inherit their approval gates, their environment parity and their audit trail
  rather than reimplementing three things they already have.

**Bad — accepted**
- We cannot close the loop ourselves. Time-to-production now depends on a pipeline
  we do not control, so "pipelines shipped" becomes a shared metric rather than
  one we can move alone.
- We must produce bundle files that fit *their* conventions — repository layout,
  naming, shared variables in `databricks.yml`. That is client-specific work and
  belongs in the customization ledger.
- A customer not yet using bundles needs that adopted first. For them, bundle
  adoption becomes phase one of the engagement rather than a prerequisite we can
  assume.

**Follow-up required**
- Confirm the client's CD tool and which repository their pipeline watches. The
  agent has to open pull requests into that repo, not a repo of ours.
- Seed the registry with *their* bundle patterns, not generic ones.

### Alternatives considered

**Keep a gated deploy tool.** Our own `bundle deploy` behind the approval gate.
Rejected: it duplicates a mechanism they already trust, puts us on the critical
path to production, and makes the security review materially harder for no gain.

**Generate notebooks and submit jobs directly.** What we built first. Rejected on
reading how bundles are actually used at scale — it produces exactly the
inconsistency between environments that the bundle workflow exists to remove.

**Generate bundles *and* run the deploy in dev only.** Tempting as a middle
ground. Rejected for now: two deployment paths means two things to audit, and dev
is where `databricks_submit_job` already serves the iteration need.
