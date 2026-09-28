# Migrations live in `supabase/migrations/`

One database, one migration folder. The control plane's schema (`public.*`) and
Restora's (`agentops.*`) are applied together with `supabase db push` from the
repository root, in version order, and exported verbatim from
`supabase_migrations.schema_migrations` so the folder replays history rather
than approximating it.

| Version | Name | What it is |
|---|---|---|
| `20260926024348` | `initial_control_plane_schema` | Enums, tenants, runs, spans, outcomes, approvals, registry, evaluation; RLS forced on every tenant-scoped table |
| `20260926024518` | `add_non_bypassing_app_role` | `adp_app` and `begin_tenant_scope()` (ADR-0001 Amendment 1) |
| `20260926024620` | `harden_grants_and_search_path` | Revokes PostgREST access; fixes the function search path |
| `20260927234516` | `adp_tenant_members` | Supabase user to tenant mapping (ADR-0005) |
| `20260927234526` | `platform_bridge_run_failures_to_alerts` | A failed or rolled-back run raises a Restora alert |
| `20260927234546` | `adp_seed_run_spans` | Demo traces for the two seeded runs |

`tenant_context.TENANT_SCOPED_TABLES` must list every table that carries a
`tenant_id`; a new one goes in the same migration that creates it.
