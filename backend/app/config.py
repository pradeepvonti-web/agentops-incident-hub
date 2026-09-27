import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Runtime configuration. Everything has a default that works offline."""

    supabase_url: str = ""
    supabase_key: str = ""
    supabase_schema: str = "agentops"
    #: Server-side key. Needed only for endpoints that write on a caller's behalf,
    #: such as the inbound alert webhook. Never sent to the browser.
    supabase_service_key: str = ""
    allowed_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )
    #: Seconds between polls when streaming changes over SSE.
    stream_interval_seconds: float = 3.0

    @property
    def uses_supabase(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)

    @property
    def can_write(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_key)


def load_settings() -> Settings:
    origins = os.getenv("ALLOWED_ORIGINS", "")
    return Settings(
        supabase_url=os.getenv("SUPABASE_URL", "").rstrip("/"),
        supabase_key=os.getenv("SUPABASE_PUBLISHABLE_KEY", os.getenv("SUPABASE_ANON_KEY", "")),
        supabase_schema=os.getenv("SUPABASE_SCHEMA", "agentops"),
        supabase_service_key=os.getenv("SUPABASE_SERVICE_KEY", ""),
        allowed_origins=tuple(o.strip() for o in origins.split(",") if o.strip())
        or Settings.allowed_origins,
        stream_interval_seconds=float(os.getenv("STREAM_INTERVAL_SECONDS", "3")),
    )


settings = load_settings()
