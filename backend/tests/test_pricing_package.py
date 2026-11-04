"""What gets priced: rooms + one meeting space, and every case where we must refuse to price."""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.dynamic_pricing.models import PricingPolicy
from apps.dynamic_pricing.package import QuoteNotPossibleError, build_package
from apps.inventory.models import HistoricalOccupancy, SpaceInventory

CI = date.today() + timedelta(days=40)


def cards(**over):
    base = {
        "event_overview": {"check_in_date": CI.isoformat(), "check_out_date": (CI + timedelta(days=3)).isoformat()},
        "room_block": {"total_room_nights": 180},
        "meeting_space": {"headcount": 200, "seating_style": "classroom"},
    }
    for section, values in over.items():
        base[section] = {**base.get(section, {}), **values}
    return base


@pytest.fixture
def policy(db):
    return PricingPolicy.get_solo()


@pytest.mark.django_db
def test_worked_example_rooms_plus_smallest_fitting_space(demo_property, policy):
    SpaceInventory.objects.create(property=demo_property, name="Lotus", space_type="BALLROOM",
                                  capacities_json={"classroom": 220}, rack_rate=7200, base_floor_cost=5200)
    HistoricalOccupancy.objects.create(property=demo_property, target_date="2025-01-01", source="imported",
                                       room_occupancy_pct=0.8, adr=220, revpar=176)
    pkg = build_package(cards(), demo_property, policy)
    assert pkg.space.name == "Lotus"  # 220 seats beats the 250-seat ballroom: smallest that fits
    assert pkg.room_rate == Decimal("220.00") and pkg.room_nights == 180 and pkg.nights == 3
    assert pkg.rooms_part == Decimal("39600.00") and pkg.space_part == Decimal("21600.00")
    assert pkg.base_price == Decimal("61200.00")
    assert pkg.operating_cost == Decimal("37380.00")  # 180 × 121 (55% of 220) + 3 × 5200


@pytest.mark.django_db
def test_nightly_breakdown_wins_over_total(demo_property, policy):
    blocks = [{"date": "x", "single": 20, "double": 30}, {"date": "y", "double": 70}, {"date": "z", "suite": 10}]
    pkg = build_package(cards(room_block={"blocks": blocks, "total_room_nights": 999}), demo_property, policy)
    assert pkg.room_nights == 130 and pkg.peak_rooms_per_night == 70


@pytest.mark.django_db
def test_meeting_only_event_has_no_room_cost(demo_property, policy):
    pkg = build_package(cards(room_block={"total_room_nights": 0}), demo_property, policy)
    assert pkg.room_nights == 0 and pkg.rooms_part == 0 and pkg.base_price == pkg.space_part


@pytest.mark.django_db
def test_no_space_fits_refuses_with_alternatives(demo_property, policy):
    with pytest.raises(QuoteNotPossibleError) as err:
        build_package(cards(meeting_space={"headcount": 900}), demo_property, policy)
    assert err.value.reason == "no_space_fits"
    assert err.value.alternatives[0]["name"] == "Grand Ballroom"


@pytest.mark.django_db
def test_selected_space_too_small_is_refused(demo_property, policy):
    small = SpaceInventory.objects.create(property=demo_property, name="Room 1", space_type="BOARDROOM",
                                          capacities_json={"classroom": 10}, rack_rate=500, base_floor_cost=300)
    with pytest.raises(QuoteNotPossibleError) as err:
        build_package(cards(meeting_space={"selected_zone_id": str(small.id)}), demo_property, policy)
    assert err.value.reason == "space_too_small"


@pytest.mark.django_db
def test_space_without_price_is_refused(demo_property, policy):
    SpaceInventory.objects.filter(property=demo_property).update(rack_rate=0)
    with pytest.raises(QuoteNotPossibleError) as err:
        build_package(cards(), demo_property, policy)
    assert err.value.reason == "missing_price"


@pytest.mark.django_db
def test_check_out_before_check_in_is_refused(demo_property, policy):
    with pytest.raises(QuoteNotPossibleError) as err:
        build_package(cards(event_overview={"check_out_date": (CI - timedelta(days=1)).isoformat()}), demo_property, policy)
    assert err.value.reason == "invalid_dates"


@pytest.mark.django_db
def test_missing_dates_is_an_estimate_not_a_refusal(demo_property, policy):
    pkg = build_package(cards(event_overview={"check_in_date": "TBD", "check_out_date": ""}), demo_property, policy)
    assert pkg.dates_assumed is True and pkg.nights == 1 and pkg.base_price > 0


@pytest.mark.django_db
def test_more_rooms_than_the_hotel_has_is_flagged(demo_property, policy):
    demo_property.total_rooms = 50
    demo_property.save()
    pkg = build_package(cards(), demo_property, policy)  # 60 rooms a night
    assert "hotel has 50" in pkg.warnings[0]


@pytest.mark.django_db
def test_room_rate_ignores_generated_and_future_rows(demo_property, policy):
    HistoricalOccupancy.objects.create(property=demo_property, target_date="2025-02-01", source="generated",
                                       room_occupancy_pct=0.6, adr=999, revpar=599)
    HistoricalOccupancy.objects.create(property=demo_property, target_date=date.today() + timedelta(days=5),
                                       source="imported", room_occupancy_pct=0.6, adr=888, revpar=500)
    pkg = build_package(cards(), demo_property, policy)
    assert pkg.room_rate == Decimal("200")  # nothing real in the past → default


def test_migration_fingerprints_recognise_fake_rows():
    import importlib
    from types import SimpleNamespace as Row

    m = importlib.import_module("apps.inventory.migrations.0005_reclassify_generated_occupancy")
    filler = Row(room_occupancy_pct=0.6, adr=Decimal("215"), revpar=Decimal(int(215 * 0.6)), hall_utilization_pct=0.68,
                 target_date=date(2026, 11, 3))
    seed = Row(room_occupancy_pct=0.74, adr=Decimal("210"), revpar=Decimal("148"), hall_utilization_pct=0.0,
               target_date=date(2026, 6, 3))
    real = Row(room_occupancy_pct=0.75, adr=Decimal("230"), revpar=Decimal("172"), hall_utilization_pct=0.5,
               target_date=date(2026, 7, 1))
    assert m._is_availability_filler(filler) and m._is_seed_demo_row(seed)
    assert not m._is_availability_filler(real) and not m._is_seed_demo_row(real)


@pytest.mark.django_db
def test_no_meeting_spaces_at_all_prices_rooms_with_a_warning(demo_property, policy):
    SpaceInventory.objects.filter(property=demo_property).delete()
    pkg = build_package(cards(), demo_property, policy)
    assert pkg.space is None and pkg.base_price == pkg.rooms_part > 0
    assert "No meeting spaces" in pkg.warnings[0]
