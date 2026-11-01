import pytest

from apps.inventory.models import VenueProperty


@pytest.mark.django_db
def test_map_chat_returns_interactive_markup(api_client, designer_user):
    prop = VenueProperty.objects.create(name="Test Hotel")
    api_client.force_authenticate(user=designer_user)
    response = api_client.post(
        "/api/maps/chat/",
        {
            "message": "Create interactive ballroom map from floorplan",
            "history": [],
            "html_markup": "",
            "css_stylesheet": "",
            "js_script": "",
        },
        format="json",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["assistant_message"]
    assert "data-location-id" in data["html_markup"]
    assert data["locations"]
    assert "postMessage" in data["js_script"]


@pytest.mark.django_db
def test_map_validate_endpoint(api_client, designer_user):
    api_client.force_authenticate(user=designer_user)
    fixture = __import__(
        "apps.rfp_debate.meta_client", fromlist=["MetaModelClient"]
    ).MetaModelClient._map_fixture_interactive("")
    response = api_client.post(
        "/api/maps/validate/",
        {
            "html_markup": fixture["html_markup"],
            "css_stylesheet": fixture["css_stylesheet"],
            "js_script": fixture["js_script"],
            "locations": fixture["locations"],
        },
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["valid"] is True


@pytest.mark.django_db
def test_save_map_without_property_id(api_client, designer_user):
    fixture = __import__(
        "apps.rfp_debate.meta_client", fromlist=["MetaModelClient"]
    ).MetaModelClient._map_fixture_interactive("")
    api_client.force_authenticate(user=designer_user)
    response = api_client.post(
        "/api/maps/",
        {
            "title": "Our Map",
            "html_markup": fixture["html_markup"],
            "css_stylesheet": fixture["css_stylesheet"],
            "js_script": fixture["js_script"],
            "locations": fixture["locations"],
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    assert response.json()["title"] == "Our Map"


@pytest.mark.django_db
def test_published_map_endpoint(api_client, designer_user):
    from apps.inventory.models import InteractiveVenueMap, VenueMapZone, VenueProperty

    prop = VenueProperty.objects.create(name="Pub Hotel")
    fixture = __import__(
        "apps.rfp_debate.meta_client", fromlist=["MetaModelClient"]
    ).MetaModelClient._map_fixture_interactive("")
    venue_map = InteractiveVenueMap.objects.create(
        property=prop,
        title="Default",
        html_markup=fixture["html_markup"],
        css_stylesheet=fixture["css_stylesheet"],
        js_script=fixture["js_script"],
        is_default=True,
        created_by=designer_user,
    )
    for loc in fixture["locations"]:
        VenueMapZone.objects.create(
            venue_map=venue_map,
            svg_element_id=loc["id"],
            zone_label=loc["label"],
            display_metadata_json={
                "description": loc["description"],
                "image_urls": loc.get("image_urls") or [],
            },
        )
    response = api_client.get("/api/maps/published/")
    assert response.status_code == 200
    body = response.json()
    assert body["compiled_html"]
    assert len(body["locations"]) >= 2
