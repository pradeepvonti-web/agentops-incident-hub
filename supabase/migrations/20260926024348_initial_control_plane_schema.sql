create type agent_type as enum ('data-engineering', 'data-quality', 'orchestrator');

create type environment as enum ('dev', 'test', 'prod');

create type run_status as enum (
  'queued', 'running', 'awaiting_approval',
  'succeeded', 'failed', 'rejected', 'cancelled', 'rolled_back'
);

create type step_kind as enum (
  'plan', 'tool', 'generate', 'validate', 'approve', 'deploy', 'monitor'
);

create type step_status as enum (
  'running', 'succeeded', 'failed', 'rejected', 'awaiting_approval', 'rolled_back'
);

create type tool_decision as enum (
  'allow', 'deny_not_allowlisted', 'deny_constraint',
  'deny_user_permission', 'deny_rate_limit', 'deny_approval_required'
);

create type entry_source as enum (
  'portal', 'databricks', 'vs-code', 'power-bi', 'teams', 'api-cli'
);

create table public.tenants (
  tenant_id      text primary key
                 check (tenant_id ~ '^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$'),
  display_name   text        not null,
  azure_tenant_id text,
  databricks_host text,
  payload_export_enabled boolean not null default false,
  created_at     timestamptz not null default now()
);

comment on column public.tenants.payload_export_enabled is
  'When true the tenant has explicitly consented to sending prompts, diffs and tool arguments to the control plane. Default false (ADR-0003).';

create table public.runs (
  run_id          text        primary key,
  tenant_id       text        not null references public.tenants(tenant_id) on delete cascade,
  agent           agent_type  not null,
  environment     environment not null,
  status          run_status  not null default 'queued',
  invoked_by      text        not null,
  agent_principal text        not null,
  entry_source    entry_source not null,
  requirement_digest text     not null,
  idempotency_key text,
  target_digest   text,
  title           text,
  execution_plane_version text,
  last_checkpoint_id text,
  created_at      timestamptz not null default now(),
  started_at      timestamptz,
  ended_at        timestamptz,
  unique nulls not distinct (tenant_id, idempotency_key)
);

create index runs_tenant_created on public.runs (tenant_id, created_at desc);
create index runs_tenant_status on public.runs (tenant_id, status) where status <> 'succeeded';
create index runs_tenant_source on public.runs (tenant_id, entry_source);

create table public.run_spans (
  span_id         text        primary key,
  parent_span_id  text,
  tenant_id       text        not null references public.tenants(tenant_id) on delete cascade,
  run_id          text        not null references public.runs(run_id) on delete cascade,
  name            text        not null,
  step            step_kind   not null,
  status          step_status not null,
  attempt         integer     not null default 1,
  checkpoint_id   text,
  agent           agent_type  not null,
  agent_principal text        not null,
  environment     environment not null,
  invoked_by      text        not null,
  started_at      timestamptz not null,
  ended_at        timestamptz,
  duration_ms     integer,
  error_class     text,
  tool_name       text,
  tool_decision   tool_decision,
  policy_reason   text,
  arguments_digest text,
  result_digest   text,
  model           text,
  tokens_in       integer,
  tokens_out      integer,
  cost_usd        numeric(10, 6),
  cache_hit       boolean
);

create index run_spans_run on public.run_spans (tenant_id, run_id, started_at);
create index run_spans_denials on public.run_spans (tenant_id, tool_decision)
  where tool_decision is not null and tool_decision <> 'allow';

create table public.run_outcomes (
  run_id            text        primary key references public.runs(run_id) on delete cascade,
  tenant_id         text        not null references public.tenants(tenant_id) on delete cascade,
  agent             agent_type  not null,
  environment       environment not null,
  accepted          boolean     not null,
  human_edit_lines  integer     not null default 0 check (human_edit_lines >= 0),
  generated_lines   integer     not null default 0 check (generated_lines >= 0),
  rejection_reason  text,
  time_to_decision_seconds integer,
  registry_assets_used text[]   not null default '{}',
  recorded_at       timestamptz not null default now()
);

create index run_outcomes_tenant on public.run_outcomes (tenant_id, recorded_at desc);

create table public.approvals (
  approval_id     bigserial   primary key,
  tenant_id       text        not null references public.tenants(tenant_id) on delete cascade,
  run_id          text        not null references public.runs(run_id) on delete cascade,
  approved        boolean     not null,
  artifact_digest text        not null,
  approved_by     text        not null,
  comment         text,
  decided_at      timestamptz not null default now()
);

create index approvals_run on public.approvals (tenant_id, run_id, decided_at desc);

create table public.registry_assets (
  asset_id      text        primary key,
  tenant_id     text        not null references public.tenants(tenant_id) on delete cascade,
  kind          text        not null
                check (kind in ('pipeline-template', 'dq-rule', 'transformation', 'prompt')),
  name          text        not null,
  description   text,
  owner_team    text,
  created_at    timestamptz not null default now(),
  unique (tenant_id, kind, name)
);

create table public.registry_asset_versions (
  asset_id      text        not null references public.registry_assets(asset_id) on delete cascade,
  version       integer     not null,
  tenant_id     text        not null references public.tenants(tenant_id) on delete cascade,
  body          text        not null,
  created_by    text        not null,
  created_at    timestamptz not null default now(),
  primary key (asset_id, version)
);

create table public.evaluation_scores (
  score_id      bigserial   primary key,
  tenant_id     text        not null references public.tenants(tenant_id) on delete cascade,
  run_id        text        references public.runs(run_id) on delete cascade,
  task_id       text,
  metric        text        not null,
  value         numeric     not null,
  recorded_at   timestamptz not null default now()
);

create index evaluation_scores_tenant on public.evaluation_scores (tenant_id, metric, recorded_at desc);

create or replace function public.set_current_tenant(p_tenant text)
returns void
language sql
security invoker
set search_path = ''
as $fn$
  select set_config('app.current_tenant', p_tenant, true);
$fn$;

comment on function public.set_current_tenant is
  'Call at the start of every transaction before any tenant-scoped query. The third argument (true) makes the setting transaction-local, so a pooled connection cannot carry one tenant context into the next request.';

do $mig$
declare
  t text;
begin
  foreach t in array array[
    'runs', 'run_spans', 'run_outcomes', 'approvals',
    'registry_assets', 'registry_asset_versions', 'evaluation_scores'
  ]
  loop
    execute format('alter table public.%I enable row level security', t);
    execute format('alter table public.%I force row level security', t);
    execute format($p$
      create policy tenant_isolation on public.%I
        using (tenant_id = current_setting('app.current_tenant', true))
        with check (tenant_id = current_setting('app.current_tenant', true))
    $p$, t);
  end loop;
end
$mig$;

alter table public.tenants enable row level security;
