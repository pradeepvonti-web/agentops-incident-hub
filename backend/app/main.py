from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.incidents import router as incidents_router
from app.api.platform import router as platform_router
from app.api.stream import router as stream_router
from app.api.webhooks import router as webhooks_router
from app.config import settings

app = FastAPI(
    title="Restora API",
    version="2.0.0",
    description="Agentic engineering reference application.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(incidents_router, prefix="/api/v1")
app.include_router(platform_router, prefix="/api/v1")
app.include_router(stream_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "supabase": settings.uses_supabase,
        "ingestion": settings.can_write,
    }
