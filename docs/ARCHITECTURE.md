# Architecture

```text
                 Supabase Postgres (schema: agentops)
                 RLS · triggers · SQL functions · Realtime
                    |                         |
        PostgREST + Auth + Realtime           |  REST (publishable key)
                    |                         |
            React app (browser)        FastAPI service
            auth, reads, writes        /api/v1 for agents,
            live updates               SSE stream, alert webhook
```

The browser is a first-class Supabase client: it authenticates, reads and writes
directly, and subscribes to changes. The FastAPI service is not in that path. It
exists so that agents, scripts and inbound integrations have an HTTP surface that
does not need a browser session.

## Frontend

React + TypeScript + Vite, routed with react-router-dom.

```text
frontend/src/
├── app/
│   ├── AuthProvider.tsx        session and the responder profile
│   ├── AppShell.tsx            sidebar, live counters, declare button
│   ├── CommandPalette.tsx      cmd-K over pages and incidents
│   └── DeclareIncidentDialog.tsx
├── pages/                      one file per route
├── components/
│   ├── ui.tsx                  shared presentational pieces
│   ├── forms.tsx               Modal, Field, useSubmit, PersonSelect
│   ├── SeverityBadge.tsx       the only severity representation
│   ├── StatusPill.tsx          status pill and lifecycle bar
│   └── IncidentTable.tsx
├── lib/
│   ├── supabase.ts             the client, pinned to the agentops schema
│   ├── data.ts                 every read and write in one module
│   ├── useLive.ts              realtime subscriptions as a tick counter
│   ├── useAsync.ts             load/error state
│   └── format.ts               time, duration, initials
├── marketing/
│   ├── animate.ts              GSAP + ScrollTrigger; elements opt in via data attributes
│   ├── HeroScene.tsx           three.js graph of services behind the hero
│   ├── LiveChannel.tsx         the interactive incident channel in the hero
│   ├── DemoVideo.tsx           the rendered walkthrough with chapter seeking
│   └── Tilt.tsx                pointer-driven 3D tilt for cards
├── styles.css                  the app design system
└── marketing.css               the public marketing site, measured from the reference
```

`frontend/public/media/` holds the demo video and poster. They are generated,
not recorded: `scripts/render_demo_video.py` draws every frame with Pillow and
encodes with ffmpeg, so a change to the product story is a code change.

Routes: `/` is the marketing site when signed out and the home board when signed
in; `/login` and `/status` are public; behind auth `/incidents`,
`/incidents/:reference`, `/alerts`, `/on-call`, `/status-page`,
`/post-incident`, `/insights`, `/catalog`, `/workflows`.

## Backend

FastAPI. Reads Supabase over PostgREST with the publishable key; writes only
where a service key is configured.

```text
backend/app/
├── main.py                            app, CORS, routers
├── config.py                          settings from the environment
├── models.py                          pydantic models, lifecycle constants
├── api/
│   ├── incidents.py                   incidents and derived views
│   ├── platform.py                    catalog, alerts, on-call, workflows, status
│   ├── stream.py                      GET /stream, server-sent events
│   └── webhooks.py                    POST /webhooks/alerts, inbound alerts
└── services/
    ├── incident_service.py            report rule, board, insights
    ├── platform_service.py            reference data
    └── supabase_repository.py         PostgREST client
```

`incident_service.py` still reads `sample-data/` so the API, the deterministic
scripts and the test suite all run offline. `supabase_repository.py` is the live
path. `sample-data/` is also the source the seed migrations were generated from,
which is why the two agree.

## Data flow for one incident

```text
alert arrives (webhook or the console's simulate button)
        |
        v
agentops.alerts row
        |  escalate_alert()
        v
agentops.incidents row + participant + timeline entry
        |  post_update() ...
        v
status changes -> trigger writes timeline -> Realtime pushes to every open tab
        |
        v
incident_report() filters evidence to ERROR and CRITICAL
        |
        v
post-incident tasks and follow-ups
```

See `docs/DATABASE.md` for the schema and the rules that live in SQL.
