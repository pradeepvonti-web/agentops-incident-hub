import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.config import settings
from app.services.supabase_repository import SupabaseError, SupabaseRepository

router = APIRouter(tags=["stream"])
repository = SupabaseRepository()


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.get("/stream")
async def stream(request: Request):
    """Server-sent events for incident changes.

    The browser uses Supabase Realtime directly. This endpoint exists for
    everything that is not a browser: agents, scripts, and any consumer that
    would rather hold one HTTP connection than a websocket.
    """

    async def events():
        cursor = datetime.now(timezone.utc).isoformat()
        yield _sse("ready", {"since": cursor, "source": "supabase" if settings.uses_supabase else "none"})

        while True:
            if await request.is_disconnected():
                break

            if settings.uses_supabase:
                try:
                    changed = await asyncio.to_thread(repository.changed_since, cursor)
                    for row in reversed(changed):
                        yield _sse("incident.changed", row)
                    if changed:
                        cursor = changed[0]["updated_at"]
                except SupabaseError as exc:
                    yield _sse("error", {"message": str(exc)})
            else:
                yield _sse(
                    "error",
                    {"message": "SUPABASE_URL is not configured; nothing to stream"},
                )
                break

            yield _sse("heartbeat", {"at": datetime.now(timezone.utc).isoformat()})
            await asyncio.sleep(settings.stream_interval_seconds)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
