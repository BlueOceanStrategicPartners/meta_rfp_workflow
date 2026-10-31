import threading

import pytest
from django.db import connection

from apps.core.exceptions import InventoryLockConflictError
from apps.inventory.locking import lock_zone_for_booking
from apps.inventory.models import InteractiveVenueMap, SpaceInventory, VenueMapZone, VenueProperty


@pytest.mark.django_db
def test_select_for_update_prevents_double_booking():
    prop = VenueProperty.objects.create(name="Hotel")
    space = SpaceInventory.objects.create(
        property=prop, name="Ballroom", space_type="BALLROOM", capacities_json={"classroom": 400}
    )
    venue_map = InteractiveVenueMap.objects.create(property=prop, title="Floor 1")
    zone = VenueMapZone.objects.create(
        venue_map=venue_map,
        svg_element_id="z1",
        space_inventory=space,
        zone_label="Grand Ballroom",
    )
    lock_zone_for_booking(zone.id, "key-a")
    with pytest.raises(InventoryLockConflictError):
        lock_zone_for_booking(zone.id, "key-b")
