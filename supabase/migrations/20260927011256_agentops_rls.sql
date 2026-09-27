do $$
declare
  t text;
begin
  foreach t in array array[
    'users', 'teams', 'team_members', 'escalation_paths', 'escalation_levels',
    'services', 'schedules', 'shifts', 'incidents', 'incident_participants',
    'incident_relations', 'incident_updates', 'incident_timeline', 'incident_logs',
    'actions', 'follow_ups', 'post_incident_tasks', 'alert_sources', 'alert_routes',
    'alerts', 'workflows', 'workflow_runs', 'status_page', 'status_components',
    'incident_components', 'status_updates'
  ]
  loop
    execute format('alter table agentops.%I enable row level security', t);
  end loop;
end;
$$;

-- Signed-in responders can read the whole workspace. This is a single-team
-- product; tenancy would be the first thing to add for a real deployment.
do $$
declare
  t text;
begin
  foreach t in array array[
    'users', 'teams', 'team_members', 'escalation_paths', 'escalation_levels',
    'services', 'schedules', 'shifts', 'incidents', 'incident_participants',
    'incident_relations', 'incident_updates', 'incident_timeline', 'incident_logs',
    'actions', 'follow_ups', 'post_incident_tasks', 'alert_sources', 'alert_routes',
    'alerts', 'workflows', 'workflow_runs', 'status_page', 'status_components',
    'incident_components', 'status_updates'
  ]
  loop
    execute format(
      'create policy %I on agentops.%I for select to authenticated using (true)',
      t || '_read', t
    );
  end loop;
end;
$$;

-- Everything a responder does during an incident is a write they are allowed
-- to make. Incidents themselves are never deleted, only closed.
do $$
declare
  t text;
begin
  foreach t in array array[
    'incidents', 'incident_participants', 'incident_relations', 'incident_updates',
    'incident_timeline', 'incident_logs', 'actions', 'follow_ups',
    'post_incident_tasks', 'alerts', 'alert_routes', 'alert_sources', 'workflows',
    'workflow_runs', 'services', 'teams', 'team_members', 'schedules', 'shifts',
    'escalation_paths', 'escalation_levels', 'status_page', 'status_components',
    'incident_components', 'status_updates'
  ]
  loop
    execute format(
      'create policy %I on agentops.%I for insert to authenticated with check (true)',
      t || '_insert', t
    );
    execute format(
      'create policy %I on agentops.%I for update to authenticated using (true) with check (true)',
      t || '_update', t
    );
  end loop;

  foreach t in array array[
    'incident_participants', 'incident_relations', 'actions', 'follow_ups',
    'post_incident_tasks', 'shifts', 'alert_routes', 'workflows',
    'incident_components', 'team_members', 'status_updates'
  ]
  loop
    execute format(
      'create policy %I on agentops.%I for delete to authenticated using (true)',
      t || '_delete', t
    );
  end loop;
end;
$$;

-- A profile row can only be edited by the person it belongs to.
create policy users_update_self on agentops.users
  for update to authenticated
  using (auth_id = auth.uid())
  with check (auth_id = auth.uid());

-- The status page is public, which is the entire point of a status page.
create policy status_page_public_read on agentops.status_page
  for select to anon using (true);

create policy status_components_public_read on agentops.status_components
  for select to anon using (true);

create policy status_updates_public_read on agentops.status_updates
  for select to anon using (true);

grant usage on schema agentops to anon, authenticated, service_role;
grant select on all tables in schema agentops to anon;
grant all on all tables in schema agentops to authenticated, service_role;
grant usage, select on all sequences in schema agentops to authenticated, service_role;
grant execute on all functions in schema agentops to authenticated, service_role;
