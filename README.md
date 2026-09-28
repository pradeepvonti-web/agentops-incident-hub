# Restora

https://github.com/pradeepvonti-web/agentops-incident-hub · [CI](https://github.com/pradeepvonti-web/agentops-incident-hub/actions)

A complete reference project for learning **agentic engineering**: context
engineering, deterministic tooling, reusable skills, validation, and
parallel-agent-friendly development.

It is one platform with two products in one shell:

- **Restora** — incident management: on-call, alerts, incidents, status pages,
  post-incident review. The repository root.
- **AI DevOps** — an agentic control plane for data engineering on Azure +
  Databricks: agents plan, generate and validate pipelines, humans approve them
  as pull requests, everything is traced. `aidevops/`, with its own README and
  architecture decision records.

They share one Supabase project, one sign-in and one sidebar, and they meet in
the database: a failed agent run raises a Restora alert
(`aidevops/docs/adr/0005-one-platform-with-restora.md`).

The repository keeps its original name, `agentops-incident-hub`, as does
Restora's database schema, `agentops`. Both are identifiers, not brand.

## Features

- Supabase Postgres with row level security, triggers and SQL functions
- Supabase Auth: sign in, sign up, per-responder attribution on every action
- Declare incidents, post updates, move the lifecycle, assign a lead
- Actions, follow-ups and a post-incident checklist, all editable
- Alerts: sources, routes, acknowledge, resolve, escalate into an incident
- On-call schedules with overrides, and escalation paths
- Status page you can publish to, plus a public `/status` page needing no account
- Insights: MTTD, MTTR, volume by severity, status, category and service
- Service catalog with editable owners and tiers
- Workflows you can pause, enable and run
- Command palette (cmd-K) over every page and incident
- Live updates: every open tab follows the database
- FastAPI service for agents, with an SSE stream and an inbound alert webhook
- Marketing site with GSAP scroll animation, a three.js hero, an interactive incident channel and a generated demo video
- Deterministic incident-triage scripts, backend tests, GitHub Actions CI
- AI DevOps: a run composer, runs grouped by status, run detail with the span
  trace, approvals bound to an artifact digest and gated by role, entry-point
  adoption, and a control plane with forced row-level security per tenant

## Architecture

```text
              Supabase Postgres, one project
     schema agentops (Restora)     schema public (AI DevOps)
         |            |                     |
   React app ---- FastAPI /api/v1     Control plane API
   one shell,     agents, SSE,        aidevops/, tenant-scoped,
   both products  webhooks            reads via the session token
```

`docs/ARCHITECTURE.md` has the file-by-file map, `docs/DATABASE.md` the schema
and the rules enforced in SQL, `docs/API_CONTRACT.md` the endpoints.

## Quick start

### 1. Create the database

Apply the migrations in `supabase/migrations/` to your own project — `supabase
link` then `supabase db push`; `supabase/README.md` has the details — and add
`agentops` under **Project Settings → API → Exposed schemas**. Then:

```bash
cp frontend/.env.example frontend/.env.local   # add your URL and publishable key
cp backend/.env.example backend/.env           # optional: only for /stream and webhooks
```

### 2. Run it

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and create an account. Signing up with a seeded
responder's address (for example `sam.lee@agentops.example`) adopts that
person's history.

The AI DevOps section needs its control plane:

```bash
cd aidevops
cp .env.example .env     # DATABASE_URL, SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY
uv sync
uv run uvicorn control_plane.api.app:app --port 8010
```

Without `DATABASE_URL` it still starts and every AI DevOps screen says exactly
that. `aidevops/README.md` covers tenant membership and the dev-only fallback.

The agent-facing API is optional:

```bash
cd backend
python -m venv .venv
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Or both at once:

```bash
docker compose up
```

### 3. Run the checks

```bash
cd backend
pytest
```

```bash
cd frontend
npm run build
```

```bash
cd aidevops
uv run ruff check .
uv run pytest
```

Backend and control plane tests run offline and assert how each service behaves
with no credentials, which is the state a fresh clone starts in.

### Run incident triage

```bash
python scripts/triage_pipeline.py INC-1042
```

The report is written under `artifacts/`.

## Status

Built and verified: incidents, alerts, on-call, status pages, post-incident,
insights, catalog, workflows, command palette, live updates, public status,
the marketing site, the agent API, migrations, CI.

Not built yet: onboarding, a settings area (custom fields, roles, API keys),
post-mortem documents, saved views, generated database types, multi-tenancy for
Restora itself. `docs/BUILDING_RESTORA.md` says why each is missing.

AI DevOps, built: contracts, policy engine, approval binding, tenant-scoped
store, the portal API and identity, the shell screens, the alert bridge,
migrations. Stubbed: model calls, the orchestrator, execution-plane identity,
the Azure DevOps and MCP bindings. `aidevops/README.md` keeps the exact list.

## Companion articles

- `docs/ARTICLE.md` — why: the agentic-engineering write-up this repository accompanies.
- `docs/BUILDING_RESTORA.md` — how: a walk through the codebase, the database rules, and the decisions.
- `docs/BUILD_WITH_CLAUDE_CODE.md` — step by step: the twelve stages, the prompts used, and what to check at each.
- `aidevops/docs/adr/` — the decisions behind the control plane, and ADR-0005 on merging the two products.

## Learning path

1. Ask an agent to explore the repository without modifying it.
2. Review `CLAUDE.md`, `docs/ARCHITECTURE.md` and `docs/DATABASE.md`.
3. Read the rules that live in SQL, then try to break one from the client.
4. Run the deterministic triage scripts.
5. Review the reusable skills in `skills/`.
6. Start the app and validate it against `evals/dashboard-eval.md`.
7. Split future work among backend, frontend, QA, and docs agents.

## Suggested first prompt

```text
Explore this repository without changing anything.

Explain the architecture, entry points, data flow, testing strategy,
and the five most important files to read first.

For every important claim, show the file that supports it.
```

## License

MIT
