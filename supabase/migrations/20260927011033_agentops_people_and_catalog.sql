-- People. Seeded responders have no auth_id; a real signup gets linked by email.
create table agentops.users (
  id uuid primary key default gen_random_uuid(),
  auth_id uuid unique references auth.users (id) on delete set null,
  email text not null unique,
  full_name text not null,
  job_title text,
  created_at timestamptz not null default now()
);

create table agentops.teams (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  name text not null,
  slack_channel text
);

create table agentops.team_members (
  team_id uuid not null references agentops.teams (id) on delete cascade,
  user_id uuid not null references agentops.users (id) on delete cascade,
  primary key (team_id, user_id)
);

create table agentops.escalation_paths (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  name text not null
);

create table agentops.escalation_levels (
  id uuid primary key default gen_random_uuid(),
  path_id uuid not null references agentops.escalation_paths (id) on delete cascade,
  level int not null,
  notify text not null,
  after_minutes int not null default 0,
  method text not null,
  unique (path_id, level)
);

create table agentops.services (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  name text not null,
  team_id uuid references agentops.teams (id) on delete set null,
  tier text not null default 'Tier 2',
  owner_id uuid references agentops.users (id) on delete set null,
  escalation_path_id uuid references agentops.escalation_paths (id) on delete set null
);

create table agentops.schedules (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  name text not null,
  timezone text not null default 'UTC',
  rotation text
);

create table agentops.shifts (
  id uuid primary key default gen_random_uuid(),
  schedule_id uuid not null references agentops.schedules (id) on delete cascade,
  user_id uuid not null references agentops.users (id) on delete cascade,
  starts_at timestamptz not null,
  ends_at timestamptz not null,
  is_override boolean not null default false,
  check (ends_at > starts_at)
);

create index on agentops.shifts (schedule_id, starts_at);
create index on agentops.services (team_id);
