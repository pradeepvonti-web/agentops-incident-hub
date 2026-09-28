# Architecture

```text
                       Supabase Postgres, one project
        schema agentops (Restora)          schema public (AI DevOps)
        RLS · triggers · functions         forced RLS · adp_app role
        Realtime publication               deny-all to PostgREST
              |            |                        |
   PostgREST + Auth        | REST           asyncpg, tenant scope
   + Realtime              |                        |
              |            |                        |
        React app (one shell) ---- session token --> Control plane API
        Restora screens +    |                       aidevops/, port 8010
        AI DevOps screens    |                       /v1/runs, /v1/entry
                       FastAPI service
                       /api/v1 for agents, SSE, alert webhook

   public.runs --(trigger, on failed / rolled_back)--> agentops.alerts
```

The browser is a first-class Supabase client for Restora: it authenticates,
reads and writes directly, and subscribes to changes. The FastAPI service is not
in that path. It exists so that agents, scripts and inbound integrations have an
HTTP surface that does not need a browser session.

The AI DevOps half is the opposite by design: its tables are closed to the
browser, and the shell reaches them only through the control plane, which
verifies the same Supabase session and opens a tenant scope
(`aidevops/docs/adr/0005-one-platform-with-restora.md`). The two halves meet in
the database: a failed run raises a Restora alert by trigger.

## Repository map

```text
backend/       FastAPI: agent-facing API, SSE, webhooks, offline fixtures, tests
frontend/      React + Vite: the shell, both products' screens, the marketing site
aidevops/      the AI DevOps control plane, execution plane, contracts, Terraform, ADRs
supabase/      migrations that reproduce the database (both schemas), plus how to apply them
sample-data/   the fixtures the API, scripts and tests use offline
scripts/       deterministic transformations, including the video generators
docs/          rules, contracts, this file, the database notes, three articles
evals/         checklists a change must pass
skills/        packaged workflows for an agent to run
```

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
├── devops/
│   ├── entry.ts                the six entry points, mirrored from Python (tested)
│   ├── types.ts                run, span, approval shapes from adp-contracts
│   ├── RunRow.tsx              the dense run row, status by glyph
│   └── usePoll.ts              a tick; the control plane has no realtime channel
├── pages/devops/               AI DevOps home, runs, run detail, entry points
├── lib/
│   ├── supabase.ts             the client, pinned to the agentops schema
│   ├── data.ts                 every Restora read and write in one module
│   ├── controlPlane.ts         every control plane call, with the session token
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
`/post-incident`, `/insights`, `/catalog`, `/workflows`, and the AI DevOps
section: `/devops`, `/devops/runs`, `/devops/approvals`, `/devops/runs/:runId`,
`/devops/entry-points`.

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
