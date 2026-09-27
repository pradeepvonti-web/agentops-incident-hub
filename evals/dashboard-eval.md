# Dashboard Eval

## Auth
- [ ] Signed out, every app route redirects to /login.
- [ ] /status renders signed out, with components and updates.
- [ ] Sign in with a seeded responder's email adopts that profile.
- [ ] The sidebar shows the signed-in responder and Sign out works.

## Navigation
- [ ] Every sidebar item opens its page.
- [ ] Command palette opens with cmd-K or ctrl-K.
- [ ] Command palette finds an incident by title and opens it.
- [ ] Clicking an incident row opens the detail page.

## Home
- [ ] Board shows only Triage, Investigating, Fixing, Monitoring.
- [ ] Column counts match the cards shown.
- [ ] Active and critical metrics agree with the board.

## Incidents
- [ ] Severity filters return only that severity.
- [ ] Status filter and "Active only" work.
- [ ] Search matches title and service.
- [ ] Result count updates with the filters.
- [ ] Clear all filters resets the view.

## Incident detail
- [ ] Lifecycle bar highlights the current status.
- [ ] Updates, Timeline, Actions, Follow-ups and Evidence tabs all render.
- [ ] Executive Summary evidence lists ERROR and CRITICAL entries only.
- [ ] Log timeline lists every event, including WARNING.
- [ ] Metadata rail shows lead, reporter, timestamps and duration metrics.
- [ ] Related incident links navigate.

## Other pages
- [ ] Alerts shows sources, routes and recent alerts linked to incidents.
- [ ] On-call shows who is on call now and the escalation levels.
- [ ] Status page shows components and published updates.
- [ ] Post-incident shows per-incident progress and follow-ups.
- [ ] Insights metrics agree with the incident list.
- [ ] Catalog resolves every incident's service to an owner.

## Writes
- [ ] Declare incident creates an incident and lands on its page.
- [ ] Posting an update appears immediately and can move the status.
- [ ] A status change writes a timeline entry without the client adding one.
- [ ] Adding and ticking an action persists after a reload.
- [ ] Adding a follow-up shows up on the post-incident page.
- [ ] Simulating an alert creates it, and Declare turns it into an incident.
- [ ] Publishing a status update appears on /status.
- [ ] Toggling a workflow and an alert route persists.
- [ ] An on-call override takes precedence over the rotation.
- [ ] A change made in one tab appears in a second tab without reloading.

## Visual
- [ ] No obvious clipping at desktop width.
- [ ] Tables scroll rather than squeezing on narrow viewports.
- [ ] Severity badges are distinct and never stretch.
- [ ] Mobile layout is usable.

## Quality
- [ ] No console errors from the application.
- [ ] No failed API requests.
- [ ] Loading state is visible.
- [ ] Error state exists for API failure.
