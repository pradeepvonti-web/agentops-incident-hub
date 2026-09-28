# From AI Coding Assistant to Agentic Engineering: Building Systems Where AI Can Plan, Build, Validate, and Collaborate

*The concepts from John Kim's Build with Claude Code intensive, explained one at
a time, with what each one looked like when I used it to build a real product.*

For the last couple of years the conversation about AI in software engineering
has mostly been about one question: how much faster can it write code? That
question is still fair, but it has become too narrow. The better question is:

> How do we design an engineering environment where AI can understand context,
> use tools, do the work, validate its own output, coordinate with other agents,
> and improve the workflow over time?

That is the shift from *AI-assisted coding* to *agentic engineering*. A coding
assistant helps with a task. An agentic engineering system is built to
understand a goal, gather context, choose tools, act, check itself, correct
itself, coordinate work, and leave reusable knowledge behind.

I wrote a first version of this article about a week after the course, with a
tidy diagram and an invented example application. Then I did what the course
kept telling me to do and put the agent to work on a real repository. The
example became a real product — **Restora**, an incident management platform
that started life as *AgentOps Incident Hub* — and then a second product, an
agentic data-engineering control plane called **AI DevOps**, was merged into
the same repository and the same shell. Almost every concept below now has a
story attached to it, usually one where something went wrong first.

This article explains each concept in plain terms, says why it matters, and
then shows what it actually looked like in this build. The repository is public
at [github.com/pradeepvonti-web/agentops-incident-hub](https://github.com/pradeepvonti-web/agentops-incident-hub).

---

## The example: Restora

Restora is the kind of product incident.io or PagerDuty sells: on-call
schedules, alert routing and escalation, an incident workspace with a timeline,
actions and participants, a public status page, a post-incident flow, and
insights. What exists today is a Supabase Postgres schema with 26 tables and
row-level security, a React application that reads and writes through Supabase
and updates live across browser tabs, a FastAPI service for agents with an SSE
event stream and an alert webhook, a marketing site, 26 backend tests, and
roughly 7,000 lines of frontend code — plus, since the merge, a second FastAPI
service with forced per-tenant row-level security and 171 tests of its own —
all built with Claude Code driving and me steering.

I chose incident response deliberately. It is repetitive enough to automate,
judgement-heavy enough that you cannot script it end to end, and full of rules
that live in people's heads rather than in the code. That is exactly the
terrain agentic engineering is meant for.

The second product is the other side of the same coin. AI DevOps is a control
plane where agents plan, generate and validate Databricks pipelines, humans
approve them as pull requests, and every step is traced so the acceptance rate
can be measured honestly. It had been built separately, against the same
Supabase project, with its own architecture decision records and 128
security-property tests. Merging it into Restora — one repository, one shell,
one sign-in — turned out to be the best exercise of the whole framework,
because it forced every concept to hold across two codebases at once. The
merge has its own section below.

---

## Concept 1 — Explore before you build

**What it means.** The first thing you ask an agent to do in a codebase is not
to change it. It is to understand it: what the application does, where the
entry points are, how data flows, how it is tested, and which files matter
most. Claude Code has a read-only *plan mode* for exactly this — the agent can
inspect everything and modify nothing. The workflow is *observe → understand →
verify → then act*.

**Why it matters.** An agent that starts building on a wrong mental model of
the repository produces confident, well-formatted code in the wrong place. The
cost of ten minutes of reading is nothing compared with the cost of unwinding
that.

**What it looked like here.** My first prompt against the repository was:

```
Explore this repository. Do not change anything.

Explain the architecture, the entry points, how data moves through
the system, the testing strategy, and the five files I should read
first. For every important claim, show me the file that supports it.
```

The last line is the one that earns its keep, and it is why the very first
thing the agent found was that my continuous integration was red on both jobs.
The backend tests could not import the app because of how `pytest` resolves
packages on the path; the frontend would not compile because `import.meta.env`
had no type declaration. Two one-line fixes, in a repository whose README told
people to run exactly those commands. I had written a section about validation
being the most important part of agentic engineering while my own validation
was broken. That sentence stays in because it is the most honest one here.

---

## Concept 2 — Challenge the agent

**What it means.** Language models do not reliably signal uncertainty. A
confident answer is not automatically a correct one, so the workflow must
force verification: when the agent makes a claim, ask it to prove the claim
from the source. The loop becomes *claim → evidence → verification → confirmed
or corrected*, instead of *prompt → answer → trust*.

**Why it matters.** The goal is not to make the AI sound smart. It is to make
the engineering process reliable, and reliability comes from checking.

**What it looked like here.** When the agent said "categorisation happens in
the service layer," I replied with *show me where*. The claim was half true:
keyword categorisation lives in a script (`scripts/categorize_incidents.py`),
and the category on each incident is stored data. An agent that skips that
distinction will happily add a sixth category that nothing downstream
understands. The habit is cheap and I now use it on every non-trivial claim.

---

## Concept 3 — Context engineering

**What it means.** Code is only part of what you need to build software
correctly. Product requirements, architecture decisions, business rules,
incident history, runbooks and security standards usually live in wikis,
tickets, emails and people's heads. Context engineering is the discipline of
bringing that knowledge to where the agent is working. Prompt engineering asks
*what should I say?* Context engineering asks *what should the agent know?*

**Why it matters.** If a rule only exists in an email, the agent will never
see it, and it will do something reasonable-looking that violates it.

**What it looked like here.** The rules that govern Restora are not derivable
from its source. Someone decided that incident categories are exactly five
values, that executive summaries contain only ERROR and CRITICAL events while
WARNING stays visible to engineers, and that an incident moves through seven
lifecycle statuses in order and never backwards. Those decisions live in
`docs/INCIDENT_RULES.md`, `docs/PRD.md` and `docs/ARCHITECTURE.md`, and the
agent reads them on every run without anyone re-explaining them in a prompt.

The rule that taught me the most was the evidence rule. It was documented. The
backend implemented it correctly. And the dashboard never called that function
— it fetched every log and rendered them all under a heading that said
"Evidence." Documented, implemented, and contradicted by the only screen anyone
looked at. **A rule written in two places is a bug waiting to happen.** When
the database arrived, that rule moved into one SQL function both clients call:

```sql
where l.incident_id = i.id
  and l.level in ('ERROR', 'CRITICAL')
```

---

## Concept 4 — Durable context: `CLAUDE.md`

**What it means.** `CLAUDE.md` is a file at the root of the repository that
Claude Code loads at the start of every session. It holds the project's
conventions, rules and validation requirements so they are asked once, written
down, and reused. The course frames it as storing *machine-consumable
engineering intent* alongside the code.

**Why it matters.** Without it, every session starts from zero and every
engineer re-explains the same conventions in prompts, inconsistently.

**What it looked like here.** Restora's `CLAUDE.md` names the architecture, the
canonical categories and severities, the lifecycle order, and a list of
conventions that grew as the build did: every Supabase read and write goes
through `frontend/src/lib/data.ts`; forms wrap submits in `useSubmit`; a rule
that must hold no matter who writes belongs in SQL; new tables need RLS
policies in the same migration; demo media is generated by scripts, never
edited by hand; green is the brand and orange is reserved for urgency. Each of
those lines exists because the agent did it a different way once. It also ends
with a *context discipline* loop, which is Concept 15 in miniature.

---

## Concept 5 — An agentic codebase

**What it means.** Enterprise codebases accumulate years of history: three
HTTP clients, severity spelled `"critical"`, `"CRITICAL"` and `1`, dead code,
forking paths. A human knows which pattern is current. An agent sees several
valid-looking choices. An agentic codebase is consistent, explicit, well-tested,
easy to navigate, and clear about its canonical patterns.

**Why it matters.** Competing patterns are the single most reliable way to get
an agent to produce plausible code that is wrong for *this* repository.

**What it looked like here.** The `architecture-review` skill exists to hunt
for exactly this: entry points, data flow, boundaries, competing patterns and
dead code, with a file cited for every finding. Concretely, the codebase has
one `SeverityBadge` component and no other severity representation, one
`Logo` component, one data module, and a single `ACTIVE_STATUSES` constant in
`backend/app/models.py` that nothing else re-derives. When the marketing site
was added it got its own folder and a rule that animations opt in through
data attributes rather than ad-hoc calls scattered across pages.

---

## Concept 6 — Skills: package repeated workflows

**What it means.** A skill is a reusable, named procedure the agent can run —
a `SKILL.md` file describing the steps, invoked as a slash command. The course's
guidance is to *do the workflow manually once, then package it*. The
architectural point underneath is that the AI should orchestrate deterministic
scripts, not replace them: use code for predictable transformations and the
agent for reasoning, exception handling and choosing what to do next.

**Why it matters.** Pushing arithmetic into a language model buys you variance
exactly where you do not want any. A script gives the same answer every time;
a skill makes sure the agent runs it the same way every time.

**What it looked like here.** Incident triage is the same six steps every
time — retrieve logs, parse, filter severity, categorise, aggregate service
impact, generate the report — so it is `scripts/triage_pipeline.py`, and
`skills/triage-incident/SKILL.md` tells the agent when to run it and to
validate the output against the rules file without inventing evidence. The
same principle reached into work I would have called creative: the four
videos on the landing page were never filmed. A script draws every frame of
one incident with Pillow and encodes it with ffmpeg. When I wanted a logo
tile as a PNG, the agent's hand-drawn arc had a notch twice; the fix was a
proper SVG rasteriser, not a cleverer drawing. The right move was a better
tool.

---

## Concept 7 — Agentic tooling: give the agent an interface

**What it means.** Eventually the agent hits a boundary — data it can only get
by a human clicking "Download" on an internal page. That is not an
inconvenience; it is a tooling gap. The course's rule: if the agent cannot
reach something, give it a tool — an API, a CLI, a browser, a database
connection.

**Why it matters.** Every boundary the agent cannot cross puts a human back in
the loop for a mechanical step, which is the exact work you were trying to
remove.

**What it looked like here.** Restora's FastAPI service exists for agents, not
humans: `GET /api/v1/incidents/{id}/logs` returns the raw events, `/report`
returns the filtered executive view, `/api/v1/stream` is a server-sent event
feed of database changes, and `/api/v1/webhooks/alerts` lets a monitoring
system open an alert. The workflow changed from *human downloads file → hands
it to agent* to *agent requests logs → continues automatically*.

---

## Concept 8 — MCP: the agent beyond the repository

**What it means.** The Model Context Protocol is a standard way to plug
external systems into the agent as tools: databases, design tools,
observability, ticketing. Through MCP the agent gains eyes, ears and hands on
the operating environment, not just the source tree.

**Why it matters.** Most engineering work involves systems that are not files.
Without MCP the agent can only describe what to do in those systems; with it,
the agent does it.

**What it looked like here.** The entire database was built through Supabase's
MCP server. Fifteen migrations — types, tables, functions, triggers, policies,
seed data, views — were applied from the agent's session without me opening a
SQL editor, then exported verbatim to `supabase/migrations/` so anyone can
reproduce them with `supabase db push`. The same server exposes a security
advisor, and after the row-level security migration the agent ran it and found
that the anonymous role still had `SELECT` granted on every table. The
policies blocked the reads, but the tables were discoverable through GraphQL
introspection. The next migration narrowed the grants to the three status-page
tables. **An agent with a linter is a different thing from an agent with a text
editor.**

MCP also has a ceiling, and it is worth knowing where. Supabase's REST layer
only serves schemas listed in a project setting with no API behind it; a human
had to open the dashboard and add `agentops` to a list. When the signup
confirmation email hit the shared SMTP rate limit, that was a dashboard toggle
too. The agent's job at those moments was to say precisely what was blocked and
why — the SSE stream reported `Invalid schema: agentops` verbatim — and it did.
The human is the tool of last resort, and a good system tells you clearly when
it is your turn.

---

## Concept 9 — Design before code

**What it means.** The naive flow is *PRD → code → repeated UI rework*. The
better flow is *PRD → design → code*: get high-fidelity screens in front of a
human first, then hand the agent the PRD plus the designs plus the architecture
rules plus the project conventions. That is far richer context than "build me
a dashboard."

**Why it matters.** UI is where vague prompts produce the most expensive
churn, because every reviewer has an opinion and none of them were in the
prompt.

**What it looked like here.** Rather than invent a UI I gave the agent five
hundred screenshots of a real incident product and asked it to build to that.
It sampled the images, pulled the exact accent colour and chrome greys out of
the pixels, and rebuilt the structure — sidebar, lifecycle breadcrumb, metadata
rail, timeline — with our own name and copy. When I asked it to compare with
the company's live site, it discovered they had rebranded, read the computed
styles off the live page and rebuilt again. It also noted, unprompted, that
copying a competitor's slogan or logo would be passing off their brand; we
kept the structure and wrote everything else ourselves. The product name went
through the same tooling: my first choice turned out to be a well-known
platform with every registry taken, and the agent checked them the way it
checks anything else.

---

## Concept 10 — Agentic validation

**What it means.** Traditional AI coding is *AI generates → human checks
everything*. Agentic validation is *AI generates → runs the application → opens
a browser → walks the workflow → captures evidence → detects the issue → fixes
it → re-validates*. The agent observes the consequences of its own work, which
turns generation into a feedback loop.

**Why it matters.** This is the progression that changes the economics. Code
the agent has verified in a running system is code a human can review rather
than re-test.

**What it looked like here.** The agent walked the eval checklist in a browser
and found things no unit test would: a table that squeezed to unreadable at
800 pixels instead of scrolling, severity badges stretched to fill their grid
cell, timestamps wrapping onto two lines. Three lines of CSS each. Then it
discovered that the browser pane it was using throttles animation frames to
one per second when unfocused, so every motion on the marketing page looked
broken in its screenshots while being fine in mine. It measured that, reported
it, and stopped claiming to have verified what it could not see. **Validation
that knows its own limits is worth more than validation that reports green.**

The backend tests run with no credentials on purpose: they assert what the
service does when Supabase is *not* configured — the webhook returns 503
naming the missing variable, the stream emits one error and closes — because
that is the state every fresh clone and every CI run starts in.

---

## Concept 11 — Objective evals

**What it means.** Some validation is objective (a unit test has an answer);
some is subjective (visual quality). Evals make the subjective measurable by
writing down explicit criteria in advance, so the question changes from *does
this look okay?* to *did the implementation satisfy the defined checks?*

**Why it matters.** Without a written checklist, "validated" means whatever the
agent happened to look at.

**What it looked like here.** `evals/dashboard-eval.md` is organised into Auth,
Navigation, Home, Incidents, Incident detail, Writes, Visual and Quality:
filters return the right counts, the executive summary shows only the allowed
severities, a change in one tab appears in another without a reload, nothing
clips at desktop width, mobile is usable, no console errors, no failed
requests. `skills/validate-dashboard/SKILL.md` tells the agent to start the
servers, execute every check section by section, capture evidence into
`screenshots/`, fix the smallest relevant thing when a check fails, and
produce a report. The checklist grew a *Writes* section when the app gained
writes, which is the point: the eval is a living contract, not a one-time QA
pass.

---

## Concept 12 — Parallel development: subagents and agent teams

**What it means.** Once one agent works reliably, the next lever is scale.
Claude Code offers *subagents* (one-off helpers spawned for a bounded task,
with their own context window) and *agent teams* (several long-running agents
sharing context and coordinating on interdependent work). The picture the
course draws is an orchestrator over a backend agent, a frontend agent and a
QA agent, all reading the same shared context.

**Why it matters.** Backend, frontend, tests and documentation are separable
work streams; running them in parallel is where "AI pair programming" becomes
something closer to AI team orchestration.

**What it looked like here.** Honestly: I ran one agent, not a team. The build
was sequential, one session at a time, with me beside it. I would rather say
that than draw the diagram. The repository is *shaped* for it — `CLAUDE.md`,
the docs and the evals are the shared context a team would need — but the
sessions on worktrees and parallel development are the part of the framework
I have not exercised.

---

## Concept 13 — Worktrees for isolation

**What it means.** Parallel agents need separation. A git worktree gives each
agent its own checkout of its own branch inside the same repository, so a
backend agent and a frontend agent cannot overwrite each other's files, and a
human or an orchestrator merges validated work.

**Why it matters.** Parallelism without isolation creates chaos. This is where
ordinary software-engineering discipline becomes *more* important with agents,
not less.

**What it looked like here.** Not exercised, for the same reason as Concept 12.
Everything landed on `main` through a single sequence of commits with CI
running on each push. That was the right choice for one agent; it would be the
wrong one for three.

---

## Concept 14 — Human attention is the bottleneck

**What it means.** With one agent, watching it is easy. With several, the
human's attention becomes the scarce resource, so the system should interrupt
only when it matters: the agent finished, failed, needs approval, found an
ambiguity, found a security risk, or cannot pass validation. The engineer's
role shifts from typing to orchestrating, reviewing, architecting and deciding.

**Why it matters.** If every agent demands the same attention as a pair
programmer, running five of them buys you nothing.

**What it looked like here.** Even with one agent, the moments that needed me
were exactly the ones on that list: a dashboard setting with no API, a rate
limit, a cost decision (reuse an existing Supabase project with its own schema
rather than pay for a new one), a design direction ("green, not orange"; "add
orange back"), a product name, a logo I rejected. Everything else — the
migrations, the tests, the CSS fixes, the videos — I reviewed after the fact.
Less time watching terminals, more time on judgement, which is what the course
promised.

---

## Concept 15 — Compound engineering

**What it means.** Every solved problem should make the next one easier. The
chain is *problem → learning → rule → skill → tool → automation → reusable
capability*. The output of engineering work is no longer just code; it is also
rules, skills, tools, evaluation criteria and architectural knowledge, and
those compound.

**Why it matters.** This is the difference between an organisation that gets
faster with agents and one that just gets busier.

**What it looked like here.** The evidence bug from Concept 3 is the cleanest
example. A bug became a rule in `docs/INCIDENT_RULES.md`. The rule became a
convention in `CLAUDE.md` — *never re-filter severity in the UI; render the
report endpoint*. The convention became a test, a checkbox in the eval, and
finally a SQL function that both clients call. It grew company: a trigger on
the incidents table writes a timeline entry whenever status or severity
changes, so no client can forget; multi-step writes — declare an incident, post
an update that moves the status, escalate an alert — became single
transactional functions. The next agent to touch that screen inherits all of
it. The *context discipline* block at the end of `CLAUDE.md` is the loop
written down: verify the rule, put it in `docs/`, update the implementation and
tests, update the skill, and if the rule lives in the database, add a
migration.

---

## The merge: two products, one platform

Near the end I handed the agent a zip of the second codebase and said
"combine with Restora." That is an ambiguous instruction, and what happened
next is the framework working as described.

**It asked before it built (Concept 14).** "Combine" could mean four
materially different things — wire the products together at their existing
seams, merge the repositories into one platform, apply Restora's agentic
scaffolding to the other codebase, or just write about both. The agent read
the second codebase first, laid out the four readings with what each would
cost, recommended one, and waited. I chose the biggest: one repository, one
platform. An agent that had guessed would have spent an hour on the wrong one.

**It found the seam in the code, not in a diagram (Concept 1).** Both products
already lived in the same Supabase project — Restora in its `agentops` schema,
the control plane in `public` — and the control plane's own migration had
deliberately revoked all browser access to its tables. So the obvious shortcut,
reading agent runs straight from the browser the way Restora reads incidents,
would have reversed a decision recorded in an ADR. The agent noticed, said so,
and went the other way: the shell calls the control plane's API with the
session it already has, and the API opens a tenant scope. That respected three
existing ADRs and produced a fourth, ADR-0005, which records why.

**The rule went into the database again (Concepts 3 and 15).** The two
products needed to meet somewhere, and the meeting point is a failed agent run
becoming a Restora alert. The agent wrote that as a trigger on the runs table,
not as application code — because the convention in `CLAUDE.md`, learned from
the evidence bug months earlier, says a rule that must hold for every writer
lives in SQL. The trigger fires whether the run was moved by the control
plane, the runtime, or a hotfix at 2am. Compound engineering is exactly this:
a lesson from one product applied, unprompted, to the next.

**The stubs became real, with the fakes the original authors left
(Concept 5).** The control plane's portal routes were documented stubs
returning 501. The agent implemented them over the existing tenant-scoped
store, reusing the repository's own testing pattern — a recording fake that
proves every read opens a tenant scope first — and added tests for the
approval rules: a member cannot decide, an approver's decision binds to the
artifact digest they saw, and a stale digest is refused rather than silently
re-bound. 128 tests became 171. The one identity decision it had to make —
verifying the shell's Supabase session instead of the planned Entra SSO — it
made, wrote down, and confined to a single method so it could not spread.

**MCP caught a real hole, in the old product (Concept 8).** Running the
security advisor after the merge's migrations surfaced a finding that predated
the merge: every `security definer` RPC in Restora's schema was executable by
the anonymous role, because Postgres grants execute to `PUBLIC` by default.
An unauthenticated caller with the publishable key could declare an incident.
Row-level security inside the functions limited the damage; it did not remove
it. One migration later the grant is explicit — signed-in responders and the
service role, nothing else — and the default for future functions is closed.
I would not have found that by reading the code. The linter did.

**Validation stopped where it should (Concept 10).** The agent proved the
identity path end to end in the browser: signed in as me, the shell's token
reached the control plane, was verified against Supabase Auth, and the request
stopped at "DATABASE_URL is not set" — because the agent did not have the
database password and I did. It reported that as the exact boundary of what it
had verified, then checked the hardened RPC grant the same way, as two live
calls: anonymous refused, signed in served. What it could not test, it named.

**And the portal was retired, not kept (Concept 5 again).** The second product
had a Next.js front door with stubbed data. Keeping it alongside the Restora
shell would have been two shells sharing a login — the duplicated chrome was
the cost, not the sign-in. Its Linear-derived patterns carried over as
design notes; the code did not. An agentic codebase has one way to do a thing.

None of this was a new capability. It was the same fifteen concepts, applied
to a second codebase by an agent that had the first one's context — and the
context is what made the second one fast.

## The five pillars

Everything above collapses into five things the environment around the model
has to provide:

1. **Context engineering** — the right knowledge at the right time; not the
   most context, the right context. (Concepts 1–4)
2. **Agentic validation** — objective ways for the agent to know whether its
   work succeeded: tests, browser automation, screenshots, logs, evals.
   (Concepts 10–11)
3. **Agentic tooling** — interfaces to the systems it needs: APIs, CLIs, MCP,
   browsers, databases. (Concepts 7–8)
4. **Agentic codebase** — a repository that is easy for agents to understand:
   fewer competing patterns and dead code, more explicit contracts, tests and
   documentation. (Concepts 5–6)
5. **Compound engineering** — repeated work turned into reusable capability.
   (Concepts 12–15)

---

## The repository, stage by stage

The repository is laid out so a reader can follow the same path:

```
agentops-incident-hub/
├── CLAUDE.md                  durable context for both products (Concept 4)
├── docs/                      PRD, rules, architecture, API contract (Concept 3)
├── backend/                   FastAPI agent API, SSE, webhooks, tests (Concepts 7, 10)
├── frontend/                  one shell: Restora, AI DevOps, the marketing site (Concept 9)
├── aidevops/                  the control plane, execution plane, contracts, ADRs
├── supabase/migrations/       one database, both schemas, applied through MCP (Concept 8)
├── scripts/                   deterministic pipeline and media renderers (Concept 6)
├── skills/                    triage-incident, architecture-review, validate-dashboard
├── evals/                     dashboard-eval, incident-report-eval (Concept 11)
└── sample-data/               offline fixture the API and tests run on
```

The stages, and which ones this build actually went through:

| Stage | What it means | Done here |
|---|---|---|
| 1 Explore | Understand the repository before touching it | Yes |
| 2 Engineer context | Add PRD, rules, architecture docs | Yes |
| 3 Clean the codebase | Remove competing patterns | Yes |
| 4 Deterministic tools | Scripts for repeatable transformations | Yes |
| 5 Create skills | Package repeated workflows | Yes |
| 6 APIs and MCP | Give the agent access to external systems | Yes |
| 7 Design before code | Generate and review UI first | Yes |
| 8 Self-validation | Browser checks, screenshots, evals | Yes |
| 9 Parallel agents | Split backend, frontend, QA, docs | No |
| 10 Worktrees | Isolate concurrent development | No |
| 11 Capture learning | Turn new knowledge into rules and skills | Yes |
| 12 Compound | Make each run improve the next | Yes, on a small scale |

`docs/BUILD_WITH_CLAUDE_CODE.md` walks each stage with the prompts used;
`docs/BUILDING_RESTORA.md` walks the codebase file by file.

---

## The bigger shift

For years the model was *developer + IDE + code*, then *developer + AI
copilot*. The next one looks like an engineer above an orchestrator above a set
of agents — development, testing, security, data, documentation, operations.
The engineer does not disappear; the engineer's leverage changes. The
high-value skills become architecture, specification quality, context
engineering, validation design, tooling, orchestration and judgement. Coding
still matters, but the higher-order skill is designing an environment in
which AI systems produce reliable engineering outcomes.

## What I actually think now

The article I drafted after the course was about how much faster an agent
could write code. The one I can defend after building with it is about
whether the environment around the model is good enough that its output can be
trusted without someone reading every line.

That means context the agent can reach, tools it can call, rules it cannot
silently violate, tests that go red when it does, and a record — in docs, in
skills, in SQL — of what was learned last time. Most of that is ordinary
engineering discipline, which is the slightly deflating conclusion. The
practices that make a codebase good for agents are the ones that make it good
for people, held to more strictly than we usually bother.

Give the model context, so it knows what matters. Tools, so it can act.
Validation, so it can verify. Structure, so agents can collaborate. Memory and
reusable skills, so the organisation improves over time. That is the
difference between using AI in software engineering and redesigning software
engineering around AI — and my repository failed that standard on its first
day, in two places, while I was writing about it. That is where the technology
is: the ideas are right, and the work is still work.

---

**Acknowledgement:** Many of the concepts in this article were inspired by
John Kim's *Build with Claude Code — 2-Day Intensive* (Sep 16–17, 2026),
including context engineering, agentic validation, MCPs, reusable skills, and
multi-agent development. The examples, architecture, and AgentOps Incident Hub
implementation approach in this article are my own interpretation and extension
of those ideas.
