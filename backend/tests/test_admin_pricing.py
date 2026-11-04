"""Admin pricing: policy, model status, retrain, quotes and the "Why this price?" explanation."""
from decimal import Decimal

import pytest

from apps.admin_command_center.models import AdminAuditEvent
from apps.dynamic_pricing.models import PricingPolicy
from apps.dynamic_pricing.services import compute_dynamic_quote


def _assert_ladder(quote):
    assert quote.walk_away_floor_price <= quote.optimal_target_price <= quote.initial_anchor_price


@pytest.mark.django_db
def test_fallback_ladder_keeps_target_above_floor(seeded_rfp):
    quote = compute_dynamic_quote(seeded_rfp)
    assert quote.engine == "fallback" and quote.used_fallback_engine is True
    _assert_ladder(quote)


@pytest.mark.django_db
def test_policy_get_and_put(admin_client, admin_user):
    body = admin_client.get("/api/admin-center/pricing/policy/").json()
    assert body["walk_away_floor_margin_pct"] == pytest.approx(0.12)
    body["walk_away_floor_margin_pct"] = 0.15
    body["seasonality_json"] = {"12": 1.3}
    res = admin_client.put("/api/admin-center/pricing/policy/", body, format="json")
    assert res.status_code == 200, res.json()
    assert res.json()["updated_by"] == admin_user.email
    assert PricingPolicy.get_solo().walk_away_floor_margin_pct == pytest.approx(0.15)
    event = AdminAuditEvent.objects.get(action="pricing.policy.update")
    assert "walk_away_floor_margin_pct" in event.payload_json["changes"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "patch",
    [
        {"target_markup_pct": 0.10},  # target would sit below the 12% floor
        {"walk_away_floor_margin_pct": 2},
        {"max_autonomous_discount_pct": 0.9},
        {"seasonality_json": {"13": 1.1}},
        {"seasonality_json": {"6": 9}},
        {"event_multiplier": 0},
    ],
)
def test_policy_rejects_invalid_rules(admin_client, patch):
    body = admin_client.get("/api/admin-center/pricing/policy/").json()
    body.update(patch)
    res = admin_client.put("/api/admin-center/pricing/policy/", body, format="json")
    assert res.status_code == 400
    assert res.json()["detail"]


@pytest.mark.django_db
def test_policy_change_moves_the_next_quote(seeded_rfp):
    before = compute_dynamic_quote(seeded_rfp)
    policy = PricingPolicy.get_solo()
    policy.walk_away_floor_margin_pct = 0.30
    policy.target_markup_pct = 0.40
    policy.save()
    after = compute_dynamic_quote(seeded_rfp)
    assert after.walk_away_floor_price > before.walk_away_floor_price
    _assert_ladder(after)


@pytest.mark.django_db
def test_guardrails_endpoint_reads_policy(admin_client):
    policy = PricingPolicy.get_solo()
    policy.max_autonomous_discount_pct = 0.2
    policy.save()
    assert admin_client.get("/api/pricing/admin/guardrails/").json()["max_autonomous_discount_pct"] == 0.2


@pytest.mark.django_db
def test_retrain_skips_without_enough_real_history(admin_client, demo_property):
    status = admin_client.get("/api/admin-center/pricing/model/").json()
    assert status["artifact_exists"] is False and status["is_active"] is False
    res = admin_client.post("/api/admin-center/pricing/retrain/").json()
    assert res["status"] == "skipped_insufficient_data"
    assert res["rows_required"] == 60


@pytest.mark.django_db
def test_retrain_reports_quality_and_quotes_use_the_model(admin_client, demo_history, seeded_rfp):
    res = admin_client.post("/api/admin-center/pricing/retrain/").json()
    assert res["status"] == "ok", res
    assert res["version"] == 1 and res["metrics"]["improvement_pct"] > 0

    status = admin_client.get("/api/admin-center/pricing/model/").json()
    assert status["is_active"] is True and status["rows_used"] >= 1000
    assert status["data"]["demo"] >= 1000 and status["data"]["trainable"] >= 1000
    assert status["feature_importance"][0]["label"]
    assert AdminAuditEvent.objects.filter(action="pricing.retrain").count() == 1

    quote = compute_dynamic_quote(seeded_rfp)
    assert quote.engine == "model" and quote.model_version == 1
    rows = admin_client.get(f"/api/admin-center/pricing/quotes/?rfp={seeded_rfp.id}").json()
    assert rows[0]["engine"] == "model" and rows[0]["fallback_reason_label"] == ""
    assert Decimal(rows[0]["floor"]) <= Decimal(rows[0]["target"])


@pytest.mark.django_db
def test_quote_explanation_endpoint_adds_up(admin_client, seeded_rfp):
    quote = compute_dynamic_quote(seeded_rfp)
    body = admin_client.get(f"/api/admin-center/pricing/quotes/{quote.id}/explanation/").json()
    assert body["engine"] == "fallback" and body["fallback_reason_label"] == "Not enough history to train"
    target_step = next(s for s in body["steps"] if s["ends"] == "target")
    anchor_step = next(s for s in body["steps"] if s["ends"] == "anchor")
    assert target_step["running_total"] == body["target"]
    assert anchor_step["running_total"] == body["anchor"]
    assert body["floor_steps"][-1]["running_total"] == body["floor"]
    assert body["inputs"]["base_price"] == body["steps"][0]["running_total"]
    assert admin_client.get("/api/admin-center/pricing/quotes/00000000-0000-0000-0000-000000000000/explanation/").status_code == 404


@pytest.mark.django_db
def test_occupancy_rows_show_their_source(admin_client, demo_property):
    from apps.inventory.models import HistoricalOccupancy

    HistoricalOccupancy.objects.create(property=demo_property, target_date="2026-01-05", source="generated", room_occupancy_pct=0.6, adr=215, revpar=129)
    HistoricalOccupancy.objects.create(property=demo_property, target_date="2026-01-06", source="imported", room_occupancy_pct=0.6, adr=200, revpar=120)
    rows = admin_client.get(f"/api/admin-center/occupancy/?property={demo_property.id}").json()
    assert {r["source"] for r in rows} == {"generated", "imported"}
    summary = admin_client.get("/api/admin-center/occupancy/summary/").json()
    assert summary["by_source"]["generated"] == 1 and summary["by_source"]["imported"] == 1
