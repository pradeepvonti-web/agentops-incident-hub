create schema if not exists agentops;

comment on schema agentops is
  'AgentOps Incident Hub. Isolated from this project''s public schema.';

create type agentops.severity as enum ('INFO', 'WARNING', 'ERROR', 'CRITICAL');

create type agentops.category as enum (
  'Availability', 'Performance', 'Security', 'Data', 'Integration'
);

-- Lifecycle order matters: an incident moves forward through these.
create type agentops.incident_status as enum (
  'Triage', 'Investigating', 'Fixing', 'Monitoring', 'Documenting', 'Reviewing', 'Closed'
);

create type agentops.task_status as enum ('Open', 'Done');

create type agentops.priority as enum ('Low', 'Medium', 'High');

create type agentops.alert_priority as enum ('Low', 'Medium', 'High', 'Urgent');

create type agentops.alert_status as enum ('Open', 'Escalated', 'Resolved');

create type agentops.component_status as enum (
  'Operational', 'Degraded performance', 'Partial outage', 'Major outage'
);

create type agentops.timeline_kind as enum (
  'alert', 'declared', 'update', 'status', 'severity', 'action', 'note', 'closed'
);

-- Triage through Monitoring count as active everywhere in the product.
create function agentops.is_active(s agentops.incident_status)
returns boolean
language sql
immutable
set search_path = ''
as $$
  select s = any (array[
    'Triage', 'Investigating', 'Fixing', 'Monitoring'
  ]::agentops.incident_status[])
$$;
