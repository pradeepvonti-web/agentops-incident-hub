-- Push changes to every open tab. Only the tables a responder watches while an
-- incident is running need to be in the publication.
alter publication supabase_realtime add table
  agentops.incidents,
  agentops.incident_updates,
  agentops.incident_timeline,
  agentops.actions,
  agentops.follow_ups,
  agentops.post_incident_tasks,
  agentops.alerts,
  agentops.status_updates,
  agentops.status_components,
  agentops.workflows;
