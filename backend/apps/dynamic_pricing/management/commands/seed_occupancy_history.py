"""Seed realistic demo occupancy history for training the pricing model.

Rows are labelled source="demo" (deliberate demo data: it trains the model), unlike app-generated
filler ("generated", never trains). Real imported rows are never overwritten.

  python manage.py seed_occupancy_history                 # 3 years into the database
  python manage.py seed_occupancy_history --years 5 --replace
  python manage.py seed_occupancy_history --csv artifacts/occupancy_3y.csv   # file for the Occupancy page
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.inventory.models import HistoricalOccupancy, OccupancySource, VenueProperty

MONTH_OCCUPANCY = {1: 0.55, 2: 0.58, 3: 0.63, 4: 0.66, 5: 0.70, 6: 0.82, 7: 0.85, 8: 0.76, 9: 0.70, 10: 0.72, 11: 0.80, 12: 0.84}
WEEKDAY_EFFECT = {0: -0.05, 1: -0.02, 2: 0.0, 3: 0.04, 4: 0.08, 5: 0.10, 6: -0.06}  # Mon..Sun
EVENTS_PER_YEAR = 12


def _event_days(start: date, end: date, rng: random.Random) -> dict[date, float]:
    events: dict[date, float] = {}
    span_days = (end - start).days
    for _ in range(int(EVENTS_PER_YEAR * span_days / 365)):
        first = start + timedelta(days=rng.randrange(span_days))
        boost = round(rng.uniform(1.2, 1.5), 2)
        for k in range(rng.randint(2, 4)):
            events[first + timedelta(days=k)] = boost
    return events


def generate_rows(years: int, *, seed: int = 7, end: date | None = None) -> list[dict]:
    rng = random.Random(seed)
    end = end or date.today() - timedelta(days=1)
    start = end - timedelta(days=365 * years - 1)
    events = _event_days(start, end, rng)
    rows = []
    day = start
    while day <= end:
        event = events.get(day, 1.0)
        occ = MONTH_OCCUPANCY[day.month] + WEEKDAY_EFFECT[day.weekday()] + (0.12 if event > 1 else 0) + rng.gauss(0, 0.03)
        occ = round(min(0.98, max(0.30, occ)), 3)
        adr = round(180 + 120 * (occ - 0.5) + (25 if day.month in (6, 7, 11, 12) else 0) + 40 * (event - 1) + rng.gauss(0, 6), 2)
        rows.append(
            {
                "target_date": day,
                "room_occupancy_pct": occ,
                "hall_utilization_pct": round(min(0.95, max(0.2, occ - 0.1 + rng.gauss(0, 0.05))), 3),
                "adr": adr,
                "revpar": round(adr * occ, 2),
                "is_peak_season": occ >= 0.85 or event > 1,
                "local_event_multiplier": event,
            }
        )
        day += timedelta(days=1)
    return rows


class Command(BaseCommand):
    help = "Seed realistic demo occupancy history (labelled 'demo') for training the pricing model."

    def add_arguments(self, parser):
        parser.add_argument("--years", type=int, default=3, help="How many years back from yesterday (default 3).")
        parser.add_argument("--property", default="", help="Property id or name (default: the first property).")
        parser.add_argument("--csv", default="", help="Write a CSV for the Occupancy page instead of the database.")
        parser.add_argument("--replace", action="store_true", help="Delete existing demo rows for the property first.")
        parser.add_argument("--seed", type=int, default=7, help="Random seed (same seed = same data).")

    def handle(self, *args, **opts):
        if opts["years"] < 1 or opts["years"] > 20:
            raise CommandError("--years must be between 1 and 20.")
        rows = generate_rows(opts["years"], seed=opts["seed"])

        if opts["csv"]:
            path = Path(opts["csv"])
            path.parent.mkdir(parents=True, exist_ok=True)
            fields = ["target_date", "room_occupancy_pct", "hall_utilization_pct", "adr", "revpar", "is_peak_season", "local_event_multiplier"]
            with path.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=fields)
                writer.writeheader()
                for row in rows:
                    writer.writerow({**row, "target_date": row["target_date"].isoformat(), "is_peak_season": str(row["is_peak_season"]).lower()})
            self.stdout.write(self.style.SUCCESS(f"Wrote {len(rows)} days to {path}. Upload it on the admin Occupancy page."))
            return

        ref = opts["property"]
        prop = (
            VenueProperty.objects.filter(pk=ref).first() if ref and len(ref) == 36 else VenueProperty.objects.filter(name=ref).first()
        ) if ref else VenueProperty.objects.order_by("created_at").first()
        if prop is None:
            raise CommandError("No property found. Run seed_demo or add one in the admin Inventory page.")
        if opts["replace"]:
            deleted, _ = HistoricalOccupancy.objects.filter(property=prop, source=OccupancySource.DEMO).delete()
            self.stdout.write(f"Removed {deleted} old demo rows.")
        existing = set(HistoricalOccupancy.objects.filter(property=prop).values_list("target_date", flat=True))
        new = [
            HistoricalOccupancy(property=prop, source=OccupancySource.DEMO, **row)
            for row in rows
            if row["target_date"] not in existing  # never overwrite real or generated rows
        ]
        HistoricalOccupancy.objects.bulk_create(new, batch_size=500)
        self.stdout.write(
            self.style.SUCCESS(
                f"Added {len(new)} demo days for {prop.name} ({rows[0]['target_date']} to {rows[-1]['target_date']}); "
                f"skipped {len(rows) - len(new)} days that already had data. Now press Retrain model in the admin."
            )
        )
