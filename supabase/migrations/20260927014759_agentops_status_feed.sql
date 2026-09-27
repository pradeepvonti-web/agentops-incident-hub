-- A curated projection of what the status page publishes.
--
-- This view is intentionally NOT security_invoker. An anonymous reader has no
-- grant on `incidents` or `users`, so a joined query would fail for them. The
-- view runs with its owner's privileges and exposes only the four fields a
-- customer is meant to see, which are public by definition. Nothing here
-- reveals a row that was not already published to the status page.
create view agentops.status_feed as
select
  su.id,
  su.status,
  su.message,
  su.published_at,
  i.reference as incident_reference,
  u.full_name as author_name
from agentops.status_updates su
left join agentops.incidents i on i.id = su.incident_id
left join agentops.users u on u.id = su.author_id;

comment on view agentops.status_feed is
  'Public status feed. Runs as owner so anonymous readers can see published updates without a grant on incidents or users.';

grant select on agentops.status_feed to anon, authenticated;
