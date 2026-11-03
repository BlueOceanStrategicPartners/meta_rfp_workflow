"""Pricing policy + regression tests for the two ladder bugs (floor above target; retrain ~150x)."""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.admin_command_center.models import AdminAuditEvent
from apps.dynamic_pricing import services as pricing_services
from apps.dynamic_pricing.models import PricingPolicy
from apps.dynamic_pricing.services import compute_dynamic_quote, train_and_save_model
from apps.inventory.models import HistoricalOccupancy


def _assert_ladder(quote):
    assert quote.walk_away_floor_price <= quote.optimal_target_price <= quote.initial_anchor_price


@pytest.fixture
def isolated_model(tmp_path, monkeypatch):
    """Keep test training away from the real artifacts folder."""
    monkeypatch.setattr(pricing_services, "MODEL_PATH", tmp_path / "xgb.json")
    monkeypatch.setattr(pricing_services, "MODEL_META_PATH", tmp_path / "xgb.meta.json")
    return tmp_path


@pytest.mark.django_db
def test_fallback_ladder_keeps_target_above_floor(seeded_rfp, isolated_model):
    quote = compute_dynamic_quote(seeded_rfp)
    assert quote.used_fallback_engine is True
    _assert_ladder(quote)


@pytest.mark.django_db
def test_retrained_model_keeps_prices_in_a_sane_range(seeded_rfp, demo_property, isolated_model):
    fallback = compute_dynamic_quote(seeded_rfp)
    start = date(2026, 6, 1)
    for i in range(20):
        HistoricalOccupancy.objects.create(
            property=demo_property,
            target_date=start + timedelta(days=i),
            room_occupancy_pct=0.7,
            adr=200 + i,
            revpar=140 + i,
        )
    assert train_and_save_model(demo_property.id).endswith("xgb.json")
    model_quote = compute_dynamic_quote(seeded_rfp)
    assert model_quote.used_fallback_engine is False
    _assert_ladder(model_quote)
    # Before the fix the label was RevPAR in currency (~150) used as a multiplier: ~150x prices.
    assert 0.8 <= model_quote.xgboost_demand_score <= 1.5
    assert model_quote.optimal_target_price < fallback.optimal_target_price * 5


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
def test_policy_change_moves_the_next_quote(seeded_rfp, isolated_model):
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
def test_model_status_retrain_and_quotes(admin_client, seeded_rfp, demo_property, isolated_model):
    status = admin_client.get("/api/admin-center/pricing/model/").json()
    assert status["artifact_exists"] is False
    skipped = admin_client.post("/api/admin-center/pricing/retrain/").json()
    assert skipped["status"] == "skipped_insufficient_data"

    for i in range(6):
        HistoricalOccupancy.objects.create(
            property=demo_property, target_date=date(2026, 6, 1) + timedelta(days=i),
            room_occupancy_pct=0.7, adr=200, revpar=140 + i,
        )
    trained = admin_client.post("/api/admin-center/pricing/retrain/").json()
    assert trained["status"] == "ok"
    assert trained["trained_at"]
    assert AdminAuditEvent.objects.filter(action="pricing.retrain").count() == 2

    quotes = admin_client.get(f"/api/admin-center/pricing/quotes/?rfp={seeded_rfp.id}").json()
    assert quotes and quotes[0]["rfp_id"] == str(seeded_rfp.id)
    assert Decimal(quotes[0]["floor"]) <= Decimal(quotes[0]["target"])
