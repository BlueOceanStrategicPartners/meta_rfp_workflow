from django.db import transaction

from apps.core.exceptions import InventoryLockConflictError

from .models import SpaceInventory


def lock_space_for_booking(space_id, idempotency_key: str) -> SpaceInventory:
    """Serialize concurrent bookings with select_for_update(nowait=True)."""
    try:
        with transaction.atomic():
            space = SpaceInventory.objects.select_for_update(nowait=True).get(pk=space_id)
            if space.is_booked and space.booking_idempotency_key != idempotency_key:
                raise InventoryLockConflictError("Space inventory already booked.")
            space.is_booked = True
            space.booking_idempotency_key = idempotency_key
            space.save(update_fields=["is_booked", "booking_idempotency_key"])
            return space
    except SpaceInventory.DoesNotExist as exc:
        raise InventoryLockConflictError("Space not found.") from exc
    except Exception as exc:
        if isinstance(exc, InventoryLockConflictError):
            raise
        raise InventoryLockConflictError("Could not acquire inventory lock.") from exc


def lock_zone_for_booking(zone_id, idempotency_key: str) -> SpaceInventory:
    """Backward-compatible alias — zone_id is treated as space_inventory id."""
    return lock_space_for_booking(zone_id, idempotency_key)
