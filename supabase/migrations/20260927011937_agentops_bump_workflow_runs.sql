create function agentops.bump_workflow_runs(p_workflow uuid)
returns agentops.workflows
language sql
security definer
set search_path = ''
as $$
  update agentops.workflows
     set runs_7d = runs_7d + 1
   where id = p_workflow
  returning *;
$$;

grant execute on function agentops.bump_workflow_runs(uuid) to authenticated, service_role;
