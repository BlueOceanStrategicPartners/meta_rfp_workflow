import pytest

from apps.admin_command_center.models import AdminAuditEvent
from apps.dynamic_pricing.models import DynamicPricingQuote
from apps.rfp_debate.models import RFPStatus


@pytest.mark.django_db
def test_list_and_status_filter(admin_client, seeded_rfp):
    rows = admin_client.get("/api/admin-center/rfps/").json()
    assert [r["id"] for r in rows] == [str(seeded_rfp.id)]
    assert rows[0]["rounds"] >= 1
    assert admin_client.get("/api/admin-center/rfps/?status=BOOKED").json() == []
    assert admin_client.get("/api/admin-center/rfps/?status=NOPE").status_code == 400


@pytest.mark.django_db
def test_detail_has_rounds_quotes_and_sla(admin_client, seeded_rfp):
    body = admin_client.get(f"/api/admin-center/rfps/{seeded_rfp.id}/").json()
    assert body["rounds"][0]["extractor_model_id"]
    assert "flags" in body["rounds"][0]
    assert body["quotes"]
    assert body["sla"]["duration_seconds"] is not None  # sla_completed_at is now written


@pytest.mark.django_db
def test_override_updates_cards_reprices_and_audits(admin_client, seeded_rfp):
    seeded_rfp.amber_conflict_fields_json = ["total_room_nights"]
    seeded_rfp.save(update_fields=["amber_conflict_fields_json"])
    quotes_before = DynamicPricingQuote.objects.filter(rfp=seeded_rfp).count()

    res = admin_client.post(
        f"/api/admin-center/rfps/{seeded_rfp.id}/override/",
        {"fields": {"company_name": "Globex", "total_room_nights": 90}, "note": "Confirmed by phone"},
        format="json",
    )
    assert res.status_code == 200, res.json()
    assert res.json()["ok"] is True

    seeded_rfp.refresh_from_db()
    cards = seeded_rfp.active_ui_cards_json
    assert cards["event_overview"]["company_name"] == "Globex"
    assert cards["room_block"]["total_room_nights"] == 90
    assert "total_room_nights" not in seeded_rfp.amber_conflict_fields_json
    assert DynamicPricingQuote.objects.filter(rfp=seeded_rfp).count() == quotes_before + 1
    event = AdminAuditEvent.objects.get(action="debate.override")
    assert event.payload_json["after"]["company_name"] == "Globex"


@pytest.mark.django_db
def test_override_over_capacity_returns_alternatives(admin_client, seeded_rfp, demo_property):
    from apps.inventory.models import SpaceInventory

    small = SpaceInventory.objects.create(
        property=demo_property, name="Tiny Room", space_type="BOARDROOM", capacities_json={"classroom": 10}
    )
    cards = dict(seeded_rfp.active_ui_cards_json)
    cards["meeting_space"] = {**cards.get("meeting_space", {}), "selected_zone_id": str(small.id), "seating_style": "classroom"}
    seeded_rfp.active_ui_cards_json = cards
    seeded_rfp.save(update_fields=["active_ui_cards_json"])

    res = admin_client.post(
        f"/api/admin-center/rfps/{seeded_rfp.id}/override/", {"fields": {"headcount": 200}}, format="json"
    )
    assert res.status_code == 400
    assert "capacity" in res.json()["detail"]
    assert res.json()["alternatives"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "fields",
    [{}, {"unknown": 1}, {"check_in_date": "soon"}, {"headcount": -5}, {"seating_style": "stadium"},
     {"check_in_date": "2026-12-05", "check_out_date": "2026-12-01"}],
)
def test_override_rejects_bad_input(admin_client, seeded_rfp, fields):
    res = admin_client.post(
        f"/api/admin-center/rfps/{seeded_rfp.id}/override/", {"fields": fields}, format="json"
    )
    assert res.status_code == 400
    assert res.json()["detail"]


@pytest.mark.django_db
def test_old_override_path_is_an_alias(admin_client, seeded_rfp):
    res = admin_client.post(
        f"/api/admin-center/debate/{seeded_rfp.id}/override/", {"fields": {"event_type": "Gala"}}, format="json"
    )
    assert res.status_code == 200
    seeded_rfp.refresh_from_db()
    assert seeded_rfp.status == RFPStatus.NEGOTIATING
