# Databricks Asset Bundle template — Azure DevOps

The repository layout an agent-authored pull request lands in, and the pipeline
that ships it.

This is two things at once: the scaffold the Data Engineering agent generates
into, and a standalone deliverable. A client not yet using bundles adopts this
first — before any agent touches anything.

## Layout

```
databricks.yml                    root config: variables, targets per environment
resources/<job>.yml               one file per job          ← agent writes
source/<pipeline>.py              transformation code       ← agent writes
tests/                            unit tests                ← agent writes
azure-pipelines.yml               CI/CD                     ← platform team
.azure/steps-deploy.yml           shared deploy steps       ← platform team
```

The split in that last column is the important one.

## What the agent writes, and what it must not

**Writes:** `resources/*.yml`, `source/*.py`, `tests/*.py`

**Never writes:** `databricks.yml` targets, `azure-pipelines.yml`, `.azure/*`

An agent that can edit its own deployment targets can promote its own work to
prod. An agent that can edit the pipeline can remove its own approval gate. Both
are enforced by branch policy — path-scoped required reviewers on those files —
not by asking the agent nicely.

## Flow

| Trigger | What happens |
|---|---|
| Agent opens PR | `bundle validate` against **all three targets** + unit tests. No deploy. |
| Human reviews and merges | Deploy to dev, automatically |
| | Deploy to test — Azure DevOps environment approval |
| | Deploy to prod — Azure DevOps environment approval |

Validation runs against every target on the pull request, not just dev. A bundle
that resolves in dev and fails in prod is exactly the surprise environment parity
exists to prevent, and discovering it at the prod approval gate is discovering it
too late.

## Setup

**1. Azure DevOps Environments** — create `databricks-dev`, `databricks-test`,
`databricks-prod`. Add approvers to test and prod.

Approvals live on the environment, deliberately not in YAML. A pull request that
could edit its own gate is not a gate.

**2. Service connection** — an Azure Resource Manager service connection named
`databricks-deploy`, using **Workload identity federation**, not a secret.

No stored credential, nothing to rotate, nothing to leak. This is the same
position ADR-0002 takes for agent identity, for the same reasons.

**3. Service principals** — one per environment, granted `CAN_MANAGE` on the
bundle's workspace path and the Unity Catalog privileges its jobs need. Fill the
`service_principal_id` variable per target in `databricks.yml`.

Deployed jobs `run_as` the service principal, never the person who merged. That is
what makes the audit trail answer *what* deployed this rather than *who happened
to click merge*.

**4. Branch policies on `main`** — require a pull request, require the Validate
stage to pass, and require a reviewer. Add path-scoped reviewers for
`databricks.yml`, `azure-pipelines.yml` and `.azure/**`.

## Notes

- **Replace every `REPLACE-` placeholder** in `databricks.yml` before first use.
  `bundle validate` will fail loudly until you do, which is intended.
- **Scheduled jobs deploy paused.** A human unpauses after the first successful
  manual run. An agent-authored job that starts running the moment it merges is
  how a bad pipeline runs forty times overnight.
- **Nothing environment-specific belongs in `resources/*.yml`.** It comes from
  `${var.*}`, resolved per target. A hard-coded catalog is the first thing to
  look for when reviewing an agent-authored resource.
- **The agent gets no fast path.** Same pipeline, same gates, same reviewers as a
  human's pull request. That is what makes "an agent opened this" an uninteresting
  fact rather than a security conversation.

## Agent runtime prerequisites

The Data Engineering agent relies on the official **Databricks AI Tools** skills
for bundle authoring conventions — `databricks-dabs` in particular. Install them
into the agent runtime image, pinned:

```bash
databricks aitools install
```

Pinned deliberately. The skills shape what the agent writes, so an unpinned
upgrade can move acceptance rate with no change on our side. Treat a version bump
as a change that needs an evaluation run before it ships. See
[ADR-0004](../../docs/adr/0004-databricks-ai-tools.md).
