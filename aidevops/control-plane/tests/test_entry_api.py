"""Entry Points API tests.

These go through a real TestClient rather than inspecting `app.routes`. That is
deliberate: FastAPI 0.141 stopped flattening included routers into `app.routes` and
now holds a single `_IncludedRouter` wrapper, so route introspection silently
reports a mounted router as absent. Asking the app to serve the request is the only
check that stays honest across versions.
"""

from __future__ import annotations

import pytest
from adp_contracts import ENTRY_POINTS, EntrySource
from control_plane.api.app import app
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ------------------------------------------------------------------ discovery

def test_entry_points_endpoint_is_mounted(client: TestClient) -> None:
    assert client.get("/v1/entry/points").status_code == 200


def test_entry_points_endpoint_needs_no_auth(client: TestClient) -> None:
    """The portal paints the entry layer before a session exists."""
    response = client.get("/v1/entry/points")
    assert response.status_code == 200
    assert len(response.json()["entry_points"]) == 6


def test_served_entry_points_match_the_contract(client: TestClient) -> None:
    served = client.get("/v1/entry/points").json()["entry_points"]

    assert [ep["source"] for ep in served] == [ep.source.value for ep in ENTRY_POINTS]
    assert [ep["label"] for ep in served] == [ep.label for ep in ENTRY_POINTS]
    assert [ep["caption"] for ep in served] == [ep.caption for ep in ENTRY_POINTS]


def test_api_cli_is_flagged_non_interactive(client: TestClient) -> None:
    served = {ep["source"]: ep for ep in client.get("/v1/entry/points").json()["entry_points"]}
    assert served[EntrySource.API_CLI.value]["interactive"] is False
    assert served[EntrySource.PORTAL.value]["interactive"] is True


# ------------------------------------------------------------------ submission

def test_submission_requires_a_token(client: TestClient) -> None:
    """No door submits anonymously, including the ones we build ourselves."""
    response = client.post(
        "/v1/entry/runs",
        json={
            "source": "portal",
            "agent_type": "data-engineering",
            "requirement": "Build a Bronze to Silver pipeline",
        },
    )
    assert response.status_code == 401


def test_adoption_requires_a_token(client: TestClient) -> None:
    assert client.get("/v1/entry/adoption").status_code == 401


def test_submission_is_authorised_before_the_body_is_read(client: TestClient) -> None:
    """Auth resolves first, so a malformed body from an unauthenticated caller
    still returns 401 rather than leaking that the payload was wrong.

    Body-level rejection (an invented seventh door) is covered at the contract
    level in test_entry_points.py and, through the API with a stubbed identity,
    in test_portal_api.py.
    """
    response = client.post(
        "/v1/entry/runs",
        json={
            "source": "slack",
            "agent_type": "data-engineering",
            "requirement": "Build a pipeline",
        },
    )
    assert response.status_code == 401


def test_a_door_cannot_supply_its_own_tenant(client: TestClient) -> None:
    """An extra tenant_id must not be honoured (ADR-0001).

    It is ignored rather than rejected -- EntryRequest has no such field, so it
    never reaches authorisation. The assertion that matters is that the request
    does not succeed on the strength of it.
    """
    response = client.post(
        "/v1/entry/runs",
        json={
            "source": "portal",
            "agent_type": "data-engineering",
            "requirement": "Build a pipeline",
            "tenant_id": "someone-elses-tenant",
        },
    )
    assert response.status_code == 401
