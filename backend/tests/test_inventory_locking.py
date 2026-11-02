import pytest

from apps.core.exceptions import InventoryLockConflictError
from apps.inventory.locking import lock_space_for_booking
from apps.inventory.models import SpaceInventory, VenueProperty


@pytest.mark.django_db
def test_select_for_update_prevents_double_booking():
    prop = VenueProperty.objects.create(name="Hotel")
    space = SpaceInventory.objects.create(
        property=prop, name="Ballroom", space_type="BALLROOM", capacities_json={"classroom": 400}
    )
    lock_space_for_booking(space.id, "key-a")
    with pytest.raises(InventoryLockConflictError):
        lock_space_for_booking(space.id, "key-b")
