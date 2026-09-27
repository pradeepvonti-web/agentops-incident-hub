"""Read and write the agentops schema through Supabase's REST API.

The frontend talks to Supabase directly. This module exists so that agents,
scripts and server-side integrations can use the same data through `/api/v1`
without a database password, and so the inbound alert webhook has somewhere to
put what it receives.
"""

from typing import Any

import httpx

from app.config import Settings, settings as default_settings


class SupabaseError(RuntimeError):
    pass


class SupabaseNotConfigured(SupabaseError):
    pass


class SupabaseRepository:
    def __init__(self, settings: Settings = default_settings, client: httpx.Client | None = None):
        self.settings = settings
        self._client = client

    # ---------------------------------------------------------------- plumbing

    def _headers(self, *, write: bool = False) -> dict[str, str]:
        # This service is a server-side actor with no user session, so it uses
        # the service key whenever one is configured. With only the publishable
        # key it sees exactly what an anonymous visitor sees, which is the
        # status page and nothing else.
        key = self.settings.supabase_service_key or (
            "" if write else self.settings.supabase_key
        )
        if not self.settings.supabase_url or not key:
            raise SupabaseNotConfigured(
                "Set SUPABASE_URL and SUPABASE_SERVICE_KEY"
                + (" (writes require the service key)" if write else "")
            )
        profile = "Content-Profile" if write else "Accept-Profile"
        return {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            profile: self.settings.supabase_schema,
            "Accept-Profile": self.settings.supabase_schema,
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, *, write: bool = False, **kwargs) -> Any:
        url = f"{self.settings.supabase_url}/rest/v1{path}"
        headers = self._headers(write=write)
        client = self._client or httpx.Client(timeout=15)
        try:
            response = client.request(method, url, headers=headers, **kwargs)
        finally:
            if self._client is None:
                client.close()

        if response.status_code >= 400:
            raise SupabaseError(f"{response.status_code}: {response.text}")
        if not response.content:
            return None
        return response.json()

    def select(self, table: str, params: dict[str, str] | None = None) -> list[dict]:
        return self._request("GET", f"/{table}", params=params or {}) or []

    def rpc(self, name: str, payload: dict[str, Any]) -> Any:
        return self._request("POST", f"/rpc/{name}", json=payload)

    # ------------------------------------------------------------------ reads

    def incidents(self, **filters: str) -> list[dict]:
        params = {"select": "*", "order": "severity,reference"}
        params.update(filters)
        return self.select("incident_list", params)

    def incident(self, reference: str) -> dict | None:
        rows = self.select(
            "incident_list", {"select": "*", "reference": f"eq.{reference}", "limit": "1"}
        )
        return rows[0] if rows else None

    def report(self, incident_id: str) -> dict:
        return self.rpc("incident_report", {"p_incident": incident_id})

    def changed_since(self, timestamp: str) -> list[dict]:
        """Incidents touched since `timestamp`, newest first. Drives the SSE stream."""
        return self.select(
            "incident_list",
            {
                "select": "reference,title,severity,status,updated_at",
                "updated_at": f"gt.{timestamp}",
                "order": "updated_at.desc",
                "limit": "25",
            },
        )

    # ----------------------------------------------------------------- writes

    def record_alert(self, title: str, source_slug: str, priority: str, payload: dict) -> dict:
        """Insert an alert the way an inbound monitoring webhook would."""
        sources = self.select(
            "alert_sources", {"select": "id", "slug": f"eq.{source_slug}", "limit": "1"}
        )
        if not sources:
            raise SupabaseError(f"Unknown alert source: {source_slug}")

        url = f"{self.settings.supabase_url}/rest/v1/alerts"
        headers = self._headers(write=True) | {"Prefer": "return=representation"}
        client = self._client or httpx.Client(timeout=15)
        try:
            response = client.post(
                url,
                headers=headers,
                json={
                    "title": title,
                    "source_id": sources[0]["id"],
                    "priority": priority,
                    "payload": payload,
                },
            )
        finally:
            if self._client is None:
                client.close()

        if response.status_code >= 400:
            raise SupabaseError(f"{response.status_code}: {response.text}")
        rows = response.json()
        return rows[0] if isinstance(rows, list) and rows else {}
