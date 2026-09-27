-- RLS already stopped anonymous readers everywhere except the status page, but
-- the table grants were wider than that, which made every table discoverable
-- through GraphQL introspection. Narrow the grants to match the policies.
revoke select on all tables in schema agentops from anon;

grant select on
  agentops.status_page,
  agentops.status_components,
  agentops.status_updates
to anon;
