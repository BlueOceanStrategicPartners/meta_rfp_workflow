import uuid

from django.conf import settings
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


class InteractiveVenueMap(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(
        VenueProperty, on_delete=models.CASCADE, related_name="venue_maps"
    )
    title = models.CharField(max_length=255)
    source_image_file = models.FileField(upload_to="venue_maps/", blank=True)
    generated_html_svg = models.TextField(blank=True)
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_maps",
    )
    version = models.PositiveIntegerField(default=1)
    vectorization_confidence = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.title


class VenueMapZone(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    venue_map = models.ForeignKey(
        InteractiveVenueMap, on_delete=models.CASCADE, related_name="zones"
    )
    svg_element_id = models.CharField(max_length=128)
    space_inventory = models.ForeignKey(
        SpaceInventory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="map_zones",
    )
    zone_label = models.CharField(max_length=255)
    polygon_coords_json = models.JSONField(default=list)
    display_metadata_json = models.JSONField(default=dict)
    updated_by_agent = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)

    class Meta:
        unique_together = ("venue_map", "svg_element_id")

    def __str__(self) -> str:
        return self.zone_label


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

    class Meta:
        unique_together = ("property", "target_date")
