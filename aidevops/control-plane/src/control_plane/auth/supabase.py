"""Portal identity: a Supabase Auth session. Implements ADR-0005.

The AI DevOps screens live inside the Restora shell, and that shell signs people
in with Supabase Auth, so the bearer token the control plane receives is a
Supabase access token. Rather than verify the signature locally -- which means
tracking the project's signing keys and their rotation -- the control plane asks
Supabase Auth who the token belongs to. One HTTPS call per request, cached
nowhere: a revoked session stops working on the next request, which is what a
revocation should mean.

Execution-plane callers do not come through here. They present an Entra workload
identity (ADR-0002); see `require_execution_plane`, which is still a stub.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
import structlog

log = structlog.get_logger(__name__)


class IdentityUnavailable(RuntimeError):
    """Supabase Auth could not be reached or answered unexpectedly.

    Distinct from an invalid token on purpose: the caller should get a 503 and
    retry, not a 401 that sends them back to the sign-in screen.
    """


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str | None = None

    @property
    def display_name(self) -> str:
        """What a run records as `invoked_by`. The email when there is one,
        because a run list full of UUIDs is unreadable; the id otherwise."""
        return self.email or self.id


class SupabaseIdentity:
    def __init__(
        self,
        url: str,
        publishable_key: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not url or not publishable_key:
            raise ValueError("SupabaseIdentity needs the project URL and publishable key")
        self._key = publishable_key
        self._client = httpx.AsyncClient(
            base_url=url.rstrip("/"), timeout=5.0, transport=transport
        )

    async def user_for(self, access_token: str) -> AuthUser | None:
        """The user a token belongs to, or None when Supabase rejects it."""
        try:
            response = await self._client.get(
                "/auth/v1/user",
                headers={"apikey": self._key, "Authorization": f"Bearer {access_token}"},
            )
        except httpx.HTTPError as exc:
            log.warning("identity_lookup_failed", error=str(exc))
            raise IdentityUnavailable(str(exc)) from exc

        if response.status_code in (401, 403):
            return None
        if response.status_code != 200:
            raise IdentityUnavailable(f"auth returned {response.status_code}")

        body = response.json()
        user_id = body.get("id")
        if not user_id:
            return None
        return AuthUser(id=str(user_id), email=body.get("email"))

    async def aclose(self) -> None:
        await self._client.aclose()
