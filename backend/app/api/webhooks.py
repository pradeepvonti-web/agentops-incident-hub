from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.services.supabase_repository import (
    SupabaseError,
    SupabaseNotConfigured,
    SupabaseRepository,
)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
repository = SupabaseRepository()


class InboundAlert(BaseModel):
    """What a monitoring system posts when something crosses a threshold."""

    title: str = Field(min_length=3, max_length=200)
    source: str = "http"
    priority: Literal["Low", "Medium", "High", "Urgent"] = "Medium"
    payload: dict = Field(default_factory=dict)


@router.post("/alerts", status_code=201)
def receive_alert(alert: InboundAlert):
    if not settings.can_write:
        raise HTTPException(
            status_code=503,
            detail="Alert ingestion needs SUPABASE_SERVICE_KEY. See backend/.env.example.",
        )
    try:
        row = repository.record_alert(
            alert.title, alert.source, alert.priority, alert.payload
        )
    except SupabaseNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except SupabaseError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return {"accepted": True, "reference": row.get("reference"), "id": row.get("id")}
