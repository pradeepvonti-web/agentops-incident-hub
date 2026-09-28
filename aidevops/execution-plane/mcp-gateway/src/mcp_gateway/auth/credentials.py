"""Agent credential acquisition. Implements ADR-0002 sections 1, 2 and 6.

Two rules this module exists to enforce, mechanically rather than by convention:

1. **No secrets.** Tokens come from workload identity federation. There is no code
   path here that accepts a client secret or a Databricks PAT, so there is no code
   path that can leak one.
2. **Short-lived, run-scoped.** Tokens expire in 15 minutes and are cached per
   (principal, scope) only for their own lifetime. A long-running agent renews per
   step rather than holding a long-lived credential.

`prod` refuses to start without federation configured. That is deliberate: the most
likely way a secret ends up in production is a developer convenience path that was
never closed off.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Protocol

import structlog
from adp_contracts import AgentPrincipal, Environment

log = structlog.get_logger(__name__)

#: Agent tokens are deliberately short-lived (ADR-0002 section 6).
TOKEN_LIFETIME_SECONDS = 15 * 60

#: Renew slightly early so a call never starts with a token about to expire.
RENEWAL_MARGIN_SECONDS = 60


@dataclass(frozen=True)
class AccessToken:
    token: str
    expires_at: float
    scope: str

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.expires_at - RENEWAL_MARGIN_SECONDS


class CredentialProvider(Protocol):
    """How the gateway obtains a token for an agent principal."""

    def token_for(self, principal: AgentPrincipal, scope: str) -> AccessToken: ...


class FederatedCredentialProvider:
    """Production path: workload identity federation, no secrets.

    The runtime's own managed identity (or Kubernetes service account token) is
    exchanged for a token for the agent's principal. Nothing is stored on disk and
    nothing is read from an environment variable that could hold a secret.
    """

    def __init__(self) -> None:
        # Imported lazily so that local development and unit tests do not require
        # the Azure SDK to be installed or an Azure environment to be present.
        from azure.identity import DefaultAzureCredential

        self._credential = DefaultAzureCredential(
            exclude_interactive_browser_credential=True,
            exclude_shared_token_cache_credential=True,
        )
        self._cache: dict[tuple[str, str], AccessToken] = {}

    def token_for(self, principal: AgentPrincipal, scope: str) -> AccessToken:
        key = (principal.name, scope)
        cached = self._cache.get(key)
        if cached is not None and not cached.is_expired:
            return cached

        log.info(
            "acquiring_agent_token",
            agent_principal=principal.name,
            agent_type=str(principal.agent_type),
            environment=str(principal.environment),
            scope=scope,
        )

        raw = self._credential.get_token(scope)
        token = AccessToken(
            token=raw.token,
            expires_at=min(
                float(raw.expires_on), time.time() + TOKEN_LIFETIME_SECONDS
            ),
            scope=scope,
        )
        self._cache[key] = token
        return token


class DeveloperCredentialProvider:
    """Local development only. Uses the developer's own Entra identity.

    This exists so nobody invents a shared dev service principal with a secret in a
    .env file. It refuses to operate outside `dev` (ADR-0002 consequences).
    """

    def __init__(self) -> None:
        self._cache: dict[tuple[str, str], AccessToken] = {}

    def token_for(self, principal: AgentPrincipal, scope: str) -> AccessToken:
        if principal.environment is not Environment.DEV:
            raise RuntimeError(
                "DeveloperCredentialProvider is only valid in dev. "
                f"Refusing to issue a token for {principal.name}."
            )

        from azure.identity import AzureCliCredential

        key = (principal.name, scope)
        cached = self._cache.get(key)
        if cached is not None and not cached.is_expired:
            return cached

        log.warning(
            "using_developer_credential",
            agent_principal=principal.name,
            detail="acting as the signed-in developer, not the agent principal",
        )
        raw = AzureCliCredential().get_token(scope)
        token = AccessToken(
            token=raw.token,
            expires_at=min(float(raw.expires_on), time.time() + TOKEN_LIFETIME_SECONDS),
            scope=scope,
        )
        self._cache[key] = token
        return token


def build_credential_provider(environment: Environment | str) -> CredentialProvider:
    """Select a provider, and fail closed outside dev.

    The `ADP_ALLOW_DEVELOPER_CREDENTIALS` escape hatch is honoured only in dev, so
    setting it in a production manifest does nothing.
    """
    env = Environment(str(environment))
    allow_dev = os.environ.get("ADP_ALLOW_DEVELOPER_CREDENTIALS") == "1"

    if env is Environment.DEV and allow_dev:
        return DeveloperCredentialProvider()

    if env is not Environment.DEV and allow_dev:
        log.error(
            "developer_credentials_requested_outside_dev",
            environment=str(env),
            detail="ignoring the flag; federation is mandatory outside dev",
        )

    return FederatedCredentialProvider()
