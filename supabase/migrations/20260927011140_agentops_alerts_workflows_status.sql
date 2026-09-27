create table agentops.alert_sources (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  name text not null,
  description text not null default '',
  connected boolean not null default true
);

create table agentops.alert_routes (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  source_id uuid references agentops.alert_sources (id) on delete cascade,
  condition text not null,
  escalation_path_id uuid references agentops.escalation_paths (id) on delete set null,
  priority agentops.alert_priority not null default 'Medium',
  active boolean not null default true
);

create sequence agentops.alert_reference_seq start 9100;

create table agentops.alerts (
  id uuid primary key default gen_random_uuid(),
  reference text not null unique
    default 'ALERT-' || nextval('agentops.alert_reference_seq')::text,
  title text not null,
  payload jsonb not null default '{}'::jsonb,
  source_id uuid references agentops.alert_sources (id) on delete set null,
  route_id uuid references agentops.alert_routes (id) on delete set null,
  priority agentops.alert_priority not null default 'Medium',
  status agentops.alert_status not null default 'Open',
  incident_id uuid references agentops.incidents (id) on delete set null,
  acknowledged_by uuid references agentops.users (id) on delete set null,
  acknowledged_at timestamptz,
  received_at timestamptz not null default now()
);

create index on agentops.alerts (status, received_at desc);

create table agentops.workflows (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  enabled boolean not null default true,
  trigger text not null,
  conditions text[] not null default '{}',
  steps text[] not null default '{}',
  runs_7d int not null default 0,
  created_at timestamptz not null default now()
);

create table agentops.workflow_runs (
  id uuid primary key default gen_random_uuid(),
  workflow_id uuid not null references agentops.workflows (id) on delete cascade,
  incident_id uuid references agentops.incidents (id) on delete set null,
  outcome text not null,
  ran_at timestamptz not null default now()
);

-- Single-row configuration for the public status page.
create table agentops.status_page (
  id boolean primary key default true check (id),
  name text not null,
  url text not null,
  overall text not null default 'All systems operational'
);

create table agentops.status_components (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  status agentops.component_status not null default 'Operational',
  uptime_90d numeric(5, 2) not null default 100.00,
  position int not null default 0
);

create table agentops.incident_components (
  incident_id uuid not null references agentops.incidents (id) on delete cascade,
  component_id uuid not null references agentops.status_components (id) on delete cascade,
  primary key (incident_id, component_id)
);

create table agentops.status_updates (
  id uuid primary key default gen_random_uuid(),
  incident_id uuid references agentops.incidents (id) on delete set null,
  status agentops.incident_status not null,
  message text not null,
  author_id uuid references agentops.users (id) on delete set null,
  published_at timestamptz not null default now()
);

create index on agentops.status_updates (published_at desc);
