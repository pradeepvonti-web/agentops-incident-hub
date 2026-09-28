-- ADR-0001 amendment: FORCE ROW LEVEL SECURITY is necessary but not sufficient.
--
-- A role with BYPASSRLS ignores FORCE entirely. In Supabase both `postgres` and
-- `service_role` carry BYPASSRLS, so a control plane connecting with either of
-- them has no tenant isolation at all -- while every policy looks correctly
-- configured in the catalog.
--
-- Fix: a dedicated role with no BYPASSRLS that the application drops into for the
-- duration of each transaction. NOLOGIN on purpose -- there is no new credential
-- to leak; the app keeps its existing connection and gives up privilege instead of
-- acquiring it.

create role adp_app nologin nosuperuser nobypassrls nocreatedb nocreaterole;

grant usage on schema public to adp_app;

grant select, insert, update, delete on
  public.runs, public.run_spans, public.run_outcomes, public.approvals,
  public.registry_assets, public.registry_asset_versions, public.evaluation_scores
to adp_app;

-- Read-only on the tenant registry: the app resolves a tenant, it does not
-- create one. Onboarding is an admin action.
grant select on public.tenants to adp_app;

grant usage, select on all sequences in schema public to adp_app;

grant adp_app to postgres;

-- One call that both drops privilege and sets the tenant. Deliberately not two
-- functions: it must be impossible to set a tenant context while still holding a
-- role that ignores it.
create or replace function public.begin_tenant_scope(p_tenant text)
returns void
language plpgsql
security invoker
as $fn$
begin
  if p_tenant is null or p_tenant = '' then
    raise exception 'begin_tenant_scope requires a tenant';
  end if;
  -- LOCAL: both revert at commit or rollback, so a pooled connection cannot carry
  -- one request's tenant or privilege into the next.
  set local role adp_app;
  perform set_config('app.current_tenant', p_tenant, true);
end
$fn$;

comment on function public.begin_tenant_scope is
  'Call at the start of every transaction that touches tenant data. Drops into the adp_app role (which has no BYPASSRLS) and sets the tenant for RLS. Both are transaction-local. Never connect the application as postgres or service_role without calling this.';
