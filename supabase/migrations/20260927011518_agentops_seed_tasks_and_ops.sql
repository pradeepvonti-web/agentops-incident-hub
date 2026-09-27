insert into agentops.incident_participants (incident_id, user_id)
select i.id, u.id
  from (values
    ('INC-1042', 'sam.lee@agentops.example'), ('INC-1042', 'alex.moreau@agentops.example'),
    ('INC-1042', 'priya.raman@agentops.example'),
    ('INC-1043', 'dana.okafor@agentops.example'), ('INC-1043', 'sam.lee@agentops.example'),
    ('INC-1044', 'priya.raman@agentops.example'), ('INC-1044', 'dana.okafor@agentops.example'),
    ('INC-1044', 'sam.lee@agentops.example'),
    ('INC-1045', 'sam.lee@agentops.example'), ('INC-1045', 'dana.okafor@agentops.example'),
    ('INC-1046', 'alex.moreau@agentops.example'), ('INC-1046', 'sam.lee@agentops.example'),
    ('INC-1047', 'dana.okafor@agentops.example'),
    ('INC-1048', 'dana.okafor@agentops.example'), ('INC-1048', 'priya.raman@agentops.example'),
    ('INC-1049', 'sam.lee@agentops.example')
  ) as v(reference, email)
  join agentops.incidents i on i.reference = v.reference
  join agentops.users u on u.email = v.email;

insert into agentops.incident_relations (incident_id, related_id)
select a.id, b.id
  from (values ('INC-1042', 'INC-1046'), ('INC-1046', 'INC-1042')) as v(a_ref, b_ref)
  join agentops.incidents a on a.reference = v.a_ref
  join agentops.incidents b on b.reference = v.b_ref;

insert into agentops.actions (incident_id, description, owner_id, status)
select i.id, v.description, u.id, v.status::agentops.task_status
  from (values
    ('INC-1042', 'Roll back payments 4.12.0', 'priya.raman@agentops.example', 'Open'),
    ('INC-1042', 'Drain and restart checkout pods in eu-west', 'sam.lee@agentops.example', 'Open'),
    ('INC-1042', 'Post customer-facing status update', 'alex.moreau@agentops.example', 'Done'),
    ('INC-1043', 'Keep the expansion flag off until load tested', 'dana.okafor@agentops.example', 'Open'),
    ('INC-1044', 'Promote replacement signing key', 'priya.raman@agentops.example', 'Done'),
    ('INC-1046', 'Open a ticket with the partner', 'alex.moreau@agentops.example', 'Open')
  ) as v(reference, description, email, status)
  join agentops.incidents i on i.reference = v.reference
  join agentops.users u on u.email = v.email;

insert into agentops.follow_ups (incident_id, title, owner_id, status, priority, due_on)
select i.id, v.title, u.id, v.status::agentops.task_status,
       v.priority::agentops.priority, v.due_on::date
  from (values
    ('INC-1042', 'Add connection-pool saturation alert to payments', 'priya.raman@agentops.example', 'Open', 'High', '2026-10-03'),
    ('INC-1043', 'Load test query expansion at 10x cardinality', 'dana.okafor@agentops.example', 'Open', 'Medium', '2026-10-10'),
    ('INC-1044', 'Alert on signing keys expiring within 7 days', 'priya.raman@agentops.example', 'Done', 'High', '2026-09-30'),
    ('INC-1044', 'Add rotation smoke test to the identity pipeline', 'sam.lee@agentops.example', 'Open', 'High', '2026-10-08'),
    ('INC-1045', 'Reconcile duplicate order rows for 26 Sep', 'dana.okafor@agentops.example', 'Open', 'Medium', '2026-10-01'),
    ('INC-1048', 'Reject zero cache TTL in config validation', 'dana.okafor@agentops.example', 'Open', 'High', '2026-10-05')
  ) as v(reference, title, email, status, priority, due_on)
  join agentops.incidents i on i.reference = v.reference
  join agentops.users u on u.email = v.email;

insert into agentops.post_incident_tasks (incident_id, title, status, owner_id, due_on, position)
select i.id, v.title, v.status::agentops.task_status, u.id, v.due_on::date, v.position
  from (values
    ('INC-1044', 'Review the incident timeline', 'Done', 'priya.raman@agentops.example', null, 1),
    ('INC-1044', 'Create the post-mortem', 'Done', 'priya.raman@agentops.example', null, 2),
    ('INC-1044', 'Schedule the debrief', 'Done', 'dana.okafor@agentops.example', null, 3),
    ('INC-1044', 'Share the post-mortem', 'Done', 'priya.raman@agentops.example', null, 4),
    ('INC-1045', 'Review the incident timeline', 'Done', 'sam.lee@agentops.example', null, 1),
    ('INC-1045', 'Create the post-mortem', 'Open', 'sam.lee@agentops.example', '2026-10-02', 2),
    ('INC-1045', 'Schedule the debrief', 'Open', 'dana.okafor@agentops.example', '2026-10-02', 3),
    ('INC-1048', 'Review the incident timeline', 'Done', 'dana.okafor@agentops.example', null, 1),
    ('INC-1048', 'Create the post-mortem', 'Open', 'dana.okafor@agentops.example', '2026-09-30', 2),
    ('INC-1048', 'Review follow-ups', 'Open', 'priya.raman@agentops.example', '2026-09-30', 3),
    ('INC-1049', 'Review the incident timeline', 'Done', 'sam.lee@agentops.example', null, 1),
    ('INC-1049', 'Create the post-mortem', 'Done', 'sam.lee@agentops.example', null, 2)
  ) as v(reference, title, status, email, due_on, position)
  join agentops.incidents i on i.reference = v.reference
  join agentops.users u on u.email = v.email;

insert into agentops.alert_sources (slug, name, description, connected) values
  ('http', 'HTTP alerts', 'Generic webhook source', true),
  ('metrics', 'Metrics alerts', 'Threshold alerts from the metrics pipeline', true),
  ('status-views', 'Status page views', 'Spikes in status page traffic', true),
  ('email', 'Email alerts', 'Parsed from the alerts mailbox', false);

insert into agentops.alert_routes (name, source_id, condition, escalation_path_id, priority, active)
select v.name, s.id, v.condition, p.id, v.priority::agentops.alert_priority, v.active
  from (values
    ('Checkout alert route', 'metrics', 'service is checkout-api', 'payments', 'Urgent', true),
    ('Search latency route', 'metrics', 'service is catalog-search and metric is p95_latency', 'discovery', 'High', true),
    ('Partner webhook route', 'http', 'service is partner-gateway', 'integrations', 'High', true),
    ('High status page views', 'status-views', 'views above 500 in 5 minutes', null, 'Low', false)
  ) as v(name, source_slug, condition, path_slug, priority, active)
  join agentops.alert_sources s on s.slug = v.source_slug
  left join agentops.escalation_paths p on p.slug = v.path_slug;

insert into agentops.alerts (reference, title, source_id, priority, status, received_at, incident_id)
select v.reference, v.title, s.id, v.priority::agentops.alert_priority,
       v.status::agentops.alert_status, v.received_at::timestamptz, i.id
  from (values
    ('ALERT-9001', 'checkout health check failing', 'metrics', 'Urgent', 'Escalated', '2026-09-26T18:02:00Z', 'INC-1042'),
    ('ALERT-9002', 'search p95 above 1200ms', 'metrics', 'High', 'Escalated', '2026-09-26T17:20:00Z', 'INC-1043'),
    ('ALERT-9003', 'webhook delivery failures', 'http', 'High', 'Escalated', '2026-09-26T16:05:00Z', 'INC-1046'),
    ('ALERT-9004', 'inventory queue depth above threshold', 'metrics', 'Medium', 'Escalated', '2026-09-26T19:02:00Z', 'INC-1047'),
    ('ALERT-9005', 'nightly export duration above budget', 'metrics', 'Low', 'Resolved', '2026-09-26T02:40:00Z', 'INC-1049'),
    ('ALERT-9006', 'profile cache hit rate dropped', 'metrics', 'Medium', 'Resolved', '2026-09-26T11:13:00Z', 'INC-1048'),
    ('ALERT-9007', 'payments p99 latency above 2s', 'metrics', 'High', 'Open', '2026-09-26T19:40:00Z', null),
    ('ALERT-9008', 'certificate expires in 6 days', 'http', 'Low', 'Open', '2026-09-26T20:05:00Z', null)
  ) as v(reference, title, source_slug, priority, status, received_at, incident_ref)
  join agentops.alert_sources s on s.slug = v.source_slug
  left join agentops.incidents i on i.reference = v.incident_ref;

insert into agentops.workflows (name, enabled, trigger, conditions, steps, runs_7d) values
  ('Announce critical incidents', true, 'Incident created or updated',
   array['Severity is one of CRITICAL', 'Status is not Closed'],
   array['Post a message to #incidents', 'Page the owning team''s escalation path'], 4),
  ('Publish a status page update', true, 'Incident status changed',
   array['Severity is one of CRITICAL, ERROR', 'Affected components is not empty'],
   array['Draft a customer update from the latest incident update', 'Await approval from the incident lead'], 6),
  ('Auto-declare on queue backlog', true, 'Alert received',
   array['Alert title contains queue depth', 'Priority is one of Medium, High, Urgent'],
   array['Declare an incident at WARNING', 'Assign the owning team from the catalog'], 1),
  ('Nudge overdue follow-ups', false, 'Scheduled, weekdays at 09:00',
   array['Follow-up status is Open', 'Due date is in the past'],
   array['Send a reminder to the follow-up owner'], 0);

insert into agentops.status_page (id, name, url, overall)
values (true, 'AgentOps Status', 'status.agentops.example', 'Degraded performance');

insert into agentops.status_components (name, status, uptime_90d, position) values
  ('Checkout', 'Partial outage', 99.82, 1),
  ('Search', 'Degraded performance', 99.94, 2),
  ('Identity', 'Operational', 99.99, 3),
  ('Orders', 'Operational', 99.97, 4),
  ('Partner Gateway', 'Degraded performance', 99.88, 5),
  ('Reporting', 'Operational', 99.95, 6);

insert into agentops.incident_components (incident_id, component_id)
select i.id, c.id
  from (values
    ('INC-1042', 'Checkout'), ('INC-1042', 'Orders'),
    ('INC-1043', 'Search'), ('INC-1046', 'Partner Gateway'),
    ('INC-1044', 'Identity'), ('INC-1049', 'Reporting')
  ) as v(reference, component)
  join agentops.incidents i on i.reference = v.reference
  join agentops.status_components c on c.name = v.component;

insert into agentops.status_updates (incident_id, status, message, author_id, published_at)
select i.id, v.status::agentops.incident_status, v.message, u.id, v.published_at::timestamptz
  from (values
    ('INC-1042', 'Investigating',
     'Customers may be unable to complete checkout. We have identified the cause and are rolling back a recent change.',
     'alex.moreau@agentops.example', '2026-09-26T18:20:00Z'),
    ('INC-1043', 'Monitoring',
     'Search results are returning normally. We are monitoring performance for the next 30 minutes.',
     'dana.okafor@agentops.example', '2026-09-26T18:10:00Z'),
    ('INC-1046', 'Investigating',
     'Some partner integrations are delayed while an upstream provider recovers.',
     'alex.moreau@agentops.example', '2026-09-26T16:25:00Z')
  ) as v(reference, status, message, email, published_at)
  join agentops.incidents i on i.reference = v.reference
  join agentops.users u on u.email = v.email;
