-- The signed-in person's profile row, or null for anonymous readers.
create function agentops.current_user_id()
returns uuid
language sql
stable
security definer
set search_path = ''
as $$
  select id from agentops.users where auth_id = auth.uid()
$$;

create function agentops.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

create trigger incidents_set_updated_at
  before update on agentops.incidents
  for each row execute function agentops.set_updated_at();

-- Every status or severity change writes its own timeline entry, so the audit
-- trail cannot be skipped by a client that forgets to add one.
create function agentops.log_incident_change()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if new.status is distinct from old.status then
    insert into agentops.incident_timeline (incident_id, kind, title, detail, author_id)
    values (
      new.id,
      case when new.status = 'Closed' then 'closed'::agentops.timeline_kind
           else 'status'::agentops.timeline_kind end,
      format('Status changed from %s to %s', old.status, new.status),
      '',
      agentops.current_user_id()
    );
  end if;

  if new.severity is distinct from old.severity then
    insert into agentops.incident_timeline (incident_id, kind, title, detail, author_id)
    values (
      new.id,
      'severity',
      format('Severity changed from %s to %s', old.severity, new.severity),
      '',
      agentops.current_user_id()
    );
  end if;

  return new;
end;
$$;

create trigger incidents_log_change
  after update on agentops.incidents
  for each row execute function agentops.log_incident_change();

-- A new Supabase Auth user is matched to a seeded responder by email when one
-- exists, so signing in as sam.lee@agentops.example adopts Sam's history.
create function agentops.handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  update agentops.users
     set auth_id = new.id
   where lower(email) = lower(new.email)
     and auth_id is null;

  if not found then
    insert into agentops.users (auth_id, email, full_name)
    values (
      new.id,
      new.email,
      coalesce(nullif(new.raw_user_meta_data ->> 'full_name', ''), split_part(new.email, '@', 1))
    )
    on conflict (email) do update set auth_id = excluded.auth_id;
  end if;

  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function agentops.handle_new_auth_user();

-- The executive-evidence rule lives here, once: ERROR and CRITICAL only.
create function agentops.incident_report(p_incident uuid)
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  select jsonb_build_object(
    'incident_id', i.reference,
    'title', i.title,
    'service', coalesce(s.slug, ''),
    'severity', i.severity,
    'category', i.category,
    'status', i.status,
    'probable_cause', i.probable_cause,
    'suggested_next_action', i.suggested_next_action,
    'first_occurrence', (
      select min(occurred_at) from agentops.incident_logs where incident_id = i.id
    ),
    'latest_occurrence', (
      select max(occurred_at) from agentops.incident_logs where incident_id = i.id
    ),
    'evidence', coalesce((
      select jsonb_agg(
               to_char(l.occurred_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
               || ' [' || l.level || '] ' || l.message
               order by l.occurred_at
             )
        from agentops.incident_logs l
       where l.incident_id = i.id
         and l.level in ('ERROR', 'CRITICAL')
    ), '[]'::jsonb)
  )
  from agentops.incidents i
  left join agentops.services s on s.id = i.service_id
  where i.id = p_incident;
$$;
