from django.core.management.base import BaseCommand

from apps.designer_studio.models import ProposalTemplate, REQUIRED_PLACEHOLDERS
from apps.accounts_rbac.models import CustomUser, UserRole
from apps.inventory.models import HistoricalOccupancy, SpaceInventory, VenueProperty


class Command(BaseCommand):
    help = "Seed demo property, spaces, occupancy, users, and default proposal template"

    def handle(self, *args, **options):
        prop, _ = VenueProperty.objects.get_or_create(name="Meta Grand Hotel")
        SpaceInventory.objects.get_or_create(
            property=prop,
            name="Grand Sapphire Ballroom",
            defaults={
                "space_type": "BALLROOM",
                "capacities_json": {"classroom": 250, "banquet": 400, "theater": 500},
                "rack_rate": 8500,
                "base_floor_cost": 6000,
            },
        )
        SpaceInventory.objects.get_or_create(
            property=prop,
            name="Lotus Pavilion",
            defaults={
                "space_type": "BALLROOM",
                "capacities_json": {"classroom": 220, "banquet": 350},
                "rack_rate": 7200,
                "base_floor_cost": 5200,
            },
        )
        for i in range(10):
            HistoricalOccupancy.objects.get_or_create(
                property=prop,
                target_date=f"2026-06-{i+1:02d}",
                defaults={
                    "room_occupancy_pct": 0.7 + i * 0.02,
                    "adr": 200 + i * 5,
                    "revpar": 140 + i * 4,
                },
            )
        designer, _ = CustomUser.objects.get_or_create(
            email="designer@demo.local",
            defaults={"username": "designer", "role": UserRole.DESIGNER},
        )
        if not designer.password:
            designer.set_password("demo12345")
            designer.save()
        html = "".join(
            f"<div>{p}</div>" for p in REQUIRED_PLACEHOLDERS
        )
        ProposalTemplate.objects.update_or_create(
            name="Corporate Summit Theme",
            designer=designer,
            defaults={"html_markup": html, "css_stylesheet": "body{margin:0;}", "is_default": True},
        )
        self.stdout.write(self.style.SUCCESS("Seed complete"))
