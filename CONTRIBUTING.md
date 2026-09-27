# Contributing

The repository is built to be worked on by people and by agents, so the rules
are written down rather than assumed. Read `CLAUDE.md` first; it is short.

## Before you change anything

- Run the checks so you know the baseline is green:
  `cd backend && pytest` and `cd frontend && npm run build`.
- If the change touches user-facing behaviour, open `evals/dashboard-eval.md`
  and note which checks it affects.

## Where things go

| Change | Where |
|--------|-------|
| A business rule | `docs/INCIDENT_RULES.md`, then the place that enforces it |
| A rule that must hold for every writer | A trigger, check or function in a new file under `supabase/migrations/` |
| Backend logic | `backend/app/services/`, with a test in `backend/tests/` |
| A frontend read or write | `frontend/src/lib/data.ts` |
| A new screen | One file in `frontend/src/pages/`, one route in `App.tsx` |
| A repeatable transformation | A script in `scripts/` |
| A repeated workflow | A `SKILL.md` under `skills/` |
| Marketing copy or motion | `frontend/src/pages/Landing.tsx`, `frontend/src/marketing/` |

## Database changes

Write a migration, apply it with `supabase db push` (or through the Supabase
MCP server), run the security advisor, and re-export the folder with the query
in `supabase/README.md`. New tables get their RLS policies in the same
migration. Keep `sample-data/` in step with the seed migrations; the offline
tests read it.

## Finishing a change

1. Tests pass with no Supabase credentials configured.
2. `npm run build` passes.
3. The relevant eval checks were walked, in a browser, and anything that could
   not be verified is stated.
4. Any durable rule you discovered is written into `docs/` and, if it belongs
   in the database, into a migration.
5. Small pull requests, with the evidence in the description.
