import { supabase } from "./supabase";
import type {
  Action,
  AlertRoute,
  AlertRow,
  AlertSource,
  Category,
  ComponentStatus,
  EscalationPath,
  FollowUp,
  IncidentDetail,
  IncidentReport,
  IncidentRow,
  Insights,
  Person,
  Priority,
  Schedule,
  ServiceRow,
  Severity,
  Status,
  StatusPage,
  TeamRow,
  Workflow
} from "../types";
import { ACTIVE_STATUSES, CATEGORIES, LIFECYCLE, SEVERITIES } from "../types";

const PERSON = "id, full_name, email, job_title";

/**
 * Runs a PostgREST query and returns its rows. The schema has no generated
 * types, so the caller names the shape it expects.
 */
async function q<T>(
  builder: PromiseLike<{ data: unknown; error: { message: string } | null }>
): Promise<T> {
  const { data, error } = await builder;
  if (error) throw new Error(error.message);
  return data as T;
}

/* ------------------------------------------------------------------ reads */

export type IncidentQuery = {
  severity?: Severity;
  status?: Status | "active";
  service?: string;
  category?: Category;
  q?: string;
};

export async function listIncidents(query: IncidentQuery = {}): Promise<IncidentRow[]> {
  let builder = supabase.from("incident_list").select("*");

  if (query.severity) builder = builder.eq("severity", query.severity);
  if (query.status === "active") builder = builder.eq("is_active", true);
  else if (query.status) builder = builder.eq("status", query.status);
  if (query.service) builder = builder.eq("service_slug", query.service);
  if (query.category) builder = builder.eq("category", query.category);
  if (query.q) {
    const term = `%${query.q}%`;
    builder = builder.or(
      `reference.ilike.${term},title.ilike.${term},summary.ilike.${term},service_slug.ilike.${term}`
    );
  }

  const rows = await q<IncidentRow[]>(builder);
  const order = Object.fromEntries(SEVERITIES.map((s, i) => [s, i]));
  return rows.sort(
    (a, b) => order[a.severity] - order[b.severity] || a.reference.localeCompare(b.reference)
  );
}

export async function getIncident(reference: string): Promise<IncidentDetail> {
  const row = await q<IncidentRow>(
    supabase.from("incident_list").select("*").eq("reference", reference).single()
  );

  const [core, participants, components, relations, logs, updates, timeline, actions, followUps, tasks] =
    await Promise.all([
      supabase
        .from("incidents")
        .select("probable_cause, suggested_next_action")
        .eq("id", row.id)
        .single(),
      supabase.from("incident_participants").select(`user:users(${PERSON})`).eq("incident_id", row.id),
      supabase
        .from("incident_components")
        .select("component:status_components(id, name)")
        .eq("incident_id", row.id),
      supabase
        .from("incident_relations")
        .select("related:incidents!incident_relations_related_id_fkey(id, reference, title, severity)")
        .eq("incident_id", row.id),
      supabase
        .from("incident_logs")
        .select("id, level, message, occurred_at")
        .eq("incident_id", row.id)
        .order("occurred_at"),
      supabase
        .from("incident_updates")
        .select(`id, status, severity, message, next_update_in_minutes, created_at, author:users(${PERSON})`)
        .eq("incident_id", row.id)
        .order("created_at", { ascending: false }),
      supabase
        .from("incident_timeline")
        .select(`id, kind, title, detail, occurred_at, author:users(${PERSON})`)
        .eq("incident_id", row.id)
        .order("occurred_at"),
      supabase
        .from("actions")
        .select(`id, description, status, owner:users(${PERSON})`)
        .eq("incident_id", row.id)
        .order("created_at"),
      supabase
        .from("follow_ups")
        .select(`id, title, status, priority, due_on, owner:users(${PERSON})`)
        .eq("incident_id", row.id)
        .order("created_at"),
      supabase
        .from("post_incident_tasks")
        .select(`id, title, status, due_on, position, owner:users(${PERSON})`)
        .eq("incident_id", row.id)
        .order("position")
    ]);

  return {
    ...row,
    probable_cause: (core.data as { probable_cause?: string } | null)?.probable_cause ?? "",
    suggested_next_action:
      (core.data as { suggested_next_action?: string } | null)?.suggested_next_action ?? "",
    participants: (participants.data ?? []).map(r => (r as unknown as { user: Person }).user).filter(Boolean),
    components: (components.data ?? [])
      .map(r => (r as unknown as { component: { id: string; name: string } }).component)
      .filter(Boolean),
    related: (relations.data ?? [])
      .map(r => (r as unknown as { related: IncidentDetail["related"][number] }).related)
      .filter(Boolean),
    logs: (logs.data ?? []) as unknown as IncidentDetail["logs"],
    updates: (updates.data ?? []) as unknown as IncidentDetail["updates"],
    timeline: (timeline.data ?? []) as unknown as IncidentDetail["timeline"],
    actions: (actions.data ?? []) as unknown as Action[],
    follow_ups: (followUps.data ?? []) as unknown as FollowUp[],
    post_incident_tasks: (tasks.data ?? []) as unknown as IncidentDetail["post_incident_tasks"]
  };
}

/** The deterministic report. The ERROR/CRITICAL rule lives in SQL, not here. */
export async function getReport(incidentId: string): Promise<IncidentReport> {
  return q<IncidentReport>(supabase.rpc("incident_report", { p_incident: incidentId }));
}

export async function getBoard() {
  const rows = await listIncidents({ status: "active" });
  return {
    columns: ACTIVE_STATUSES.map(status => ({
      status,
      incidents: rows.filter(r => r.status === status)
    })),
    active_count: rows.length,
    critical_count: rows.filter(r => r.severity === "CRITICAL").length
  };
}

export async function getInsights(): Promise<Insights> {
  const [totals, rows] = await Promise.all([
    supabase.from("insight_totals").select("*").single(),
    listIncidents()
  ]);
  const t = (totals.data ?? {}) as Record<string, number | null>;

  const tally = (key: (r: IncidentRow) => string, universe?: string[]) => {
    const counts = new Map<string, number>();
    for (const name of universe ?? []) counts.set(name, 0);
    for (const row of rows) counts.set(key(row), (counts.get(key(row)) ?? 0) + 1);
    return [...counts].map(([name, count]) => ({ name, count }));
  };

  return {
    total_incidents: Number(t.total_incidents ?? 0),
    active_incidents: Number(t.active_incidents ?? 0),
    active_critical: Number(t.active_critical ?? 0),
    mean_minutes_to_declare:
      t.mean_minutes_to_declare === null ? null : Number(t.mean_minutes_to_declare),
    mean_minutes_to_fix: t.mean_minutes_to_fix === null ? null : Number(t.mean_minutes_to_fix),
    open_follow_ups: Number(t.open_follow_ups ?? 0),
    open_tasks: Number(t.open_tasks ?? 0),
    by_severity: tally(r => r.severity, SEVERITIES),
    by_status: tally(r => r.status, LIFECYCLE),
    by_category: tally(r => r.category, CATEGORIES),
    by_service: tally(r => r.service_slug ?? "unassigned")
  };
}

export async function getPostIncident() {
  const [tasks, followUps] = await Promise.all([
    supabase
      .from("post_incident_tasks")
      .select(
        `id, title, status, due_on, position, owner:users(${PERSON}), incident:incidents(id, reference, title, severity, status, lead:users!incidents_lead_id_fkey(${PERSON}))`
      )
      .order("position"),
    supabase
      .from("follow_ups")
      .select(
        `id, title, status, priority, due_on, owner:users(${PERSON}), incident:incidents(id, reference, title)`
      )
      .order("due_on", { nullsFirst: false })
  ]);

  type TaskRow = {
    id: string;
    title: string;
    status: "Open" | "Done";
    due_on: string | null;
    position: number;
    owner: Person | null;
    incident: {
      id: string;
      reference: string;
      title: string;
      severity: Severity;
      status: Status;
      lead: Person | null;
    };
  };

  const rows = (tasks.data ?? []) as unknown as TaskRow[];
  const byIncident = new Map<string, { incident: TaskRow["incident"]; tasks: TaskRow[] }>();
  for (const row of rows) {
    if (!row.incident) continue;
    const entry = byIncident.get(row.incident.id) ?? { incident: row.incident, tasks: [] };
    entry.tasks.push(row);
    byIncident.set(row.incident.id, entry);
  }

  return {
    incidents: [...byIncident.values()],
    follow_ups: (followUps.data ?? []) as unknown as (FollowUp & {
      incident: { id: string; reference: string; title: string };
    })[],
    outstanding_tasks: rows.filter(r => r.status === "Open").length
  };
}

export async function getCatalog(): Promise<{ services: ServiceRow[]; teams: TeamRow[] }> {
  const [services, teams, openIncidents] = await Promise.all([
    supabase
      .from("services")
      .select(
        `id, slug, name, tier, team:teams(id, name), owner:users(${PERSON}), escalation_path:escalation_paths(id, name)`
      )
      .order("slug"),
    supabase
      .from("teams")
      .select(`id, slug, name, slack_channel, members:team_members(user:users(${PERSON}))`)
      .order("name"),
    supabase.from("incident_list").select("service_slug, is_active").eq("is_active", true)
  ]);

  const open = new Map<string, number>();
  for (const row of (openIncidents.data ?? []) as { service_slug: string | null }[]) {
    if (row.service_slug) open.set(row.service_slug, (open.get(row.service_slug) ?? 0) + 1);
  }

  const serviceRows = ((services.data ?? []) as unknown as Omit<ServiceRow, "open_incidents">[]).map(
    s => ({ ...s, open_incidents: open.get(s.slug) ?? 0 })
  );

  const teamRows = ((teams.data ?? []) as unknown as {
    id: string;
    slug: string;
    name: string;
    slack_channel: string | null;
    members: { user: Person }[];
  }[]).map(t => ({
    ...t,
    members: t.members.map(m => m.user).filter(Boolean),
    services: serviceRows.filter(s => s.team?.id === t.id).map(s => s.slug)
  }));

  return { services: serviceRows, teams: teamRows };
}

export async function getAlerts(): Promise<{
  sources: AlertSource[];
  routes: AlertRoute[];
  recent: AlertRow[];
}> {
  const [sources, routes, recent] = await Promise.all([
    supabase.from("alert_sources").select("*").order("slug"),
    supabase
      .from("alert_routes")
      .select(
        "id, name, condition, priority, active, source:alert_sources(id, name), escalation_path:escalation_paths(id, name)"
      )
      .order("name"),
    supabase
      .from("alerts")
      .select(
        `id, reference, title, priority, status, received_at, acknowledged_at, source:alert_sources(id, name), acknowledged_by:users(${PERSON}), incident:incidents(id, reference)`
      )
      .order("received_at", { ascending: false })
      .limit(50)
  ]);

  const alerts = (recent.data ?? []) as unknown as AlertRow[];
  const dayAgo = Date.now() - 24 * 60 * 60 * 1000;

  return {
    sources: ((sources.data ?? []) as unknown as Omit<AlertSource, "alerts_24h">[]).map(s => ({
      ...s,
      alerts_24h: alerts.filter(
        a => a.source?.id === s.id && new Date(a.received_at).getTime() > dayAgo
      ).length
    })),
    routes: (routes.data ?? []) as unknown as AlertRoute[],
    recent: alerts
  };
}

/**
 * Alerts the database raised for one AI DevOps run. The bridge trigger stores
 * the run id in the alert payload, so this is a payload filter, not a join --
 * the control plane's tables are not readable from the browser (ADR-0005).
 */
export async function getAlertsForRun(runId: string): Promise<AlertRow[]> {
  const rows = await supabase
    .from("alerts")
    .select(
      `id, reference, title, priority, status, received_at, acknowledged_at, source:alert_sources(id, name), acknowledged_by:users(${PERSON}), incident:incidents(id, reference)`
    )
    .eq("payload->>run_id", runId)
    .order("received_at", { ascending: false });
  return (rows.data ?? []) as unknown as AlertRow[];
}

export async function getOnCall(): Promise<{
  schedules: Schedule[];
  escalation_paths: EscalationPath[];
}> {
  const [schedules, paths] = await Promise.all([
    supabase
      .from("schedules")
      .select(
        `id, slug, name, timezone, rotation, shifts(id, starts_at, ends_at, is_override, user:users(${PERSON}))`
      )
      .order("name"),
    supabase
      .from("escalation_paths")
      .select("id, slug, name, levels:escalation_levels(id, level, notify, after_minutes, method)")
      .order("name")
  ]);

  const rows = (schedules.data ?? []) as unknown as Schedule[];
  for (const s of rows) {
    s.shifts = [...(s.shifts ?? [])].sort((a, b) => a.starts_at.localeCompare(b.starts_at));
  }
  for (const p of (paths.data ?? []) as unknown as EscalationPath[]) {
    p.levels = [...(p.levels ?? [])].sort((a, b) => a.level - b.level);
  }

  return { schedules: rows, escalation_paths: (paths.data ?? []) as unknown as EscalationPath[] };
}

export async function getWorkflows(): Promise<Workflow[]> {
  return q<Workflow[]>(supabase.from("workflows").select("*").order("created_at"));
}

export async function getStatusPage(): Promise<StatusPage> {
  const [page, components, updates] = await Promise.all([
    supabase.from("status_page").select("*").single(),
    supabase.from("status_components").select("*").order("position"),
    // status_feed is the projection anonymous readers are allowed to see.
    supabase
      .from("status_feed")
      .select("id, status, message, published_at, incident_reference, author_name")
      .order("published_at", { ascending: false })
      .limit(20)
  ]);

  const p = (page.data ?? {}) as { name?: string; url?: string; overall?: string };
  return {
    name: p.name ?? "Status",
    url: p.url ?? "",
    overall: p.overall ?? "All systems operational",
    components: (components.data ?? []) as unknown as StatusPage["components"],
    updates: (updates.data ?? []) as unknown as StatusPage["updates"]
  };
}

export async function listPeople(): Promise<Person[]> {
  return q<Person[]>(supabase.from("users").select(PERSON).order("full_name"));
}

export async function listServiceOptions() {
  return q<{ id: string; slug: string; name: string }[]>(
    supabase.from("services").select("id, slug, name").order("name")
  );
}

/* ----------------------------------------------------------------- writes */

export async function declareIncident(input: {
  title: string;
  severity: Severity;
  category: Category;
  serviceId?: string | null;
  summary?: string;
  status?: Status;
}): Promise<IncidentRow> {
  return q<IncidentRow>(
    supabase.rpc("declare_incident", {
      p_title: input.title,
      p_severity: input.severity,
      p_category: input.category,
      p_service_id: input.serviceId ?? null,
      p_summary: input.summary ?? "",
      p_status: input.status ?? "Triage"
    })
  );
}

export async function postUpdate(input: {
  incidentId: string;
  message: string;
  status?: Status | null;
  severity?: Severity | null;
  nextUpdateInMinutes?: number | null;
}) {
  await q<unknown>(
    supabase.rpc("post_update", {
      p_incident: input.incidentId,
      p_message: input.message,
      p_status: input.status ?? null,
      p_severity: input.severity ?? null,
      p_next_update_in_minutes: input.nextUpdateInMinutes ?? null
    })
  );
}

export async function updateIncident(
  incidentId: string,
  patch: Partial<{
    title: string;
    summary: string;
    severity: Severity;
    category: Category;
    status: Status;
    lead_id: string | null;
    service_id: string | null;
    probable_cause: string;
    suggested_next_action: string;
  }>
) {
  const { error } = await supabase.from("incidents").update(patch).eq("id", incidentId);
  if (error) throw new Error(error.message);
}

export async function addAction(incidentId: string, description: string, ownerId: string | null) {
  const { error } = await supabase
    .from("actions")
    .insert({ incident_id: incidentId, description, owner_id: ownerId });
  if (error) throw new Error(error.message);
}

export async function setTaskStatus(
  table: "actions" | "follow_ups" | "post_incident_tasks",
  id: string,
  status: "Open" | "Done"
) {
  const { error } = await supabase.from(table).update({ status }).eq("id", id);
  if (error) throw new Error(error.message);
}

export async function deleteRow(
  table: "actions" | "follow_ups" | "post_incident_tasks" | "incident_relations",
  id: string
) {
  const { error } = await supabase.from(table).delete().eq("id", id);
  if (error) throw new Error(error.message);
}

export async function addFollowUp(input: {
  incidentId: string;
  title: string;
  ownerId: string | null;
  priority: Priority;
  dueOn: string | null;
}) {
  const { error } = await supabase.from("follow_ups").insert({
    incident_id: input.incidentId,
    title: input.title,
    owner_id: input.ownerId,
    priority: input.priority,
    due_on: input.dueOn
  });
  if (error) throw new Error(error.message);
}

export async function startPostIncidentFlow(incidentId: string, ownerId: string | null) {
  const titles = [
    "Review the incident timeline",
    "Create the post-mortem",
    "Schedule the debrief",
    "Share the post-mortem",
    "Review follow-ups"
  ];
  const { error } = await supabase.from("post_incident_tasks").insert(
    titles.map((title, i) => ({
      incident_id: incidentId,
      title,
      owner_id: ownerId,
      position: i + 1
    }))
  );
  if (error) throw new Error(error.message);
}

export async function addParticipant(incidentId: string, userId: string) {
  const { error } = await supabase
    .from("incident_participants")
    .insert({ incident_id: incidentId, user_id: userId });
  if (error && !error.message.includes("duplicate")) throw new Error(error.message);
}

export async function acknowledgeAlert(alertId: string, userId: string) {
  const { error } = await supabase
    .from("alerts")
    .update({ acknowledged_by: userId, acknowledged_at: new Date().toISOString() })
    .eq("id", alertId);
  if (error) throw new Error(error.message);
}

export async function resolveAlert(alertId: string) {
  const { error } = await supabase.from("alerts").update({ status: "Resolved" }).eq("id", alertId);
  if (error) throw new Error(error.message);
}

export async function escalateAlert(alertId: string, severity: Severity, category: Category) {
  return q<IncidentRow>(
    supabase.rpc("escalate_alert", {
      p_alert: alertId,
      p_severity: severity,
      p_category: category
    })
  );
}

/** Simulates an inbound alert the way a monitoring webhook would deliver one. */
export async function createAlert(input: {
  title: string;
  sourceId: string;
  priority: "Low" | "Medium" | "High" | "Urgent";
}) {
  const { error } = await supabase.from("alerts").insert({
    title: input.title,
    source_id: input.sourceId,
    priority: input.priority,
    payload: { simulated: true, received_from: "console" }
  });
  if (error) throw new Error(error.message);
}

export async function setRouteActive(routeId: string, active: boolean) {
  const { error } = await supabase.from("alert_routes").update({ active }).eq("id", routeId);
  if (error) throw new Error(error.message);
}

export async function setWorkflowEnabled(workflowId: string, enabled: boolean) {
  const { error } = await supabase.from("workflows").update({ enabled }).eq("id", workflowId);
  if (error) throw new Error(error.message);
}

export async function runWorkflow(workflowId: string, outcome: string) {
  const { error } = await supabase
    .from("workflow_runs")
    .insert({ workflow_id: workflowId, outcome });
  if (error) throw new Error(error.message);
  const { error: bump } = await supabase.rpc("bump_workflow_runs", { p_workflow: workflowId });
  if (bump) throw new Error(bump.message);
}

export async function publishStatusUpdate(input: {
  incidentId: string | null;
  status: Status;
  message: string;
  authorId: string | null;
}) {
  const { error } = await supabase.from("status_updates").insert({
    incident_id: input.incidentId,
    status: input.status,
    message: input.message,
    author_id: input.authorId
  });
  if (error) throw new Error(error.message);
}

export async function setComponentStatus(componentId: string, status: ComponentStatus) {
  const { error } = await supabase
    .from("status_components")
    .update({ status })
    .eq("id", componentId);
  if (error) throw new Error(error.message);
}

export async function setOverallStatus(overall: string) {
  const { error } = await supabase.from("status_page").update({ overall }).eq("id", true);
  if (error) throw new Error(error.message);
}

export async function addShiftOverride(input: {
  scheduleId: string;
  userId: string;
  startsAt: string;
  endsAt: string;
}) {
  const { error } = await supabase.from("shifts").insert({
    schedule_id: input.scheduleId,
    user_id: input.userId,
    starts_at: input.startsAt,
    ends_at: input.endsAt,
    is_override: true
  });
  if (error) throw new Error(error.message);
}

export async function updateService(
  serviceId: string,
  patch: Partial<{ tier: string; owner_id: string | null; team_id: string | null }>
) {
  const { error } = await supabase.from("services").update(patch).eq("id", serviceId);
  if (error) throw new Error(error.message);
}
