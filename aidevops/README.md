# Data & Analytics AI DevOps Platform

Agentic data engineering on Azure + Databricks, with a human in the loop.

An **agentic control plane** for data engineering. Agents plan, generate and validate
pipelines; humans approve them as pull requests; everything is traced so we can prove
the agents actually work.

We do not build storage, compute or query engines. Databricks does that. We build the
layer above it.

This folder is one half of a single platform. The other half is Restora, the
incident management product at the repository root; its React application is
the shell these screens render in, and its alerts are where a failed agent run
lands. [ADR-0005](docs/adr/0005-one-platform-with-restora.md) is the decision.

---

## The one thing to understand first

The product is **two planes**, and almost every design decision follows from the
split:

```
  Our Azure subscription                Customer's Azure subscription
  ----------------------                -----------------------------
  CONTROL PLANE (multi-tenant)          EXECUTION PLANE (isolated)
   - Shell, API                          - Agent runtime
   - Orchestrator, work queue            - MCP Gateway
   - Reusable Asset Registry             - All credentials (their Key Vault)
   - Evaluation, acceptance rate         - Full traces, with payloads
   - Metadata only                       - All data access
                        ^                       |
                        |____ outbound poll ____|
```

**The customer's data and credentials never leave their subscription.** The execution
plane polls us; we never call into their network. That is what makes an enterprise
security review a short conversation, and it is not retrofittable.

Read [ADR-0001](docs/adr/0001-tenancy-model.md) before changing anything structural.

---

## Architecture decisions

Decisions that are expensive to reverse. Read them before writing code.

| ADR | Decision | Why it had to be first |
|-----|----------|------------------------|
| [0001](docs/adr/0001-tenancy-model.md) | Pooled control plane, isolated execution plane | A second customer costs a Terraform apply, not a quarter |
| [0002](docs/adr/0002-agent-identity.md) | One workload identity per agent, per tenant, per environment | First question the security review asks |
| [0003](docs/adr/0003-trace-model.md) | OTel spans, payloads stay in tenant | Traces cannot be backfilled |
| [0004](docs/adr/0004-databricks-ai-tools.md) | Adopt Databricks' skills, not its tool surface | Vendor tools look free and are expensive to unwind |
| [0005](docs/adr/0005-one-platform-with-restora.md) | The control plane inside the Restora shell; Supabase Auth for humans | One team, one front door, one identity |

Full architecture: [docs/architecture/v3-platform-architecture.html](docs/architecture/v3-platform-architecture.html)

---

## Layout

```
packages/adp-contracts/      Shared models. The only code both planes import.
control-plane/               Multi-tenant SaaS: API, store, evaluation (orchestrator: Month 2)
execution-plane/
  agent-runtime/             The seven-step loop: plan -> ... -> monitor
  mcp-gateway/               Single mediated path from agents to enterprise systems
infra/terraform/             Both planes, as code
templates/                   The Databricks bundle a run produces
docs/adr/                    Architecture decision records

../frontend/src/pages/devops/   The screens, inside the Restora shell (ADR-0005)
../frontend/src/lib/controlPlane.ts   The shell's client for this API
../supabase/migrations/         The database, both schemas, one folder
```

---

## Getting started

From this folder:

```bash
uv sync
uv run pytest
uv run ruff check .
terraform -chdir=infra/terraform/execution-plane validate
```

171 tests, 6 skipped without a live database. They are mostly security-property
tests rather than feature tests -- each one corresponds to a claim we make to the
design partner's security review.

### Running the control plane

```bash
cp .env.example .env     # DATABASE_URL, SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY
uv run uvicorn control_plane.api.app:app --port 8010
```

or the `control-plane` launch configuration. `Settings.from_env` reads `.env`
when a variable is not already exported. Without `DATABASE_URL` the API starts,
`/health` reports `database_configured: false`, and every portal route answers
503 naming the variable.

Then start the shell (`frontend/`, the `web` launch configuration), sign in, and
open **AI DevOps** in the sidebar. A signed-in user with no row in
`public.tenant_members` is placed in `ADP_DEV_TENANT` as an approver in
development; in any other environment they get a 403. To map a real user:

```sql
insert into public.tenant_members (auth_user_id, tenant_id, role)
values ('<auth.users.id>', 'acme', 'approver');
```

### Live database tests

```bash
DATABASE_URL='postgresql://...' uv run pytest control-plane/tests/test_supabase_integration.py
```

Not in the default suite on purpose: a test that needs a network and a credential
should not be able to fail someone's local run for reasons unrelated to their change.

---

## What exists, and what does not

Honest status. `STUB -- Month 1` in the source marks each gap, with implementation
notes attached.

### Working

- **Contracts** -- run, span, outcome, identity, entry models with validation
- **Privacy boundary** -- `Span.for_control_plane()` allowlist projection, with a
  test that fails if a future field leaks
- **Policy engine** -- per-agent tool allowlists, constraints, rate limits,
  the on-behalf-of intersection rule, default deny
- **Approval binding** -- approvals bind to an artifact digest and go void if the
  artifact changes; the API refuses a stale digest with a 409
- **Acceptance rate** -- computed, with a small-sample guard and the reuse comparison
- **Agent identity Terraform** -- federated credentials, no secrets, UC grants
- **Portal API** -- `/v1/runs`, `/v1/runs/{id}` with the span tree, approvals
  gated by role, `/v1/runs/stats`, `/v1/entry/runs` queuing a run,
  `/v1/entry/adoption`; every read inside a tenant scope
- **Portal identity** -- Supabase session verified against Supabase Auth,
  tenant from `tenant_members`, dev-only fallback (ADR-0005)
- **Postgres store** -- migrations applied and exported to `supabase/migrations/`,
  RLS forced, `adp_app` non-bypassing role, tenant-scoped repository
- **The shell** -- home with the composer, runs grouped by status, run detail
  with trace and approval, entry points with adoption
- **Bridge to Restora** -- a failed or rolled-back run raises an alert, by trigger

### Stubbed

- Model calls in `plan` and `generate`
- Azure DevOps REST calls in `git_open_pull_request` (payloads are built; three
  calls remain)
- MCP stdio binding in `server.py:main`
- Execution-plane token validation (`require_execution_plane`): the runtime
  cannot yet claim work or post spans
- The orchestrator: a submitted run is queued and visible, and nothing picks it up
- Unity Catalog effective-permissions lookup
- Container apps in the execution plane Terraform

---

## Invariants

Things that must stay true. Each has a test; if you break one, the test tells you
which promise you are breaking.

1. **No payload field reaches the control plane.** The `for_control_plane()`
   projection is allowlist-based.
   `packages/adp-contracts/tests/test_privacy_boundary.py`
2. **Default deny.** An agent with no policy entry can call nothing.
3. **An agent never exceeds its invoking human.** The intersection rule.
4. **An agent opens pull requests; it never merges one.**
5. **Approval binds to content, not to a run.** And a member cannot approve.
   `control-plane/tests/test_portal_api.py`
6. **Every step emits a span, including failures and denials.**
7. **Prod writes require an approved step in the same run.**
8. **Every read of tenant data opens a scope first.** The one exception is the
   membership lookup that chooses the scope, and it is one method.
   `control-plane/tests/test_tenant_scope.py`, `test_identity.py`

---

## The metric

**Acceptance rate** -- the percentage of agent outputs merged without human edit.

Always reported with clean-accept rate, median edit ratio and `n`.
`control-plane/src/control_plane/evaluation/acceptance.py` refuses to describe a
sample below 20 as meaningful, because an 80% acceptance rate over five runs is
noise and it is exactly the number that ends up on a slide. The shell shows the
number greyed, with its `n`, until it means something.
