import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from app.models import (
    ACTIVE_STATUSES,
    LIFECYCLE,
    Board,
    BoardColumn,
    FollowUpItem,
    IncidentDetail,
    IncidentReport,
    IncidentSummary,
    Insights,
    NamedCount,
    PostIncidentItem,
    PostIncidentView,
    SeverityCount,
)

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "sample-data" / "incidents"

SEVERITY_ORDER = {"CRITICAL": 0, "ERROR": 1, "WARNING": 2, "INFO": 3}
EVIDENCE_LEVELS = {"ERROR", "CRITICAL"}


class IncidentNotFoundError(KeyError):
    pass


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _minutes_between(start: str | None, end: str | None) -> float | None:
    a, b = _parse(start), _parse(end)
    if a is None or b is None:
        return None
    return (b - a).total_seconds() / 60


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 1)


class IncidentService:
    """Reads incidents from disk and derives every incident-shaped view."""

    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir

    def _load_path(self, path: Path) -> IncidentDetail:
        return IncidentDetail.model_validate(
            json.loads(path.read_text(encoding="utf-8"))
        )

    def _all(self) -> list[IncidentDetail]:
        return [self._load_path(p) for p in sorted(self.data_dir.glob("*.json"))]

    def _summarize(self, x: IncidentDetail) -> IncidentSummary:
        return IncidentSummary(**x.model_dump(include=set(IncidentSummary.model_fields)))

    def list_incidents(
        self,
        severity: str | None = None,
        status: str | None = None,
        service: str | None = None,
        category: str | None = None,
        q: str | None = None,
    ) -> list[IncidentSummary]:
        items = self._all()
        if severity:
            severity = severity.upper()
            items = [x for x in items if x.severity == severity]
        if status:
            if status.lower() == "active":
                items = [x for x in items if x.status in ACTIVE_STATUSES]
            else:
                items = [x for x in items if x.status.lower() == status.lower()]
        if service:
            items = [x for x in items if x.service.lower() == service.lower()]
        if category:
            items = [x for x in items if x.category.lower() == category.lower()]
        if q:
            needle = q.lower()
            items = [
                x
                for x in items
                if needle in x.id.lower()
                or needle in x.title.lower()
                or needle in x.service.lower()
                or needle in x.summary.lower()
            ]
        items.sort(key=lambda x: (SEVERITY_ORDER[x.severity], x.id))
        return [self._summarize(x) for x in items]

    def get_incident(self, incident_id: str) -> IncidentDetail:
        path = self.data_dir / f"{incident_id}.json"
        if not path.exists():
            raise IncidentNotFoundError(incident_id)
        return self._load_path(path)

    def get_logs(self, incident_id: str):
        return self.get_incident(incident_id).logs

    def build_report(self, incident_id: str) -> IncidentReport:
        x = self.get_incident(incident_id)
        evidence = [
            f"{e.timestamp} [{e.level}] {e.message}"
            for e in x.logs
            if e.level in EVIDENCE_LEVELS
        ]
        return IncidentReport(
            incident_id=x.id,
            title=x.title,
            service=x.service,
            severity=x.severity,
            category=x.category,
            status=x.status,
            first_occurrence=x.first_occurrence,
            latest_occurrence=x.latest_occurrence,
            probable_cause=x.probable_cause,
            suggested_next_action=x.suggested_next_action,
            evidence=evidence,
        )

    def board(self) -> Board:
        items = self._all()
        columns = [
            BoardColumn(
                status=status,
                incidents=sorted(
                    (self._summarize(x) for x in items if x.status == status),
                    key=lambda x: (SEVERITY_ORDER[x.severity], x.id),
                ),
            )
            for status in ACTIVE_STATUSES
        ]
        active = [x for x in items if x.status in ACTIVE_STATUSES]
        return Board(
            columns=columns,
            active_count=len(active),
            critical_count=len([x for x in active if x.severity == "CRITICAL"]),
        )

    def insights(self) -> Insights:
        items = self._all()
        ack, res = [], []
        for x in items:
            a = _minutes_between(x.timestamps.impact_started_at, x.timestamps.declared_at)
            r = _minutes_between(x.timestamps.impact_started_at, x.timestamps.fixed_at)
            if a is not None:
                ack.append(a)
            if r is not None:
                res.append(r)

        def counts(values) -> list[NamedCount]:
            return [
                NamedCount(name=name, count=count)
                for name, count in sorted(Counter(values).items())
            ]

        severity_counts = Counter(x.severity for x in items)
        return Insights(
            total_incidents=len(items),
            active_incidents=len([x for x in items if x.status in ACTIVE_STATUSES]),
            mean_time_to_acknowledge_minutes=_mean(ack),
            mean_time_to_resolve_minutes=_mean(res),
            open_follow_ups=len(
                [f for x in items for f in x.follow_ups if f.status == "Open"]
            ),
            by_severity=[
                SeverityCount(severity=s, count=severity_counts.get(s, 0))
                for s in ("CRITICAL", "ERROR", "WARNING", "INFO")
            ],
            by_category=counts(x.category for x in items),
            by_service=counts(x.service for x in items),
            by_status=[
                NamedCount(name=s, count=len([x for x in items if x.status == s]))
                for s in LIFECYCLE
            ],
        )

    def post_incident(self) -> PostIncidentView:
        items = self._all()
        incidents = [
            PostIncidentItem(
                incident_id=x.id,
                title=x.title,
                severity=x.severity,
                status=x.status,
                lead=x.lead,
                tasks=x.post_incident_tasks,
            )
            for x in items
            if x.post_incident_tasks
        ]
        follow_ups = [
            FollowUpItem(
                **f.model_dump(), incident_id=x.id, incident_title=x.title
            )
            for x in items
            for f in x.follow_ups
        ]
        follow_ups.sort(key=lambda f: (f.status == "Done", f.due or "9999"))
        return PostIncidentView(
            incidents=incidents,
            follow_ups=follow_ups,
            outstanding_tasks=len(
                [t for i in incidents for t in i.tasks if t.status == "Open"]
            ),
        )
