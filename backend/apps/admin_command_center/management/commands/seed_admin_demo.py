"""Demo data for the Admin Command Center (idempotent).

Runs seed_demo, adds extra spaces and 60 days of occupancy, then pushes a few demo RFPs
through the real debate pipeline (fixture mode when no API key) so every admin page has data.
"""
import csv
import math
from datetime import date, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

from apps.accounts_rbac.demo_accounts import ensure_admin_demo_user
from apps.accounts_rbac.models import CustomUser, UserRole
from apps.inventory.models import HistoricalOccupancy, SpaceInventory, VenueProperty
from apps.rfp_debate.models import RFPStatus, RFPSubmission

DEMO_MARKER = "[admin-demo]"

EXTRA_SPACES = [
    {
        "name": "Boardroom B",
        "space_type": "BOARDROOM",
        "capacities_json": {"classroom": 20, "banquet": 16, "u_shape": 14},
        "rack_rate": 1200,
        "base_floor_cost": 800,
    },
    {
        "name": "Garden Terrace",
        "space_type": "OUTDOOR",
        "capacities_json": {"cocktail": 300, "banquet": 180},
        "rack_rate": 5400,
        "base_floor_cost": 3600,
    },
    {
        "name": "Deluxe Room Block",
        "space_type": "ROOM_BLOCK",
        "capacities_json": {},
        "rack_rate": 240,
        "base_floor_cost": 150,
    },
]

# (company shown in the admin, source text, what to do after the pipeline)
DEMO_RFPS = [
    ("Northwind Traders", "Northwind sales kickoff, 3 nights from 2026-12-01, 120 rooms, 200 guests classroom.", None),
    ("Contoso Pharma", "MISMATCH_FIXTURE Contoso summit, room blocks do not add up, please check.", "amber"),
    ("Fabrikam Group", "Fabrikam leadership offsite, 2 nights, 40 guests banquet.", "booked"),
    ("Globex Corporation", "Globex partner conference, 3 nights, 180 guests theater, VIP client.", "escalated"),
]


class Command(BaseCommand):
    help = "Seed demo data for the Admin Command Center (spaces, occupancy, RFPs, admin user)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--write-csv",
            action="store_true",
            help="Also write artifacts/sample_occupancy.csv for the upload demo.",
        )

    def handle(self, *args, **options):
        call_command("seed_demo")
        admin = ensure_admin_demo_user(reset_password=True)
        prop = VenueProperty.objects.get(name="Meta Grand Hotel")

        for spec in EXTRA_SPACES:
            SpaceInventory.objects.get_or_create(
                property=prop, name=spec["name"], defaults={k: v for k, v in spec.items() if k != "name"}
            )

        start = date(2026, 4, 1)
        for day in range(60):
            target = start + timedelta(days=day)
            wave = math.sin(day / 6)
            occupancy = round(0.68 + 0.18 * wave, 3)
            adr = round(205 + 25 * wave, 2)
            HistoricalOccupancy.objects.get_or_create(
                property=prop,
                target_date=target,
                defaults={
                    "room_occupancy_pct": occupancy,
                    "hall_utilization_pct": round(0.5 + 0.2 * wave, 3),
                    "adr": adr,
                    "revpar": round(adr * occupancy, 2),
                    "is_peak_season": target.weekday() >= 4,
                },
            )

        client, _ = CustomUser.objects.get_or_create(
            email="demo-client@local", defaults={"username": "demo_client", "role": UserRole.CLIENT}
        )
        created = 0
        for company, text, outcome in DEMO_RFPS:
            source = f"{DEMO_MARKER} {text}"
            if RFPSubmission.objects.filter(source_document_text=source).exists():
                continue
            rfp = RFPSubmission.objects.create(client=client, source_document_text=source)
            self._run_pipeline(rfp)
            rfp.refresh_from_db()
            cards = dict(rfp.active_ui_cards_json or {})
            overview = dict(cards.get("event_overview") or {})
            overview["company_name"] = company
            # Offline sample extraction uses fixed past dates; demo requests should be bookable.
            check_in = date.today() + timedelta(days=30 + 7 * created)
            overview["check_in_date"] = check_in.isoformat()
            overview["check_out_date"] = (check_in + timedelta(days=3)).isoformat()
            cards["event_overview"] = overview
            rfp.active_ui_cards_json = cards
            rfp.save(update_fields=["active_ui_cards_json", "updated_at"])
            self._apply_outcome(rfp, outcome, admin)
            created += 1

        if options["write_csv"]:
            path = self._write_csv()
            self.stdout.write(f"Sample CSV written to {path}")
        self.stdout.write(self.style.SUCCESS(f"Admin demo ready ({created} new demo RFPs). Sign in as admin@demo.local / admin12345"))

    def _run_pipeline(self, rfp):
        from apps.rfp_debate.tasks import run_debate_pipeline

        run_debate_pipeline(str(rfp.id))

    def _apply_outcome(self, rfp, outcome, admin):
        if outcome == "amber":
            rfp.amber_conflict_fields_json = ["total_room_nights"]
            cards = dict(rfp.active_ui_cards_json or {})
            room = dict(cards.get("room_block") or {})
            room["amber_fields"] = ["total_room_nights"]
            cards["room_block"] = room
            rfp.active_ui_cards_json = cards
            rfp.status = RFPStatus.AWAITING_USER_CARD_EDIT
            rfp.save(update_fields=["amber_conflict_fields_json", "active_ui_cards_json", "status", "updated_at"])
        elif outcome == "booked":
            quote = rfp.pricing_quotes.order_by("-created_at").first()
            if quote:
                quote.agreed_final_price = quote.optimal_target_price
                quote.save(update_fields=["agreed_final_price"])
            rfp.status = RFPStatus.BOOKED
            rfp.save(update_fields=["status", "updated_at"])
        elif outcome == "escalated":
            from apps.admin_command_center.services.negotiation import takeover

            if rfp.status != RFPStatus.ESCALATED:
                rfp.status = RFPStatus.NEGOTIATING
                rfp.save(update_fields=["status", "updated_at"])
                takeover(rfp, admin)

    def _write_csv(self) -> Path:
        path = Path(settings.BASE_DIR) / "artifacts" / "sample_occupancy.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["target_date", "room_occupancy_pct", "hall_utilization_pct", "adr", "revpar", "is_peak_season"])
            start = date(2026, 7, 1)
            for day in range(30):
                target = start + timedelta(days=day)
                occ = round(0.75 + 0.15 * math.sin(day / 5), 3)
                adr = round(230 + 20 * math.sin(day / 5), 2)
                writer.writerow([target.isoformat(), occ, 0.55, adr, round(adr * occ, 2), "true" if target.weekday() >= 4 else "false"])
            writer.writerow(["2026-07-31", "1.4", "0.5", "240", "200", "false"])  # deliberate bad row for the report
        return path
