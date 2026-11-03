from datetime import date

from django.utils import timezone

from apps.inventory.models import HistoricalOccupancy, VenueProperty
from apps.inventory.room_availability import (
    build_availability_table,
    detect_availability_inquiry,
    ensure_occupancy_rows,
    next_calendar_week_range,
)


def test_detects_next_week_visit_question():
    assert detect_availability_inquiry(
        "We hope to come to your property next week, what are the suitable dates?"
    )


def test_detects_availability_phrase():
    assert detect_availability_inquiry("Can you check room availability for next week?")


def test_build_table_has_seven_rows(db):
    prop = VenueProperty.objects.create(name="Test Hotel")
    start, _ = next_calendar_week_range(ref=date(2026, 11, 3))
    ensure_occupancy_rows(prop, start, 7)
    table = build_availability_table(property=prop, start=start, days=7)
    assert table["type"] == "availability_table"
    assert len(table["rows"]) == 7
    assert "date_iso" in table["rows"][0]


def test_ensure_occupancy_does_not_clobber(db):
    prop = VenueProperty.objects.create(name="Test Hotel 2")
    start = timezone.localdate()
    HistoricalOccupancy.objects.create(
        property=prop,
        target_date=start,
        room_occupancy_pct=0.99,
    )
    ensure_occupancy_rows(prop, start, 3)
    row = HistoricalOccupancy.objects.get(property=prop, target_date=start)
    assert row.room_occupancy_pct == 0.99
