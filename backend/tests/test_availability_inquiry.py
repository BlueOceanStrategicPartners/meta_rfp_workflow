from apps.inventory.models import VenueProperty
from apps.negotiation_agent.availability_inquiry import try_availability_response


def test_try_availability_returns_table(db):
    VenueProperty.objects.create(name="Meta Grand Hotel")
    spoken, ui = try_availability_response(
        "What suitable dates do you have next week for a site visit?"
    )
    assert ui is not None
    assert ui["type"] == "availability_table"
    assert isinstance(spoken, str) and spoken.strip()
