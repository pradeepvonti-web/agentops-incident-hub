"""Portal routes, through the real app with the two things that need a network
swapped out: identity (a dependency override) and the database (a fake
repository on `app.state`).

What these hold: the shape the shell depends on, the role gate on approvals, and
the two refusals that keep an approval bound to content -- no artifact, or a
different artifact from the one the reviewer saw.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from control_plane.api.app import app
from control_plane.store.tenant_context import TenantContext, require_tenant
from fastapi.testclient import TestClient

NOW = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


def _run(run_id: str, status: str, **over: Any) -> dict[str, Any]:
    row = {
        "run_id": run_id,
        "tenant_id": "acme",
        "agent": "data-engineering",
        "environment": "prod",
        "status": status,
        "invoked_by": "r.mehta",
        "agent_principal": "agent-data-engineering-acme-prod",
        "entry_source": "teams",
        "title": f"Title for {run_id}",
        "created_at": NOW,
        "started_at": NOW,
        "ended_at": NOW + timedelta(seconds=90) if status == "succeeded" else None,
        "execution_plane_version": "0.1.0",
    }
    row.update(over)
    return row


def _span(span_id: str, step: str, status: str, result_digest: str | None) -> dict[str, Any]:
    return {"span_id": span_id, "step": step, "status": status, "result_digest": result_digest}


class FakeRuns:
    """The repository surface the API uses, over dicts."""

    def __init__(self) -> None:
        self.runs: dict[str, dict[str, Any]] = {
            "run_1": _run("run_1", "awaiting_approval"),
            "run_2": _run("run_2", "succeeded", environment="dev", entry_source="portal"),
            "run_3": _run("run_3", "running", environment="dev", entry_source="portal"),
        }
        self.spans: dict[str, list[dict[str, Any]]] = {
            "run_1": [
                _span("s1", "plan", "succeeded", "sha256:plan"),
                _span("s2", "generate", "failed", "sha256:old"),
                _span("s3", "generate", "succeeded", "sha256:current"),
                _span("s4", "approve", "awaiting_approval", None),
            ],
            "run_3": [_span("s5", "plan", "succeeded", None)],
        }
        self.approvals: list[dict[str, Any]] = []
        self.created: list[dict[str, Any]] = []

    async def list_runs(self, tenant_id, *, status=None, agent=None, environment=None,
                        entry_source=None, limit=50):
        rows = list(self.runs.values())
        if status:
            rows = [r for r in rows if r["status"] == status]
        if agent:
            rows = [r for r in rows if r["agent"] == agent]
        if environment:
            rows = [r for r in rows if r["environment"] == environment]
        return rows[:limit]

    async def get_run(self, tenant_id, run_id):
        return self.runs.get(run_id)

    async def get_spans(self, tenant_id, run_id):
        return self.spans.get(run_id, [])

    async def get_approvals(self, tenant_id, run_id):
        return [a for a in self.approvals if a["run_id"] == run_id]

    async def record_approval(self, tenant_id, *, run_id, approved, artifact_digest,
                              approved_by, comment=None):
        row = {
            "approval_id": len(self.approvals) + 1, "run_id": run_id, "approved": approved,
            "artifact_digest": artifact_digest, "approved_by": approved_by,
            "comment": comment, "decided_at": NOW,
        }
        self.approvals.append(row)
        if self.runs[run_id]["status"] == "awaiting_approval":
            self.runs[run_id]["status"] = "running" if approved else "rejected"
        return row

    async def acceptance_stats(self, tenant_id, days=7):
        return {"n": 5, "accepted": 4, "clean_accepted": 2, "median_edit_ratio": 0.12}

    async def count_by_status(self, tenant_id):
        out: dict[str, int] = {}
        for r in self.runs.values():
            out[r["status"]] = out.get(r["status"], 0) + 1
        return out

    async def runs_by_source(self, tenant_id):
        out: dict[str, int] = {}
        for r in self.runs.values():
            out[r["entry_source"]] = out.get(r["entry_source"], 0) + 1
        return out

    async def create_run(self, tenant_id, **kw):
        row = _run(kw["run_id"], "queued", tenant_id=tenant_id, agent=kw["agent"],
                   environment=kw["environment"], invoked_by=kw["invoked_by"],
                   entry_source=kw["entry_source"], title=kw.get("title"),
                   started_at=None)
        # What the real repository stores: the digest, never the text.
        row["requirement_digest"] = "sha256:" + str(hash(kw["requirement"]))
        self.runs[row["run_id"]] = row
        self.created.append(row)
        return row


def _as(role: str) -> TenantContext:
    return TenantContext(tenant_id="acme", user_object_id="user-1", role=role,
                         display_name="sam@acme.example")


@pytest.fixture
def repo() -> FakeRuns:
    return FakeRuns()


def _client(repo: FakeRuns | None, role: str = "member") -> TestClient:
    app.dependency_overrides[require_tenant] = lambda: _as(role)
    app.state.runs = repo
    return TestClient(app, headers={"Authorization": "Bearer test"})


@pytest.fixture(autouse=True)
def _reset():
    yield
    app.dependency_overrides.clear()
    app.state.runs = None


# ---------------------------------------------------------------- unconfigured

def test_runs_answer_503_without_a_database() -> None:
    client = _client(None)
    response = client.get("/v1/runs")
    assert response.status_code == 503
    assert "DATABASE_URL" in response.json()["detail"]


def test_health_reports_what_is_configured() -> None:
    body = TestClient(app).get("/health").json()
    assert body["status"] == "ok"
    assert body["database_configured"] is False


# ---------------------------------------------------------------------- reads

def test_list_runs_returns_summaries(repo: FakeRuns) -> None:
    rows = _client(repo).get("/v1/runs").json()
    assert {r["run_id"] for r in rows} == {"run_1", "run_2", "run_3"}
    by_id = {r["run_id"]: r for r in rows}
    assert by_id["run_1"]["awaiting_approval"] is True
    assert by_id["run_1"]["agent_type"] == "data-engineering"
    assert by_id["run_1"]["entry_source"] == "teams"
    assert by_id["run_2"]["duration_seconds"] == 90
    assert by_id["run_3"]["duration_seconds"] is None


def test_list_runs_filters_by_status(repo: FakeRuns) -> None:
    rows = _client(repo).get("/v1/runs", params={"status": "awaiting_approval"}).json()
    assert [r["run_id"] for r in rows] == ["run_1"]


def test_list_runs_rejects_an_unknown_status(repo: FakeRuns) -> None:
    assert _client(repo).get("/v1/runs", params={"status": "pending"}).status_code == 422


def test_summaries_carry_no_payload_fields(repo: FakeRuns) -> None:
    row = _client(repo).get("/v1/runs").json()[0]
    for word in ("requirement", "requirement_digest", "prompt", "arguments", "result"):
        assert word not in row


def test_get_run_includes_spans_and_the_current_artifact(repo: FakeRuns) -> None:
    body = _client(repo).get("/v1/runs/run_1").json()
    assert body["run"]["run_id"] == "run_1"
    assert [s["span_id"] for s in body["spans"]] == ["s1", "s2", "s3", "s4"]
    # The newest *successful* generate step, not the failed attempt after the plan.
    assert body["artifact_digest"] == "sha256:current"
    assert body["approvals"] == []


def test_get_run_without_a_generate_step_has_no_artifact(repo: FakeRuns) -> None:
    assert _client(repo).get("/v1/runs/run_3").json()["artifact_digest"] is None


def test_get_unknown_run_is_404(repo: FakeRuns) -> None:
    assert _client(repo).get("/v1/runs/run_404").status_code == 404


def test_stats_report_n_and_whether_it_is_meaningful(repo: FakeRuns) -> None:
    body = _client(repo).get("/v1/runs/stats").json()
    assert body["by_status"] == {"awaiting_approval": 1, "succeeded": 1, "running": 1}
    assert body["acceptance"]["n"] == 5
    assert body["acceptance"]["acceptance_rate"] == pytest.approx(0.8)
    assert body["acceptance"]["clean_accept_rate"] == pytest.approx(0.4)
    # Five runs is exactly the number that reaches a slide. It must say so.
    assert body["acceptance"]["meaningful"] is False


# ------------------------------------------------------------------ approvals

def _decide(client: TestClient, run_id: str, digest: str, approved: bool = True):
    return client.post(
        f"/v1/runs/{run_id}/approval",
        json={"approved": approved, "artifact_digest": digest, "comment": "looks right"},
    )


def test_a_member_cannot_decide(repo: FakeRuns) -> None:
    response = _decide(_client(repo, "member"), "run_1", "sha256:current")
    assert response.status_code == 403
    assert repo.approvals == []


def test_a_decision_needs_an_artifact_digest(repo: FakeRuns) -> None:
    response = _client(repo, "approver").post(
        "/v1/runs/run_1/approval", json={"approved": True}
    )
    assert response.status_code == 422


def test_a_stale_digest_is_refused(repo: FakeRuns) -> None:
    """The reviewer saw an older artifact. Re-binding silently is the bug
    ADR-0002 section 5 forbids, so this is a 409, not a success."""
    response = _decide(_client(repo, "approver"), "run_1", "sha256:old")
    assert response.status_code == 409
    assert repo.runs["run_1"]["status"] == "awaiting_approval"
    assert repo.approvals == []


def test_a_run_without_an_artifact_cannot_be_approved(repo: FakeRuns) -> None:
    repo.runs["run_3"]["status"] = "awaiting_approval"
    response = _decide(_client(repo, "approver"), "run_3", "sha256:anything")
    assert response.status_code == 409
    assert "no artifact" in response.json()["detail"]


def test_a_run_not_awaiting_approval_cannot_be_decided(repo: FakeRuns) -> None:
    response = _decide(_client(repo, "approver"), "run_2", "sha256:current")
    assert response.status_code == 409


def test_an_approver_releases_the_run(repo: FakeRuns) -> None:
    response = _decide(_client(repo, "approver"), "run_1", "sha256:current")
    assert response.status_code == 200
    assert response.json()["status"] == "running"
    assert repo.runs["run_1"]["status"] == "running"
    # The human, never the agent, and the exact digest.
    assert repo.approvals[0]["approved_by"] == "user-1"
    assert repo.approvals[0]["artifact_digest"] == "sha256:current"


def test_a_rejection_stops_the_run(repo: FakeRuns) -> None:
    response = _decide(_client(repo, "admin"), "run_1", "sha256:current", approved=False)
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert repo.runs["run_1"]["status"] == "rejected"


# ----------------------------------------------------------------- submission

def test_submitting_a_run_queues_it(repo: FakeRuns) -> None:
    response = _client(repo).post(
        "/v1/entry/runs",
        json={
            "source": "portal",
            "agent_type": "data-engineering",
            "environment": "prod",
            "requirement": "Build a Silver table for sales orders",
            "title": "Bronze to Silver: sales_orders",
        },
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["requires_approval"] is True
    created = repo.created[0]
    assert created["run_id"] == body["run_id"]
    assert created["title"] == "Bronze to Silver: sales_orders"
    assert created["invoked_by"] == "sam@acme.example"
    # The requirement text is not among what was stored (ADR-0003 section 3).
    assert "requirement" not in created
    assert created["requirement_digest"].startswith("sha256:")


def test_an_invented_door_is_rejected_at_the_body(repo: FakeRuns) -> None:
    response = _client(repo).post(
        "/v1/entry/runs",
        json={"source": "slack", "agent_type": "data-engineering", "requirement": "x"},
    )
    assert response.status_code == 422
    assert repo.created == []


def test_automation_without_an_idempotency_key_is_refused(repo: FakeRuns) -> None:
    response = _client(repo).post(
        "/v1/entry/runs",
        json={"source": "api-cli", "agent_type": "data-quality", "requirement": "sweep"},
    )
    assert response.status_code == 400
    assert repo.created == []


def test_adoption_names_all_six_doors(repo: FakeRuns) -> None:
    body = _client(repo).get("/v1/entry/adoption").json()
    assert body["tenant_id"] == "acme"
    assert set(body["by_source"]) == {
        "portal", "databricks", "vs-code", "power-bi", "teams", "api-cli"
    }
    assert body["by_source"]["portal"] == 2
    assert body["by_source"]["teams"] == 1
    assert body["by_source"]["power-bi"] == 0


# ------------------------------------------------------------ execution plane

def test_agent_routes_are_not_reachable_with_a_portal_session(repo: FakeRuns) -> None:
    """A Supabase session is a human. The execution plane presents a workload
    identity, and that path is still the documented stub."""
    response = _client(repo, "admin").post("/v1/agent/spans", json=[])
    assert response.status_code == 501


def test_agent_routes_still_require_a_token() -> None:
    assert TestClient(app).post("/v1/agent/spans", json=[]).status_code == 401
