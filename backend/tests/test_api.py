import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_list_incidents():
    r = client.get("/api/v1/incidents")
    assert r.status_code == 200
    assert len(r.json()) >= 3

def test_critical_filter():
    r = client.get("/api/v1/incidents?severity=CRITICAL")
    assert r.status_code == 200
    rows = r.json()
    assert rows
    assert all(x["severity"] == "CRITICAL" for x in rows)

def test_detail():
    r = client.get("/api/v1/incidents/INC-1042")
    assert r.status_code == 200
    assert r.json()["id"] == "INC-1042"

def test_unknown_is_404():
    assert client.get("/api/v1/incidents/DOES-NOT-EXIST").status_code == 404

def test_logs_include_all_levels():
    r = client.get("/api/v1/incidents/INC-1042/logs")
    assert r.status_code == 200
    levels = {x["level"] for x in r.json()}
    assert "WARNING" in levels

def test_report_evidence_is_error_and_critical_only():
    r = client.get("/api/v1/incidents/INC-1042/report")
    assert r.status_code == 200
    body = r.json()
    assert body["incident_id"] == "INC-1042"
    assert body["evidence"]
    assert all("[ERROR]" in x or "[CRITICAL]" in x for x in body["evidence"])

def test_report_category_is_canonical():
    r = client.get("/api/v1/incidents/INC-1046/report")
    assert r.status_code == 200
    assert r.json()["category"] in {
        "Availability", "Performance", "Security", "Data", "Integration"
    }

def test_report_unknown_is_404():
    assert client.get("/api/v1/incidents/DOES-NOT-EXIST/report").status_code == 404

def test_board_groups_active_incidents_only():
    r = client.get("/api/v1/board")
    assert r.status_code == 200
    board = r.json()
    assert [c["status"] for c in board["columns"]] == [
        "Triage", "Investigating", "Fixing", "Monitoring"
    ]
    for column in board["columns"]:
        assert all(x["status"] == column["status"] for x in column["incidents"])
    assert board["active_count"] == sum(len(c["incidents"]) for c in board["columns"])
    assert board["critical_count"] >= 1

def test_status_filter_and_active_shortcut():
    r = client.get("/api/v1/incidents?status=Closed")
    assert r.status_code == 200
    assert r.json()
    assert all(x["status"] == "Closed" for x in r.json())

    r = client.get("/api/v1/incidents?status=active")
    assert all(
        x["status"] in {"Triage", "Investigating", "Fixing", "Monitoring"}
        for x in r.json()
    )

def test_search_matches_title_and_service():
    assert [x["id"] for x in client.get("/api/v1/incidents?q=checkout").json()] == ["INC-1042"]
    assert client.get("/api/v1/incidents?q=nothing-matches-this").json() == []

def test_service_and_category_filters():
    r = client.get("/api/v1/incidents?service=identity")
    assert [x["id"] for x in r.json()] == ["INC-1044"]
    r = client.get("/api/v1/incidents?category=Integration")
    assert {x["id"] for x in r.json()} == {"INC-1046", "INC-1047"}

def test_list_is_sorted_by_severity():
    severities = [x["severity"] for x in client.get("/api/v1/incidents").json()]
    order = {"CRITICAL": 0, "ERROR": 1, "WARNING": 2, "INFO": 3}
    assert severities == sorted(severities, key=lambda s: order[s])

def test_insights_metrics():
    body = client.get("/api/v1/insights").json()
    assert body["total_incidents"] == 8
    assert body["active_incidents"] == body["total_incidents"] - len(
        client.get("/api/v1/incidents?status=Closed").json()
    ) - len(client.get("/api/v1/incidents?status=Documenting").json()) - len(
        client.get("/api/v1/incidents?status=Reviewing").json()
    )
    assert body["mean_time_to_acknowledge_minutes"] > 0
    assert body["mean_time_to_resolve_minutes"] > 0
    assert sum(x["count"] for x in body["by_severity"]) == 8
    assert sum(x["count"] for x in body["by_status"]) == 8

def test_post_incident_view():
    body = client.get("/api/v1/post-incident").json()
    assert body["incidents"]
    assert body["follow_ups"]
    assert body["outstanding_tasks"] == len(
        [t for i in body["incidents"] for t in i["tasks"] if t["status"] == "Open"]
    )
    assert all(f["incident_id"].startswith("INC-") for f in body["follow_ups"])

def test_detail_carries_timeline_and_updates():
    body = client.get("/api/v1/incidents/INC-1042").json()
    assert body["lead"] == "Sam Lee"
    assert body["timestamps"]["declared_at"]
    assert body["updates"] and body["timeline"]
    assert body["related_incidents"] == ["INC-1046"]

def test_platform_endpoints():
    catalog = client.get("/api/v1/catalog").json()
    assert {s["id"] for s in catalog["services"]} >= {"checkout-api", "identity"}
    assert catalog["teams"]

    alerts = client.get("/api/v1/alerts").json()
    assert alerts["sources"] and alerts["routes"] and alerts["recent"]

    oncall = client.get("/api/v1/oncall").json()
    assert oncall["schedules"] and oncall["escalation_paths"]

    assert client.get("/api/v1/workflows").json()

    status_page = client.get("/api/v1/status-page").json()
    assert status_page["components"] and status_page["updates"]

def test_every_incident_service_exists_in_catalog():
    services = {s["id"] for s in client.get("/api/v1/catalog").json()["services"]}
    for incident in client.get("/api/v1/incidents").json():
        assert incident["service"] in services

# --- Supabase integration surface -------------------------------------------
# These run offline: they assert how the service behaves when Supabase is not
# configured, which is the state every fresh clone and CI run starts in.

def test_health_reports_integration_state():
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert "supabase" in body and "ingestion" in body

def test_alert_webhook_validates_payload():
    r = client.post("/api/v1/webhooks/alerts", json={"title": "x"})
    assert r.status_code == 422

def test_alert_webhook_needs_a_service_key():
    r = client.post(
        "/api/v1/webhooks/alerts",
        json={"title": "checkout error rate above 5%", "source": "metrics", "priority": "High"},
    )
    assert r.status_code == 503
    assert "SUPABASE_SERVICE_KEY" in r.json()["detail"]

def test_repository_prefers_the_service_key_over_the_publishable_one():
    import httpx
    from app.config import Settings
    from app.services.supabase_repository import SupabaseRepository

    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["apikey"] = request.headers["apikey"]
        return httpx.Response(200, json=[])

    repo = SupabaseRepository(
        Settings(
            supabase_url="https://example.supabase.co",
            supabase_key="publishable",
            supabase_service_key="service",
        ),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    repo.incidents()
    assert seen["apikey"] == "service"

def test_stream_says_so_when_supabase_is_absent():
    with client.stream("GET", "/api/v1/stream") as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        body = "".join(r.iter_text())
    assert "event: ready" in body
    assert "not configured" in body

def test_supabase_repository_refuses_without_configuration():
    from app.config import Settings
    from app.services.supabase_repository import SupabaseNotConfigured, SupabaseRepository

    repo = SupabaseRepository(Settings())
    with pytest.raises(SupabaseNotConfigured):
        repo.incidents()

def test_supabase_repository_builds_a_schema_scoped_request():
    import httpx
    from app.config import Settings

    from app.services.supabase_repository import SupabaseRepository

    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        return httpx.Response(200, json=[{"reference": "INC-1042"}])

    repo = SupabaseRepository(
        Settings(supabase_url="https://example.supabase.co", supabase_key="test-key"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    rows = repo.incidents(**{"status": "eq.Fixing"})

    assert rows == [{"reference": "INC-1042"}]
    assert "/rest/v1/incident_list" in seen["url"]
    assert "status=eq.Fixing" in seen["url"]
    assert seen["headers"]["accept-profile"] == "agentops"
    assert seen["headers"]["apikey"] == "test-key"
