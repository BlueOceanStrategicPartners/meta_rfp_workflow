import pytest

from apps.designer_studio.models import REQUIRED_PLACEHOLDERS


@pytest.mark.django_db
def test_designer_chat_returns_html_with_placeholders(api_client, designer_user):
    api_client.force_authenticate(user=designer_user)
    response = api_client.post(
        "/api/designer/chat/",
        {"message": "Create a luxury dark proposal template", "history": []},
        format="json",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["assistant_message"]
    html = data["html_markup"]
    for token in REQUIRED_PLACEHOLDERS:
        assert token in html
    assert len(data["history"]) == 2


@pytest.mark.django_db
def test_designer_validate_endpoint(api_client, designer_user):
    api_client.force_authenticate(user=designer_user)
    html = "".join(f"<div>{p}</div>" for p in REQUIRED_PLACEHOLDERS)
    css = "body{margin:0;} .proposal-cta{display:block;}"
    response = api_client.post(
        "/api/designer/validate/",
        {"html_markup": html, "css_stylesheet": css, "js_script": ""},
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["valid"] is True


@pytest.mark.django_db
def test_designer_preview_injects_sample_data(api_client, designer_user):
    api_client.force_authenticate(user=designer_user)
    html = "<h1>{{client_name}}</h1>{{cta_accept_button}}"
    response = api_client.post(
        "/api/designer/preview/",
        {"html_markup": html, "css_stylesheet": ""},
        format="json",
    )
    assert response.status_code == 200
    compiled = response.json()["compiled_html"]
    assert "Acme Corporation" in compiled
    assert "Accept Proposal" in compiled


@pytest.mark.django_db
def test_designer_preview_injects_default_venue_map(api_client, designer_user):
    from apps.inventory.models import InteractiveVenueMap, VenueMapZone, VenueProperty
    from apps.rfp_debate.meta_client import MetaModelClient

    api_client.force_authenticate(user=designer_user)
    prop, _ = VenueProperty.objects.get_or_create(name="Meta Grand Hotel")
    fixture = MetaModelClient._map_fixture_interactive("")
    venue_map = InteractiveVenueMap.objects.create(
        title="Test Default Map",
        property=prop,
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
            display_metadata_json={"description": loc["description"]},
        )
    html = "<section>{{selected_map_svg}}</section>{{cta_accept_button}}"
    response = api_client.post(
        "/api/designer/preview/",
        {"html_markup": html, "css_stylesheet": "", "js_script": ""},
        format="json",
    )
    assert response.status_code == 200
    compiled = response.json()["compiled_html"]
    assert "proposal-venue-map-frame" in compiled
    assert "grand-ballroom" in compiled.lower() or "venue-map" in compiled.lower()


@pytest.mark.django_db
def test_designer_default_venue_map_api(api_client, designer_user):
    api_client.force_authenticate(user=designer_user)
    response = api_client.get("/api/designer/default-venue-map/")
    assert response.status_code == 200
    data = response.json()
    assert "available" in data


@pytest.mark.django_db
def test_designer_inject_default_map_slot(api_client, designer_user):
    api_client.force_authenticate(user=designer_user)
    response = api_client.post(
        "/api/designer/inject-default-venue-map/",
        {"html_markup": "<main>{{client_name}}</main>", "css_stylesheet": "body{margin:0;}"},
        format="json",
    )
    assert response.status_code == 200
    data = response.json()
    assert "{{selected_map_svg}}" in data["html_markup"]
    assert "venue-map-slot" in data["html_markup"]


@pytest.mark.django_db
def test_save_template_runs_validation(api_client, designer_user):
    api_client.force_authenticate(user=designer_user)
    bad_html = "<div>{{client_name}}</div>"
    response = api_client.post(
        "/api/designer/templates/",
        {"name": "Broken", "html_markup": bad_html, "css_stylesheet": ""},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_patch_template_clears_chat_history(api_client, designer_user):
    api_client.force_authenticate(user=designer_user)
    html = "".join(f"<div>{p}</div>" for p in REQUIRED_PLACEHOLDERS)
    create = api_client.post(
        "/api/designer/templates/",
        {
            "name": "Chatty",
            "html_markup": html,
            "css_stylesheet": "body{margin:0;}",
            "chat_history_json": [{"role": "user", "content": "hi", "ts": "2026-01-01T00:00:00Z"}],
        },
        format="json",
    )
    assert create.status_code == 201
    template_id = create.json()["id"]
    cleared = api_client.patch(
        f"/api/designer/templates/{template_id}/",
        {"chat_history_json": []},
        format="json",
    )
    assert cleared.status_code == 200
    detail = api_client.get(f"/api/designer/templates/{template_id}/")
    assert detail.json()["chat_history_json"] == []
