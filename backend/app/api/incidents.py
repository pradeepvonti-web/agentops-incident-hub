from fastapi import APIRouter, HTTPException, Query

from app.models import (
    Board,
    IncidentDetail,
    IncidentReport,
    Insights,
    IncidentSummary,
    LogEvent,
    PostIncidentView,
)
from app.services.incident_service import IncidentNotFoundError, IncidentService

router = APIRouter(tags=["incidents"])
service = IncidentService()


@router.get("/incidents", response_model=list[IncidentSummary])
def list_incidents(
    severity: str | None = Query(default=None),
    status: str | None = Query(default=None, description="A lifecycle status, or 'active'"),
    service_name: str | None = Query(default=None, alias="service"),
    category: str | None = Query(default=None),
    q: str | None = Query(default=None, description="Free-text match on id, title, service, summary"),
):
    return service.list_incidents(severity, status, service_name, category, q)


@router.get("/board", response_model=Board)
def board():
    return service.board()


@router.get("/insights", response_model=Insights)
def insights():
    return service.insights()


@router.get("/post-incident", response_model=PostIncidentView)
def post_incident():
    return service.post_incident()


@router.get("/incidents/{incident_id}", response_model=IncidentDetail)
def get_incident(incident_id: str):
    try:
        return service.get_incident(incident_id)
    except IncidentNotFoundError:
        raise HTTPException(status_code=404, detail="Incident not found")


@router.get("/incidents/{incident_id}/logs", response_model=list[LogEvent])
def get_logs(incident_id: str):
    try:
        return service.get_logs(incident_id)
    except IncidentNotFoundError:
        raise HTTPException(status_code=404, detail="Incident not found")


@router.get("/incidents/{incident_id}/report", response_model=IncidentReport)
def get_report(incident_id: str):
    try:
        return service.build_report(incident_id)
    except IncidentNotFoundError:
        raise HTTPException(status_code=404, detail="Incident not found")
