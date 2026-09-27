from typing import Literal
from pydantic import BaseModel, Field

Severity = Literal["INFO", "WARNING", "ERROR", "CRITICAL"]
Category = Literal["Availability", "Performance", "Security", "Data", "Integration"]
Status = Literal[
    "Triage",
    "Investigating",
    "Fixing",
    "Monitoring",
    "Documenting",
    "Reviewing",
    "Closed",
]

# Statuses in lifecycle order. Anything before "Closed" is an open incident.
LIFECYCLE: tuple[str, ...] = (
    "Triage",
    "Investigating",
    "Fixing",
    "Monitoring",
    "Documenting",
    "Reviewing",
    "Closed",
)
ACTIVE_STATUSES: tuple[str, ...] = ("Triage", "Investigating", "Fixing", "Monitoring")


class LogEvent(BaseModel):
    timestamp: str
    level: Severity
    message: str


class Timestamps(BaseModel):
    impact_started_at: str | None = None
    declared_at: str | None = None
    identified_at: str | None = None
    fixed_at: str | None = None
    closed_at: str | None = None


class IncidentUpdate(BaseModel):
    timestamp: str
    author: str
    status: Status
    severity: Severity
    message: str
    next_update_in_minutes: int | None = None


class TimelineEntry(BaseModel):
    timestamp: str
    kind: Literal["alert", "declared", "update", "status", "action", "closed"]
    title: str
    detail: str = ""
    author: str = ""


class Action(BaseModel):
    id: str
    description: str
    owner: str
    status: Literal["Open", "Done"]


class FollowUp(BaseModel):
    id: str
    title: str
    owner: str
    status: Literal["Open", "Done"]
    priority: Literal["Low", "Medium", "High"]
    due: str | None = None


class PostIncidentTask(BaseModel):
    id: str
    title: str
    status: Literal["Open", "Done"]
    owner: str
    due: str | None = None


class IncidentSummary(BaseModel):
    id: str
    title: str
    service: str
    severity: Severity
    category: Category
    status: Status
    summary: str = ""
    lead: str = "Unassigned"
    first_occurrence: str
    latest_occurrence: str


class IncidentDetail(IncidentSummary):
    reporter: str = ""
    participants: list[str] = Field(default_factory=list)
    affected_components: list[str] = Field(default_factory=list)
    timestamps: Timestamps = Field(default_factory=Timestamps)
    probable_cause: str
    suggested_next_action: str
    related_incidents: list[str] = Field(default_factory=list)
    logs: list[LogEvent] = Field(default_factory=list)
    updates: list[IncidentUpdate] = Field(default_factory=list)
    timeline: list[TimelineEntry] = Field(default_factory=list)
    actions: list[Action] = Field(default_factory=list)
    follow_ups: list[FollowUp] = Field(default_factory=list)
    post_incident_tasks: list[PostIncidentTask] = Field(default_factory=list)


class IncidentReport(BaseModel):
    incident_id: str
    title: str
    service: str
    severity: Severity
    category: Category
    status: Status
    first_occurrence: str
    latest_occurrence: str
    probable_cause: str
    suggested_next_action: str
    evidence: list[str]


class BoardColumn(BaseModel):
    status: Status
    incidents: list[IncidentSummary]


class Board(BaseModel):
    columns: list[BoardColumn]
    active_count: int
    critical_count: int


class SeverityCount(BaseModel):
    severity: Severity
    count: int


class NamedCount(BaseModel):
    name: str
    count: int


class Insights(BaseModel):
    total_incidents: int
    active_incidents: int
    mean_time_to_acknowledge_minutes: float | None
    mean_time_to_resolve_minutes: float | None
    open_follow_ups: int
    by_severity: list[SeverityCount]
    by_category: list[NamedCount]
    by_service: list[NamedCount]
    by_status: list[NamedCount]


class PostIncidentItem(BaseModel):
    incident_id: str
    title: str
    severity: Severity
    status: Status
    lead: str
    tasks: list[PostIncidentTask]


class FollowUpItem(FollowUp):
    incident_id: str
    incident_title: str


class PostIncidentView(BaseModel):
    incidents: list[PostIncidentItem]
    follow_ups: list[FollowUpItem]
    outstanding_tasks: int
