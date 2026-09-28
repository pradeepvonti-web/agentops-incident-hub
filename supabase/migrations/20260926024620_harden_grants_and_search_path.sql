-- Close the three findings from the Supabase security advisor.

-- 1. Supabase grants SELECT on new public tables to `anon` and `authenticated`,
--    which exposes them through PostgREST and GraphQL to anyone holding the
--    publishable key. RLS still returns zero rows without a tenant context, so
--    this was not a data leak -- but the control plane talks to Postgres directly
--    and has no use for PostgREST, so the grant is pure attack surface.
revoke all on all tables in schema public from anon, authenticated;
revoke all on all sequences in schema public from anon, authenticated;
revoke all on all functions in schema public from anon, authenticated;

-- And for anything a later migration creates.
alter default privileges in schema public
  revoke all on tables from anon, authenticated;
alter default privileges in schema public
  revoke all on sequences from anon, authenticated;
alter default privileges in schema public
  revoke all on functions from anon, authenticated;

-- 2. A function without a fixed search_path can be hijacked by a caller who puts
--    a malicious schema earlier in their path. The body touches no tables, so
--    an empty path is safe.
create or replace function public.begin_tenant_scope(p_tenant text)
returns void
language plpgsql
security invoker
set search_path = ''
as $fn$
begin
  if p_tenant is null or p_tenant = '' then
    raise exception 'begin_tenant_scope requires a tenant';
  end if;
  set local role adp_app;
  perform set_config('app.current_tenant', p_tenant, true);
end
$fn$;

grant execute on function public.begin_tenant_scope(text) to adp_app;

-- 3. `tenants` has RLS on with no policy. That is deliberate: deny-all to every
--    role that does not bypass RLS. The app reads it only via its explicit
--    SELECT grant, and nothing writes it except admin onboarding.
comment on table public.tenants is
  'Tenant registry. RLS is enabled with no policy on purpose: deny-all. The '
  'advisor flags this as rls_enabled_no_policy; that is the intended state, not '
  'an oversight. Onboarding a tenant is an admin action, not an app action.';
