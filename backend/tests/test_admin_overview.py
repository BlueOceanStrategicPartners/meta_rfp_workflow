import pytest

from apps.admin_command_center.services.stats import percentile
from apps.rfp_debate.models import RFPStatus


def test_percentile_nearest_rank():
    assert percentile([], 50) is None
    assert percentile([10.0], 95) == 10.0
    assert percentile([1, 2, 3, 4], 50) == 2
    assert percentile([5, 1, 3, 2, 4], 95) == 5


@pytest.mark.django_db
def test_overview_counts_match_data(admin_client, seeded_rfp):
    body = admin_client.get("/api/admin-center/overview/").json()
    assert body["rfps"]["total"] == 1
    assert body["rfps"]["by_status"]["NEGOTIATING"] == 1
    assert set(body["rfps"]["by_status"]) == set(RFPStatus.values)
    assert body["sla"]["measured"] == 1
    assert body["sla"]["within_target_pct"] == 1.0
    assert body["pricing"]["quotes"] >= 1
    assert body["inventory"] == {"properties": 1, "spaces": 1, "booked": 0}
    assert body["debate"]["rounds"] >= 1


@pytest.mark.django_db
def test_attention_lists_escalated_and_amber(admin_client, seeded_rfp):
    seeded_rfp.amber_conflict_fields_json = ["total_room_nights"]
    seeded_rfp.save(update_fields=["amber_conflict_fields_json"])
    items = admin_client.get("/api/admin-center/overview/").json()["attention"]
    assert items == [
        {"rfp_id": str(seeded_rfp.id), "company_name": items[0]["company_name"], "status": seeded_rfp.status, "reason": "amber_fields"}
    ]
    admin_client.post(f"/api/admin-center/negotiations/{seeded_rfp.id}/takeover/")
    body = admin_client.get("/api/admin-center/overview/").json()
    assert body["attention"][0]["reason"] == "escalated"
    assert body["recent_activity"][0]["action"] == "negotiation.takeover"


@pytest.mark.django_db
def test_overview_empty_database(admin_client):
    body = admin_client.get("/api/admin-center/overview/").json()
    assert body["rfps"]["total"] == 0
    assert body["sla"]["p50_seconds"] is None
    assert body["pricing"]["fallback_rate"] is None
    assert body["attention"] == []


@pytest.mark.django_db
def test_audit_endpoint_filters(admin_client, seeded_rfp):
    admin_client.post(f"/api/admin-center/negotiations/{seeded_rfp.id}/takeover/")
    rows = admin_client.get(f"/api/admin-center/audit/?target_type=rfp&target_id={seeded_rfp.id}").json()
    assert rows[0]["action"] == "negotiation.takeover"
    assert rows[0]["actor"] == "admin@example.com"
    assert admin_client.get("/api/admin-center/audit/?target_type=space").json() == []
