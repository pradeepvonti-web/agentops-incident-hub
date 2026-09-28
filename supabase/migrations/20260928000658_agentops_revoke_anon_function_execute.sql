-- Security advisor 0028/0029: every SECURITY DEFINER function in agentops was
-- executable by anon and authenticated, because Postgres grants EXECUTE to
-- PUBLIC on new functions. RLS inside the functions limited the damage, but
-- an anonymous caller could still reach declare_incident() through
-- /rest/v1/rpc. Nothing anonymous needs any of these: the public status page
-- reads the status_feed view and nothing else.
--
-- The grant is now explicit per role. Signed-in responders keep the RPCs the
-- app calls and the helpers its views and policies use; trigger functions are
-- callable by nobody, since the trigger runs them as the table owner.

revoke execute on all functions in schema agentops from public, anon, authenticated;

-- The RPCs the app and the agent API call, for signed-in users and services.
grant execute on function
  agentops.declare_incident(text, agentops.severity, agentops.category, uuid, text, agentops.incident_status, timestamptz),
  agentops.post_update(uuid, text, agentops.incident_status, agentops.severity, integer),
  agentops.escalate_alert(uuid, agentops.severity, agentops.category),
  agentops.incident_report(uuid),
  agentops.on_call_now(uuid, timestamptz),
  agentops.bump_workflow_runs(uuid),
  agentops.current_user_id(),
  agentops.is_active(agentops.incident_status)
to authenticated, service_role;

-- Anything created later starts closed as well.
alter default privileges for role postgres in schema agentops
  revoke execute on functions from public;
