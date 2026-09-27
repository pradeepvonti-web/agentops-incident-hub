# API Contract

There are two APIs. The browser uses Supabase; agents and integrations use
FastAPI.

## Supabase (used by the web app)

Base: `https://<project>.supabase.co/rest/v1`, schema `agentops`, publishable
key, RLS enforced. Tables and views are listed in `docs/DATABASE.md`.

Clients call these functions rather than writing the rows by hand:

| RPC | Purpose |
|-----|---------|
| `declare_incident` | Create an incident with its reporter and opening timeline entry |
| `post_update` | Share an update, optionally moving status and backfilling timestamps |
| `escalate_alert` | Turn an alert into an incident |
| `incident_report` | The deterministic report, evidence filtered to ERROR and CRITICAL |
| `bump_workflow_runs` | Increment a workflow's run counter |

## FastAPI (`/api/v1`, for agents and integrations)

### GET /incidents
Filters, combined with AND: `severity`, `status` (a lifecycle status or
`active`), `service`, `category`, `q`. Sorted by severity then id.

### GET /incidents/{incident_id}
Full detail. 404 when unknown.

### GET /incidents/{incident_id}/logs
Every log event, all severities.

### GET /incidents/{incident_id}/report
`evidence` contains ERROR and CRITICAL entries only.

### GET /board
Active incidents in the four open lifecycle columns.

### GET /insights
Counts by severity, category, service and status, plus mean time to declare and
mean time to resolve.

### GET /post-incident
Incidents with a post-incident flow, every follow-up, outstanding task count.

### GET /catalog · /alerts · /oncall · /workflows · /status-page
Reference data.

### GET /stream
Server-sent events. Emits `ready`, then `incident.changed` per changed incident
and a `heartbeat` on each poll. Requires `SUPABASE_URL`; without it the stream
emits one `error` event and closes.

```bash
curl -N http://localhost:8000/api/v1/stream
```

### POST /webhooks/alerts
Inbound alert ingestion, for a monitoring system with no user session.

```json
{ "title": "checkout error rate above 5%", "source": "metrics", "priority": "High", "payload": {} }
```

`201` with the new alert reference. `503` when `SUPABASE_SERVICE_KEY` is unset,
`502` when Supabase rejects the write.

### GET /health
`{"status": "ok", "supabase": bool, "ingestion": bool}`. Not under `/api/v1`.
