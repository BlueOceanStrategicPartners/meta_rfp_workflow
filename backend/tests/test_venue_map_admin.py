import pytest

from apps.designer_studio.venue_map_admin import try_handle_venue_map_admin_message
from apps.designer_studio.venue_map_context import MAP_SECTION_SNIPPET, remove_map_slot_from_template
from apps.inventory.models import InteractiveVenueMap, VenueProperty


@pytest.mark.django_db
def test_remove_map_slot_from_proposal_html():
    html = f"<main>{MAP_SECTION_SNIPPET}</main>"
    cleaned = remove_map_slot_from_template(html)
    assert "{{selected_map_svg}}" not in cleaned
    assert "venue-map-proposal" not in cleaned


@pytest.mark.django_db
def test_chat_list_maps_command(designer_user):
    prop, _ = VenueProperty.objects.get_or_create(name="Test Prop")
    InteractiveVenueMap.objects.create(
        property=prop,
        title="Summit floorplan",
        created_by=designer_user,
        is_default=True,
        html_markup="<svg></svg>",
    )
    out = try_handle_venue_map_admin_message(
        message="list my saved venue maps",
        user=designer_user,
        html_markup="",
        css_stylesheet="",
    )
    assert out is not None
    assert out["venue_maps_action"] == "list"
    assert len(out["venue_maps"]) == 1
    assert "Summit floorplan" in out["assistant_message"]


@pytest.mark.django_db
def test_chat_set_default_map(designer_user):
    prop, _ = VenueProperty.objects.get_or_create(name="Test Prop 2")
    a = InteractiveVenueMap.objects.create(
        property=prop,
        title="Map A",
        created_by=designer_user,
        is_default=True,
    )
    b = InteractiveVenueMap.objects.create(
        property=prop,
        title="Map B",
        created_by=designer_user,
        is_default=False,
    )
    out = try_handle_venue_map_admin_message(
        message="make Map B the default map",
        user=designer_user,
        html_markup="",
        css_stylesheet="",
    )
    assert out is not None
    assert out["venue_maps_action"] == "set_default"
    b.refresh_from_db()
    a.refresh_from_db()
    assert b.is_default is True
    assert a.is_default is False


@pytest.mark.django_db
def test_proposal_design_prompt_not_handled_as_map_admin(designer_user):
    """Regression: mentioning 'default map' in a design brief must not hijack chat."""
    brief = (
        "Create an interactive proposal with animations and icons. "
        "Add the map slot — we don't have a default map yet but can build it after the proposal."
    )
    out = try_handle_venue_map_admin_message(
        message=brief,
        user=designer_user,
        html_markup="",
        css_stylesheet="",
    )
    assert out is None


@pytest.mark.django_db
def test_remove_venue_map_slot_api(api_client, designer_user):
    html = f"<div>{MAP_SECTION_SNIPPET}</div>"
    api_client.force_authenticate(user=designer_user)
    res = api_client.post(
        "/api/designer/remove-venue-map-slot/",
        {"html_markup": html, "css_stylesheet": ".x{}"},
        format="json",
    )
    assert res.status_code == 200
    assert "{{selected_map_svg}}" not in res.data["html_markup"]
