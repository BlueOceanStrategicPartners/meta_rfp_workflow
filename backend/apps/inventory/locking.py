from django.db import transaction

from apps.core.exceptions import InventoryLockConflictError

from .models import SpaceInventory, VenueMapZone


def lock_zone_for_booking(zone_id, idempotency_key: str) -> VenueMapZone:
    """Serialize concurrent bookings with select_for_update(nowait=True)."""
    try:
        with transaction.atomic():
            zone = VenueMapZone.objects.select_for_update(nowait=True).get(pk=zone_id)
            if zone.is_locked:
                if zone.space_inventory and zone.space_inventory.booking_idempotency_key == idempotency_key:
                    return zone
                raise InventoryLockConflictError("Zone already locked for another booking.")
            zone.is_locked = True
            zone.save(update_fields=["is_locked"])
            if zone.space_inventory_id:
                space = SpaceInventory.objects.select_for_update(nowait=True).get(
                    pk=zone.space_inventory_id
                )
                if space.is_booked and space.booking_idempotency_key != idempotency_key:
                    raise InventoryLockConflictError("Space inventory already booked.")
                space.is_booked = True
                space.booking_idempotency_key = idempotency_key
                space.save(update_fields=["is_booked", "booking_idempotency_key"])
            return zone
    except VenueMapZone.DoesNotExist as exc:
        raise InventoryLockConflictError("Zone not found.") from exc
    except Exception as exc:
        if isinstance(exc, InventoryLockConflictError):
            raise
        raise InventoryLockConflictError("Could not acquire inventory lock.") from exc
