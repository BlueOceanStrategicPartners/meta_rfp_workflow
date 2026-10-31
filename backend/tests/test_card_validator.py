import pytest

from apps.core.exceptions import CardMutationValidationError
from apps.inventory.models import InteractiveVenueMap, SpaceInventory, VenueMapZone, VenueProperty
from apps.rfp_debate.models import RFPSubmission
from apps.ui_card_validator.services import validate_card_mutation


@pytest.mark.django_db
def test_card_mutation_capacity_conflict(client_user):
    prop = VenueProperty.objects.create(name="Hotel")
    space = SpaceInventory.objects.create(
        property=prop,
        name="Boardroom",
        space_type="BOARDROOM",
        capacities_json={"classroom": 150},
        rack_rate=100,
        base_floor_cost=80,
    )
    big = SpaceInventory.objects.create(
        property=prop,
        name="Ballroom",
        space_type="BALLROOM",
        capacities_json={"classroom": 400},
        rack_rate=500,
        base_floor_cost=300,
    )
    venue_map = InteractiveVenueMap.objects.create(property=prop, title="Map")
    small_zone = VenueMapZone.objects.create(
        venue_map=venue_map,
        svg_element_id="s1",
        space_inventory=space,
        zone_label="Boardroom",
    )
    VenueMapZone.objects.create(
        venue_map=venue_map,
        svg_element_id="b1",
        space_inventory=big,
        zone_label="Ballroom",
    )
    rfp = RFPSubmission.objects.create(
        client=client_user,
        active_ui_cards_json={
            "meeting_space": {
                "headcount": 120,
                "seating_style": "classroom",
                "selected_zone_id": str(small_zone.id),
            },
            "event_overview": {"check_in_date": "2026-06-01", "check_out_date": "2026-06-03"},
            "room_block": {"blocks": []},
        },
    )
    with pytest.raises(CardMutationValidationError):
        validate_card_mutation(
            str(rfp.id),
            {"meeting_space": {"headcount": 400, "seating_style": "classroom", "selected_zone_id": str(small_zone.id)}},
        )
