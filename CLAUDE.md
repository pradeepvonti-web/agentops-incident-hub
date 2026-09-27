# Restora — Project Context

## Architecture
- Database: Supabase Postgres, schema `agentops` (see `docs/DATABASE.md`)
- Auth: Supabase Auth; the responder profile is `agentops.users`
- Frontend: React + TypeScript + Vite, talking to Supabase directly
- Backend: FastAPI, the agent-facing API at `/api/v1` plus SSE and webhooks
- `sample-data/` is the offline fixture the API, scripts and tests use, and the
  source the seed migrations were generated from. Keep the two in step.

## Canonical incident categories
Use only:
- Availability
- Performance
- Security
- Data
- Integration

## Severity
Use only:
- INFO
- WARNING
- ERROR
- CRITICAL

Executive evidence includes only ERROR and CRITICAL events.

## Lifecycle statuses
Use only, in order:
Triage, Investigating, Fixing, Monitoring, Documenting, Reviewing, Closed.

Triage through Monitoring are "active". The definition lives in
`ACTIVE_STATUSES` in `backend/app/models.py`; do not re-derive it elsewhere.

## Conventions
- Business logic belongs in `backend/app/services`.
- API handlers stay thin.
- Frontend API access belongs in `frontend/src/lib/api.ts`.
- Reuse `SeverityBadge`; do not invent another severity representation.
- Prefer deterministic scripts for repeatable transformations.
- The executive summary renders `/incidents/{id}/report`; never re-filter severity in the UI.
- One page per route under `frontend/src/pages`; shared chrome lives in `frontend/src/app`.
- Shared presentational pieces belong in `frontend/src/components/ui.tsx`;
  forms and modals in `frontend/src/components/forms.tsx`.
- Every Supabase read and write goes through `frontend/src/lib/data.ts`. Pages do
  not import the supabase client.
- Load data with `useAsync`, and subscribe with `useLiveTable`/`useLiveTables`
  so a write in one tab refreshes the others.
- Wrap form submits in `useSubmit`; it owns pending and error state.
- A rule that must hold no matter who writes belongs in SQL: a trigger, a check,
  or a `security definer` function. Do not enforce it only in the client.
- Multi-step writes go in a Postgres function, not several round trips.
- New tables need RLS policies in the same migration that creates them.
- Reference data (catalog, alerts, on-call, workflows, status page) is served by
  `PlatformService`, not `IncidentService`.

## Validation
- Backend behavior changes require pytest coverage.
- Tests run as `cd backend && pytest`; `backend/pytest.ini` puts `backend/` on the path.
- The frontend must pass `npm run build` (`tsc -b` included) before a change is done.
- Run the Supabase security advisor after DDL and resolve anything it flags, or
  write down why the finding is intended.
- User-facing behavior should be checked against `evals/dashboard-eval.md`.

## Context discipline
When a durable new rule is discovered:
1. verify it,
2. write it into the appropriate `docs/` file,
3. update implementation/tests,
4. update reusable skills when applicable.
