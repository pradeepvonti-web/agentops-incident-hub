-- One platform (ADR-0005): a failed or rolled-back agent run is an operational
-- event, and Restora is where operational events are handled. This trigger
-- raises a Restora alert from the row change itself, so it holds no matter which
-- writer moved the run -- the control plane, the runtime, or a hotfix in SQL.
-- No client has to remember to do it (CLAUDE.md: rules that must hold for every
-- writer live in the database).
--
-- Only metadata crosses: run id, tenant, agent, environment, entry source and the
-- run's title. Nothing from the payload tier exists on `runs` to leak (ADR-0003).

insert into agentops.alert_sources (slug, name, description, connected)
select 'ai-devops',
       'AI DevOps control plane',
       'Agent runs that failed or were rolled back',
       true
where not exists (select 1 from agentops.alert_sources where slug = 'ai-devops');

create or replace function public.raise_alert_for_failed_run()
returns trigger
language plpgsql
security definer
set search_path = ''
as $fn$
declare
  v_source uuid;
begin
  if new.status not in ('failed', 'rolled_back') then
    return new;
  end if;
  if tg_op = 'UPDATE' and old.status = new.status then
    return new;
  end if;

  select id into v_source from agentops.alert_sources where slug = 'ai-devops';

  insert into agentops.alerts (title, payload, source_id, priority)
  values (
    format('Agent run %s: %s', replace(new.status::text, '_', ' '),
           coalesce(new.title, new.run_id)),
    jsonb_build_object(
      'run_id', new.run_id,
      'tenant_id', new.tenant_id,
      'agent', new.agent,
      'environment', new.environment,
      'entry_source', new.entry_source,
      'status', new.status,
      'invoked_by', new.invoked_by
    ),
    v_source,
    case when new.environment = 'prod'
         then 'Urgent'::agentops.alert_priority
         else 'High'::agentops.alert_priority end
  );
  return new;
end
$fn$;

comment on function public.raise_alert_for_failed_run is
  'Trigger: a run entering failed or rolled_back raises an agentops alert from the ai-devops source. Definer, because the writer holds the adp_app role and has no grant on agentops.';

revoke all on function public.raise_alert_for_failed_run() from public, anon, authenticated;

create trigger runs_raise_alert_on_failure
  after insert or update of status on public.runs
  for each row execute function public.raise_alert_for_failed_run();
