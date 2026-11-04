"""Quotes: same scale on both engines, ladder always holds, explanation adds up, every fallback says why."""
import random
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.dynamic_pricing import model_store, services
from apps.dynamic_pricing.services import compute_dynamic_quote
from apps.dynamic_pricing.training import train_model
from apps.rfp_debate.models import RFPSubmission


def _rfp(user, *, days_ahead=40, nights=3, rooms=180, headcount=200, style="classroom", **overview):
    ci = date.today() + timedelta(days=days_ahead)
    cards = {
        "event_overview": {"company_name": "Test", "check_in_date": ci.isoformat(),
                           "check_out_date": (ci + timedelta(days=nights)).isoformat(), **overview},
        "room_block": {"total_room_nights": rooms},
        "meeting_space": {"headcount": headcount, "seating_style": style},
    }
    return RFPSubmission.objects.create(client=user, source_document_text="t", active_ui_cards_json=cards)


def _assert_adds_up(quote):
    steps = quote.explanation_json["steps"]
    target_step = next(s for s in steps if s["ends"] == "target")
    anchor_step = next(s for s in steps if s["ends"] == "anchor")
    assert Decimal(target_step["running_total"]) == quote.optimal_target_price
    assert Decimal(anchor_step["running_total"]) == quote.initial_anchor_price
    total = Decimal("0")
    for step in steps:  # every running total is the previous one plus this step's amount
        total = Decimal(step["amount"]) if step["kind"] == "base" else total + Decimal(step["amount"])
        assert total == Decimal(step["running_total"])


@pytest.mark.django_db
def test_ladder_and_explanation_hold_for_many_random_requests(client_user, demo_history):
    assert train_model(demo_history)["status"] == "ok"
    rng = random.Random(3)
    engines = set()
    for _ in range(40):
        rooms, headcount = rng.choice([0, 20, 90, 300]), rng.choice([0, 30, 150, 240])
        rfp = _rfp(
            client_user, days_ahead=rng.randint(1, 400), nights=rng.randint(1, 6),
            rooms=rooms, headcount=headcount, style=rng.choice(["classroom", "banquet"]),
        )
        if not rooms and not headcount:
            with pytest.raises(services.QuoteNotPossibleError):  # nothing to price: refused, never 0
                compute_dynamic_quote(rfp)
            continue
        quote = compute_dynamic_quote(rfp)
        assert quote.walk_away_floor_price < quote.optimal_target_price < quote.initial_anchor_price
        _assert_adds_up(quote)
        engines.add(quote.engine)
    assert engines == {"model"}


@pytest.mark.django_db
def test_retraining_does_not_change_the_price_scale(client_user, demo_history):
    rfp = _rfp(client_user)
    fallback = compute_dynamic_quote(rfp)
    train_model(demo_history)
    model = compute_dynamic_quote(rfp)
    assert fallback.engine == "fallback" and model.engine == "model"
    ratio = model.optimal_target_price / fallback.optimal_target_price
    assert Decimal("0.75") <= ratio <= Decimal("1.25"), ratio  # was ~0.15 before (rooms vs ballroom)


@pytest.mark.django_db
def test_demand_limit_appears_in_the_explanation(client_user, demo_history, monkeypatch):
    train_model(demo_history)
    monkeypatch.setattr(services, "DEMAND_INDEX_MAX", 0.85)  # force the clamp
    quote = compute_dynamic_quote(_rfp(client_user))
    assert any(s["key"] == "demand_limit" for s in quote.explanation_json["steps"])
    _assert_adds_up(quote)


@pytest.mark.django_db
def test_floor_guard_step_when_markup_is_too_small(client_user, demo_property):
    from apps.dynamic_pricing.models import PricingPolicy

    policy = PricingPolicy.get_solo()
    policy.walk_away_floor_margin_pct = 0.9  # floor far above the goal price
    policy.target_markup_pct = 0.95
    policy.save()
    quote = compute_dynamic_quote(_rfp(client_user))
    assert quote.optimal_target_price >= quote.walk_away_floor_price * Decimal("1.05") - Decimal("0.01")
    _assert_adds_up(quote)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "setup,expected",
    [
        ("nothing", "insufficient_history"),
        ("history_no_model", "no_model"),
        ("dates_missing", "dates_missing"),
        ("far_ahead", "extreme_request"),
        ("out_of_bounds", "prediction_out_of_bounds"),
        ("corrupt", "model_error"),
        ("inactive", "model_not_better_than_baseline"),
    ],
)
def test_every_fallback_says_why(client_user, demo_property, setup, expected, monkeypatch):
    from apps.dynamic_pricing.management.commands.seed_occupancy_history import generate_rows
    from apps.inventory.models import HistoricalOccupancy

    if setup != "nothing":
        HistoricalOccupancy.objects.bulk_create(
            [HistoricalOccupancy(property=demo_property, source="demo", **r) for r in generate_rows(3)]
        )
    if setup in ("dates_missing", "far_ahead", "out_of_bounds", "corrupt", "inactive"):
        train_model(demo_property)
    kwargs = {}
    if setup == "dates_missing":
        kwargs = {"check_in_date": "TBD"}
    if setup == "far_ahead":
        rfp = _rfp(client_user, days_ahead=900)
    else:
        rfp = _rfp(client_user, **kwargs)
    if setup == "out_of_bounds":
        monkeypatch.setattr(services, "RAW_PREDICTION_BOUNDS", (5.0, 6.0))
    if setup == "corrupt":
        model_store.model_path(demo_property.id).write_text("not a model", encoding="utf-8")
        model_store._booster_cache.clear()
    if setup == "inactive":
        meta = model_store.read_meta(demo_property.id)
        meta.update(is_active=False, inactive_reason="model_not_better_than_baseline")
        model_store.write_meta(demo_property.id, meta)
    quote = compute_dynamic_quote(rfp)
    assert quote.engine == "fallback"
    assert quote.fallback_reason == expected
    _assert_adds_up(quote)
    if setup == "corrupt":
        assert model_store.read_meta(demo_property.id)["last_error"]


@pytest.mark.django_db
def test_training_ignores_generated_and_future_rows(demo_property):
    from apps.inventory.models import HistoricalOccupancy

    today = date.today()
    HistoricalOccupancy.objects.bulk_create(
        [HistoricalOccupancy(property=demo_property, target_date=today - timedelta(days=i + 1), source="generated",
                             room_occupancy_pct=0.6, adr=215, revpar=129) for i in range(200)]
        + [HistoricalOccupancy(property=demo_property, target_date=today + timedelta(days=i), source="imported",
                               room_occupancy_pct=0.6, adr=200, revpar=120) for i in range(100)]
    )
    result = train_model(demo_property)
    assert result["status"] == "skipped_insufficient_data" and result["rows_available"] == 0
