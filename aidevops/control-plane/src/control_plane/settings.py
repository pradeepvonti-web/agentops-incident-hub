"""Configuration, read once from the environment at startup.

Everything here is either public (URLs, the publishable key, browser origins) or
a credential that lives in the shell or Key Vault (DATABASE_URL). Nothing is
read from a file in the repository; `.env.example` documents the names.
"""

from __future__ import annotations

import os
import pathlib
from collections.abc import Mapping
from dataclasses import dataclass


def dotenv_values(path: str | os.PathLike[str] = ".env") -> dict[str, str]:
    """`KEY=VALUE` lines from a local .env, for development.

    Real environment variables always win over the file, and the file is never
    committed (.gitignore). This exists so `uv run uvicorn` from the launch
    configuration finds DATABASE_URL without the shell having to export it.
    """
    values: dict[str, str] = {}
    try:
        text = pathlib.Path(path).read_text(encoding="utf-8")
    except OSError:
        return values
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("'\"")
    return values


#: Where the unified shell runs in development. Port 5174 is the one this
#: repository's launch configuration uses; 5173 is Vite's default.
DEFAULT_ORIGINS = ("http://localhost:5173", "http://localhost:5174")


@dataclass(frozen=True)
class Settings:
    database_url: str = ""
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    environment: str = "dev"
    dev_tenant: str = ""
    allowed_origins: tuple[str, ...] = DEFAULT_ORIGINS

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        e = {**dotenv_values(), **os.environ} if env is None else env
        origins = tuple(
            o.strip() for o in e.get("ADP_ALLOWED_ORIGINS", "").split(",") if o.strip()
        )
        return cls(
            database_url=e.get("DATABASE_URL", ""),
            supabase_url=e.get("SUPABASE_URL", "").rstrip("/"),
            supabase_publishable_key=e.get("SUPABASE_PUBLISHABLE_KEY", ""),
            environment=e.get("ADP_ENVIRONMENT", "dev"),
            dev_tenant=e.get("ADP_DEV_TENANT", ""),
            allowed_origins=origins or DEFAULT_ORIGINS,
        )

    @property
    def dev_tenant_fallback(self) -> str:
        """The tenant an unmapped user lands in. Development only.

        Outside `ADP_ENVIRONMENT=dev` this is always empty, whatever the variable
        says: an unmapped account in test or prod is a 403, never a guess. Same
        rule as `ADP_ALLOW_DEVELOPER_CREDENTIALS` in the gateway.
        """
        return self.dev_tenant if self.environment == "dev" else ""
