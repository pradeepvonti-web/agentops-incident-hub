insert into agentops.users (email, full_name, job_title) values
  ('sam.lee@agentops.example', 'Sam Lee', 'Staff Engineer'),
  ('priya.raman@agentops.example', 'Priya Raman', 'Platform Lead'),
  ('dana.okafor@agentops.example', 'Dana Okafor', 'Senior Engineer'),
  ('alex.moreau@agentops.example', 'Alex Moreau', 'Support Engineer');

insert into agentops.teams (slug, name, slack_channel) values
  ('payments', 'Payments', '#team-payments'),
  ('discovery', 'Discovery', '#team-discovery'),
  ('platform', 'Platform', '#team-platform'),
  ('orders', 'Orders', '#team-orders'),
  ('integrations', 'Integrations', '#team-integrations'),
  ('data', 'Data', '#team-data');

insert into agentops.team_members (team_id, user_id)
select t.id, u.id
  from (values
    ('payments', 'priya.raman@agentops.example'),
    ('payments', 'sam.lee@agentops.example'),
    ('discovery', 'dana.okafor@agentops.example'),
    ('platform', 'priya.raman@agentops.example'),
    ('platform', 'dana.okafor@agentops.example'),
    ('orders', 'sam.lee@agentops.example'),
    ('orders', 'dana.okafor@agentops.example'),
    ('integrations', 'alex.moreau@agentops.example'),
    ('data', 'sam.lee@agentops.example')
  ) as m(team_slug, email)
  join agentops.teams t on t.slug = m.team_slug
  join agentops.users u on u.email = m.email;

insert into agentops.escalation_paths (slug, name) values
  ('payments', 'Payments primary'),
  ('discovery', 'Discovery primary'),
  ('platform', 'Platform primary'),
  ('orders', 'Orders primary'),
  ('integrations', 'Integrations primary'),
  ('data', 'Data primary');

insert into agentops.escalation_levels (path_id, level, notify, after_minutes, method)
select p.id, l.level, l.notify, l.after_minutes, l.method
  from (values
    ('payments', 1, 'Payments primary schedule', 0, 'Push and SMS'),
    ('payments', 2, 'Priya Raman', 10, 'Phone call'),
    ('payments', 3, 'Engineering manager', 20, 'Phone call'),
    ('discovery', 1, 'Discovery primary schedule', 0, 'Push'),
    ('discovery', 2, 'Platform primary schedule', 15, 'Push and SMS'),
    ('platform', 1, 'Platform primary schedule', 0, 'Push and SMS'),
    ('platform', 2, 'Priya Raman', 10, 'Phone call'),
    ('orders', 1, 'Orders primary schedule', 0, 'Push'),
    ('orders', 2, 'Sam Lee', 15, 'SMS'),
    ('integrations', 1, 'Integrations primary schedule', 0, 'Push'),
    ('integrations', 2, 'Alex Moreau', 15, 'SMS'),
    ('data', 1, 'Data primary schedule', 0, 'Push')
  ) as l(path_slug, level, notify, after_minutes, method)
  join agentops.escalation_paths p on p.slug = l.path_slug;

insert into agentops.services (slug, name, team_id, tier, owner_id, escalation_path_id)
select s.slug, s.name, t.id, s.tier, u.id, p.id
  from (values
    ('checkout-api', 'Checkout API', 'payments', 'Tier 1', 'priya.raman@agentops.example', 'payments'),
    ('catalog-search', 'Catalog Search', 'discovery', 'Tier 1', 'dana.okafor@agentops.example', 'discovery'),
    ('identity', 'Identity', 'platform', 'Tier 1', 'priya.raman@agentops.example', 'platform'),
    ('order-ingestion', 'Order Ingestion', 'orders', 'Tier 2', 'sam.lee@agentops.example', 'orders'),
    ('partner-gateway', 'Partner Gateway', 'integrations', 'Tier 2', 'alex.moreau@agentops.example', 'integrations'),
    ('inventory-sync', 'Inventory Sync', 'orders', 'Tier 2', 'dana.okafor@agentops.example', 'orders'),
    ('profile', 'Profile', 'platform', 'Tier 2', 'dana.okafor@agentops.example', 'platform'),
    ('reporting', 'Reporting', 'data', 'Tier 3', 'sam.lee@agentops.example', 'data')
  ) as s(slug, name, team_slug, tier, owner_email, path_slug)
  join agentops.teams t on t.slug = s.team_slug
  join agentops.users u on u.email = s.owner_email
  join agentops.escalation_paths p on p.slug = s.path_slug;

insert into agentops.schedules (slug, name, timezone, rotation) values
  ('payments', 'Payments primary', 'Europe/London', 'Weekly handover, Thursday 09:00'),
  ('discovery', 'Discovery primary', 'Europe/Berlin', 'Daily handover, 18:00'),
  ('integrations', 'Integrations primary', 'America/New_York', 'Weekly handover, Monday 09:00');

insert into agentops.shifts (schedule_id, user_id, starts_at, ends_at)
select s.id, u.id, v.starts_at::timestamptz, v.ends_at::timestamptz
  from (values
    ('payments', 'priya.raman@agentops.example', '2026-09-26T08:00:00Z', '2026-09-26T20:00:00Z'),
    ('payments', 'sam.lee@agentops.example', '2026-09-26T20:00:00Z', '2026-09-27T08:00:00Z'),
    ('payments', 'priya.raman@agentops.example', '2026-09-27T08:00:00Z', '2026-09-27T20:00:00Z'),
    ('payments', 'sam.lee@agentops.example', '2026-09-27T20:00:00Z', '2026-09-28T08:00:00Z'),
    ('discovery', 'dana.okafor@agentops.example', '2026-09-26T06:00:00Z', '2026-09-26T18:00:00Z'),
    ('discovery', 'alex.moreau@agentops.example', '2026-09-26T18:00:00Z', '2026-09-27T06:00:00Z'),
    ('discovery', 'dana.okafor@agentops.example', '2026-09-27T06:00:00Z', '2026-09-27T18:00:00Z'),
    ('integrations', 'alex.moreau@agentops.example', '2026-09-26T13:00:00Z', '2026-09-27T13:00:00Z'),
    ('integrations', 'sam.lee@agentops.example', '2026-09-27T13:00:00Z', '2026-09-28T13:00:00Z')
  ) as v(schedule_slug, email, starts_at, ends_at)
  join agentops.schedules s on s.slug = v.schedule_slug
  join agentops.users u on u.email = v.email;
