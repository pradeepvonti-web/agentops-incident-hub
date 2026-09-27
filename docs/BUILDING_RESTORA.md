# Inside Restora: how the codebase is put together

Restora is an incident management platform — on-call, alerts, response, status
pages, post-incident — built as a working product rather than a demo. This is a
walk through the code: what runs where, why it is shaped the way it is, and the
handful of rules that hold it together. If you want the *why* of the whole
project, read `docs/ARTICLE.md` first. This one is the *how*.

The numbers, so you know what you are reading about: roughly 7,000 lines of
TypeScript and CSS in the frontend, 840 lines of Python in the API, 26 tables
and three views in Postgres, 15 migrations, 26 backend tests, and about 400
lines of deterministic scripts. It is small enough to read in an afternoon.

## The shape of it

```text
              Supabase Postgres (schema: agentops)
              RLS · triggers · SQL functions · Realtime
                    │                          │
        PostgREST + Auth + Realtime            │  REST (service key)
                    │                          │
            React app (browser)          FastAPI service
            auth, reads, writes          /api/v1 for agents,
            live updates                 SSE stream, alert webhook
```

Two clients, one database. The browser is a first-class Supabase client — it
authenticates, reads, writes and subscribes directly. The FastAPI service is
*not* in that path; it exists for things that are not a browser: agents,
scripts, a monitoring system posting an alert. They share the schema and the
rules in it, which is the point.

The repository:

```text
backend/        FastAPI: the agent-facing API, SSE, webhooks, offline fixtures
frontend/       React + Vite: the product and the marketing site
sample-data/    the fixtures the API, scripts and tests use offline
scripts/        deterministic transformations, including the video generators
docs/           rules, contracts, architecture — written for agents to read
evals/          checklists a change must pass
skills/         packaged workflows for an agent to run
```

## The database is where the rules live

Everything Restora owns is in the `agentops` schema of a Supabase project. That
name is a leftover from the project's first name, and I left it: renaming a live
schema is churn with no user-visible payoff, and the brand is not the schema.

The tables group the way the product does:

| Area | Tables |
|------|--------|
| People | `users`, `teams`, `team_members` |
| Catalog | `services`, `escalation_paths`, `escalation_levels` |
| On-call | `schedules`, `shifts` |
| Incidents | `incidents`, `incident_participants`, `incident_relations`, `incident_updates`, `incident_timeline`, `incident_logs` |
| Work | `actions`, `follow_ups`, `post_incident_tasks` |
| Alerts | `alert_sources`, `alert_routes`, `alerts` |
| Automation | `workflows`, `workflow_runs` |
| Status page | `status_page`, `status_components`, `incident_components`, `status_updates` |

The decision that shaped the most code: **a rule that must hold no matter who
writes belongs in SQL, not in a client.** Four examples.

**The executive-evidence rule.** Leadership summaries may contain only ERROR and
CRITICAL log events; WARNING stays visible for engineers. That filter exists in
exactly one place, a SQL function:

```sql
'evidence', coalesce((
  select jsonb_agg(to_char(l.occurred_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
                   || ' [' || l.level || '] ' || l.message order by l.occurred_at)
    from agentops.incident_logs l
   where l.incident_id = i.id
     and l.level in ('ERROR', 'CRITICAL')
), '[]'::jsonb)
```

The React app calls `incident_report()` and renders what comes back. The Python
API does the same. Neither re-filters. Earlier in this project's life the
frontend showed every log under a heading called "Evidence" while the backend
implemented the rule correctly and nobody called it — a rule in two places is a
bug waiting to happen, and that bug is what taught me to put it in one.

**The audit trail writes itself.** An `after update` trigger on `incidents`
appends a timeline entry whenever status or severity changes:

```sql
if new.status is distinct from old.status then
  insert into agentops.incident_timeline (incident_id, kind, title, detail, author_id)
  values (new.id, case when new.status = 'Closed' then 'closed' else 'status' end,
          format('Status changed from %s to %s', old.status, new.status), '',
          agentops.current_user_id());
end if;
```

A client cannot forget to log a status change, because the client does not log
it. `current_user_id()` resolves the signed-in Supabase Auth user to their
profile row, so the entry carries who did it.

**Multi-step writes are one function.** Declaring an incident creates the row,
adds the reporter as a participant, and writes the opening timeline entry.
Posting an update can move the status and backfills `identified_at`,
`fixed_at` and `closed_at` from the transition. Escalating an alert declares an
incident and links the two. Each is a `security definer` function —
`declare_incident`, `post_update`, `escalate_alert` — so it is one transaction
and one round trip, and the invariants hold even from `psql`.

**Auth links to a seeded identity.** A trigger on `auth.users` matches a new
signup to a seeded responder by email, so signing up as
`sam.lee@agentops.example` adopts Sam's incidents. Otherwise it creates a fresh
profile. Nothing in the app has to know how accounts come to exist.

### Row level security

RLS is on for all 26 tables. Signed-in responders read the whole workspace and
write everything incident response touches; it is a single-team product, and
tenancy would be the first change for a real deployment. Anonymous readers get
exactly three tables — `status_page`, `status_components`, `status_updates` —
which is what makes the public `/status` page work without an account.

Two details worth knowing. First, the grants match the policies: an early
version left `anon` with `SELECT` on everything (RLS blocked the reads, but the
tables were still discoverable through GraphQL introspection), and Supabase's
security advisor caught it. Second, `status_feed` is a view that deliberately is
*not* `security_invoker`. An anonymous reader has no grant on `incidents` or
`users`, so a joined query would fail; the view runs as its owner and exposes
only the five fields a customer should see. That is written down in
`docs/DATABASE.md` next to the view, because a definer view is the kind of
decision that should never be silent.

### Realtime

Ten tables are in the `supabase_realtime` publication. The browser subscribes
through a hook that turns changes into a counter:

```ts
export function useLiveTable(table: string): number {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const channel = supabase.channel(`live:${table}`)
      .on("postgres_changes", { event: "*", schema: SCHEMA, table }, () => setTick(n => n + 1))
      .subscribe();
    return () => { supabase.removeChannel(channel); };
  }, [table]);
  return tick;
}
```

Pages put that tick in their fetch dependencies, and a write in one tab lands
in every other tab within a second. It is the least clever realtime design I
could think of, which is why it has not broken.

## The frontend

React 18, TypeScript, Vite, react-router-dom 7, `@supabase/supabase-js`.
Nothing else for the product. The marketing site adds GSAP and three.js.

```text
frontend/src/
├── app/            AuthProvider, AppShell, CommandPalette, DeclareIncidentDialog
├── pages/          one file per route, thirteen of them
├── components/     ui.tsx, forms.tsx, Logo, SeverityBadge, StatusPill, IncidentTable
├── lib/
│   ├── supabase.ts   the client, pinned to the agentops schema
│   ├── data.ts       every read and every write, ~600 lines
│   ├── useLive.ts    realtime as a tick counter
│   ├── useAsync.ts   load / error state for a fetcher
│   └── format.ts     time, duration, initials
├── marketing/      animate.ts, HeroScene, LiveChannel, DemoVideo, Tilt
├── styles.css      the product design system
└── marketing.css   the marketing site
```

**All data access goes through `lib/data.ts`.** Pages never import the Supabase
client. Reads return typed view models built from PostgREST's embedded selects:

```ts
supabase.from("post_incident_tasks").select(
  `id, title, status, due_on, position, owner:users(${PERSON}),
   incident:incidents(id, reference, title, severity, status,
                      lead:users!incidents_lead_id_fkey(${PERSON}))`
)
```

`incidents` has two foreign keys to `users` (lead and reporter), so the join
has to name which one it wants. The schema has no generated TypeScript types —
the queries are cast through a small `q<T>()` helper that names the shape the
caller expects. That is a deliberate trade: generated types would be safer, and
adding them is one `supabase gen types` away, but keeping the data layer
readable mattered more while the shape was still moving.

Writes are thin: `updateIncident(id, patch)`, `setTaskStatus(table, id,
status)`, `addFollowUp(...)`. The complicated ones call the SQL functions.

**Forms share one submit hook.** `useSubmit(action, onDone)` owns pending and
error state, so every form on the site behaves the same way and no page
hand-rolls a loading flag.

**The incident workspace** — `pages/IncidentDetail.tsx` — is where most of the
product lives: the lifecycle bar, inline severity and status selects, an update
composer that can move the incident forward, five tabs (updates, timeline,
actions, follow-ups, evidence), and a metadata rail for lead, service,
timestamps, duration metrics, post-incident tasks and related incidents. It
subscribes to six tables. Every control writes through `data.ts` and waits for
the realtime tick to refetch rather than optimistically patching local state —
slower by a few hundred milliseconds, and never wrong.

**Two severity representations would be one too many.** `SeverityBadge` is the
only way severity is drawn. `StatusPill` and `LifecycleBar` are the only ways
status is drawn. CLAUDE.md says so, and the eval checks it.

## The marketing site

The landing page was measured from a reference — content column 1192px, body
16/24, serif headings at weight 400 with tight tracking, pill buttons at
12px 20px, oat panels at `#f8f5f0` and `#f1ebe2`. The values are in the header
comment of `marketing.css`. The structure follows the reference section for
section; the copy, the name, the customers and the quotes are all ours.

The design is green with an orange "pop": green carries the brand, orange marks
urgency and the agent. The declare-incident button in the app is the one orange
control there, because it is the one emergency action.

Four things make it move.

**GSAP.** `marketing/animate.ts` scopes every tween to the page root and tears
them down on unmount. Elements opt in with data attributes — `data-reveal`,
`data-reveal="stagger"`, `data-count`, `data-marquee`, `data-float` — so the
markup says what animates. There is a failsafe that reveals everything after
three seconds, because a background tab at load time throttles the animation
ticker and a hero that never appears is worse than one that appears without
ceremony.

**three.js.** `HeroScene.tsx` draws 220 nodes on a squashed sphere, edges
between near neighbours, a few orange nodes pulsing. It follows the pointer and
sits behind the headline under a radial mask. Reduced-motion users get it
still.

**Generated video.** There are four videos on the page and none was filmed.
`scripts/render_demo_video.py` and `scripts/render_feature_clips.py` draw every
frame with Pillow — the actual UI, running one incident from alert to customer
update — and encode with the ffmpeg binary that `imageio-ffmpeg` ships. Change
the story, re-run the script, new video. The clips are 40–180 KB each.

**An interactive channel.** `LiveChannel.tsx` is the hero's incident
conversation. Messages type in; the agent's chips are real buttons; clicking
"Roll back" continues the story and moves the status pill. It is the product's
pitch, done as the product rather than as a picture of it.

The logo is a wordmark: `restora`, lowercase, with the `o` in orange. One
component, `components/Logo.tsx`, on every surface; a lowercase-r tile for the
favicon and home-screen icons, rendered from the SVG by resvg.

## The FastAPI service

`backend/app/` is 840 lines. Routers stay thin; logic lives in services.

```text
api/incidents.py     /incidents, /board, /insights, /post-incident
api/platform.py      /catalog, /alerts, /oncall, /workflows, /status-page
api/stream.py        GET /stream — server-sent events
api/webhooks.py      POST /webhooks/alerts — inbound alert ingestion
services/incident_service.py     report rule, board, insights, over fixtures
services/platform_service.py     reference data
services/supabase_repository.py  PostgREST client for the live path
```

Two things about it are unusual and intentional.

The read endpoints serve `sample-data/` — the same eight incidents the seed
migrations were generated from — so the API, the scripts and the whole test
suite run **offline**. CI has no Supabase credentials and the tests assert the
unconfigured behaviour on purpose: the webhook returns 503 with a message naming
the missing variable, the stream emits one `error` event and closes. The live
path, `supabase_repository.py`, uses the service key when present, because a
server-side actor has no user session; with only the publishable key it sees
exactly what an anonymous visitor sees. A `MockTransport` test proves it sends
`Accept-Profile: agentops` and prefers the service key.

The SSE stream exists because the browser has Realtime and everything else does
not. It polls `incident_list` for rows with `updated_at` past a cursor and
emits `incident.changed` events with a heartbeat between polls. Running it
against the real project during development surfaced the exact blocker of the
day — `Invalid schema: agentops` before the schema was exposed, `permission
denied` before the service key — which is the nicest thing an integration
endpoint can do.

## The tooling around the code

This part is easy to skip and is most of why the codebase is pleasant to work
in.

`docs/INCIDENT_RULES.md` holds the canonical categories, severities and
lifecycle statuses and says where each is enforced. `docs/API_CONTRACT.md`
lists both APIs. `docs/DATABASE.md` explains the schema, the SQL-enforced rules,
the RLS reasoning and the migration list. `CLAUDE.md` carries the conventions
an agent must follow to touch the code: one page per route, all data through
`data.ts`, wrap submits in `useSubmit`, rules that must always hold go in SQL,
new tables get RLS in the same migration, run the security advisor after DDL.

`evals/dashboard-eval.md` is the checklist a user-facing change has to pass —
auth, navigation, writes, visual, quality — and it grew a "writes" section when
the app grew a write path. `skills/` packages the repeated workflows: triage an
incident, review the architecture, validate the dashboard.

`scripts/` are the deterministic transformations: parse and filter logs,
categorise by keyword, aggregate by service, render a report, render the
videos. The agent orchestrates; the scripts do the arithmetic.

## What I would change, and what is missing

The `q<T>()` casts in `data.ts` should become generated types once the schema
settles. The FastAPI reads should have a Supabase-backed mode so the agent API
and the app cannot drift. Tenancy would touch every RLS policy and should be
designed, not bolted on. And the product is missing the screens the reference
has that this does not: onboarding, settings (custom fields, roles, API keys),
post-mortem documents, shoutouts, saved views.

None of that is hidden. The codebase tells you what it does, in the docs an
agent reads and in the SQL that enforces it. That was the goal.

---

Run it: expose the `agentops` schema in your Supabase project, copy
`frontend/.env.example` to `.env.local`, `npm run dev`. Backend tests are
`cd backend && pytest`. The videos regenerate with
`python scripts/render_demo_video.py`.
