-- One platform (ADR-0005): the AI DevOps screens live inside the Restora shell,
-- so the portal's identity is a Supabase Auth user, not an Entra token. This
-- table is the only bridge between that identity and a tenant.
--
-- The control plane reads it once per request, before any tenant scope exists,
-- because it is how the scope is chosen. That read is the single query in the
-- codebase allowed to run outside `begin_tenant_scope`, and it is confined to
-- `Database.resolve_membership` so it cannot spread.
--
-- A user belongs to exactly one tenant. Two would mean a request could name the
-- tenant it wants, which ADR-0001 forbids.

create table public.tenant_members (
  auth_user_id uuid        primary key,
  tenant_id    text        not null references public.tenants(tenant_id) on delete cascade,
  role         text        not null default 'member'
               check (role in ('member', 'approver', 'admin')),
  created_at   timestamptz not null default now()
);

comment on table public.tenant_members is
  'Maps a Supabase Auth user to the one tenant they may see. Read by the control plane before a tenant scope is opened; RLS enabled with no policy on purpose (deny-all to PostgREST). Membership is an admin action.';

comment on column public.tenant_members.role is
  'member: may view runs and submit them. approver: may also decide approvals. admin: reserved for onboarding. An agent principal is never a member (ADR-0002).';

-- Deny-all to every non-bypassing role, exactly like `tenants`.
alter table public.tenant_members enable row level security;

create index tenant_members_tenant on public.tenant_members (tenant_id);
