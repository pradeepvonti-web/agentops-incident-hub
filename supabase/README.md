# Reproducing the database

One database, two schemas: Restora in `agentops`, the AI DevOps control plane in
`public` (`aidevops/`). These migrations create both from nothing: types, tables, functions, triggers, row-level security,
seed data, views, the realtime publication. They are the exact statements that
were applied to the reference project, exported from
`supabase_migrations.schema_migrations`, so `supabase db push` replays history
rather than approximating it.

## Apply them to your own project

```bash
supabase login
supabase link --project-ref <your-project-ref>
supabase db push
```

Then two settings the CLI cannot change:

1. **Project Settings → API → Exposed schemas** — add `agentops`. PostgREST
   serves only `public` by default and the app cannot read anything until this
   is set.
2. **Authentication → Sign In / Providers → Email → Confirm email** — turn it
   off for a demo workspace. The seeded responders use `@agentops.example`
   addresses that cannot receive mail, and the shared SMTP sender is
   rate-limited.

Finally, copy `frontend/.env.example` to `frontend/.env.local` with your
project URL and publishable key.

## What each migration does

| File | Purpose |
|------|---------|
| `…_schema_and_enums` | The schema, the enum types, `is_active()` |
| `…_people_and_catalog` | users, teams, services, escalation paths, schedules, shifts |
| `…_incidents` | incidents and everything hanging off one |
| `…_alerts_workflows_status` | alerts, workflows, status page |
| `…_functions_and_triggers` | `incident_report()`, the audit trigger, auth linking |
| `…_rpcs` | `declare_incident`, `post_update`, `escalate_alert`, `on_call_now` |
| `…_rls` | policies and grants for every table |
| `…_seed_*` (three) | eight incidents, the catalog, alerts, on-call, workflows, status page |
| `…_views` | `incident_list`, `insight_totals` |
| `…_bump_workflow_runs` | the run counter |
| `…_realtime_publication` | ten tables into `supabase_realtime` |
| `…_tighten_anon_grants` | anonymous readers see only the status page |
| `…_status_feed` | the public status projection (deliberately not `security_invoker`) |
| `…_revoke_anon_function_execute` | RPCs are executable by `authenticated` and `service_role` only, never `anon` |

And the control plane's (`aidevops/`), which sort first by version:

| File | Purpose |
|------|---------|
| `…_initial_control_plane_schema` | tenants, runs, spans, outcomes, approvals, registry, evaluation; RLS forced |
| `…_add_non_bypassing_app_role` | `adp_app` and `begin_tenant_scope()` (ADR-0001 Amendment 1) |
| `…_harden_grants_and_search_path` | no PostgREST access to `public`; fixed search path |
| `…_adp_tenant_members` | Supabase user to tenant mapping (ADR-0005) |
| `…_platform_bridge_run_failures_to_alerts` | a failed or rolled-back run raises an `agentops` alert |
| `…_adp_seed_run_spans` | demo traces for the two seeded runs |

The reasoning behind the RLS design and the definer view is in
`docs/DATABASE.md`.

## Regenerating this folder

If you change the schema through the Supabase MCP server or the dashboard,
re-export so the folder stays the source of truth:

```sql
select version, name, array_to_string(statements, E'\n\n') as sql
from supabase_migrations.schema_migrations
order by version;
```

One file per row, named `<version>_<name>.sql`.
