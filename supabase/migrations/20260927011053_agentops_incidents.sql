-- References read INC-1050 onwards; the seeded eight take 1042-1049.
create sequence agentops.incident_reference_seq start 1050;

create table agentops.incidents (
  id uuid primary key default gen_random_uuid(),
  reference text not null unique
    default 'INC-' || nextval('agentops.incident_reference_seq')::text,
  title text not null,
  summary text not null default '',
  service_id uuid references agentops.services (id) on delete set null,
  severity agentops.severity not null,
  category agentops.category not null,
  status agentops.incident_status not null default 'Triage',
  lead_id uuid references agentops.users (id) on delete set null,
  reporter_id uuid references agentops.users (id) on delete set null,
  probable_cause text not null default '',
  suggested_next_action text not null default '',
  impact_started_at timestamptz,
  declared_at timestamptz not null default now(),
  identified_at timestamptz,
  fixed_at timestamptz,
  closed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index on agentops.incidents (status);
create index on agentops.incidents (severity);
create index on agentops.incidents (service_id);

create table agentops.incident_participants (
  incident_id uuid not null references agentops.incidents (id) on delete cascade,
  user_id uuid not null references agentops.users (id) on delete cascade,
  primary key (incident_id, user_id)
);

create table agentops.incident_relations (
  incident_id uuid not null references agentops.incidents (id) on delete cascade,
  related_id uuid not null references agentops.incidents (id) on delete cascade,
  primary key (incident_id, related_id),
  check (incident_id <> related_id)
);

create table agentops.incident_updates (
  id uuid primary key default gen_random_uuid(),
  incident_id uuid not null references agentops.incidents (id) on delete cascade,
  author_id uuid references agentops.users (id) on delete set null,
  status agentops.incident_status not null,
  severity agentops.severity not null,
  message text not null,
  next_update_in_minutes int,
  created_at timestamptz not null default now()
);

create index on agentops.incident_updates (incident_id, created_at desc);

create table agentops.incident_timeline (
  id uuid primary key default gen_random_uuid(),
  incident_id uuid not null references agentops.incidents (id) on delete cascade,
  kind agentops.timeline_kind not null,
  title text not null,
  detail text not null default '',
  author_id uuid references agentops.users (id) on delete set null,
  occurred_at timestamptz not null default now()
);

create index on agentops.incident_timeline (incident_id, occurred_at);

-- Raw evidence. The ERROR/CRITICAL rule is applied when a report is built.
create table agentops.incident_logs (
  id uuid primary key default gen_random_uuid(),
  incident_id uuid not null references agentops.incidents (id) on delete cascade,
  level agentops.severity not null,
  message text not null,
  occurred_at timestamptz not null
);

create index on agentops.incident_logs (incident_id, occurred_at);

create table agentops.actions (
  id uuid primary key default gen_random_uuid(),
  incident_id uuid not null references agentops.incidents (id) on delete cascade,
  description text not null,
  owner_id uuid references agentops.users (id) on delete set null,
  status agentops.task_status not null default 'Open',
  created_at timestamptz not null default now()
);

create table agentops.follow_ups (
  id uuid primary key default gen_random_uuid(),
  incident_id uuid not null references agentops.incidents (id) on delete cascade,
  title text not null,
  owner_id uuid references agentops.users (id) on delete set null,
  status agentops.task_status not null default 'Open',
  priority agentops.priority not null default 'Medium',
  due_on date,
  created_at timestamptz not null default now()
);

create table agentops.post_incident_tasks (
  id uuid primary key default gen_random_uuid(),
  incident_id uuid not null references agentops.incidents (id) on delete cascade,
  title text not null,
  status agentops.task_status not null default 'Open',
  owner_id uuid references agentops.users (id) on delete set null,
  due_on date,
  position int not null default 0
);

create index on agentops.post_incident_tasks (incident_id, position);
