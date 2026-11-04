"""Mark occupancy rows that the app invented as "generated" so they never train the pricing model.

Two known generators wrote plausible-looking rows that are not real history:
- room_availability.ensure_occupancy_rows: adr 215, revpar = int(215 * occupancy),
  hall = min(0.85, occupancy + 0.08)
- seed_demo: 2026-06-01..10 with adr = 200 + 5i, revpar = 140 + 4i, occupancy = 0.70 + 0.02i
"""
from datetime import date
from decimal import Decimal

from django.db import migrations


def _is_availability_filler(row) -> bool:
    occ = float(row.room_occupancy_pct)
    return (
        Decimal(row.adr) == Decimal("215")
        and Decimal(row.revpar) == Decimal(int(215 * occ))
        and abs(float(row.hall_utilization_pct) - min(0.85, occ + 0.08)) < 1e-6
    )


def _is_seed_demo_row(row) -> bool:
    if not (date(2026, 6, 1) <= row.target_date <= date(2026, 6, 10)):
        return False
    i = row.target_date.day - 1
    return (
        Decimal(row.adr) == Decimal(200 + i * 5)
        and Decimal(row.revpar) == Decimal(140 + i * 4)
        and abs(float(row.room_occupancy_pct) - (0.7 + i * 0.02)) < 1e-6
    )


def reclassify(apps, schema_editor):
    HistoricalOccupancy = apps.get_model("inventory", "HistoricalOccupancy")
    ids = [
        row.pk
        for row in HistoricalOccupancy.objects.all().iterator()
        if _is_availability_filler(row) or _is_seed_demo_row(row)
    ]
    if ids:
        HistoricalOccupancy.objects.filter(pk__in=ids).update(source="generated")


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0004_historicaloccupancy_source_venueproperty_total_rooms"),
    ]

    operations = [migrations.RunPython(reclassify, migrations.RunPython.noop)]
