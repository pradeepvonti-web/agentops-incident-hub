# Incident Rules

## Categories
Only:
- Availability
- Performance
- Security
- Data
- Integration

## Severity
Only INFO, WARNING, ERROR, CRITICAL.

## Lifecycle statuses
An incident moves forward through these statuses and never skips backwards:

1. Triage
2. Investigating
3. Fixing
4. Monitoring
5. Documenting
6. Reviewing
7. Closed

Triage through Monitoring count as **active**. `GET /api/v1/incidents?status=active`
and the home board both use that definition, which lives in
`ACTIVE_STATUSES` in `backend/app/models.py`.

## Keyword hints
- auth, unauthorized, forbidden, token, credential -> Security
- timeout, latency, slow, saturation -> Performance
- unavailable, connection refused, health check, outage -> Availability
- malformed, corruption, schema, duplicate -> Data
- webhook, upstream, downstream, external API -> Integration

When no keyword matches, `scripts/categorize_incidents.py` falls back to the
category recorded on the incident.

## Executive evidence
Only ERROR and CRITICAL log events.

The rule is enforced once, in `IncidentService.build_report`, and exposed through
`GET /api/v1/incidents/{incident_id}/report`. Clients render that response rather
than re-filtering logs themselves.

WARNING and INFO events stay available for technical analysis through
`GET /api/v1/incidents/{incident_id}/logs` and the dashboard log timeline.

## Required summary fields
- incident ID
- title
- service
- severity
- category
- first occurrence
- latest occurrence
- probable cause
- suggested next action

## Ownership
Every incident's `service` must exist in `sample-data/catalog/catalog.json`.
The catalog is what connects an incident to a team and an escalation path,
and a test asserts the link holds.
