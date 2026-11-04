import uuid

from django.db import models


class SpaceType(models.TextChoices):
    ROOM_BLOCK = "ROOM_BLOCK", "Room block"
    BALLROOM = "BALLROOM", "Ballroom"
    BOARDROOM = "BOARDROOM", "Boardroom"
    OUTDOOR = "OUTDOOR", "Outdoor"


class VenueProperty(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    timezone = models.CharField(max_length=64, default="UTC")
    # Guest rooms in the hotel (matches room_availability.DEFAULT_ROOM_COUNT for the demo property).
    total_rooms = models.PositiveIntegerField(default=320)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name


class SpaceInventory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(
        VenueProperty, on_delete=models.CASCADE, related_name="spaces"
    )
    name = models.CharField(max_length=255)
    space_type = models.CharField(max_length=32, choices=SpaceType.choices)
    capacities_json = models.JSONField(default=dict)
    base_floor_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    rack_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    av_capabilities_json = models.JSONField(default=dict)
    is_booked = models.BooleanField(default=False)
    booking_idempotency_key = models.CharField(max_length=64, blank=True, null=True, unique=True)

    def __str__(self) -> str:
        return f"{self.property.name} — {self.name}"


class OccupancySource(models.TextChoices):
    IMPORTED = "imported", "Imported"
    DEMO = "demo", "Demo history"
    MANUAL = "manual", "Manual"
    GENERATED = "generated", "App-generated"


# Rows the pricing model may learn from. App-generated filler never trains it.
TRAINABLE_OCCUPANCY_SOURCES = (
    OccupancySource.IMPORTED,
    OccupancySource.DEMO,
    OccupancySource.MANUAL,
)


class HistoricalOccupancy(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(
        VenueProperty, on_delete=models.CASCADE, related_name="occupancy_history"
    )
    target_date = models.DateField(db_index=True)
    room_occupancy_pct = models.FloatField(default=0)
    hall_utilization_pct = models.FloatField(default=0)
    adr = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    revpar = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_peak_season = models.BooleanField(default=False)
    local_event_multiplier = models.FloatField(default=1.0)
    source = models.CharField(
        max_length=16, choices=OccupancySource.choices, default=OccupancySource.IMPORTED, db_index=True
    )

    class Meta:
        unique_together = ("property", "target_date")
