import pytest

from apps.designer_studio.models import ALL_BINDING_PLACEHOLDERS, MANDATORY_PLACEHOLDERS


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
    for token in ALL_BINDING_PLACEHOLDERS:
        assert token in html
    assert len(data["history"]) == 2


@pytest.mark.django_db
def test_designer_validate_endpoint(api_client, designer_user):
    api_client.force_authenticate(user=designer_user)
    html = "".join(f"<div>{p}</div>" for p in ALL_BINDING_PLACEHOLDERS)
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
def test_save_template_auto_repair_or_reject(api_client, designer_user):
    api_client.force_authenticate(user=designer_user)
    bad_html = "<div>{{client_name}}</div>"
    response = api_client.post(
        "/api/designer/templates/",
        {"name": "Broken", "html_markup": bad_html, "css_stylesheet": "body{margin:0;}"},
        format="json",
    )
    if response.status_code == 201:
        body = response.json()
        assert any(p in body["html_markup"] for p in MANDATORY_PLACEHOLDERS if p != "{{client_name}}")
    else:
        assert response.status_code == 400


@pytest.mark.django_db
def test_save_template_without_map_placeholder(api_client, designer_user):
    api_client.force_authenticate(user=designer_user)
    html = "".join(f"<div>{p}</div>" for p in MANDATORY_PLACEHOLDERS)
    css = "body{margin:0;} .proposal-cta{display:block;}"
    response = api_client.post(
        "/api/designer/templates/",
        {"name": "No map", "html_markup": html, "css_stylesheet": css, "js_script": ""},
        format="json",
    )
    assert response.status_code == 201, response.content


@pytest.mark.django_db
def test_patch_template_clears_chat_history(api_client, designer_user):
    api_client.force_authenticate(user=designer_user)
    html = "".join(f"<div>{p}</div>" for p in ALL_BINDING_PLACEHOLDERS)
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
