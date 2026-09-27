-- Declaring an incident is one transaction: the incident, its reporter as a
-- participant, and the opening timeline entry.
create function agentops.declare_incident(
  p_title text,
  p_severity agentops.severity,
  p_category agentops.category,
  p_service_id uuid default null,
  p_summary text default '',
  p_status agentops.incident_status default 'Triage',
  p_impact_started_at timestamptz default null
)
returns agentops.incidents
language plpgsql
security definer
set search_path = ''
as $$
declare
  actor uuid := agentops.current_user_id();
  row agentops.incidents;
begin
  if actor is null then
    raise exception 'A signed-in user is required to declare an incident';
  end if;

  insert into agentops.incidents (
    title, summary, service_id, severity, category, status,
    reporter_id, lead_id, impact_started_at, declared_at
  )
  values (
    p_title, p_summary, p_service_id, p_severity, p_category, p_status,
    actor, actor, coalesce(p_impact_started_at, now()), now()
  )
  returning * into row;

  insert into agentops.incident_participants (incident_id, user_id)
  values (row.id, actor);

  insert into agentops.incident_timeline (incident_id, kind, title, detail, author_id)
  values (
    row.id,
    'declared',
    'Incident declared',
    format('Declared at %s by %s', row.severity,
           (select full_name from agentops.users where id = actor)),
    actor
  );

  return row;
end;
$$;

-- Posting an update is the one action that can also move the incident forward.
create function agentops.post_update(
  p_incident uuid,
  p_message text,
  p_status agentops.incident_status default null,
  p_severity agentops.severity default null,
  p_next_update_in_minutes int default null
)
returns agentops.incident_updates
language plpgsql
security definer
set search_path = ''
as $$
declare
  actor uuid := agentops.current_user_id();
  target agentops.incidents;
  row agentops.incident_updates;
begin
  if actor is null then
    raise exception 'A signed-in user is required to post an update';
  end if;

  select * into target from agentops.incidents where id = p_incident;
  if not found then
    raise exception 'Unknown incident %', p_incident;
  end if;

  update agentops.incidents
     set status = coalesce(p_status, status),
         severity = coalesce(p_severity, severity),
         identified_at = case
           when identified_at is null and coalesce(p_status, status) = 'Fixing'
           then now() else identified_at end,
         fixed_at = case
           when fixed_at is null and coalesce(p_status, status) in ('Monitoring', 'Documenting')
           then now() else fixed_at end,
         closed_at = case
           when coalesce(p_status, status) = 'Closed' then now() else closed_at end
   where id = p_incident
  returning * into target;

  insert into agentops.incident_updates (
    incident_id, author_id, status, severity, message, next_update_in_minutes
  )
  values (
    p_incident, actor, target.status, target.severity, p_message, p_next_update_in_minutes
  )
  returning * into row;

  insert into agentops.incident_timeline (incident_id, kind, title, detail, author_id)
  values (p_incident, 'update', 'Update shared', p_message, actor);

  insert into agentops.incident_participants (incident_id, user_id)
  values (p_incident, actor)
  on conflict do nothing;

  return row;
end;
$$;

-- Turning an alert into an incident, the way an on-call responder would.
create function agentops.escalate_alert(
  p_alert uuid,
  p_severity agentops.severity default 'ERROR',
  p_category agentops.category default 'Availability'
)
returns agentops.incidents
language plpgsql
security definer
set search_path = ''
as $$
declare
  actor uuid := agentops.current_user_id();
  alert agentops.alerts;
  row agentops.incidents;
begin
  select * into alert from agentops.alerts where id = p_alert;
  if not found then
    raise exception 'Unknown alert %', p_alert;
  end if;

  if alert.incident_id is not null then
    select * into row from agentops.incidents where id = alert.incident_id;
    return row;
  end if;

  row := agentops.declare_incident(
    alert.title, p_severity, p_category, null,
    format('Escalated from alert %s.', alert.reference), 'Triage', alert.received_at
  );

  update agentops.alerts
     set incident_id = row.id,
         status = 'Escalated',
         acknowledged_by = coalesce(acknowledged_by, actor),
         acknowledged_at = coalesce(acknowledged_at, now())
   where id = p_alert;

  insert into agentops.incident_timeline (incident_id, kind, title, detail, author_id)
  values (
    row.id, 'alert', format('Alert %s escalated', alert.reference), alert.title, actor
  );

  return row;
end;
$$;

-- Who is on call for a schedule at a given moment.
create function agentops.on_call_now(p_schedule uuid, p_at timestamptz default now())
returns agentops.users
language sql
stable
security definer
set search_path = ''
as $$
  select u.*
    from agentops.shifts s
    join agentops.users u on u.id = s.user_id
   where s.schedule_id = p_schedule
     and p_at >= s.starts_at
     and p_at < s.ends_at
   order by s.is_override desc, s.starts_at desc
   limit 1
$$;
