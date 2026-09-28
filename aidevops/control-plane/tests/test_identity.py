"""Session-to-tenant resolution (ADR-0005).

Supabase Auth is replaced by an httpx mock transport, the database by a fake
with one method, because the property under test is the decision table in
`require_tenant`: which combination of token, membership and environment yields
which outcome. Nothing here needs a network.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest
from control_plane.auth.supabase import AuthUser, IdentityUnavailable, SupabaseIdentity
from control_plane.settings import Settings
from control_plane.store.database import Membership
from control_plane.store.tenant_context import require_execution_plane, require_tenant
from fastapi import HTTPException

# ------------------------------------------------------------ SupabaseIdentity


def _identity(status: int, body: dict | None = None) -> SupabaseIdentity:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/auth/v1/user"
        assert request.headers["apikey"] == "sb_publishable_test"
        assert request.headers["Authorization"] == "Bearer tok"
        return httpx.Response(status, content=json.dumps(body or {}))

    return SupabaseIdentity(
        "https://example.supabase.co/", "sb_publishable_test",
        transport=httpx.MockTransport(handler),
    )


async def test_a_valid_token_resolves_to_its_user() -> None:
    user = await _identity(200, {"id": "u-1", "email": "sam@acme.example"}).user_for("tok")
    assert user == AuthUser(id="u-1", email="sam@acme.example")
    assert user.display_name == "sam@acme.example"


async def test_an_expired_token_is_none_not_an_error() -> None:
    assert await _identity(401, {"msg": "expired"}).user_for("tok") is None


async def test_an_outage_is_distinguishable_from_a_bad_token() -> None:
    with pytest.raises(IdentityUnavailable):
        await _identity(502).user_for("tok")


def test_identity_needs_both_url_and_key() -> None:
    with pytest.raises(ValueError):
        SupabaseIdentity("", "key")


# --------------------------------------------------------------- require_tenant


class FakeIdentity:
    def __init__(self, user: AuthUser | None, *, down: bool = False) -> None:
        self.user, self.down = user, down

    async def user_for(self, token: str) -> AuthUser | None:
        if self.down:
            raise IdentityUnavailable("auth returned 503")
        return self.user


class FakeDb:
    def __init__(self, membership: Membership | None) -> None:
        self.membership = membership
        self.asked: list[str] = []

    async def resolve_membership(self, auth_user_id: str) -> Membership | None:
        self.asked.append(auth_user_id)
        return self.membership


def _request(*, identity=None, db=None, settings: Settings | None = None):
    state = SimpleNamespace(identity=identity, db=db, settings=settings or Settings())
    return SimpleNamespace(app=SimpleNamespace(state=state))


SAM = AuthUser(id="u-1", email="sam@acme.example")


async def _status(coro) -> int:
    with pytest.raises(HTTPException) as info:
        await coro
    return info.value.status_code


async def test_no_token_is_401_before_anything_is_looked_at() -> None:
    assert await _status(require_tenant(_request(), None)) == 401
    assert await _status(require_tenant(_request(), "Basic xyz")) == 401


async def test_unconfigured_identity_is_503() -> None:
    assert await _status(require_tenant(_request(identity=None), "Bearer tok")) == 503


async def test_identity_outage_is_503_not_401() -> None:
    req = _request(identity=FakeIdentity(SAM, down=True), db=FakeDb(None))
    assert await _status(require_tenant(req, "Bearer tok")) == 503


async def test_unrecognised_token_is_401() -> None:
    req = _request(identity=FakeIdentity(None), db=FakeDb(None))
    assert await _status(require_tenant(req, "Bearer tok")) == 401


async def test_unconfigured_database_is_503() -> None:
    req = _request(identity=FakeIdentity(SAM), db=None)
    assert await _status(require_tenant(req, "Bearer tok")) == 503


async def test_membership_decides_the_tenant_and_role() -> None:
    db = FakeDb(Membership(tenant_id="globex", role="approver"))
    ctx = await require_tenant(_request(identity=FakeIdentity(SAM), db=db), "Bearer tok")
    assert ctx.tenant_id == "globex"
    assert ctx.role == "approver"
    assert ctx.may_approve
    assert ctx.user_object_id == "u-1"
    assert ctx.display_name == "sam@acme.example"
    assert db.asked == ["u-1"]


async def test_a_member_may_not_approve() -> None:
    db = FakeDb(Membership(tenant_id="acme", role="member"))
    ctx = await require_tenant(_request(identity=FakeIdentity(SAM), db=db), "Bearer tok")
    assert not ctx.may_approve


async def test_no_membership_is_403_outside_dev() -> None:
    for env in ("test", "prod"):
        settings = Settings(environment=env, dev_tenant="acme")
        req = _request(identity=FakeIdentity(SAM), db=FakeDb(None), settings=settings)
        assert await _status(require_tenant(req, "Bearer tok")) == 403


async def test_no_membership_and_no_dev_tenant_is_403_even_in_dev() -> None:
    req = _request(identity=FakeIdentity(SAM), db=FakeDb(None),
                   settings=Settings(environment="dev", dev_tenant=""))
    assert await _status(require_tenant(req, "Bearer tok")) == 403


async def test_dev_tenant_fallback_places_an_unmapped_user_as_approver() -> None:
    settings = Settings(environment="dev", dev_tenant="acme")
    req = _request(identity=FakeIdentity(SAM), db=FakeDb(None), settings=settings)
    ctx = await require_tenant(req, "Bearer tok")
    assert ctx.tenant_id == "acme"
    assert ctx.may_approve


async def test_membership_wins_over_the_dev_fallback() -> None:
    settings = Settings(environment="dev", dev_tenant="acme")
    db = FakeDb(Membership(tenant_id="globex", role="member"))
    ctx = await require_tenant(_request(identity=FakeIdentity(SAM), db=db, settings=settings),
                               "Bearer tok")
    assert ctx.tenant_id == "globex"


# ------------------------------------------------------------ settings


def test_dev_fallback_is_empty_outside_dev() -> None:
    assert Settings(environment="prod", dev_tenant="acme").dev_tenant_fallback == ""
    assert Settings(environment="dev", dev_tenant="acme").dev_tenant_fallback == "acme"


def test_settings_read_the_documented_variables() -> None:
    s = Settings.from_env({
        "DATABASE_URL": "postgresql://x", "SUPABASE_URL": "https://p.supabase.co/",
        "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_x", "ADP_ENVIRONMENT": "test",
        "ADP_DEV_TENANT": "acme", "ADP_ALLOWED_ORIGINS": "http://a, http://b",
    })
    assert s.supabase_url == "https://p.supabase.co"
    assert s.allowed_origins == ("http://a", "http://b")
    assert s.dev_tenant_fallback == ""


# ------------------------------------------------------- execution plane stub


async def test_execution_plane_identity_is_still_a_stub() -> None:
    assert await _status(require_execution_plane(None)) == 401
    assert await _status(require_execution_plane("Bearer agent")) == 501
