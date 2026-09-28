# ADR-0005: One platform — the control plane inside the Restora shell

**Status:** Accepted
**Date:** 2026-09-27
**Deciders:** Founding team
**Supersedes:** — (amends the portal identity assumption in ADR-0002 §2)

## Context

The AI DevOps platform and Restora, an incident management product, were built
as two repositories against the same Supabase project — the control plane in
`public`, Restora in `agentops`. The people who use them are the same people: a
data engineer who approves an agent's pull request at 15:00 is the one paged at
03:00 when the pipeline it deployed fails.

Two front doors for one team is a cost with no benefit. The portal was a Next.js
application with its own shell, its own session and stubbed data fetching;
Restora already had a working shell, a working session, live updates and an
alerting surface. Merging the repositories forces the question this ADR answers:
where do the AI DevOps screens live, who is the user, and how do the two halves
talk.

## Decision

### 1. One shell

The AI DevOps screens are routes in the Restora application
(`frontend/src/pages/devops/`), rendered inside its sidebar as a second section.
The Next.js portal is retired. The Linear-derived patterns it established —
dense run rows grouped by status, status by glyph never by row fill, approvals
first because finished work waiting on a human is the most expensive state —
carry over; the Restora design system supplies the surface.

### 2. One identity for humans: Supabase Auth

The portal's identity was to be Entra SSO (ADR-0002 §2). Inside the Restora
shell the session already exists and it is a Supabase Auth session, so that is
what the control plane receives. It verifies the token by asking Supabase Auth
who it belongs to (`GET /auth/v1/user`) rather than validating signatures
locally: one call per request, no key rotation to track, and a revoked session
stops working on the next request.

The user-to-tenant step is one row in `public.tenant_members`, written by an
admin, never by a request. A user belongs to exactly one tenant, because two
would let a request name the tenant it wants, which ADR-0001 forbids. The
table is deny-all to PostgREST and is read by exactly one method
(`Database.resolve_membership`) — the single query in the codebase that runs
before a tenant scope exists, because it is how the scope is chosen.

Roles are `member`, `approver`, `admin`. Deciding an approval is a grant, not a
default: a member submits runs and watches them.

**Agent identity is unchanged.** Execution-plane callers present an Entra
workload identity (ADR-0002); `require_execution_plane` is the separate
dependency for those routes and remains the documented stub. A Supabase session
can never reach `/v1/agent/*`.

### 3. The control plane's tables stay closed to the browser

The shell does not read `public.runs` through PostgREST. Migration 0003's
revocation stands. Every read goes through the control plane API, which opens a
tenant scope from the session (`begin_tenant_scope`, ADR-0001 Amendment 1).
The shell polls; it does not subscribe. A realtime channel on these tables
would need a browser-readable grant, which is the thing we are not doing.

### 4. The bridge is a trigger

A run entering `failed` or `rolled_back` raises a Restora alert from the row
change itself (`public.raise_alert_for_failed_run`, security definer, empty
search path). It holds no matter which writer moved the run — control plane,
runtime, or a hotfix in SQL — and no client has to remember to do it. Only
metadata crosses: run id, tenant, agent, environment, entry source, title.
Nothing from the payload tier exists on `runs` to leak (ADR-0003).

The alert carries the run id in its payload, so the run detail page can show
what Restora did about it, and a Restora alert can be escalated into an
incident by the ordinary path.

### 5. One migration folder

`supabase/migrations/` at the repository root is the single source for the
whole database, both schemas, in version order, exported verbatim from the
applied history.

## Consequences

- A developer runs one frontend and two APIs (Restora's agent API on 8000, the
  control plane on 8010). The launch configuration starts both.
- `DATABASE_URL` for the control plane is a direct Postgres credential and is
  the one thing a fresh clone must obtain by hand; every portal route answers
  503 and names it until then.
- The dev-only `ADP_DEV_TENANT` fallback places an unmapped user in a tenant as
  an approver so a fresh clone has something to look at. It is ignored outside
  `ADP_ENVIRONMENT=dev`; there an unmapped account is a 403.
- Entra SSO for humans is no longer on the roadmap for the shell. If a customer
  requires it, the path is Supabase Auth's SAML/OIDC provider, not a second
  identity path in the control plane.
- The shell's TypeScript mirror of the six entry points moved to
  `frontend/src/devops/entry.ts`; the contract test that holds it in step with
  Python now points there.

## Alternatives considered

- **Keep the Next.js portal, share a session.** Two shells with one session is
  still two shells; the cost was the duplicated chrome, not the login.
- **Grant `authenticated` SELECT on the control plane's tables with a tenant
  policy keyed on a JWT claim.** Reverses migration 0003 and moves tenant
  resolution into PostgREST, where `begin_tenant_scope` and the non-bypassing
  role do not apply. Rejected: it makes two isolation mechanisms where the
  ADRs argue for one.
- **Raise the alert from the control plane in application code.** Works until
  the one writer that is not the control plane moves a run. The trigger is the
  version that cannot be forgotten.
