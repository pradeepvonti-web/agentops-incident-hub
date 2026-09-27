export type Severity = "INFO" | "WARNING" | "ERROR" | "CRITICAL";

export type Category =
  | "Availability"
  | "Performance"
  | "Security"
  | "Data"
  | "Integration";

export type Status =
  | "Triage"
  | "Investigating"
  | "Fixing"
  | "Monitoring"
  | "Documenting"
  | "Reviewing"
  | "Closed";

export const LIFECYCLE: Status[] = [
  "Triage",
  "Investigating",
  "Fixing",
  "Monitoring",
  "Documenting",
  "Reviewing",
  "Closed"
];

export const ACTIVE_STATUSES: Status[] = [
  "Triage",
  "Investigating",
  "Fixing",
  "Monitoring"
];

export const SEVERITIES: Severity[] = ["CRITICAL", "ERROR", "WARNING", "INFO"];

export const CATEGORIES: Category[] = [
  "Availability",
  "Performance",
  "Security",
  "Data",
  "Integration"
];

export type TaskStatus = "Open" | "Done";
export type Priority = "Low" | "Medium" | "High";
export type AlertPriority = "Low" | "Medium" | "High" | "Urgent";
export type AlertStatus = "Open" | "Escalated" | "Resolved";
export type ComponentStatus =
  | "Operational"
  | "Degraded performance"
  | "Partial outage"
  | "Major outage";

export type Person = {
  id: string;
  full_name: string;
  email: string;
  job_title: string | null;
};

/** One row of `agentops.incident_list`. */
export type IncidentRow = {
  id: string;
  reference: string;
  title: string;
  summary: string;
  severity: Severity;
  category: Category;
  status: Status;
  is_active: boolean;
  service_slug: string | null;
  service_name: string | null;
  team_name: string | null;
  lead_name: string | null;
  lead_id: string | null;
  reporter_name: string | null;
  impact_started_at: string | null;
  declared_at: string;
  identified_at: string | null;
  fixed_at: string | null;
  closed_at: string | null;
  updated_at: string;
  minutes_to_declare: number | null;
  minutes_to_fix: number | null;
  first_occurrence: string | null;
  latest_occurrence: string | null;
  open_follow_ups: number;
  open_tasks: number;
};

export type LogEvent = {
  id: string;
  level: Severity;
  message: string;
  occurred_at: string;
};

export type IncidentUpdate = {
  id: string;
  status: Status;
  severity: Severity;
  message: string;
  next_update_in_minutes: number | null;
  created_at: string;
  author: Person | null;
};

export type TimelineEntry = {
  id: string;
  kind: "alert" | "declared" | "update" | "status" | "severity" | "action" | "note" | "closed";
  title: string;
  detail: string;
  occurred_at: string;
  author: Person | null;
};

export type Action = {
  id: string;
  description: string;
  status: TaskStatus;
  owner: Person | null;
};

export type FollowUp = {
  id: string;
  title: string;
  status: TaskStatus;
  priority: Priority;
  due_on: string | null;
  owner: Person | null;
};

export type PostIncidentTask = {
  id: string;
  title: string;
  status: TaskStatus;
  due_on: string | null;
  position: number;
  owner: Person | null;
};

export type IncidentDetail = IncidentRow & {
  probable_cause: string;
  suggested_next_action: string;
  participants: Person[];
  components: { id: string; name: string }[];
  related: { id: string; reference: string; title: string; severity: Severity }[];
  logs: LogEvent[];
  updates: IncidentUpdate[];
  timeline: TimelineEntry[];
  actions: Action[];
  follow_ups: FollowUp[];
  post_incident_tasks: PostIncidentTask[];
};

export type IncidentReport = {
  incident_id: string;
  title: string;
  service: string;
  severity: Severity;
  category: Category;
  status: Status;
  probable_cause: string;
  suggested_next_action: string;
  first_occurrence: string | null;
  latest_occurrence: string | null;
  evidence: string[];
};

export type Insights = {
  total_incidents: number;
  active_incidents: number;
  active_critical: number;
  mean_minutes_to_declare: number | null;
  mean_minutes_to_fix: number | null;
  open_follow_ups: number;
  open_tasks: number;
  by_severity: { name: string; count: number }[];
  by_category: { name: string; count: number }[];
  by_service: { name: string; count: number }[];
  by_status: { name: string; count: number }[];
};

export type ServiceRow = {
  id: string;
  slug: string;
  name: string;
  tier: string;
  team: { id: string; name: string } | null;
  owner: Person | null;
  escalation_path: { id: string; name: string } | null;
  open_incidents: number;
};

export type TeamRow = {
  id: string;
  slug: string;
  name: string;
  slack_channel: string | null;
  members: Person[];
  services: string[];
};

export type AlertSource = {
  id: string;
  slug: string;
  name: string;
  description: string;
  connected: boolean;
  alerts_24h: number;
};

export type AlertRoute = {
  id: string;
  name: string;
  condition: string;
  priority: AlertPriority;
  active: boolean;
  source: { id: string; name: string } | null;
  escalation_path: { id: string; name: string } | null;
};

export type AlertRow = {
  id: string;
  reference: string;
  title: string;
  priority: AlertPriority;
  status: AlertStatus;
  received_at: string;
  acknowledged_at: string | null;
  source: { id: string; name: string } | null;
  acknowledged_by: Person | null;
  incident: { id: string; reference: string } | null;
};

export type Shift = {
  id: string;
  starts_at: string;
  ends_at: string;
  is_override: boolean;
  user: Person;
};

export type Schedule = {
  id: string;
  slug: string;
  name: string;
  timezone: string;
  rotation: string | null;
  shifts: Shift[];
};

export type EscalationPath = {
  id: string;
  slug: string;
  name: string;
  levels: {
    id: string;
    level: number;
    notify: string;
    after_minutes: number;
    method: string;
  }[];
};

export type Workflow = {
  id: string;
  name: string;
  enabled: boolean;
  trigger: string;
  conditions: string[];
  steps: string[];
  runs_7d: number;
};

export type StatusPage = {
  name: string;
  url: string;
  overall: string;
  components: {
    id: string;
    name: string;
    status: ComponentStatus;
    uptime_90d: number;
    position: number;
  }[];
  updates: {
    id: string;
    status: Status;
    message: string;
    published_at: string;
    incident_reference: string | null;
    author_name: string | null;
  }[];
};
