insert into agentops.incidents (
  reference, title, summary, service_id, severity, category, status,
  lead_id, reporter_id, probable_cause, suggested_next_action,
  impact_started_at, declared_at, identified_at, fixed_at, closed_at
)
select v.reference, v.title, v.summary, s.id, v.severity::agentops.severity,
       v.category::agentops.category, v.status::agentops.incident_status,
       lead.id, reporter.id, v.probable_cause, v.next_action,
       v.impact_started_at::timestamptz, v.declared_at::timestamptz,
       v.identified_at::timestamptz, v.fixed_at::timestamptz, v.closed_at::timestamptz
  from (values
    ('INC-1042', 'Checkout API unavailable',
     'Customers cannot complete checkout. Checkout instances fail to reach the payments dependency and health checks are flapping.',
     'checkout-api', 'CRITICAL', 'Availability', 'Fixing',
     'sam.lee@agentops.example', 'alex.moreau@agentops.example',
     'Checkout instances cannot establish connections to the payments dependency.',
     'Check payments service health and recent network or deployment changes before restarting checkout instances.',
     '2026-09-26T18:00:00Z', '2026-09-26T18:04:00Z', '2026-09-26T18:09:00Z', null, null),

    ('INC-1043', 'Search latency regression',
     'Catalog search p95 latency tripled after the query-expansion flag was enabled for 50% of traffic.',
     'catalog-search', 'ERROR', 'Performance', 'Monitoring',
     'dana.okafor@agentops.example', 'sam.lee@agentops.example',
     'A high-cardinality query pattern is saturating the search cluster.',
     'Disable the new query expansion flag and compare p95 latency before and after rollback.',
     '2026-09-26T17:18:00Z', '2026-09-26T17:26:00Z', '2026-09-26T17:44:00Z', '2026-09-26T18:05:00Z', null),

    ('INC-1044', 'Expired auth signing key',
     'The active JWT signing key expired before its replacement was promoted, rejecting 40% of authentication attempts.',
     'identity', 'CRITICAL', 'Security', 'Closed',
     'priya.raman@agentops.example', 'dana.okafor@agentops.example',
     'The active signing key expired before the replacement key was promoted.',
     'Verify rotation automation and add an alert for keys expiring within seven days.',
     '2026-09-26T15:08:00Z', '2026-09-26T15:12:00Z', '2026-09-26T15:19:00Z', '2026-09-26T15:44:00Z', '2026-09-26T16:30:00Z'),

    ('INC-1045', 'Duplicate order records',
     'Retry processing created duplicate order rows for delayed messages. No customer impact, reconciliation required.',
     'order-ingestion', 'WARNING', 'Data', 'Documenting',
     'sam.lee@agentops.example', 'sam.lee@agentops.example',
     'Retry processing is creating duplicate order rows for delayed messages.',
     'Add idempotency checks and reconcile duplicate records.',
     '2026-09-26T14:00:00Z', '2026-09-26T14:06:00Z', '2026-09-26T14:22:00Z', '2026-09-26T14:50:00Z', null),

    ('INC-1046', 'Partner webhook failures',
     'A partner endpoint is intermittently returning 502s, so outbound webhooks are failing and retrying.',
     'partner-gateway', 'ERROR', 'Integration', 'Investigating',
     'alex.moreau@agentops.example', 'alex.moreau@agentops.example',
     'The external partner endpoint is intermittently returning 502 responses.',
     'Confirm partner status, enable bounded retries, and inspect failures by endpoint.',
     '2026-09-26T16:03:00Z', '2026-09-26T16:10:00Z', null, null, null),

    ('INC-1047', 'Inventory sync backlog growing',
     'The warehouse sync queue is growing faster than it drains. Stock levels may lag by up to an hour.',
     'inventory-sync', 'WARNING', 'Integration', 'Triage',
     null, null,
     'Queue consumers are not keeping up with the warehouse feed.',
     'Scale the sync consumers and confirm whether the warehouse feed volume changed.',
     '2026-09-26T19:00:00Z', '2026-09-26T19:05:00Z', null, null, null),

    ('INC-1048', 'Elevated 5xx on profile service',
     'Profile reads returned 5xx for 18 minutes after a bad cache configuration reached production.',
     'profile', 'ERROR', 'Availability', 'Reviewing',
     'dana.okafor@agentops.example', 'priya.raman@agentops.example',
     'A cache TTL of zero was rolled out, sending every read to the database.',
     'Add a configuration guardrail rejecting a zero TTL and backfill the change log.',
     '2026-09-26T11:12:00Z', '2026-09-26T11:16:00Z', '2026-09-26T11:21:00Z', '2026-09-26T11:32:00Z', null),

    ('INC-1049', 'Report exports timing out',
     'Large CSV exports timed out for enterprise accounts during the nightly reporting window.',
     'reporting', 'WARNING', 'Performance', 'Closed',
     'sam.lee@agentops.example', 'alex.moreau@agentops.example',
     'Export queries were not using the account index after a schema migration.',
     'Rebuild the account index and add an export duration budget to CI.',
     '2026-09-26T02:38:00Z', '2026-09-26T02:45:00Z', '2026-09-26T02:52:00Z', '2026-09-26T03:05:00Z', '2026-09-26T09:00:00Z')
  ) as v(reference, title, summary, service_slug, severity, category, status,
         lead_email, reporter_email, probable_cause, next_action,
         impact_started_at, declared_at, identified_at, fixed_at, closed_at)
  left join agentops.services s on s.slug = v.service_slug
  left join agentops.users lead on lead.email = v.lead_email
  left join agentops.users reporter on reporter.email = v.reporter_email;

insert into agentops.incident_logs (incident_id, level, message, occurred_at)
select i.id, v.level::agentops.severity, v.message, v.occurred_at::timestamptz
  from (values
    ('INC-1042', 'WARNING', 'payments latency exceeded 900ms', '2026-09-26T18:02:14Z'),
    ('INC-1042', 'ERROR', 'payments connection refused for request 82a1', '2026-09-26T18:03:01Z'),
    ('INC-1042', 'CRITICAL', 'checkout health check failed: payments unavailable', '2026-09-26T18:03:18Z'),
    ('INC-1042', 'ERROR', 'payments connection refused for request 83cc', '2026-09-26T18:15:50Z'),
    ('INC-1043', 'WARNING', 'search p95 latency is 1350ms', '2026-09-26T17:20:00Z'),
    ('INC-1043', 'ERROR', 'search request timeout after 3000ms', '2026-09-26T17:25:10Z'),
    ('INC-1043', 'ERROR', 'search shard timeout for query expansion', '2026-09-26T18:10:11Z'),
    ('INC-1044', 'ERROR', 'token validation failed: signing key expired', '2026-09-26T15:10:44Z'),
    ('INC-1044', 'CRITICAL', 'authentication failures exceed 40 percent', '2026-09-26T15:11:02Z'),
    ('INC-1044', 'INFO', 'new signing key promoted successfully', '2026-09-26T15:44:03Z'),
    ('INC-1045', 'WARNING', 'duplicate order key detected: ORD-9981', '2026-09-26T14:01:10Z'),
    ('INC-1045', 'WARNING', 'duplicate order key detected: ORD-9990', '2026-09-26T14:48:12Z'),
    ('INC-1046', 'ERROR', 'third-party webhook returned HTTP 502', '2026-09-26T16:05:22Z'),
    ('INC-1046', 'WARNING', 'webhook retry scheduled', '2026-09-26T16:35:20Z'),
    ('INC-1046', 'ERROR', 'upstream external API returned HTTP 502', '2026-09-26T18:01:40Z'),
    ('INC-1047', 'WARNING', 'inventory sync queue depth 12000 and rising', '2026-09-26T19:02:00Z'),
    ('INC-1047', 'ERROR', 'inventory sync consumer lag exceeded 45 minutes', '2026-09-26T19:21:00Z'),
    ('INC-1048', 'ERROR', 'profile read returned HTTP 503', '2026-09-26T11:14:00Z'),
    ('INC-1048', 'CRITICAL', 'profile database connections saturated', '2026-09-26T11:18:00Z'),
    ('INC-1048', 'INFO', 'cache ttl restored to 300s', '2026-09-26T11:32:00Z'),
    ('INC-1049', 'WARNING', 'export job exceeded 120s soft limit', '2026-09-26T02:40:00Z'),
    ('INC-1049', 'ERROR', 'export job cancelled after 300s', '2026-09-26T02:51:00Z'),
    ('INC-1049', 'INFO', 'account index rebuilt', '2026-09-26T03:05:00Z')
  ) as v(reference, level, message, occurred_at)
  join agentops.incidents i on i.reference = v.reference;

insert into agentops.incident_updates (
  incident_id, author_id, status, severity, message, next_update_in_minutes, created_at
)
select i.id, u.id, v.status::agentops.incident_status, v.severity::agentops.severity,
       v.message, v.next_update, v.created_at::timestamptz
  from (values
    ('INC-1042', 'sam.lee@agentops.example', 'Investigating', 'CRITICAL',
     'Checkout is failing for all regions. Paging the payments on-call now.', 15, '2026-09-26T18:05:00Z'),
    ('INC-1042', 'priya.raman@agentops.example', 'Fixing', 'CRITICAL',
     'Payments connection pool was exhausted after the 17:50 deploy. Rolling back.', 15, '2026-09-26T18:12:00Z'),
    ('INC-1043', 'dana.okafor@agentops.example', 'Investigating', 'ERROR',
     'p95 is 3x baseline. Correlating with this morning''s flag rollout.', 30, '2026-09-26T17:30:00Z'),
    ('INC-1043', 'dana.okafor@agentops.example', 'Monitoring', 'ERROR',
     'Flag disabled. Latency back to baseline, watching for 30 minutes.', 30, '2026-09-26T18:05:00Z'),
    ('INC-1044', 'priya.raman@agentops.example', 'Investigating', 'CRITICAL',
     'Authentication failures across all clients. Checking key rotation state.', 15, '2026-09-26T15:15:00Z'),
    ('INC-1044', 'priya.raman@agentops.example', 'Monitoring', 'CRITICAL',
     'Replacement key promoted. Error rate back to zero.', 30, '2026-09-26T15:45:00Z'),
    ('INC-1044', 'priya.raman@agentops.example', 'Closed', 'CRITICAL',
     'Post-mortem published, follow-ups assigned.', null, '2026-09-26T16:30:00Z'),
    ('INC-1045', 'sam.lee@agentops.example', 'Investigating', 'WARNING',
     'Two duplicate orders confirmed. No customer-visible impact yet.', 60, '2026-09-26T14:10:00Z'),
    ('INC-1045', 'sam.lee@agentops.example', 'Documenting', 'WARNING',
     'Consumer patched with an idempotency key. Writing this up.', null, '2026-09-26T14:50:00Z'),
    ('INC-1046', 'alex.moreau@agentops.example', 'Investigating', 'ERROR',
     'Partner has acknowledged degraded service on their side. Retries are bounded.', 60, '2026-09-26T16:20:00Z'),
    ('INC-1048', 'dana.okafor@agentops.example', 'Fixing', 'ERROR',
     'Config change identified. Reverting now.', 15, '2026-09-26T11:20:00Z'),
    ('INC-1048', 'dana.okafor@agentops.example', 'Reviewing', 'ERROR',
     'Error rate is back to zero. Drafting the post-mortem.', null, '2026-09-26T11:35:00Z'),
    ('INC-1049', 'sam.lee@agentops.example', 'Monitoring', 'WARNING',
     'Index rebuilt, exports completing in under 20s.', null, '2026-09-26T03:05:00Z'),
    ('INC-1049', 'sam.lee@agentops.example', 'Closed', 'WARNING',
     'Closed after a clean nightly run.', null, '2026-09-26T09:00:00Z')
  ) as v(reference, email, status, severity, message, next_update, created_at)
  join agentops.incidents i on i.reference = v.reference
  join agentops.users u on u.email = v.email;

insert into agentops.incident_timeline (incident_id, kind, title, detail, author_id, occurred_at)
select i.id, v.kind::agentops.timeline_kind, v.title, v.detail, u.id, v.occurred_at::timestamptz
  from (values
    ('INC-1042', 'alert', 'Alert fired: checkout health check failing',
     'Routed to Payments on-call via the Checkout alert route.', 'sam.lee@agentops.example', '2026-09-26T18:02:14Z'),
    ('INC-1042', 'declared', 'Incident declared', 'Declared at CRITICAL by Alex Moreau.',
     'alex.moreau@agentops.example', '2026-09-26T18:04:00Z'),
    ('INC-1042', 'update', 'Update shared', 'Checkout is failing for all regions. Paging the payments on-call now.',
     'sam.lee@agentops.example', '2026-09-26T18:05:00Z'),
    ('INC-1042', 'status', 'Status changed from Investigating to Fixing',
     'Root cause identified in the payments connection pool.', 'priya.raman@agentops.example', '2026-09-26T18:09:00Z'),
    ('INC-1042', 'action', 'Action assigned: roll back payments 4.12.0', 'Owner: Priya Raman',
     'sam.lee@agentops.example', '2026-09-26T18:15:00Z'),
    ('INC-1043', 'alert', 'Alert fired: search p95 above threshold', 'Routed to Catalog on-call.',
     'dana.okafor@agentops.example', '2026-09-26T17:20:00Z'),
    ('INC-1043', 'declared', 'Incident declared', 'Declared at ERROR by Sam Lee.',
     'sam.lee@agentops.example', '2026-09-26T17:26:00Z'),
    ('INC-1043', 'status', 'Cause identified', 'Query expansion flag is generating high-cardinality queries.',
     'dana.okafor@agentops.example', '2026-09-26T17:44:00Z'),
    ('INC-1043', 'status', 'Status changed from Fixing to Monitoring', 'Flag disabled for all traffic.',
     'dana.okafor@agentops.example', '2026-09-26T18:05:00Z'),
    ('INC-1044', 'alert', 'Alert fired: authentication error rate', 'Urgent priority, paged Identity on-call.',
     'priya.raman@agentops.example', '2026-09-26T15:10:44Z'),
    ('INC-1044', 'declared', 'Incident declared', 'Declared at CRITICAL by Dana Okafor.',
     'dana.okafor@agentops.example', '2026-09-26T15:12:00Z'),
    ('INC-1044', 'status', 'Cause identified', 'Signing key expired at 15:08 UTC; replacement never promoted.',
     'priya.raman@agentops.example', '2026-09-26T15:19:00Z'),
    ('INC-1044', 'status', 'Fixed', 'New signing key promoted successfully.',
     'priya.raman@agentops.example', '2026-09-26T15:44:00Z'),
    ('INC-1044', 'closed', 'Incident closed', 'Post-mortem published.',
     'priya.raman@agentops.example', '2026-09-26T16:30:00Z'),
    ('INC-1045', 'alert', 'Alert fired: duplicate order keys', 'Low priority, no page.',
     'sam.lee@agentops.example', '2026-09-26T14:01:10Z'),
    ('INC-1045', 'declared', 'Incident declared', 'Declared at WARNING by Sam Lee.',
     'sam.lee@agentops.example', '2026-09-26T14:06:00Z'),
    ('INC-1045', 'status', 'Status changed from Fixing to Documenting', 'Idempotency key deployed.',
     'sam.lee@agentops.example', '2026-09-26T14:50:00Z'),
    ('INC-1046', 'alert', 'Alert fired: webhook delivery failures', 'Routed to Integrations on-call.',
     'alex.moreau@agentops.example', '2026-09-26T16:05:22Z'),
    ('INC-1046', 'declared', 'Incident declared', 'Declared at ERROR by Alex Moreau.',
     'alex.moreau@agentops.example', '2026-09-26T16:10:00Z'),
    ('INC-1047', 'alert', 'Alert fired: queue depth above threshold', 'Awaiting triage.',
     'dana.okafor@agentops.example', '2026-09-26T19:02:00Z'),
    ('INC-1047', 'declared', 'Incident declared', 'Auto-declared by the queue-depth workflow.',
     'dana.okafor@agentops.example', '2026-09-26T19:05:00Z'),
    ('INC-1048', 'declared', 'Incident declared', 'Declared at ERROR by Priya Raman.',
     'priya.raman@agentops.example', '2026-09-26T11:16:00Z'),
    ('INC-1048', 'status', 'Cause identified', 'Cache TTL set to zero in the 11:10 config push.',
     'dana.okafor@agentops.example', '2026-09-26T11:21:00Z'),
    ('INC-1048', 'status', 'Fixed', 'TTL restored to 300s.',
     'dana.okafor@agentops.example', '2026-09-26T11:32:00Z'),
    ('INC-1049', 'declared', 'Incident declared', 'Declared at WARNING by Alex Moreau.',
     'alex.moreau@agentops.example', '2026-09-26T02:45:00Z'),
    ('INC-1049', 'status', 'Cause identified', 'Missing account index after migration 0142.',
     'sam.lee@agentops.example', '2026-09-26T02:52:00Z'),
    ('INC-1049', 'closed', 'Incident closed', 'Clean nightly run confirmed.',
     'sam.lee@agentops.example', '2026-09-26T09:00:00Z')
  ) as v(reference, kind, title, detail, email, occurred_at)
  join agentops.incidents i on i.reference = v.reference
  join agentops.users u on u.email = v.email;
