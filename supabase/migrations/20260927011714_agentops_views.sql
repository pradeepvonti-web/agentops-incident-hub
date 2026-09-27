-- Denormalised incident row the UI lists and filters on.
create view agentops.incident_list
with (security_invoker = true)
as
select
  i.id,
  i.reference,
  i.title,
  i.summary,
  i.severity,
  i.category,
  i.status,
  agentops.is_active(i.status) as is_active,
  s.slug as service_slug,
  s.name as service_name,
  t.name as team_name,
  lead.full_name as lead_name,
  lead.id as lead_id,
  reporter.full_name as reporter_name,
  i.impact_started_at,
  i.declared_at,
  i.identified_at,
  i.fixed_at,
  i.closed_at,
  i.updated_at,
  extract(epoch from (i.declared_at - i.impact_started_at)) / 60 as minutes_to_declare,
  extract(epoch from (i.fixed_at - i.impact_started_at)) / 60 as minutes_to_fix,
  (select max(l.occurred_at) from agentops.incident_logs l where l.incident_id = i.id)
    as latest_occurrence,
  (select min(l.occurred_at) from agentops.incident_logs l where l.incident_id = i.id)
    as first_occurrence,
  (select count(*) from agentops.follow_ups f
    where f.incident_id = i.id and f.status = 'Open') as open_follow_ups,
  (select count(*) from agentops.post_incident_tasks p
    where p.incident_id = i.id and p.status = 'Open') as open_tasks
from agentops.incidents i
left join agentops.services s on s.id = i.service_id
left join agentops.teams t on t.id = s.team_id
left join agentops.users lead on lead.id = i.lead_id
left join agentops.users reporter on reporter.id = i.reporter_id;

-- Single-row headline metrics for the insights page.
create view agentops.insight_totals
with (security_invoker = true)
as
select
  count(*) as total_incidents,
  count(*) filter (where agentops.is_active(status)) as active_incidents,
  count(*) filter (where severity = 'CRITICAL' and agentops.is_active(status))
    as active_critical,
  round(avg(extract(epoch from (declared_at - impact_started_at)) / 60)::numeric, 1)
    as mean_minutes_to_declare,
  round(avg(extract(epoch from (fixed_at - impact_started_at)) / 60)::numeric, 1)
    as mean_minutes_to_fix,
  (select count(*) from agentops.follow_ups where status = 'Open') as open_follow_ups,
  (select count(*) from agentops.post_incident_tasks where status = 'Open') as open_tasks
from agentops.incidents;

grant select on agentops.incident_list, agentops.insight_totals
  to anon, authenticated, service_role;
