# PRD — Restora

## Problem
Incident response involves manually gathering logs, categorizing errors,
summarizing impact, chasing follow-ups and preparing updates for other people.

## Goal
An incident platform that a team could actually work an incident in, built so
that agents can read the rules, call the tools and check their own work.

## User stories
- Responders see what is active right now, grouped by lifecycle status.
- Responders filter and search the full incident history.
- Responders read an incident's updates, timeline, actions and follow-ups.
- Leads see who is on call and which escalation path an alert would take.
- Leaders read a summary containing only ERROR and CRITICAL evidence.
- Customers see component status and published updates.
- Teams close incidents out through a post-incident checklist.
- Agents retrieve any of the above through `/api/v1`.

## Required views
1. Home — active incident board and headline metrics
2. Incidents — filterable list
3. Incident detail — updates, timeline, actions, follow-ups, evidence, metadata
4. Alerts — sources, routes, recent alerts
5. On-call — schedules, shifts, escalation paths
6. Status page — components and customer updates
7. Post-incident — flow checklists and follow-ups
8. Insights — volume and duration metrics
9. Catalog — services and teams
10. Workflows — automation rules

## Acceptance criteria
- The board shows only Triage, Investigating, Fixing and Monitoring.
- Severity and status filters combine, and the result count updates.
- Incident detail shows probable cause, next action and the full log timeline.
- Executive evidence contains ERROR and CRITICAL entries only.
- Every incident's service resolves to a catalog entry with an owner.
- Command palette (cmd-K) reaches every page and every incident.
- Raw logs and every view are available through the API.
