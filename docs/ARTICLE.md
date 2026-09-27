# From AI Coding Assistant to Agentic Engineering

*What actually happened when I stopped describing the example and built it.*

In September I sat through John Kim's two-day *Build with Claude Code*
intensive, and for about a week afterwards I had a tidy article drafted. It had
numbered sections. It had a diagram with an orchestrator at the top and six
agents underneath. It explained context engineering, agentic validation, MCPs,
skills and compound engineering in the order the course had explained them,
with an example application I had invented to hang the ideas on.

Then I did the thing the course kept telling me to do, which was to stop
theorising and put the agent to work on a real repository. This is the article
that came out the other side. It is less symmetrical and more useful, because
almost every lesson below is attached to something that went wrong.

## The example

The application is called Restora now. It started as *AgentOps Incident Hub*,
which is still the name of the repository, and it is an incident management
platform: on-call schedules, alert routing, an incident workspace with a
timeline and actions, a status page customers can read, a post-incident flow,
insights. If you have used incident.io or PagerDuty you know the shape.

I picked incident response on purpose. It is the kind of work most engineering
teams do badly: repetitive enough to automate, judgement-heavy enough that you
cannot script it end to end, and full of rules that live in people's heads
rather than in the code. That is exactly the terrain the course was describing.

What exists today is a working product, not a slide. A Postgres schema with 26
tables and row-level security, a React app that reads and writes through
Supabase and updates live across tabs, a FastAPI service for agents, a marketing
site, 26 backend tests, and about 7,000 lines of frontend code. All of it was
built with Claude Code driving and me steering, over a handful of sessions.

## First, I asked it to look, not build

The course's opening lesson is deceptively plain: before you ask an agent to
change anything, ask it to understand. So the first prompt I gave against the
repository was not "build the dashboard." It was closer to:

```
Explore this repository. Do not change anything.

Explain the architecture, the entry points, how data moves through
the system, the testing strategy, and the five files I should read
first. For every important claim, show me the file that supports it.
```

The last line is the one that earns its keep. Without it you get a plausible
summary. With it you get a summary you can check, and the first thing the agent
found by checking was that my own continuous integration was red. Both jobs.
The backend tests could not import the app because of a `sys.path` quirk in how
`pytest` resolves packages; the frontend would not compile because
`import.meta.env` had no type declaration. Two one-line fixes, sitting in a
repository whose README told people to run exactly those commands.

I had written a whole section about validation being the most important part
of agentic engineering while my validation was broken. I have left that
sentence in here because it is the most honest thing in the article.

The habit that came out of it: when the agent tells me something like
"categorisation happens in the service layer," I reply with *show me where*.
Confidence and correctness are different variables. In this codebase the claim
was half true — keyword categorisation lives in a script, the category on each
incident is stored data — and an agent that skips the distinction will happily
add a sixth category nothing downstream understands.

## Context is the part that is not in the code

This is the idea from the course that reorganised how I think about a
repository.

The rules that govern this product are not derivable from its source. Someone
decided that incident categories are exactly five values, that executive
summaries contain only ERROR and CRITICAL events while WARNING stays visible to
engineers, that an incident moves through seven lifecycle statuses in order and
never backwards. In a real company those decisions live in a Confluence page and
one person's memory. Here they live in `docs/INCIDENT_RULES.md`, and the
conventions for touching the code live in `CLAUDE.md`, and the agent reads both
on every run without anyone re-explaining them in a prompt.

None of that is new engineering practice. What is new is who consumes it.
Written down, the rules are read by the thing doing the work.

The rule that taught me the most was the evidence rule. It was in the docs. The
backend implemented it correctly, in a function that filtered logs to ERROR and
CRITICAL. And the dashboard never called that function — it fetched every log
and rendered them all under a heading that said "Evidence." Documented,
implemented, and contradicted by the only screen anyone looked at.

The fix was small. The lesson was not: **a rule written in two places is a bug
waiting to happen.** Later, when the database arrived, that rule moved into
SQL, into one function that both clients call:

```sql
where l.incident_id = i.id
  and l.level in ('ERROR', 'CRITICAL')
```

And it grew company. A trigger on the incidents table writes a timeline entry
whenever status or severity changes, so no client can forget to log one. The
multi-step writes — declare an incident, post an update that moves the status,
escalate an alert — became single transactional functions. The convention that
emerged, and that is now in `CLAUDE.md`, is that anything which must hold no
matter who writes belongs in the database, not in a client. That sentence is
the compound-engineering loop the course describes, observed in the wild: a bug
became a rule, the rule became a convention, the convention became a test and a
checkbox in the eval. The next agent to touch that screen inherits all of it.

## Tools, and the one time the tool was me

The course's framing of tooling is that when an agent cannot reach something,
you give it an interface rather than declaring the task impossible. I expected
that lesson to be about the small API endpoint I added so an agent can fetch
raw logs without a human downloading a file. It turned out to be about MCP, and
about the limits of MCP.

The entire database was built through Supabase's MCP server. Fifteen migrations
— types, tables, functions, triggers, policies, seed data, views — applied from
the agent's session without me opening a SQL editor. The same server exposed a
security advisor, and after the row-level security migration the agent ran it
and found that the anonymous role had been granted `SELECT` on every table.
The policies blocked the reads, but the tables were still discoverable through
GraphQL introspection. The grants were narrowed to the three status-page tables
in the next migration. An agent with a linter is a different thing from an agent
with a text editor.

Then it hit two walls no tool could climb. Supabase's REST layer only serves
schemas listed in a project setting, and there is no API for that setting; a
human had to open the dashboard and add `agentops` to a list. And when I signed
up to test the app, the confirmation email hit the shared SMTP rate limit,
because the demo domain does not receive mail — again a dashboard toggle, again
me. The agent's job at those moments was to say precisely what was blocked and
why, and it did: the SSE stream it had built reported `Invalid schema:
agentops` verbatim. The human is the tool of last resort, and a good system
tells you clearly when it is your turn.

## Let the deterministic thing be deterministic

Incident triage follows the same six steps every time, so it is a Python script,
and a skill file tells the agent when to run it and what to check afterwards.
That part matched the course exactly. The surprise was how often the same
principle applied to work I would have called creative.

The landing page has four videos on it and none was filmed. The agent wrote a
script that draws every frame of one incident — declared, investigated, rolled
back, closed, customer notified — with Pillow, and encodes it with ffmpeg.
Change the story, re-run the script, new video. When I wanted a logo tile as a
PNG, the agent tried to draw the arc with Pillow twice, produced a notch both
times, and switched to a proper SVG rasteriser on the third attempt. The right
move was not a smarter drawing; it was a better tool.

The model orchestrates and interprets. The scripts do the arithmetic. Pushing
arithmetic into a language model buys you variance where you specifically do
not want any.

## Validation, and knowing where it stops

The course demonstrates an agent that runs the application, opens a browser,
walks the workflow, sees the result and fixes what broke. I was sceptical of how
much of that was demo. It is real, with a caveat I only found by doing it.

The eval file in the repository is a checklist: filters return the right counts,
the executive summary shows only the allowed severities, a change in one tab
appears in another without a reload, nothing clips at desktop width, mobile is
usable. The agent walked that list in a browser and found things no unit test
would: a table that squeezed to unreadable at 800 pixels instead of scrolling,
severity badges stretched to fill their grid cell, timestamps wrapping onto two
lines. Three lines of CSS each. Then it found that the browser pane it was
using throttles animation frames to one per second when unfocused — so every
motion on the marketing page looked broken in its screenshots while being fine
in mine. It measured that, reported it, and stopped claiming to have verified
what it could not see.

That last part is the whole point. Validation that knows its own limits is
worth more than validation that reports green.

The backend tests, incidentally, run with no credentials on purpose. They
assert what the service does when Supabase is *not* configured — the webhook
returns 503 naming the missing variable, the stream emits one error and closes
— because that is the state every fresh clone and every CI run starts in.

## Design before code, and a target that moved

Rather than invent a UI, I gave the agent five hundred screenshots of a real
incident product from late 2024 and asked it to build to that. It sampled the
images, pulled the exact accent colour and chrome greys out of the pixels, and
rebuilt the structure — sidebar, lifecycle breadcrumb, metadata rail, timeline —
with our own name and copy. Then I asked it to compare against the live site.

The company had rebranded in the meantime. Dark to white, bold sans to a
regular-weight serif, rounded rectangles to pills, a new pitch. The agent read
the computed styles off the live page — heading size, tracking, button padding,
the exact background of the product stage — and rebuilt again to that. It also
noted, unprompted, that chasing another company's current design is a
treadmill, and that copying their slogan or logo would be passing off their
brand. We kept the structure and wrote everything else ourselves.

The name went the same way. My first choice, Restor, turned out to be a
well-known conservation platform with the `.com`, the `.ai`, the GitHub handle
and the npm package all taken. The agent checked the registries the way it
checks anything else, and I picked Restora instead, whose `.io` was free.
Tooling again, applied to a decision I would have made on instinct.

## What I did not do

I ran one agent, not a team. The course's sessions on worktrees and parallel
development are the part of the framework I have not exercised, and I would
rather say that than draw the diagram. Everything in this article is a single
agent with a human beside it, which is enough to learn the shape of the thing.

The product is missing what the reference has and this does not: onboarding,
a settings area, post-mortem documents, saved views. The frontend casts its
database results through a helper instead of generated types, which was the
right trade while the schema was moving and is the wrong one now. All of it is
written down in the repository, because the next agent to open it should not
have to rediscover any of it.

## What I actually think now

The article I drafted after the course was about how much faster an agent
could write code. The one I can defend after building with it is about
something else: whether the environment around the model is good enough that
its output can be trusted without someone reading every line.

That means context the agent can reach, tools it can call, rules it cannot
silently violate, tests that go red when it does, and a record — in docs, in
skills, in SQL — of what was learned the last time. Most of that is ordinary
engineering discipline, which is the slightly deflating conclusion. The
practices that make a codebase good for agents are the ones that make it good
for people, held to more strictly than we usually bother.

My repository failed that standard on the first day, in two places, while I was
writing about it. That is where the technology is: the ideas are right, and the
work is still work.

The repository is public at https://github.com/pradeepvonti-web/agentops-incident-hub. The companion
piece, `docs/BUILDING_RESTORA.md`, walks the codebase file by file.

---

**Acknowledgement:** Many of the concepts in this article were inspired by
John Kim's *Build with Claude Code — 2-Day Intensive* (Sep 16–17, 2026),
including context engineering, agentic validation, MCPs, reusable skills, and
multi-agent development. The examples, architecture, and AgentOps Incident Hub
implementation approach in this article are my own interpretation and extension
of those ideas.
