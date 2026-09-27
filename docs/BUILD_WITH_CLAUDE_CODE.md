# Build With Claude Code, step by step

*How Restora was built — every stage, the prompt that started it, what the
agent did, and what to check before moving on.*

The other two articles in this repository explain *why* agentic engineering
matters and *how* the codebase is put together. This one is the recipe. It
follows the twelve stages John Kim's *Build with Claude Code* intensive lays
out, in order, and for each stage it shows what I actually typed into Claude
Code, what came back, and what I verified before trusting it. Where this
project skipped a stage, it says so.

You can follow it against your own repository. The prompts are generic on
purpose; the outputs are specific to this one so you can see what "done" looks
like.

A note on setup: everything here ran in the Claude Code desktop app, with its
built-in browser pane for verification and a Supabase MCP server connected for
the database work. No custom tooling. If you have the CLI instead, the prompts
are identical; only the browser steps change.

---

## Stage 1 — Explore before you build

**The idea.** An agent that starts by changing code is guessing. An agent that
starts by reading and citing is building a model it can be held to.

**The prompt.**

```
Explore this repository. Do not change anything.

Explain the architecture, the entry points, how data moves through the
system, the testing strategy, and the five files I should read first.

For every important claim, show me the file that supports it.
```

**What happened.** The agent read the tree, the README and `CLAUDE.md`, then
every source file, then ran the test suite and the frontend build — because
"the testing strategy" is not a claim it can support without running the tests.
Both were red. The backend could not import its own package under `pytest`'s
default path resolution; the frontend would not compile because
`import.meta.env` had no type declaration. The README told users to run exactly
those commands.

**What to check.** Read the file citations, not the prose. Pick two claims and
open the files yourself. If the agent says the tests pass, ask for the output.

**What we learned.** The most valuable thing an exploration produces is not a
summary — it is the list of places the repository disagrees with its own
documentation.

---

## Stage 2 — Engineer the context

**The idea.** The rules that govern software mostly live outside the code. Put
them where the agent reads them on every run.

**The prompt.**

```
Write the business rules for this product into docs/INCIDENT_RULES.md:
the canonical categories, the severity levels, what may appear in an
executive summary, and the fields every incident report must contain.
Then add the conventions for changing this codebase to CLAUDE.md.
Keep both short enough that you would actually read them.
```

**What happened.** `docs/` gained `PRD.md`, `INCIDENT_RULES.md`,
`ARCHITECTURE.md`, `API_CONTRACT.md` and `REPORT_TEMPLATE.md`. `CLAUDE.md`
gained a conventions section: business logic in the services layer, handlers
stay thin, frontend data access in one module, reuse the shared severity badge,
prefer deterministic scripts for repeatable transformations.

Later stages kept adding to it. The line that matters most arrived in
stage 6: *a rule that must hold no matter who writes belongs in SQL, not in a
client.* It was not written from theory; it was written after a bug.

**What to check.** Give the agent a small task that touches a rule and confirm
it consults the rule rather than re-deriving it. If it invents a sixth
category, the docs are not being read — or are not being read *first*.

---

## Stage 3 — Clean the codebase

**The idea.** Humans tolerate three ways of doing the same thing because they
know which one is current. An agent sees three valid examples.

**The prompt.**

```
Review the repository for competing patterns, duplicate abstractions,
dead code and multiple representations of the same concept. Do not
modify anything. For each issue show the affected files, the competing
approaches, the canonical choice you recommend, and the migration impact.
```

**What happened.** The clearest finding was the evidence rule. It lived in the
docs, was implemented correctly in the backend's report function, and was
contradicted by the frontend, which fetched every log and rendered them under
a heading that said "Evidence." Two sources of truth, one wrong. The fix routed
the UI through the report endpoint and renamed the unfiltered list to "Log
timeline," which is what it was.

Other findings from the same pass: a hardcoded CORS origin, a `.gitignore` that
ignored a directory the README pointed readers at, and a `--root` flag the dev
server accepted in one version and rejected in another.

**What to check.** After the cleanup, ask the agent to state the canonical
pattern for each concept in one sentence. If it cannot, neither can the next
agent.

---

## Stage 4 — Build deterministic tools

**The idea.** Do not spend a language model on arithmetic. Anything with one
correct answer is a script; the agent decides when to run it.

**The prompt.**

```
Incident triage always follows the same steps: fetch the incident, parse
the log events, filter to ERROR and CRITICAL, categorise by keyword,
aggregate by service, render the report from docs/REPORT_TEMPLATE.md.
Write each step as a small Python script under scripts/, plus one
pipeline script that runs them in order and writes to artifacts/.
Every script must produce identical output on identical input.
```

**What happened.** Six scripts. `python scripts/triage_pipeline.py INC-1042`
writes a Markdown report whose evidence section contains only ERROR and
CRITICAL lines — the rule from stage 2, enforced by code that cannot forget it.

The same principle reached further than expected. The landing page's four
videos are drawn frame by frame by `scripts/render_demo_video.py` and
`scripts/render_feature_clips.py` with Pillow and encoded with ffmpeg. The
logo's PNG icons are rasterised from the SVG by resvg. Change the source,
re-run the script, same result every time.

**What to check.** Run a script twice and diff the output. If the diff is not
empty, it is not deterministic, and the agent should not be trusting it.

---

## Stage 5 — Create skills

**The idea.** Do a workflow by hand once. Then write down what you did so the
agent can do it next time without being walked through it.

**The prompt.**

```
Package the triage workflow as skills/triage-incident/SKILL.md: the
parameter it takes, the steps in order, what to validate against
docs/INCIDENT_RULES.md, and what to return. Do the same for an
architecture review and for validating the dashboard against the eval.
```

**What happened.** Three skill files, each under ten lines. The two lines that
matter in the triage skill are the last two: *validate against the rules* and
*do not invent evidence or categories*. Both are corrections I had made by
hand more than once before writing them down.

**What to check.** Invoke the skill on a case it has not seen. The point of a
skill is that the agent's behaviour is now predictable; if you have to
re-explain, the skill is missing a step.

---

## Stage 6 — Add APIs and MCP

**The idea.** When the agent cannot reach something, the answer is an interface,
not a shrug.

**The prompts.** Two, at different times.

```
Expose the raw log events at GET /api/v1/incidents/{id}/logs so an agent
can fetch them without a human downloading a file.
```

```
Move the product onto Supabase. Design the schema, apply it as
migrations through the Supabase MCP server, add row-level security in
the same migrations that create the tables, and put the rules that must
always hold into triggers and SQL functions.
```

**What happened.** The first prompt produced one endpoint. The second produced
the database: fifteen migrations applied through MCP without a SQL editor —
types, tables, `security definer` functions for the multi-step writes, a
trigger that appends a timeline entry on every status change, policies for all
26 tables, seed data, views. Then the agent ran the MCP server's security
advisor and found that the anonymous role held `SELECT` on every table. Policies
blocked the reads, but the tables were still discoverable. A follow-up
migration narrowed the grants to the three public status-page tables.

**Where MCP stopped.** Supabase serves only the schemas listed in a project
setting, and there is no API for that setting. A human opened the dashboard and
added `agentops` to a list. A second wall: the confirmation email at signup hit
the shared SMTP rate limit. Both times the agent's job was to name the blocker
precisely, and it did — the SSE stream it had built reported `Invalid schema:
agentops` word for word.

**What to check.** Ask the agent to show you what an anonymous request can
read. Then ask it to show you what a signed-in one can. If either answer is
"everything," stop.

---

## Stage 7 — Design before code

**The idea.** Give the agent a design to build to, and it stops inventing UI.

**The prompt.**

```
Here is a zip of screenshots of a real incident product. Study them:
navigation, the incident detail layout, the pills and badges, the
colours. Build our product to that structure, with our own name, copy
and branding. Do not reproduce their logo, slogan or text.
```

**What happened.** The agent made contact sheets from 549 screenshots, read the
key screens at full resolution, and pulled the actual palette out of the pixels
— the accent, the chrome greys, the severity colours. It built the sidebar,
lifecycle breadcrumb, metadata rail and timeline to match, with a different
name and different words.

Then a second prompt: *compare against the live site.* The company had
rebranded since the screenshots were taken. The agent read computed styles off
the live page — font, weight, tracking, button padding, the exact background of
the product stage — and rebuilt to the current look. It also said, unprompted,
that copying the slogan would be passing off their brand, and that chasing
another company's palette is a treadmill.

**What to check.** Open the reference and the build side by side at the same
width. Then check the copy: every sentence should be yours.

---

## Stage 8 — Add self-validation

**The idea.** Code that has not been run is a hypothesis. The agent should run
it, look at it, and fix what it sees.

**The prompt.**

```
Walk evals/dashboard-eval.md in the browser. For each check, do it,
record the result, and if it fails fix the smallest thing that makes it
pass and re-run it. Report what you could not verify and why.
```

**What happened.** The agent started the API and the dev server, opened the
browser pane, and worked the list: filters returning the right counts, the
executive summary showing only the allowed severities, the catalog link
filtering the incident list, the command palette finding an incident by title.
It found things no unit test would: a table squeezing to unreadable at 800px,
badges stretching to fill their grid cell, timestamps wrapping. Three CSS
lines each.

It also found a limit of its own. The browser pane throttles animation frames
to one per second when it is not focused, so every GSAP tween and every video
looked frozen in its screenshots. It measured the frame rate, reported it, and
stopped claiming to have verified motion.

The backend side is deliberate too: 26 tests that run with no credentials and
assert what the service does when Supabase is *absent*, because that is the
state every clone and every CI run begins in.

**What to check.** Read the "could not verify" list before the "verified" list.
An agent that never produces the first list is not looking hard enough.

---

## Stage 9 — Introduce parallel agents

**The idea.** Once one agent is reliable, split the work: backend, frontend,
QA, docs, each with its own context, coordinated from above.

**What this project did.** One agent, sequentially. I am not going to draw the
diagram of the thing I did not build.

**The recipe, for when you do.** Give each agent a *narrow* `CLAUDE.md`
addendum naming its area and the files it may touch. Give the QA agent the eval
and nothing else. Have every agent end its turn by writing what it changed and
what it could not verify into a shared `docs/HANDOFF.md`, and have the
orchestrator read that before assigning the next task. The course is explicit
that agent teams differ from throwaway subagents because they share context;
the handoff file is the cheapest way to make that true.

---

## Stage 10 — Use worktrees for isolation

**The idea.** Two agents in one working directory will overwrite each other.
Git worktrees give each a branch and a directory of its own.

**The commands.**

```bash
git worktree add ../restora-backend  -b agent/backend
git worktree add ../restora-frontend -b agent/frontend
git worktree add ../restora-qa       -b agent/qa
```

Point one Claude Code session at each directory. Merge to `main` only what
the QA worktree has walked through the eval. Remove worktrees with
`git worktree remove` when the branch lands.

**What this project did.** Not exercised — see stage 9. The repository is
ready for it: the tests are offline, the build is one command, and `CLAUDE.md`
says what the canonical patterns are, which is what a fresh agent in a fresh
worktree needs first.

---

## Stage 11 — Capture the learning

**The idea.** Every solved problem should leave a rule behind so it is not
solved twice.

**The prompt.** This one is in `CLAUDE.md` itself, under "Context discipline":

```
When a durable new rule is discovered:
1. verify it,
2. write it into the appropriate docs/ file,
3. update implementation/tests,
4. update reusable skills when applicable.
```

**What happened.** The evidence bug from stage 3 became a sentence in
`INCIDENT_RULES.md` naming where the rule is enforced, a convention in
`CLAUDE.md` (*never re-filter severity in the UI*), an assertion in
`test_api.py`, and two checkboxes in the eval. The CI failures from stage 1
became `pytest.ini`, `vite-env.d.ts`, and two lines in the validation section
of `CLAUDE.md`. The anon-grant finding from stage 6 became a line in
`DATABASE.md` and a convention: *run the security advisor after DDL*.

**What to check.** After any fix, ask: where would the next agent learn this?
If the answer is "the git history," it is not captured.

---

## Stage 12 — Compound the system

**The idea.** Knowledge becomes a rule, the rule becomes a skill, the skill
becomes a tool, the tool becomes automation. Each turn of that loop makes the
next incident cheaper.

**What it looked like here.** The triage rule (stage 2) became a script
(stage 4) became a skill (stage 5) became a database function that both the
app and the API call (stage 6) became a test and an eval line (stage 8) became
a convention every future change is held to (stage 11). Nobody re-explained it
at any step. The `validate-dashboard` skill grew a "writes" section when the
app grew a write path — the checklist compounding alongside the code.

**What to check.** Pick a rule and trace it through the repository. If it
appears in exactly one enforcing place and is referenced everywhere else, the
system is compounding. If it appears in three places with three wordings, it
is decaying.

---

## The stages I would reorder

Having done it: put stage 8 second. Validation is not something you add once
the product exists; it is how you find out whether the product you inherited
exists. My CI was red before I wrote a line, and I only knew because the
exploration prompt asked for evidence. Everything after that was faster
because the loop was closed from the start.

The repository is at https://github.com/pradeepvonti-web/agentops-incident-hub.
The companion pieces are `docs/ARTICLE.md` (why) and
`docs/BUILDING_RESTORA.md` (how the code is put together).

---

**Acknowledgement:** Many of the concepts in this article were inspired by
John Kim's *Build with Claude Code — 2-Day Intensive* (Sep 16–17, 2026),
including context engineering, agentic validation, MCPs, reusable skills, and
multi-agent development. The examples, architecture, and AgentOps Incident Hub
implementation approach in this article are my own interpretation and extension
of those ideas.
