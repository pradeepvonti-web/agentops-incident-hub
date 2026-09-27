# Database

The database is Supabase Postgres. Everything this product owns lives in the
`agentops` schema, so it can share a project with unrelated work without
colliding with it.

## Getting connected

1. In the Supabase dashboard: **Project Settings → API → Exposed schemas**, add
   `agentops`. PostgREST serves only `public` and `graphql_public` by default,
   and the app cannot read anything until this is set.
2. Copy `frontend/.env.example` to `frontend/.env.local` and fill in the project
   URL and publishable key.
3. Copy `backend/.env.example` to `backend/.env` if you want the agent-facing
   API, the SSE stream or the alert webhook.

## Shape

| Area | Tables |
|------|--------|
| People | `users`, `teams`, `team_members` |
| Catalog | `services`, `escalation_paths`, `escalation_levels` |
| On-call | `schedules`, `shifts` |
| Incidents | `incidents`, `incident_participants`, `incident_relations`, `incident_updates`, `incident_timeline`, `incident_logs` |
| Work | `actions`, `follow_ups`, `post_incident_tasks` |
| Alerts | `alert_sources`, `alert_routes`, `alerts` |
| Automation | `workflows`, `workflow_runs` |
| Status page | `status_page`, `status_components`, `incident_components`, `status_updates` |

Views:

- `incident_list` — the denormalised row every list and board renders
- `insight_totals` — headline metrics
- `status_feed` — the curated public projection of published status updates

`incident_list` and `insight_totals` are `security_invoker`, so RLS applies to
the caller rather than the view owner.

`status_feed` deliberately is not. An anonymous reader has no grant on
`incidents` or `users`, so a joined query would fail for them; the view runs as
its owner and exposes only the status, message, timestamp, incident reference
and author name of updates that were already published to customers. Adding a
column to it is a decision about what the public can see.

## Rules that live in the database

These are enforced in SQL so that no client can skip them.

- **`incident_report(incident uuid)`** builds the executive summary and filters
  evidence to ERROR and CRITICAL. This is the only place that rule exists.
- **`log_incident_change()`** is an `after update` trigger on `incidents`. Any
  status or severity change writes its own timeline entry, whether the change
  came from the UI, the API, or psql.
- **`handle_new_auth_user()`** links a new Supabase Auth user to a seeded
  responder by email, or creates a profile if the address is new.
- **`is_active(status)`** defines which statuses count as active. `ACTIVE_STATUSES`
  in the Python models and `ACTIVE_STATUSES` in the TypeScript types both mirror
  it; the database is the source of truth.

## Functions clients call

| Function | Used for |
|----------|----------|
| `declare_incident(...)` | Incident, participant and opening timeline entry in one transaction |
| `post_update(...)` | An update that can also move status, and backfills `identified_at` / `fixed_at` / `closed_at` |
| `escalate_alert(...)` | Turns an alert into an incident and links the two |
| `on_call_now(schedule)` | Who is on call, with overrides winning |
| `bump_workflow_runs(workflow)` | Run counter |

## Row level security

Every table has RLS on.

- **Signed-in responders** can read the whole workspace and write everything an
  incident response touches. This is a single-team product; adding tenancy would
  be the first change for a real deployment, and it would touch every policy.
- **Anonymous readers** can select from `status_page`, `status_components` and
  `status_updates`, and nothing else. That is what makes `/status` work without
  an account.
- **`users`** rows can only be updated by the person they belong to.
- Incidents are never deleted, only closed. There is no delete policy on them.

Supabase's linter reports the `agentops` tables as visible to signed-in users.
That is the intended design, not an oversight: a responder can read the
workspace. The public-facing exposure is deliberately limited to the three
status-page tables.

## Realtime

`incidents`, `incident_updates`, `incident_timeline`, `actions`, `follow_ups`,
`post_incident_tasks`, `alerts`, `status_updates`, `status_components` and
`workflows` are in the `supabase_realtime` publication. The browser subscribes
through `useLiveTable`; the FastAPI `/api/v1/stream` endpoint polls the same data
for consumers that want server-sent events instead.

## Migrations

Applied in order:

```text
agentops_schema_and_enums          types, is_active()
agentops_people_and_catalog        users, teams, services, schedules, shifts
agentops_incidents                 incidents and everything hanging off one
agentops_alerts_workflows_status   alerts, workflows, status page
agentops_functions_and_triggers    report, audit trigger, auth linking
agentops_rpcs                      declare_incident, post_update, escalate_alert
agentops_rls                       policies and grants
agentops_seed_people_and_catalog   seed
agentops_seed_incidents            seed
agentops_seed_tasks_and_ops        seed
agentops_views                     incident_list, insight_totals
agentops_bump_workflow_runs        workflow counter
agentops_realtime_publication      realtime
agentops_tighten_anon_grants       anon reads only the status page
```
